import threading
from typing import Dict, Optional, Tuple
from model.model import SewerSystemModel
import pandas as pd
import time
import sys


# ====== Wątek symulacji ======
class SimulationThread(threading.Thread):
    def __init__(self, model_factory_fn, interval: float, shared: Dict, lock: threading.Lock,
                 stop_evt: threading.Event, pause_evt: threading.Event):
        super().__init__(daemon=True)
        # UWAGA: Teraz przyjmujemy funkcję fabrykującą (lambda), a nie instancję,
        # żeby móc łatwo stworzyć nowy model przy resecie.
        self.model_factory = model_factory_fn
        self.model = self.model_factory()

        self.default_interval = interval
        self.shared = shared
        self.lock = lock
        self.stop_evt = stop_evt
        self.pause_evt = pause_evt

    def _update_shared_state(self):
        """Pomocnicza funkcja do zrzutu stanu, używana w pętli i po resecie"""
        est = getattr(self.model.plant, 'estimated_flow', 0.0)
        div = getattr(self.model.overflow_point, 'diverted_flow', 0.0)

        active_ids = set()
        loc_map = {}
        for s in self.model.sensors.values():
            loc_map[s.location_id] = s.location
            active_ids.add(s.location_id)

        loc_map["KP26"] = self.model.overflow_point.location
        active_ids.add("KP26");
        active_ids.add(self.model.overflow_point.location_id)
        loc_map["Oczyszczalnia"] = self.model.plant.location
        active_ids.add("Oczyszczalnia")

        extra_points = []
        if hasattr(self.model, "coords") and self.model.coords:
            for pid, coord in self.model.coords.items():
                if pid not in active_ids:
                    lat = coord.get('lat');
                    lon = coord.get('lon')
                    if lat and lon: extra_points.append((pid, lat, lon))

        connections = []
        for src, targets in self.model.graph.items():
            if src in loc_map:
                src_loc = loc_map[src]
                src_flow = 0.0
                if src in self.model.sensors: src_flow = self.model.sensors[src].current_flow
                for tgt in targets:
                    if tgt in loc_map: connections.append((src_loc, loc_map[tgt], src_flow))

        snapshot = {
            "sensors": [(s.location_id, s.location[0], s.location[1], getattr(s, 'current_flow', 0.0),
                         getattr(s, 'status', 'NORMAL')) for s in self.model.sensors.values()],
            "overflow": (self.model.overflow_point.location_id, self.model.overflow_point.location[0],
                         self.model.overflow_point.location[1], getattr(self.model.overflow_point, 'active', False),
                         getattr(self.model.overflow_point, 'diverted_flow', 0.0)),
            "plant": (self.model.plant.location[0], self.model.plant.location[1],
                      getattr(self.model.plant, 'estimated_flow', 0.0)),
            "point": (pd.Timestamp.now().to_pydatetime(), est, div),
            "plant_params": {
                "nominal": getattr(self.model, "nominal_capacity", 1700),
                "warning": getattr(self.model, "warning_threshold", 2000),
                "hydraulic": getattr(self.model, "hydraulic_capacity", 2200)
            },
            "rain": {
                "intensity": self.model.current_rain_intensity,
                "depth": self.model.current_rain_depth
            },
            "connections": connections,
            "extra_points": extra_points,
            "max_capacity": self.model.max_capacity,
            "running": self.model.running,
            "hour": self.model.current_hour,
            "max_hours": self.model.max_hours  # Przesyłamy max_hours do UI
        }
        with self.lock:
            self.shared.update(snapshot)

    def run(self):
        print("[SIM] start")
        # Inicjalny zrzut stanu (żeby UI miało co pokazać od razu)
        self._update_shared_state()

        try:
            while not self.stop_evt.is_set():
                # 1. Obsługa RESETU
                if self.shared.get("reset_cmd", False):
                    print("[SIM] RESETOWANIE MODELU...")
                    self.model = self.model_factory()  # Tworzymy nowy, czysty model
                    self.shared["reset_cmd"] = False  # Kasujemy flagę
                    self.pause_evt.set()  # Po resecie pauzujemy (start buttonem)

                    # Czyścimy historię wykresów w shared (opcjonalnie, ale zalecane)
                    # W tym podejściu UI samo musi wykryć zmianę godziny na mniejszą i wyczyścić deque

                    self._update_shared_state()  # Wysyłamy stan "0"
                    print("[SIM] Model zresetowany.")
                    time.sleep(0.5)
                    continue

                # 2. Krok symulacji (jeśli nie pauza i model działa)
                if not self.pause_evt.is_set() and self.model.running:
                    self.model.step()
                    self._update_shared_state()
                elif not self.model.running and not self.pause_evt.is_set():
                    # Jeśli model skończył działanie (koniec godzin), wymuszamy pauzę
                    self.pause_evt.set()
                    print("[SIM] Koniec symulacji (osiągnięto max_hours).")

                # 3. Dynamiczne opóźnienie (prędkość)
                # Pobieramy interwał z shared (ustawiany suwakiem) lub domyślny
                current_interval = self.shared.get("sim_interval", self.default_interval)
                time.sleep(current_interval)

        except Exception as e:
            print("[SIM] błąd wątku:", e)
            import traceback
            traceback.print_exc()
        finally:
            print("[SIM] stop")