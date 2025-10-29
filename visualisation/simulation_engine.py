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
                    self.model.step()  # wszystko co wypisuje model, pojawi się w terminalu

                    # Zrzut stanu do współdzielonych danych (wyłącznie odczyty wykorzystywane w UI)
                    df = self.model.datacollector.get_model_vars_dataframe()
                    est = float(df["Estimated Flow"].iloc[-1]) if not df.empty else 0.0
                    div = float(df["Diverted Flow"].iloc[-1]) if (not df.empty and "Diverted Flow" in df.columns) else 0.0

                    snapshot = {
                        "sensors": [(s.location_id, s.location[0], s.location[1], getattr(s, 'current_flow', 0.0), getattr(s, 'status', 'NORMAL')) for s in self.model.sensors],
                        "overflow": (self.model.overflow_point.location_id, self.model.overflow_point.location[0], self.model.overflow_point.location[1], getattr(self.model.overflow_point, 'active', False), getattr(self.model.overflow_point, 'diverted_flow', 0.0)),
                        "plant": (self.model.plant.location[0], self.model.plant.location[1], getattr(self.model.plant, 'estimated_flow', 0.0)),
                        "point": (pd.Timestamp.now().to_pydatetime(), est, div),
                        "max_capacity": self.model.max_capacity,
                        "running": self.model.running,
                        "hour": self.model.current_hour,
                    }
                    with self.lock:
                        self.shared.update(snapshot)
                time.sleep(self.interval)
        except Exception as e:
            print("[SIM] błąd wątku:", e)
        finally:
            print("[SIM] stop")
