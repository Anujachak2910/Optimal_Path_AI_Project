// Initialize Map
const map = L.map('map', {
    zoomControl: true,
    tap: false  // Fix for iOS Safari touch issues
}).setView([20.0, 0.0], 2);

L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19,
    attribution: '© OpenStreetMap contributors',
    crossOrigin: true
}).addTo(map);

// Fix for mobile black screen: tell Leaflet to recalculate its size
// after the browser has finished painting the layout
window.addEventListener('load', () => {
    setTimeout(() => { map.invalidateSize(); }, 300);
});

// Fix for black screen when rotating the phone
window.addEventListener('resize', () => {
    setTimeout(() => { map.invalidateSize(); }, 300);
});

// Also fix orientation change specifically (mobile)
window.addEventListener('orientationchange', () => {
    setTimeout(() => { map.invalidateSize(); }, 500);
});

// Custom Icons
const createIcon = (color) => {
    return new L.Icon({
        iconUrl: `https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-${color}.png`,
        shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/0.7.7/images/marker-shadow.png',
        iconSize: [25, 41],
        iconAnchor: [12, 41],
        popupAnchor: [1, -34],
        shadowSize: [41, 41]
    });
};

const sourceIcon = createIcon('blue');
const destIcon = createIcon('red');
const pumpIcon = createIcon('orange');

let currentRouteLayer = null;
let currentMarkers = [];

// DOM Elements
const form = document.getElementById('route-form');
const sourceInput = document.getElementById('source');
const destInput = document.getElementById('destination');
const loadingDiv = document.getElementById('loading');
const resultsDiv = document.getElementById('results');
const errorMsg = document.getElementById('error-msg');

const clearMap = () => {
    if (currentRouteLayer) {
        map.removeLayer(currentRouteLayer);
    }
    currentMarkers.forEach(m => map.removeLayer(m));
    currentMarkers = [];
};

const displayError = (msg) => {
    errorMsg.textContent = msg;
    errorMsg.classList.remove('hidden');
    resultsDiv.classList.add('hidden');
};

form.addEventListener('submit', async (e) => {
    e.preventDefault();
    
    // UI state
    errorMsg.classList.add('hidden');
    resultsDiv.classList.add('hidden');
    loadingDiv.classList.remove('hidden');
    clearMap();

    const payload = {
        source: sourceInput.dataset.coords || sourceInput.value,
        destination: destInput.dataset.coords || destInput.value,
        fetch_pois: true
    };

    try {
        const response = await fetch('/route', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(payload)
        });

        // Prevent crash if Hugging Face returns a 504 Timeout or 500 HTML error page
        const contentType = response.headers.get("content-type");
        if (!contentType || !contentType.includes("application/json")) {
            throw new Error("The cloud server took too long and timed out. Please try a shorter distance.");
        }

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.detail || 'Failed to calculate route.');
        }

        // Draw Route
        const latlngs = data.route.map(pt => [pt.lat, pt.lon]);
        currentRouteLayer = L.polyline(latlngs, {
            color: '#3b82f6', 
            weight: 6,
            opacity: 0.8,
            lineJoin: 'round'
        }).addTo(map);

        // Fit bounds
        map.fitBounds(currentRouteLayer.getBounds(), { padding: [50, 50] });

        // Add Markers
        const sourceMarker = L.marker([data.source_coords.lat, data.source_coords.lon], {icon: sourceIcon})
            .bindPopup("<b>Source</b>")
            .addTo(map);
        
        const destMarker = L.marker([data.dest_coords.lat, data.dest_coords.lon], {icon: destIcon})
            .bindPopup("<b>Destination</b>")
            .addTo(map);
            
        currentMarkers.push(sourceMarker, destMarker);

        // Add POIs
        if (data.pois && data.pois.length > 0) {
            data.pois.forEach(poi => {
                const marker = L.marker([poi.lat, poi.lon], {icon: pumpIcon})
                    .bindPopup(`⛽ ${poi.name || 'Petrol Pump'}`)
                    .addTo(map);
                currentMarkers.push(marker);
            });
        }

        // Format Distance
        const distKmRaw = data.metrics.distance_km;
        const km = Math.floor(distKmRaw);
        const m = Math.round((distKmRaw - km) * 1000);
        const distText = km > 0 ? `${km} km ${m} m` : `${m} m`;

        // Format Time
        const timeMinRaw = data.metrics.time_minutes;
        const hrs = Math.floor(timeMinRaw / 60);
        const mins = Math.round(timeMinRaw % 60);
        let timeText = "";
        if (hrs > 0) timeText += `${hrs} hr `;
        timeText += `${mins} min`;

        // Update Results UI
        document.getElementById('dist-val').textContent = distText;
        document.getElementById('time-val').textContent = timeText;
        document.getElementById('pois-val').textContent = data.pois ? data.pois.length : 0;

        // Display AI Traffic Analysis
        if (data.traffic) {
            document.getElementById('traffic-status-val').textContent = data.traffic.status;
            document.getElementById('traffic-reason-val').textContent = `📍 ${data.traffic.reason}`;
            document.getElementById('traffic-area-val').textContent = `🏙️ ${data.traffic.area_type}`;
        }
        
        resultsDiv.classList.remove('hidden');

    } catch (err) {
        displayError(err.message);
    } finally {
        loadingDiv.classList.add('hidden');
    }
});

// --- Autocomplete Logic ---
let autocompleteTimeout = null;

function setupAutocomplete(inputId, listId) {
    const inputEl = document.getElementById(inputId);
    const listEl = document.getElementById(listId);

    inputEl.addEventListener('input', (e) => {
        // Clear previous coordinates if user types manually
        inputEl.dataset.coords = "";
        
        clearTimeout(autocompleteTimeout);
        const query = e.target.value;
        if (query.length < 3) {
            listEl.classList.add('hidden');
            listEl.innerHTML = '';
            return;
        }

        autocompleteTimeout = setTimeout(async () => {
            try {
                const res = await fetch(`/autocomplete?q=${encodeURIComponent(query)}`);
                const data = await res.json();
                
                listEl.innerHTML = '';
                if (data.length > 0) {
                    data.forEach(item => {
                        const li = document.createElement('li');
                        li.textContent = item.name;
                        li.addEventListener('click', () => {
                            inputEl.value = item.name;
                            inputEl.dataset.coords = `${item.lat}, ${item.lon}`; // Save exact coordinates
                            listEl.classList.add('hidden');
                        });
                        listEl.appendChild(li);
                    });
                    listEl.classList.remove('hidden');
                } else {
                    listEl.classList.add('hidden');
                }
            } catch (err) {
                console.error("Autocomplete error", err);
            }
        }, 400); // 400ms debounce
    });

    // Close list when clicking outside
    document.addEventListener('click', (e) => {
        if (e.target !== inputEl && !listEl.contains(e.target)) {
            listEl.classList.add('hidden');
        }
    });
}

setupAutocomplete('source', 'source-autocomplete');
setupAutocomplete('destination', 'dest-autocomplete');
