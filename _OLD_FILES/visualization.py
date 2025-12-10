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

# import asyncio
# import nest_asyncio
# from ipyleaflet import Map, Marker, DivIcon
# from ipywidgets import VBox, HBox, Button, Layout
# from IPython.display import display
# import plotly.graph_objects as go
# from plotly.subplots import make_subplots
# from model.model import SewerSystemModel
#
#
# def run_sewer_visualization(auto_interval=3):
#
#     # Inicjalizacja modelu
#     model = SewerSystemModel(max_capacity=500, max_hours=7)
#
#     # Inicjalizacja mapy
#     m = Map(center=(49.685, 19.21), zoom=15)
#     markers, labels = [], []
#
#     # Tworzenie markerów z etykietami dla agentów
#     def create_marker_with_label(agent, label_text):
#         location = agent.location
#         flow = getattr(agent, 'current_flow', getattr(agent, 'diverted_flow', 0))
#         text = f"{label_text}<br>{flow} m³/h"
#         marker = Marker(location=location, draggable=False)
#         label = Marker(
#             location=(location[0] + 0.0003, location[1]),
#             icon=DivIcon(html=f"""
#                 <div style="
#                     font-size: 13px;
#                     background: white;
#                     border: 1px solid black;
#                     padding: 4px 6px;
#                     border-radius: 6px;
#                     width: 110px;
#                     text-align: center;
#                     white-space: nowrap;
#                     box-shadow: 2px 2px 4px rgba(0,0,0,0.2);
#                 ">{text}</div>
#             """),
#             draggable=False
#         )
#         return marker, label
#
#     for sensor in model.sensors:
#         m1, l1 = create_marker_with_label(sensor, f"Sensor {sensor.location_id}")
#         markers.append(m1)
#         labels.append(l1)
#     for over in model.overflow_points:
#         m2, l2 = create_marker_with_label(over, f"Overflow {over.location_id}")
#         markers.append(m2)
#         labels.append(l2)
#     m3, l3 = create_marker_with_label(model.plant, "Sewage Plant")
#     markers.append(m3)
#     labels.append(l3)
#     for mk, lb in zip(markers, labels):
#         m.add(mk)
#         m.add(lb)
#
#     # Wykres Plotly
#     fig = go.FigureWidget(make_subplots(rows=1, cols=1))
#     fig.update_layout(
#         title="Przepływy w czasie",
#         xaxis_title="Godzina",
#         yaxis_title="Przepływ (m³/h)",
#         template="plotly_white",
#         height=550,
#     )
#     fig.add_hline(y=500, line_dash="dash", line_color="red", annotation_text="Limit 500 m³/h")
#
#     # Layout mapy i wykresu
#     step_btn = Button(description="⏸️ Pauza", button_style='info')
#     m.layout = Layout(width='100%', height='550px')
#     left_col = VBox([m, step_btn]); left_col.layout = Layout(width='65%', margin='10px')
#     right_col = VBox([fig]);         right_col.layout = Layout(width='35%', margin='10px')
#     dashboard = HBox([left_col, right_col]); dashboard.layout = Layout(width='100%', height='auto')
#     display(dashboard)
#
#     running = True
#
#     async def update_visualization():
#         nonlocal running
#         while model.running:
#             if running:
#                 model.step()
#
#                 # Aktualizacja etykiet
#                 for i, sensor in enumerate(model.sensors):
#                     flow = sensor.current_flow
#                     labels[i].icon = DivIcon(html=f"""
#                         <div style="font-size: 13px; background: white; border: 1px solid black;
#                                     padding: 4px 6px; border-radius: 6px; width: 110px;
#                                     text-align: center; white-space: nowrap;
#                                     box-shadow: 2px 2px 4px rgba(0,0,0,0.2);">
#                             Sensor {sensor.location_id}<br>{flow} m³/h
#                         </div>
#                     """)
#
#                 for j, over in enumerate(model.overflow_points):
#                     idx = len(model.sensors) + j
#                     flow = over.diverted_flow if over.active else 0
#                     labels[idx].icon = DivIcon(html=f"""
#                         <div style="font-size: 13px; background: white; border: 1px solid black;
#                                     padding: 4px 6px; border-radius: 6px; width: 110px;
#                                     text-align: center; white-space: nowrap;
#                                     box-shadow: 2px 2px 4px rgba(0,0,0,0.2);">
#                             Overflow {over.location_id}<br>{flow} m³/h
#                         </div>
#                     """)
#
#                 total = model.plant.total_flow
#                 labels[-1].icon = DivIcon(html=f"""
#                     <div style="font-size: 13px; background: white; border: 1px solid black;
#                                 padding: 4px 6px; border-radius: 6px; width: 110px;
#                                 text-align: center; white-space: nowrap;
#                                 box-shadow: 2px 2px 4px rgba(0,0,0,0.2);">
#                         Sewage Plant<br>{total} m³/h
#                     </div>
#                 """)
#
#                 # Aktualizacja wykresu
#                 df = model.datacollector.get_model_vars_dataframe()
#                 if not df.empty:
#                     fig.data = []
#                     for column in df.columns:
#                         if "Flow" in column:
#                             fig.add_trace(go.Scatter(
#                                 x=df.index,
#                                 y=df[column],
#                                 mode="lines+markers",
#                                 name=column
#                             ))
#                     fig.add_hline(y=500, line_dash="dash", line_color="red")
#
#             await asyncio.sleep(auto_interval)
#
#     # Obsługa pauzy
#     def toggle_simulation(change):
#         nonlocal running
#         running = not running
#         step_btn.description = "▶️ Wznów" if not running else "⏸️ Pauza"
#
#     step_btn.on_click(toggle_simulation)
#
#     # Pętla async
#     nest_asyncio.apply()
#     asyncio.ensure_future(update_visualization())
#
# run_sewer_visualization(auto_interval=3)

