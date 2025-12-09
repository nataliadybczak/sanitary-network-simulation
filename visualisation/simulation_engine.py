import threading
from typing import Dict, Optional, Tuple
from model.model import SewerSystemModel
import pandas as pd
import time


# ====== Wątek symulacji ======
class SimulationThread(threading.Thread):
    def __init__(self, model: SewerSystemModel, interval: float, shared: Dict, lock: threading.Lock,
                 stop_evt: threading.Event, pause_evt: threading.Event):
        super().__init__(daemon=True)
        self.model = model
        self.interval = interval
        self.shared = shared
        self.lock = lock
        self.stop_evt = stop_evt
        self.pause_evt = pause_evt

    def run(self):
        print("[SIM] start")
        try:
            while not self.stop_evt.is_set() and self.model.running:
                if not self.pause_evt.is_set():
                    self.model.step()

                    # Pobieranie danych bezpośrednio z obiektów (unikamy błędu nazw w DataFrame)
                    est = getattr(self.model.plant, 'estimated_flow', 0.0)
                    div = getattr(self.model.overflow_point, 'diverted_flow', 0.0)

                    # POPRAWKA: iterujemy po .values(), bo self.model.sensors to słownik
                    # Mapowanie ID -> Lokalizacja dla rysowania strzałek
                    loc_map = {s.location_id: s.location for s in self.model.sensors.values()}
                    loc_map["KP26"] = self.model.overflow_point.location
                    loc_map["Oczyszczalnia"] = self.model.plant.location

                    # Budowanie listy połączeń (strzałek)
                    connections = []
                    for src, targets in self.model.graph.items():
                        if src in loc_map:
                            src_loc = loc_map[src]

                            # Pobieramy przepływ źródła
                            src_flow = 0.0
                            # Tu sprawdzamy klucz w słowniku (to jest OK)
                            if src in self.model.sensors:
                                src_flow = self.model.sensors[src].current_flow

                            for tgt in targets:
                                if tgt in loc_map:
                                    connections.append((src_loc, loc_map[tgt], src_flow))

                    snapshot = {
                        # POPRAWKA: tutaj też iterujemy po .values()
                        "sensors": [(s.location_id, s.location[0], s.location[1], getattr(s, 'current_flow', 0.0),
                                     getattr(s, 'status', 'NORMAL')) for s in self.model.sensors.values()],
                        "overflow": (self.model.overflow_point.location_id, self.model.overflow_point.location[0],
                                     self.model.overflow_point.location[1],
                                     getattr(self.model.overflow_point, 'active', False),
                                     getattr(self.model.overflow_point, 'diverted_flow', 0.0)),
                        "plant": (self.model.plant.location[0], self.model.plant.location[1],
                                  getattr(self.model.plant, 'estimated_flow', 0.0)),
                        "point": (pd.Timestamp.now().to_pydatetime(), est, div),
                        # Przekazujemy progi wydajności oczyszczalni do kolorowania
                        "plant_params": {
                            "nominal": getattr(self.model, "nominal_capacity", 1700),
                            "warning": getattr(self.model, "warning_threshold", 2000),
                            "hydraulic": getattr(self.model, "hydraulic_capacity", 2200)
                        },
                        # Dane pogodowe
                        "rain": {
                            "intensity": self.model.current_rain_intensity,
                            "depth": self.model.current_rain_depth
                        },
                        "connections": connections,  # Topologia
                        "max_capacity": self.model.max_capacity,
                        "running": self.model.running,
                        "hour": self.model.current_hour,
                    }
                    with self.lock:
                        self.shared.update(snapshot)
                time.sleep(self.interval)
        except Exception as e:
            print("[SIM] błąd wątku:", e)
            import traceback
            traceback.print_exc()
        finally:
            print("[SIM] stop")