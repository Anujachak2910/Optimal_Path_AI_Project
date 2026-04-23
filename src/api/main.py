import logging
import os
import requests
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

from src.utils.map_utils import geocode_address, fetch_map_data, get_nearest_node, fetch_nearest_petrol_pumps
from src.utils.traffic_model import apply_traffic_model
from src.algorithms.pathfinder import find_optimal_path, haversine

app = FastAPI(title="SmartRoute AI API")

# Configure CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class RouteRequest(BaseModel):
    source: str
    destination: str
    traffic_level: float = 0.5
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
    max_distance_km = 100 # Maximum allowed distance for local processing
    
    if distance_m / 1000 > max_distance_km:
        logging.info(f"Distance > 100km ({round(distance_m/1000, 1)}km). Using OSRM API.")
        # Call public OSRM API
        osrm_url = f"http://router.project-osrm.org/route/v1/driving/{lon1},{lat1};{lon2},{lat2}?overview=full&geometries=geojson"
        try:
            resp = requests.get(osrm_url)
            resp.raise_for_status()
            data = resp.json()
            
            if data["code"] != "Ok":
                raise HTTPException(status_code=404, detail="No long-distance path found.")
                
            route_data = data["routes"][0]
            coords = route_data["geometry"]["coordinates"]
            
            # OSRM returns [lon, lat], we need {"lat": lat, "lon": lon}
            path_coords = [{"lat": pt[1], "lon": pt[0]} for pt in coords]
            
            # Time in OSRM is seconds, distance is meters
            time_minutes = round(route_data["duration"] / 60, 2)
            dist_km = round(route_data["distance"] / 1000, 2)
            
            return {
                "source_coords": {"lat": lat1, "lon": lon1},
                "dest_coords": {"lat": lat2, "lon": lon2},
                "route": path_coords,
                "metrics": {
                    "time_minutes": time_minutes,
                    "distance_km": dist_km,
                    "algorithm": "OSRM (Fast routing)"
                },
                "pois": [] # Skip POIs for long distances to save load
            }
        except Exception as e:
            logging.error(f"OSRM Error: {e}")
            raise HTTPException(status_code=500, detail=f"Long-distance routing failed: {e}")
    
    try:
        # 2. Fetch Map Graph
        G = fetch_map_data(lat1, lon1, lat2, lon2)
        
        # 3. Apply Traffic Model
        G = apply_traffic_model(G, simulation_level=req.traffic_level)
        
        # 4. Find nearest nodes
        source_node = get_nearest_node(G, lat1, lon1)
        dest_node = get_nearest_node(G, lat2, lon2)
        
        # 5. Pathfinding (Strictly A* for optimal performance)
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
