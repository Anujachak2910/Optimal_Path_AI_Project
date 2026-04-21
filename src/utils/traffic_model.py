import random
import networkx as nx

import math

def apply_traffic_model(G: nx.MultiDiGraph, simulation_level: float = 0.5):
    """
    Apply a mock traffic model to the graph edges.
    simulation_level: 0.0 (no traffic) to 1.0 (heavy traffic)
    We will modify the 'travel_time' edge attribute to 'traffic_time'.
    """
    for u, v, k, data in G.edges(keys=True, data=True):
        base_time = data.get('travel_time')
        if base_time is None or (isinstance(base_time, float) and math.isnan(base_time)):
            length = data.get('length', 100)
            if isinstance(length, list): length = length[0]
            if length is None or (isinstance(length, float) and math.isnan(length)): length = 100
            base_time = float(length) / 50 * 3.6
        
        # Determine road type factor
        highway = data.get('highway', 'unclassified')
        if isinstance(highway, list):
            highway = highway[0]
            
        traffic_factor = 1.0
        # Major roads get more traffic but have higher capacity. 
        # For simulation, we'll just add random delays scaled by simulation_level
        if highway in ['motorway', 'trunk', 'primary']:
            traffic_factor += random.uniform(0.1, 1.0) * simulation_level
        elif highway in ['secondary', 'tertiary']:
            traffic_factor += random.uniform(0.0, 0.5) * simulation_level
        else:
            traffic_factor += random.uniform(0.0, 0.2) * simulation_level
            
        traffic_time = base_time * traffic_factor
        
        # Calculate cost = length + alpha * traffic_delay
        # We will just use traffic_time as the weight for A* / Dijkstra
        data['traffic_time'] = traffic_time

    return G
