# trail_proj_trails_only.py
from pathlib import Path
import geopandas as gpd
import pandas as pd
import folium
from folium.plugins import MarkerCluster
import html, re, googlemaps
from dotenv import load_dotenv
import os

load_dotenv() 

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
gmaps = googlemaps.Client(key=GOOGLE_API_KEY)


BASE_DIR = Path(r"C:\Users\isaac\Desktop\Trails Project IH 2025")
TRAILS_PATH = BASE_DIR / "data/raw/trails_slc_clipped.shp"
OUTPUT_HTML = BASE_DIR / "data/processed/trails_map_trails_only.html"
TRAILHEADS_PATH = BASE_DIR / "data/processed/trailheads_area_clipped_all.geojson"

#load data --
trails = gpd.read_file(TRAILS_PATH)
trailheads = gpd.read_file(TRAILHEADS_PATH)

print("Trailheads columns:", trailheads.columns.tolist())

# Convert CRS and clip trailheads to trails extent
if trails.crs.is_geographic:
    trails = trails.to_crs(epsg=26912)
if trailheads.crs is None or not trailheads.crs.is_geographic:
    trailheads = trailheads.to_crs(trails.crs)
trailheads = trailheads[trailheads.geometry.notnull()]


minx, miny, maxx, maxy = trails.total_bounds
buffer = 2000
#trailheads = trailheads.cx[minx-buffer:maxx+buffer, miny-buffer:maxy+buffer]
print(f"Filtered trailheads: {len(trailheads)}")


# Keep only trails with difficulty ratings
mtn_trails = trails[trails["HikeDiffic"].notnull()].copy()
mtn_trails["Length_mi"] = (mtn_trails.geometry.length / 1609.34).round(1)

#fetch trailhead info from Google Places API
def fetch_trailhead_info(name, lat, lon):
    try:
        result = gmaps.places_nearby(location=(lat, lon), keyword=name, radius=500)
        if result.get("results"):
            place = result["results"][0]
            rating = place.get("rating", None)
            user_ratings_total = place.get("user_ratings_total", None)
            place_id = place.get("place_id", None)

            # Get detailed info (including reviews)
            details = gmaps.place(place_id=place_id, fields=["review"])
            top_review = None
            if "result" in details and "reviews" in details["result"]:
                top_review = details["result"]["reviews"][0]["text"]

            # Google Maps link
            maps_link = f"https://www.google.com/maps/place/?q=place_id:{place_id}" if place_id else None

            return rating, user_ratings_total, top_review, maps_link
        return None, None, None, None
    except Exception as e:
        print(f"Error fetching info for {name}: {e}")
        return None, None, None, None
# -------------------------------
# Create Map
# -------------------------------
bounds = mtn_trails.to_crs(epsg=4326).total_bounds
center_lat = (bounds[1] + bounds[3]) / 2
center_lon = (bounds[0] + bounds[2]) / 2

m = folium.Map(
    location=[center_lat, center_lon],
    zoom_start=12,
    tiles="https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png",
    attr="© OpenTopoMap contributors",
)

# -------------------------------
# Color Function
# -------------------------------
def get_color(difficulty):
    d = str(difficulty).lower()
    if "beginner" in d:
        return "#3CB371"  # green
    elif "intermediate" in d:
        return "#FFA500"  # orange
    elif "advanced" in d:
        return "#DC143C"  # red
    return "gray"

# -------------------------------
# Add Trails Layer
# -------------------------------
folium.GeoJson(
    mtn_trails.to_crs(epsg=4326),
    style_function=lambda feature: {
        "color": get_color(feature["properties"]["HikeDiffic"]),
        "weight": 3,
        "opacity": 0.85,
    },
    highlight_function=lambda feature: {
        "weight": 7,
        "color": "#FFFF00",
        "opacity": 0.9,
    },
    tooltip=folium.GeoJsonTooltip(
        fields=["PrimaryNam", "HikeDiffic", "BikeDiffic", "Length_mi"],
        aliases=["Trail:", "Hike Difficulty:", "Bike Difficulty:", "Length (mi):"],
        localize=True,
    ),
    name="Trails",
).add_to(m)

# -------------------------------
# Add Trailhead Markers
# -------------------------------
cluster = MarkerCluster(name="Trailheads").add_to(m)

for _, row in trailheads.iterrows():
    name = re.sub(r"\s+", " ", html.escape(str(row["PrimaryName"]))).strip()
    lat, lon = row.geometry.y, row.geometry.x
    rating, user_ratings_total, top_review, maps_link = fetch_trailhead_info(name, lat, lon)

    popup_html = f"""
    <div style='font-size:14px; line-height:1.4'>
        <b>{name}</b><br>
        <b>Rating:</b> {rating if rating else "N/A"} ({user_ratings_total if user_ratings_total else 0} reviews)<br>
        <b>Top review:</b> {top_review[:200]+"..." if top_review else "N/A"}<br>
        {f'<a href="{maps_link}" target="_blank">More info on Google Maps</a>' if maps_link else ''}
    </div>
    """
    folium.Marker(
        [lat, lon],
        icon=folium.Icon(icon="car", prefix="fa", color="blue"),
        popup=folium.Popup(popup_html, max_width=300),
    ).add_to(cluster)

# -------------------------------
# Add Legend
# -------------------------------
legend_html = """
    <div style="
    position: fixed;
    bottom: 30px;
    left: 30px;
    z-index: 9999;
    width: 160px;
    background-color: white;
    border-radius: 8px;
    box-shadow: 0 0 10px rgba(0,0,0,0.3);
    padding: 10px;
    font-size: 13px;
    line-height: 1.5;">
    <b>Trail Difficulty</b><br>
    <i style="background:#3CB371; width:10px; height:10px; float:left; margin-right:5px;"></i> Beginner<br>
    <i style="background:#FFA500; width:10px; height:10px; float:left; margin-right:5px;"></i> Intermediate<br>
    <i style="background:#DC143C; width:10px; height:10px; float:left; margin-right:5px;"></i> Advanced<br>
    </div>
    """
m.get_root().html.add_child(folium.Element(legend_html))

# -------------------------------
# Finalize Map
# -------------------------------
folium.LayerControl().add_to(m)
m.save(OUTPUT_HTML)
print(f"✅ Map saved to {OUTPUT_HTML}")