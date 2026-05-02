import logging
import os
import requests
from datetime import datetime
import pytz
from concurrent.futures import ThreadPoolExecutor, as_completed
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from src.utils.map_utils import geocode_address, fetch_map_data, get_nearest_node, fetch_nearest_petrol_pumps
from src.utils.traffic_model import apply_traffic_model
from src.algorithms.pathfinder import find_optimal_path, haversine

app = FastAPI(title="SmartRoute AI API")

# Global exception handler - ALWAYS returns JSON, never HTML
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logging.error(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": f"Server error: {str(exc)[:200]}"}
    )

def _overpass_point_query(lat, lon, radius_m, limit) -> list:
    """Single fast Overpass point query (nodes only for speed)."""
    query = f"""
    [out:json][timeout:10];
    node["amenity"="fuel"](around:{radius_m},{lat},{lon});
    out {limit};
    """
    mirrors = [
        "https://overpass-api.de/api/interpreter",
        "https://overpass.kumi.systems/api/interpreter",
    ]
    for mirror in mirrors:
        try:
            resp = requests.post(mirror, data=query, timeout=12)
            resp.raise_for_status()
            elements = resp.json().get("elements", [])
            return [{"lat": el["lat"], "lon": el["lon"], "name": el.get("tags", {}).get("name", "Petrol Pump")} for el in elements if el["type"] == "node"]
        except Exception as e:
            logging.warning(f"Point query failed on {mirror}: {e}")
    return []

