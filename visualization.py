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

import asyncio
import nest_asyncio
from ipyleaflet import Map, Marker, DivIcon
from ipywidgets import VBox, HBox, Button, Layout
from IPython.display import display
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from model.model import SewerSystemModel


def run_sewer_visualization(auto_interval=3):

    # Inicjalizacja modelu
    model = SewerSystemModel(max_capacity=500, max_hours=7)

    # Inicjalizacja mapy
    m = Map(center=(49.685, 19.21), zoom=15)
    markers, labels = [], []

    # Tworzenie markerów z etykietami dla agentów
    def create_marker_with_label(agent, label_text):
        location = agent.location
        flow = getattr(agent, 'current_flow', getattr(agent, 'diverted_flow', 0))
        text = f"{label_text}<br>{flow} m³/h"
        marker = Marker(location=location, draggable=False)
        label = Marker(
            location=(location[0] + 0.0003, location[1]),
            icon=DivIcon(html=f"""
                <div style="
                    font-size: 13px;
                    background: white;
                    border: 1px solid black;
                    padding: 4px 6px;
                    border-radius: 6px;
                    width: 110px;
                    text-align: center;
                    white-space: nowrap;
                    box-shadow: 2px 2px 4px rgba(0,0,0,0.2);
                ">{text}</div>
            """),
            draggable=False
        )
        return marker, label

    for sensor in model.sensors:
        m1, l1 = create_marker_with_label(sensor, f"Sensor {sensor.location_id}")
        markers.append(m1)
        labels.append(l1)
    for over in model.overflow_points:
        m2, l2 = create_marker_with_label(over, f"Overflow {over.location_id}")
        markers.append(m2)
        labels.append(l2)
    m3, l3 = create_marker_with_label(model.plant, "Sewage Plant")
    markers.append(m3)
    labels.append(l3)
    for mk, lb in zip(markers, labels):
        m.add(mk)
        m.add(lb)

    # Wykres Plotly
    fig = go.FigureWidget(make_subplots(rows=1, cols=1))
    fig.update_layout(
        title="Przepływy w czasie",
        xaxis_title="Godzina",
        yaxis_title="Przepływ (m³/h)",
        template="plotly_white",
        height=550,
    )
    fig.add_hline(y=500, line_dash="dash", line_color="red", annotation_text="Limit 500 m³/h")

    # Layout mapy i wykresu
    step_btn = Button(description="⏸️ Pauza", button_style='info')
    m.layout = Layout(width='100%', height='550px')
    left_col = VBox([m, step_btn]); left_col.layout = Layout(width='65%', margin='10px')
    right_col = VBox([fig]);         right_col.layout = Layout(width='35%', margin='10px')
    dashboard = HBox([left_col, right_col]); dashboard.layout = Layout(width='100%', height='auto')
    display(dashboard)

    running = True

    async def update_visualization():
        nonlocal running
        while model.running:
            if running:
                model.step()

                # Aktualizacja etykiet
                for i, sensor in enumerate(model.sensors):
                    flow = sensor.current_flow
                    labels[i].icon = DivIcon(html=f"""
                        <div style="font-size: 13px; background: white; border: 1px solid black;
                                    padding: 4px 6px; border-radius: 6px; width: 110px;
                                    text-align: center; white-space: nowrap;
                                    box-shadow: 2px 2px 4px rgba(0,0,0,0.2);">
                            Sensor {sensor.location_id}<br>{flow} m³/h
                        </div>
                    """)

                for j, over in enumerate(model.overflow_points):
                    idx = len(model.sensors) + j
                    flow = over.diverted_flow if over.active else 0
                    labels[idx].icon = DivIcon(html=f"""
                        <div style="font-size: 13px; background: white; border: 1px solid black;
                                    padding: 4px 6px; border-radius: 6px; width: 110px;
                                    text-align: center; white-space: nowrap;
                                    box-shadow: 2px 2px 4px rgba(0,0,0,0.2);">
                            Overflow {over.location_id}<br>{flow} m³/h
                        </div>
                    """)

                total = model.plant.total_flow
                labels[-1].icon = DivIcon(html=f"""
                    <div style="font-size: 13px; background: white; border: 1px solid black;
                                padding: 4px 6px; border-radius: 6px; width: 110px;
                                text-align: center; white-space: nowrap;
                                box-shadow: 2px 2px 4px rgba(0,0,0,0.2);">
                        Sewage Plant<br>{total} m³/h
                    </div>
                """)

                # Aktualizacja wykresu
                df = model.datacollector.get_model_vars_dataframe()
                if not df.empty:
                    fig.data = []
                    for column in df.columns:
                        if "Flow" in column:
                            fig.add_trace(go.Scatter(
                                x=df.index,
                                y=df[column],
                                mode="lines+markers",
                                name=column
                            ))
                    fig.add_hline(y=500, line_dash="dash", line_color="red")

            await asyncio.sleep(auto_interval)

    # Obsługa pauzy
    def toggle_simulation(change):
        nonlocal running
        running = not running
        step_btn.description = "▶️ Wznów" if not running else "⏸️ Pauza"

    step_btn.on_click(toggle_simulation)

    # Pętla async
    nest_asyncio.apply()
    asyncio.ensure_future(update_visualization())

run_sewer_visualization(auto_interval=3)




