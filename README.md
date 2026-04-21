# SmartRoute AI (Optimal Path Finder)

SmartRoute AI is an intelligent, production-grade geographic routing application. It dynamically calculates the absolute mathematically optimal path between any two locations across the globe, minimizing travel time while accounting for simulated real-world traffic conditions.

## 🌟 Key Features

- **True AI Pathfinding (A* Search)**: Utilizes the industry-standard A* (A-Star) algorithm with spatial heuristics to calculate the mathematically optimal route.
- **Global Hybrid Architecture**: 
  - **Local Routing (< 100km)**: Dynamically downloads street networks from OpenStreetMap (OSM) for personalized, hyper-accurate local routing.
  - **Global Routing (> 100km)**: Automatically utilizes the OSRM Cloud API for massive, cross-country trips to ensure instantaneous results without server crashes.
- **Live Search Autocomplete**: Features a live dropdown search bar directly linked to OSM, allowing users to find exact locations and bypassing slow geocoding steps.
- **High Performance & Concurrency**: Implements thread-safe graph caching (`threading.Lock`), saving downloaded maps to the local disk to completely eliminate rate-limiting and make subsequent searches lightning fast.
- **Dynamic Optimization**: Simulates traffic delays based on road types (highways vs. local roads) and plots the nearest Points of Interest (Petrol Pumps) along your route.
- **Premium UI/UX**: Built with a responsive, glassmorphic frontend utilizing Leaflet.js for interactive mapping.

## 🛠️ Tech Stack

- **Backend**: Python, FastAPI, Uvicorn
- **AI & Graph Processing**: OSMnx, NetworkX
- **Geocoding & API**: Geopy, OpenStreetMap, OSRM Public API
- **Frontend**: HTML5, Vanilla CSS (Glassmorphism), Vanilla JavaScript, Leaflet.js

## 🚀 How to Run the Application

Follow these steps to run SmartRoute AI locally on your machine:

1. **Activate the Virtual Environment**
   Open your terminal (PowerShell) inside the `Optimal_Path_AI_project` folder and run:
   ```powershell
   .\venv\Scripts\Activate.ps1
   ```

2. **Start the FastAPI Server**
   Start the backend and serve the frontend by running:
   ```powershell
   uvicorn src.api.main:app --port 8000
   ```
   *(Press `Ctrl + C` in the terminal to stop the server).*

3. **Access the Application**
   Open your web browser and navigate to:
   **[http://127.0.0.1:8000/](http://127.0.0.1:8000/)**

## 🗺️ Usage

1. Start typing a **Source** (e.g., *Eiffel Tower*) and click the exact location from the live autocomplete dropdown.
2. Start typing a **Destination** (e.g., *Louvre Museum*) and select it from the dropdown.
3. Adjust the **Traffic Slider** to see how heavy traffic affects the calculated travel time.
4. Click **Find Optimal Path** to see the AI generate your route!