def fetch_pumps_along_route(lat1, lon1, lat2, lon2, max_results=20) -> list:
    """
    Smart petrol pump fetcher.
    - Short routes (<5 deg bbox): single fast bbox query
    - Long routes (>=5 deg bbox): 3 targeted point queries at start/mid/end
    """
    min_lat = min(lat1, lat2) - 0.1
    max_lat = max(lat1, lat2) + 0.1
    min_lon = min(lon1, lon2) - 0.1
    max_lon = max(lon1, lon2) + 0.1
    bbox_area = (max_lat - min_lat) * (max_lon - min_lon)

    pumps = []

    if bbox_area <= 8:
        # Small/medium route: one fast bbox query
        query = f"""
        [out:json][timeout:20];
        (
          node["amenity"="fuel"]({min_lat},{min_lon},{max_lat},{max_lon});
          way["amenity"="fuel"]({min_lat},{min_lon},{max_lat},{max_lon});
        );
        out center {max_results};
        """
        mirrors = [
            "https://overpass-api.de/api/interpreter",
            "https://overpass.kumi.systems/api/interpreter",
        ]
        for mirror in mirrors:
            try:
                resp = requests.post(mirror, data=query, timeout=22)
                resp.raise_for_status()
                elements = resp.json().get("elements", [])
                for el in elements:
                    if el["type"] == "node":
                        pumps.append({"lat": el["lat"], "lon": el["lon"], "name": el.get("tags", {}).get("name", "Petrol Pump")})
                    elif "center" in el:
                        pumps.append({"lat": el["center"]["lat"], "lon": el["center"]["lon"], "name": el.get("tags", {}).get("name", "Petrol Pump")})
                logging.info(f"Bbox query returned {len(pumps)} pumps")
                break
            except Exception as e:
                logging.warning(f"Bbox query failed: {e}")
    else:
        # Large route (e.g. Mumbai-Delhi): 5 evenly spaced parallel point queries
        # Interpolate 5 points from source to destination
        waypoints = [
            (
                lat1 + (lat2 - lat1) * i / 4,
                lon1 + (lon2 - lon1) * i / 4
            )
            for i in range(5)  # 0%, 25%, 50%, 75%, 100%
        ]
        per_point = max(6, max_results // 5)

        # Run all 5 queries in parallel - total time = ~5 seconds instead of 25
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [
                executor.submit(_overpass_point_query, lat, lon, 8000, per_point)
                for lat, lon in waypoints
            ]
            for future in as_completed(futures, timeout=20):
                try:
                    pumps += future.result()
                except Exception as e:
                    logging.warning(f"Parallel POI query failed: {e}")
        logging.info(f"5-point parallel queries returned {len(pumps)} pumps total")

    # Deduplicate
    seen = set()
    unique = []
    for p in pumps:
        key = (round(p["lat"], 4), round(p["lon"], 4))
        if key not in seen:
            seen.add(key)
            unique.append(p)
    return unique[:max_results]


# Configure CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/debug-pumps")
def debug_pumps():
    """Test endpoint to verify Overpass API works from this server."""
    test_points = [{"lat": 24.8171, "lon": 92.7789}]  # Silchar
    pumps = fetch_pumps_overpass(test_points, radius_m=5000)
    return {"status": "ok", "count": len(pumps), "sample": pumps[:2]}

# Major metro cities that always have higher baseline traffic
MAJOR_METROS = [
    'mumbai', 'delhi', 'bangalore', 'kolkata', 'chennai', 'hyderabad',
    'pune', 'ahmedabad', 'london', 'new york', 'paris', 'tokyo', 'beijing',
    'shanghai', 'los angeles', 'chicago', 'dubai', 'singapore', 'bangkok',
    'jakarta', 'mexico city', 'cairo', 'lagos', 'karachi', 'dhaka',
    'silchar', 'guwahati', 'bhubaneswar', 'bhopal', 'jaipur', 'lucknow'
]

def predict_traffic_level(source: str, destination: str) -> dict:
    """
    Intelligently predict traffic level based on:
    1. Current time of day (rush hours = high traffic)
    2. Day of week (weekday vs weekend)
    3. City type (major metro vs rural)
    """
    # Get current Indian time (IST) as the default timezone
    try:
        ist = pytz.timezone('Asia/Kolkata')
        now = datetime.now(ist)
    except Exception:
        now = datetime.now()

    hour = now.hour
    weekday = now.weekday()  # 0=Monday, 6=Sunday
    is_weekend = weekday >= 5

    # --- Time-based Traffic Score ---
    time_score = 0.2  # Default: light traffic
    traffic_reason = "Light traffic"

    if not is_weekend:
        if 7 <= hour <= 10:  # Morning Rush Hour
            time_score = 0.85
            traffic_reason = "Morning rush hour"
        elif 17 <= hour <= 20:  # Evening Rush Hour
            time_score = 0.9
            traffic_reason = "Evening rush hour"
        elif 11 <= hour <= 16:  # Business Hours
            time_score = 0.5
            traffic_reason = "Moderate business hour traffic"
        elif 21 <= hour <= 23:  # Late Evening
            time_score = 0.3
            traffic_reason = "Light evening traffic"
        else:  # Midnight / Early Morning
            time_score = 0.1
            traffic_reason = "Very light late night traffic"
    else:
        if 10 <= hour <= 20:  # Weekend day time
            time_score = 0.6
            traffic_reason = "Weekend outing traffic"
        else:
            time_score = 0.15
            traffic_reason = "Light weekend traffic"

    # --- Location-based Urban Density Boost ---
    combined_locations = (source + " " + destination).lower()
    is_metro = any(city in combined_locations for city in MAJOR_METROS)
    location_label = "Urban" if is_metro else "Rural/Suburban"

    if is_metro:
        # Major cities get a +20% traffic boost
        time_score = min(1.0, time_score + 0.2)
        location_label = "Major Metro City"

    # --- Final Status Label ---
    if time_score >= 0.8:
        status = "🔴 Heavy Traffic"
    elif time_score >= 0.5:
        status = "🟡 Moderate Traffic"
    elif time_score >= 0.25:
        status = "🟢 Light Traffic"
    else:
        status = "🟢 Very Light Traffic"

    return {
        "level": round(time_score, 2),
        "status": status,
        "reason": traffic_reason,
        "area_type": location_label
    }

class RouteRequest(BaseModel):
    source: str
    destination: str
    fetch_pois: bool = True

def resolve_location(loc_str: str):
    # Check if string is already lat, lon
    if "," in loc_str:
        parts = loc_str.split(",")
        try:
            lat = float(parts[0].strip())
            lon = float(parts[1].strip())
            return (lat, lon)
        except ValueError:
            pass # Fall back to geocoding
            
    return geocode_address(loc_str)

@app.get("/autocomplete")
def autocomplete(q: str):
    if not q or len(q) < 3:
        return []
    try:
        url = f"https://nominatim.openstreetmap.org/search?q={q}&format=json&limit=5"
        headers = {'User-Agent': 'smartroute_ai_optimal_path_anu_unique_2026'}
        resp = requests.get(url, headers=headers, timeout=5)
        resp.raise_for_status()
        data = resp.json()
        
        results = []
        for item in data:
            results.append({
                "name": item.get("display_name"),
                "lat": item.get("lat"),
                "lon": item.get("lon")
            })
        return results
    except Exception as e:
        logging.error(f"Autocomplete error: {e}")
        return []

@app.post("/route")
def calculate_route(req: RouteRequest):
    # 1. Geocode locations
    source_coords = resolve_location(req.source)
    dest_coords = resolve_location(req.destination)
    
    if not source_coords:
        raise HTTPException(status_code=400, detail=f"Could not find location: {req.source}")
    if not dest_coords:
        raise HTTPException(status_code=400, detail=f"Could not find location: {req.destination}")
        
    lat1, lon1 = source_coords
    lat2, lon2 = dest_coords
    
    # Calculate straight-line distance to prevent downloading massive graphs
    distance_m = haversine(lat1, lon1, lat2, lon2)
    max_distance_km = 25 # Reduced to 25km to prevent Hugging Face cloud timeouts
    
    if distance_m / 1000 > max_distance_km:
        logging.info(f"Distance > 100km ({round(distance_m/1000, 1)}km). Using OSRM API.")
        # Auto-detect traffic for long-distance routes too
        traffic_info = predict_traffic_level(req.source, req.destination)

        # Call public OSRM API
        osrm_url = f"http://router.project-osrm.org/route/v1/driving/{lon1},{lat1};{lon2},{lat2}?overview=full&geometries=geojson"
        try:
            resp = requests.get(osrm_url, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            
            if data["code"] != "Ok":
                raise HTTPException(status_code=404, detail="No long-distance path found.")
                
            route_data = data["routes"][0]
            coords = route_data["geometry"]["coordinates"]
            
            # OSRM returns [lon, lat], we need {"lat": lat, "lon": lon}
            path_coords = [{"lat": pt[1], "lon": pt[0]} for pt in coords]
            
            # Apply traffic delay to OSRM time as well
            base_time = route_data["duration"] / 60
            traffic_multiplier = 1 + (traffic_info["level"] * 0.4)
            time_minutes = round(base_time * traffic_multiplier, 2)
            dist_km = round(route_data["distance"] / 1000, 2)

            # Fetch petrol pumps using a fast single bounding box Overpass query
            pumps = []
            if req.fetch_pois:
                try:
                    pumps = fetch_pumps_along_route(lat1, lon1, lat2, lon2, max_results=20)
                except Exception as poi_err:
                    logging.warning(f"POI fetch error: {poi_err}")
                    pumps = []


            
            return {
                "source_coords": {"lat": lat1, "lon": lon1},
                "dest_coords": {"lat": lat2, "lon": lon2},
                "route": path_coords,
                "metrics": {
                    "time_minutes": time_minutes,
                    "distance_km": dist_km,
                    "algorithm": "OSRM (Fast Global Routing)"
                },
                "traffic": traffic_info,
                "pois": pumps
            }
        except Exception as e:
            logging.error(f"OSRM Error: {e}")
            raise HTTPException(status_code=500, detail=f"Long-distance routing failed: {e}")
    
    try:
        # 2. Auto-detect traffic level based on time & location
        traffic_info = predict_traffic_level(req.source, req.destination)
        logging.info(f"AI Traffic Detection: {traffic_info}")

        # 3. Fetch Map Graph
        G = fetch_map_data(lat1, lon1, lat2, lon2)
        
        # 4. Apply Traffic Model using AI-detected level
        G = apply_traffic_model(G, simulation_level=traffic_info["level"])
        
        # 5. Find nearest nodes
        source_node = get_nearest_node(G, lat1, lon1)
        dest_node = get_nearest_node(G, lat2, lon2)
        
        # 6. Pathfinding (Strictly A* for optimal performance)
        result = find_optimal_path(G, source_node, dest_node)
        
        if not result:
            raise HTTPException(status_code=404, detail="No path found between the locations.")
            
        # 6. Fetch POIs (Petrol Pumps)
        pumps = []
        if req.fetch_pois:
            pumps = fetch_nearest_petrol_pumps(lat1, lon1, lat2, lon2)
            
        return {
            "source_coords": {"lat": lat1, "lon": lon1},
            "dest_coords": {"lat": lat2, "lon": lon2},
            "route": result["path"],
            "metrics": {
                "time_minutes": result["total_time_minutes"],
                "distance_km": result["total_distance_km"],
                "algorithm": result["algorithm"]
            },
            "traffic": traffic_info,
            "pois": pumps
        }
        
    except Exception as e:
        logging.error(f"Error calculating route: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Mount static files for the frontend UI
frontend_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "frontend")
os.makedirs(frontend_dir, exist_ok=True)
app.mount("/static", StaticFiles(directory=frontend_dir), name="static")

@app.get("/")
def read_index():
    return FileResponse(os.path.join(frontend_dir, "index.html"))
