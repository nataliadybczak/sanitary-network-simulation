# ---
# jupyter:
#   jupytext:
#     cell_metadata_filter: -all
#     formats: ipynb,py:light
#     text_representation:
#       extension: .py
#       format_name: light
#       format_version: '1.5'
#       jupytext_version: 1.18.1
#   kernelspec:
#     display_name: Python 3 (ipykernel)
#     language: python
#     name: python3
# ---

from ipyleaflet import Map, Marker, MarkerCluster, Popup
from ipywidgets import HTML, VBox, Button
from IPython.display import display

from model.model import SewerSystemModel
import time

# Uruchomienie modelu
model = SewerSystemModel(max_capacity=500, max_hours=7)

# Inicjalizacja mapy (centrum Żywca)
m = Map(center=(49.685, 19.21), zoom=14)

# Markery dla agentów
agent_markers = []

def create_marker(agent, label):
    location = agent.location  # (lat, lon)
    html = HTML()
    html.value = f"<b>{label}</b><br>Flow: {getattr(agent, 'current_flow', '–')} m³/h"
    popup = Popup(child=html, close_button=False)
    marker = Marker(location=location, draggable=False)
    marker.popup = popup
    return marker

#  Markery startowe
for sensor in model.sensors:
    agent_markers.append(create_marker(sensor, f"Sensor {sensor.location_id}"))

for over in model.overflow_points:
    agent_markers.append(create_marker(over, f"Overflow {over.location_id}"))

agent_markers.append(create_marker(model.plant, "Sewage Plant"))

cluster = MarkerCluster(markers=agent_markers)
m.add(cluster)


# Przycisk do wykonania 1 kroku
def advance_model(change=None):
    if model.running:
        model.step()
        # Aktualizacja
        for i, sensor in enumerate(model.sensors):
            agent_markers[i].popup.child.value = f"<b>Sensor {sensor.location_id}</b><br>Flow: {sensor.current_flow} m³/h"
        for i, over in enumerate(model.overflow_points):
            idx = len(model.sensors) + i
            flow = over.diverted_flow if over.active else 0
            agent_markers[idx].popup.child.value = f"<b>Overflow {over.location_id}</b><br>Flow: {flow} m³/h"
        # Plant
        plant_idx = len(agent_markers) - 1
        agent_markers[plant_idx].popup.child.value = f"<b>Sewage Plant</b><br>Total: {model.plant.total_flow} m³/h"

step_btn = Button(description=f"Godzina {model.current_hour}", button_style='info')
step_btn.on_click(advance_model)

# Mapa + przycisk
display(VBox([m, step_btn]))







