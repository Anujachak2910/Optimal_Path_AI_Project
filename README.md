---
title: SmartRoute AI
emoji: 🚀
colorFrom: blue
colorTo: indigo
sdk: docker
pinned: false
---

# SmartRoute AI (Optimal Path Finder)

[![Hugging Face Space](https://img.shields.io/badge/%F0%9F%A4%97%20Hugging%20Face-Space-blue)](https://huggingface.co/spaces/AnuC2910/smartroute-maps)

SmartRoute AI is an intelligent, production-grade geographic routing application. It dynamically calculates the absolute mathematically optimal path between any two locations across the globe, minimizing travel time while accounting for real-world AI-detected traffic conditions.

## 🌐 Live Demo
You can try the application live here:  
👉 **[https://huggingface.co/spaces/AnuC2910/smartroute-maps](https://huggingface.co/spaces/AnuC2910/smartroute-maps)**

## 🌟 Key Features

- **True AI Pathfinding (A* Search)**: Utilizes the industry-standard A* (A-Star) algorithm with spatial heuristics to calculate the mathematically optimal route.
- **AI Smart Traffic Analysis**: Automatically detects real-world traffic levels based on the current time of day (Rush Hour vs. Late Night) and urban density (Major Metro vs. Rural).
- **Global Hybrid Architecture**: 
  - **Local Routing (< 100km)**: Dynamically downloads street networks from OpenStreetMap (OSM) for personalized, hyper-accurate local routing.
  - **Global Routing (> 100km)**: Automatically utilizes the OSRM Cloud API for massive, cross-country trips.
- **Live Search Autocomplete**: Features a live dropdown search bar directly linked to OSM for exact location selection.
- **Petrol Pump Detection**: Intelligently plots the nearest fuel stations along the calculated route.
- **Premium UI/UX**: Built with a responsive, glassmorphic frontend utilizing Leaflet.js for interactive mapping.

## 🛠️ Tech Stack

- **Backend**: Python, FastAPI, Uvicorn
- **AI & Graph Processing**: OSMnx, NetworkX, Pytz (Timezone Analysis)
- **Geocoding & API**: Geopy, OpenStreetMap, OSRM Public API
- **Deployment**: Docker, Hugging Face Spaces
- **Frontend**: HTML5, Vanilla CSS (Glassmorphism), Vanilla JavaScript, Leaflet.js

## 💻 Local Development (Optional)

If you wish to run SmartRoute AI locally on your own machine:

1. **Activate the Virtual Environment**
   ```powershell
   .\venv\Scripts\Activate.ps1
   ```

2. **Start the FastAPI Server**
   ```powershell
   uvicorn src.api.main:app --port 8000
   ```

3. **Access the Application**
   Open your browser and navigate to: **http://127.0.0.1:8000/**

## 🗺️ Usage

1. Start typing a **Source** (e.g., *Eiffel Tower*) and select from the dropdown.
2. Start typing a **Destination** (e.g., *Louvre Museum*) and select from the dropdown.
3. Click **Find Optimal Path**.
4. The AI will automatically analyze the **Time of Day** and **City Type** to predict traffic and calculate the fastest route!