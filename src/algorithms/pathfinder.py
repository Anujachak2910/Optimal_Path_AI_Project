import networkx as nx
import math

def haversine(lat1, lon1, lat2, lon2):
    """Calculate the great circle distance in meters between two points."""
    R = 6371000 # radius of earth in meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = math.sin(delta_phi / 2.0) ** 2 + \
        math.cos(phi1) * math.cos(phi2) * \
        math.sin(delta_lambda / 2.0) ** 2
    
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def get_path_metrics(G, path, weight='traffic_time'):
    """Calculate total distance and time for a given path."""
    total_time = 0.0
    total_distance = 0.0
    
    for i in range(len(path) - 1):
        u = path[i]
        v = path[i+1]
        # MultiDiGraph, get edge data
        edge_data = G.get_edge_data(u, v)
        # Take the shortest edge if multiple exist
        min_weight_edge = min(edge_data.values(), key=lambda d: d.get(weight, float('inf')))
        
        total_time += min_weight_edge.get('traffic_time', 0)
        total_distance += min_weight_edge.get('length', 0)
        
    return total_time, total_distance

def find_optimal_path(G, source_node, target_node, weight="traffic_time"):
    """
    Find the shortest path using the A* algorithm (optimal and most accurate).
    weight can be 'length' or 'traffic_time'
    """
    if source_node not in G or target_node not in G:
        raise ValueError("Source or target node not in graph")

    def time_heuristic(u, v):
        # Admissible heuristic: straight line distance / max speed on graph
        # Max speed assumption ~ 120 km/h = 33 m/s
        dist = haversine(G.nodes[u]['y'], G.nodes[u]['x'], G.nodes[v]['y'], G.nodes[v]['x'])
        return dist / 33.33

    try:
        # Strictly use A* as it guarantees the same optimal path as Dijkstra but much faster
        path = nx.astar_path(G, source_node, target_node, heuristic=time_heuristic, weight=weight)
            
        time_sec, distance_m = get_path_metrics(G, path, weight)
        
        # Convert path nodes to coordinates for frontend
        route_coords = [{"lat": G.nodes[node]['y'], "lon": G.nodes[node]['x']} for node in path]
        
        time_minutes = round(time_sec / 60, 2)
        dist_km = round(distance_m / 1000, 2)
        
        # Sanitize NaNs
        if math.isnan(time_minutes): time_minutes = 0.0
        if math.isnan(dist_km): dist_km = 0.0
        
        return {
            "path": route_coords,
            "total_time_minutes": time_minutes,
            "total_distance_km": dist_km,
            "algorithm": "A* (Optimal AI Search)"
        }
    except nx.NetworkXNoPath:
        return None