import asyncio
import nest_asyncio
from ipyleaflet import Map, Marker, DivIcon, AwesomeIcon
from ipywidgets import VBox, HBox, Button, Layout
from IPython.display import display
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from model.model import SewerSystemModel


def run_sewer_visualization(auto_interval=3):

    # Model
    model = SewerSystemModel(max_capacity=2000, max_hours=7)

    # Mapa
    m = Map(center=(49.684, 19.211), zoom=15)
    markers, labels = [], []

    # Tworzenie markerów
    def create_marker(agent, label, color):
        location = agent.location
        flow = getattr(agent, 'current_flow', getattr(agent, 'diverted_flow', 0))
        marker = Marker(
            location=location,
            draggable=False,
            icon=AwesomeIcon(name='circle', marker_color=color, icon_color='white')
        )
        label_marker = Marker(
            location=(location[0] + 0.0003, location[1]),
            icon=DivIcon(html=f"""
                <div style="font-size:13px;background:white;border:1px solid black;
                            padding:4px 6px;border-radius:6px;width:130px;text-align:center;
                            box-shadow:2px 2px 4px rgba(0,0,0,0.2);">
                    {label}<br>{flow} m³/h
                </div>
            """),
            draggable=False
        )
        return marker, label_marker

    # Dodanie punktów pomiarowych
    for sensor in model.sensors:
        if "Level4" in sensor.__class__.__name__:
            color = "green"
        elif "Level3" in sensor.__class__.__name__:
            color = "orange"
        else:
            color = "blue"

        m_sensor, l_sensor = create_marker(sensor, f"{sensor.location_id}", color)
        markers.append(m_sensor)
        labels.append(l_sensor)

    # Punkt przelewowy
    over = model.overflow_point
    m_over, l_over = create_marker(over, f"Overflow {over.location_id}", "red")
    markers.append(m_over)
    labels.append(l_over)

    # Oczyszczalnia
    plant = model.plant
    m_plant, l_plant = create_marker(plant, "Sewage Plant", "black")
    markers.append(m_plant)
    labels.append(l_plant)

    # Dodanie may
    for mk, lb in zip(markers, labels):
        m.add(mk)
        m.add(lb)

    # Wykres
    fig = go.FigureWidget(make_subplots(rows=1, cols=1))
    fig.update_layout(
        title="Przepływy w czasie",
        xaxis_title="Godzina",
        yaxis_title="Przepływ (m³/h)",
        template="plotly_white",
        height=550
    )
    fig.add_hline(y=model.max_capacity, line_dash="dash", line_color="red", annotation_text=f"Limit {model.max_capacity} m³/h")

    step_btn = Button(description="⏸️ Pauza", button_style='info')
    m.layout = Layout(width='100%', height='550px')
    left_col = VBox([m, step_btn]); left_col.layout = Layout(width='65%', margin='10px')
    right_col = VBox([fig]);         right_col.layout = Layout(width='35%', margin='10px')
    dashboard = HBox([left_col, right_col]); dashboard.layout = Layout(width='100%', height='auto')
    display(dashboard)

    running = True

    # Aktualizacja wizualizacji
    async def update_visualization():
        nonlocal running
        while model.running:
            if running:
                model.step()

                # Aktualizacja etykiet
                for i, sensor in enumerate(model.sensors):
                    flow = sensor.current_flow
                    color = "green" if sensor.status == "NORMAL" else "red"
                    markers[i].icon = AwesomeIcon(name='circle', marker_color=color, icon_color='white')
                    labels[i].icon = DivIcon(html=f"""
                        <div style="font-size:13px;background:white;border:1px solid black;
                                    padding:4px 6px;border-radius:6px;width:130px;text-align:center;
                                    box-shadow:2px 2px 4px rgba(0,0,0,0.2);">
                            {sensor.location_id}<br>{flow} m³/h
                        </div>
                    """)

                # Przelew
                idx_over = len(model.sensors)
                over = model.overflow_point
                color_over = "red" if over.active else "gray"
                markers[idx_over].icon = AwesomeIcon(name='tint', marker_color=color_over, icon_color='white')
                labels[idx_over].icon = DivIcon(html=f"""
                    <div style="font-size:13px;background:white;border:1px solid black;
                                padding:4px 6px;border-radius:6px;width:130px;text-align:center;
                                box-shadow:2px 2px 4px rgba(0,0,0,0.2);">
                        Overflow {over.location_id}<br>{over.diverted_flow:.1f} m³/h
                    </div>
                """)

                # Oczyszczalnia
                labels[-1].icon = DivIcon(html=f"""
                    <div style="font-size:13px;background:white;border:1px solid black;
                                padding:4px 6px;border-radius:6px;width:130px;text-align:center;
                                box-shadow:2px 2px 4px rgba(0,0,0,0.2);">
                        Sewage Plant<br>Est. Flow: {model.estimated_flow:.1f} m³/h
                    </div>
                """)

                # Wykres
                df = model.datacollector.get_model_vars_dataframe()
                if not df.empty:
                    fig.data = []
                    fig.add_trace(go.Scatter(
                        x=df.index, y=df["Estimated Flow"],
                        mode="lines+markers", name="Estimated Flow", line=dict(color="blue")
                    ))
                    if "Diverted Flow" in df.columns:
                        fig.add_trace(go.Scatter(
                            x=df.index, y=df["Diverted Flow"],
                            mode="lines+markers", name="Overflow Diverted", line=dict(color="red")
                        ))
                    fig.add_hline(y=model.max_capacity, line_dash="dash", line_color="red")

            await asyncio.sleep(auto_interval)

    def toggle_simulation(change):
        nonlocal running
        running = not running
        step_btn.description = "▶️ Wznów" if not running else "⏸️ Pauza"

    step_btn.on_click(toggle_simulation)

    nest_asyncio.apply()
    asyncio.ensure_future(update_visualization())

run_sewer_visualization(auto_interval=3)


from model.model import SewerSystemModel
model = SewerSystemModel()
print(hasattr(model, "overflow_point"))
print(hasattr(model, "overflow_points"))





