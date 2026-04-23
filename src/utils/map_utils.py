import os
import osmnx as ox
import networkx as nx
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut
import logging
import threading

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize geocoder with a very unique user agent to avoid shared IP rate limits
geolocator = Nominatim(user_agent="smartroute_ai_optimal_path_anu_unique_2026")

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data")
os.makedirs(DATA_DIR, exist_ok=True)

# Lock to prevent concurrent OSMnx downloads and rate limiting
download_lock = threading.Lock()

def geocode_address(address: str):
    """Convert an address string into (lat, lon) coordinates."""
    try:
        # Increased timeout to 10 seconds for better resilience on shared hosting
        location = geolocator.geocode(address, timeout=10)
        if location:
            return location.latitude, location.longitude
        return None
    except GeocoderTimedOut:
        logger.error("Geocoding timed out.")
        return None

def get_bounding_box(lat1, lon1, lat2, lon2, padding=0.015):
    """Calculate a bounding box (north, south, east, west) encompassing two points."""
    north = max(lat1, lat2) + padding
    south = min(lat1, lat2) - padding
    east = max(lon1, lon2) + padding
    west = min(lon1, lon2) - padding
    return north, south, east, west

def fetch_map_data(lat1, lon1, lat2, lon2):
    """Fetch the road network graph for a bounding box containing both points."""
    north, south, east, west = get_bounding_box(lat1, lon1, lat2, lon2)
    # Generate a cache key based on rounded coordinates to reuse graphs for nearby queries
    cache_key = f"graph_{round(north, 2)}_{round(south, 2)}_{round(east, 2)}_{round(west, 2)}.graphml"
    cache_path = os.path.join(DATA_DIR, cache_key)

    if os.path.exists(cache_path):
        logger.info(f"Loading graph from cache: {cache_path}")
        G = ox.load_graphml(cache_path)
    else:
        with download_lock:
            # Check again inside the lock in case another thread just finished downloading it
            if os.path.exists(cache_path):
                logger.info(f"Loading graph from cache (after wait): {cache_path}")
                return ox.load_graphml(cache_path)
                
            logger.info(f"Downloading graph for bounding box: {(west, south, east, north)}")
            # network_type="drive" for cars
            G = ox.graph_from_bbox(bbox=(west, south, east, north), network_type="drive", simplify=True)
            logger.info(f"Graph downloaded. Nodes: {len(G.nodes)}")
            
            # Add edge lengths and speeds
            logger.info("Adding edge lengths...")
            G = ox.distance.add_edge_lengths(G)
            logger.info("Adding edge speeds...")
            G = ox.routing.add_edge_speeds(G)
            logger.info("Adding edge travel times...")
            G = ox.routing.add_edge_travel_times(G)
            
            logger.info(f"Saving graph to cache: {cache_path}")
            ox.save_graphml(G, cache_path)
    
    return G

def get_nearest_node(G, lat, lon):
    """Find the nearest graph node to a given coordinate."""
    return ox.distance.nearest_nodes(G, lon, lat)

def fetch_nearest_petrol_pumps(lat1, lon1, lat2, lon2):
    """Fetch petrol pumps (amenity=fuel) within the bounding box."""
    north, south, east, west = get_bounding_box(lat1, lon1, lat2, lon2, padding=0.015)
    try:
        logger.info("Fetching petrol pumps from OSM...")
        tags = {"amenity": "fuel"}
        with download_lock:
            pois = ox.features_from_bbox(bbox=(west, south, east, north), tags=tags)
        logger.info(f"Found {len(pois)} petrol pumps.")
        
        # Extract lat/lon for the POIs
        pumps = []
        for idx, row in pois.iterrows():
            # if it's a polygon/multipolygon, use the centroid
            geom = row['geometry']
            name = row.get('name', 'Petrol Pump')
            if not isinstance(name, str):
                name = 'Petrol Pump'
                
            if geom.geom_type == 'Point':
                pumps.append({"lat": geom.y, "lon": geom.x, "name": name})
            else:
                centroid = geom.centroid
                pumps.append({"lat": centroid.y, "lon": centroid.x, "name": name})
        return pumps
    except Exception as e:
        logger.error(f"Error fetching petrol pumps: {e}")
        return []
