from mesa import Model
from .agents import BaseSensorAgent, OverflowPointAgent, SewagePlantAgent
from mesa.datacollection import DataCollector
import math
import pandas as pd
import os

# Pomocnicze: obliczanie dystansu (chociaż chyba nie będzie potrzebne)
def _calculate_distance(loc1, loc2):
    lat1, lon1 = loc1
    lat2, lon2 = loc2
    return math.sqrt((lat1 - lat2) ** 2 + (lon1 - lon2) ** 2)


# MODEL SYSTEMU KANALIZACYJNEGO
class SewerSystemModel(Model):
    def __init__(self, graph=None, mean_flows=None, max_capacity=1700, max_hours=168, rain_file="data/rain.csv"):

        #graf przepływomierzy
        default_graph = {
            "KP1": ["Oczyszczalnia"],
            "KP2": ["Oczyszczalnia"],
            "KP4": ["Oczyszczalnia"],
            "KP6": ["Oczyszczalnia"],
            "KP7": ["KP16"],
            "KP8": ["Oczyszczalnia"],
            "KP9": ["KP8"],
            "KP10": ["KP8"],
            "KP11": ["Oczyszczalnia"],
            "KP16": ["KP2", "KP26"],
            "KP25": ["KP2", "KP26"],
            "G-T1": ["Oczyszczalnia"],
            "ŁPA-P1": ["KP8"],
            "LBT1": ["Oczyszczalnia"],
            "M1": ["Oczyszczalnia"],
            }
        import os
        import pandas as pd
        # === Wczytanie współrzędnych z pliku CSV ===
        coords_path = os.path.join("data", "wspolrzedne.csv")
        if os.path.exists(coords_path):
            coords_df = pd.read_csv(coords_path)
            coords = coords_df.set_index("ID")[["lat", "lon"]].to_dict(orient="index")
            print(f"Wczytano {len(coords)} współrzędnych z pliku: {coords_path}")
        else:
            print("Brak pliku współrzędnych, używam wartości domyślnych.")
            coords = {}
        self.coords = coords

        imp_path = os.path.join("data", "impervious.csv")
        if os.path.exists(imp_path):
            df_imp = pd.read_csv(imp_path).set_index("id_sensor")
        else:
            df_imp = None

        area_path = os.path.join("data", "areas.csv")
        if os.path.exists(area_path):
            df_area = pd.read_csv(area_path).set_index("id_sensor")
        else:
            df_area = None

        #Wczytujemy średnie przepływy dla każdej godziny dla każdego przepływomierza z pliku srednie_godzinowe.csv
        if mean_flows is None:
            import pandas as pd, os
            file_path = os.path.join("data", "srednie_godzinowe.csv")
            df_h = pd.read_csv(file_path)

            # Normalizacja kolumny Godzina
            if pd.api.types.is_datetime64_any_dtype(df_h.get("Godzina", pd.Series([]))):
                df_h["Godzina"] = pd.to_datetime(df_h["Godzina"]).dt.hour
            else:
                df_h["Godzina"] = pd.to_numeric(df_h["Godzina"], errors="coerce").astype("Int64")

            # całość tabeli średnich godzinowych (używana w każdym kroku)
            self.hourly_means_df = df_h

            # Ustawienie mean_flows na startową godzinę symulacji
            # self.current_hour zaczyna się od 1 (czyli godzina pod względem doby to (1-1)%24 = 0)
            start_hour = (getattr(self, "current_hour", 1) - 1) % 24
            row = df_h.loc[df_h["Godzina"] == start_hour]
            if row.empty:
                # jeśli brakuje wiersza, to 0
                row = df_h.loc[df_h["Godzina"] == 0]
            # słownik {przepływomierz: średni przepływ}
            mean_flows = row.drop(columns=["Godzina"]).iloc[0].to_dict()

            print(f"Wczytano średnie godzinowe z {file_path}. Startowa godzina={start_hour}.")
            print(f"Dostępne liczniki: {len(mean_flows)}")
        else:
            self.hourly_means_df = None

        self.mean_flows = mean_flows

        self.graph = graph or default_graph
        self.max_capacity = max_capacity
        self.max_hours = max_hours
        self.kp26_split_factor = 0.0  # ułamek, jaka część powinna iść na KP26
        self.nominal_capacity = 1700  # pełne oczyszczanie
        self.hydraulic_capacity = 2200  # maks. hydrauliczny odbiór
        self.warning_threshold = 2000  # po tym zaczynamy wykorzystywać przelew KP26

        self.current_hour = 1
        self.running = True

        # Intensywność deszczu
        file_path = os.path.join(rain_file[0:rain_file.rfind("/")],rain_file[rain_file.rfind("/")+1:])
        # file_path = os.path.join("data", "rain.csv") #standardowy plik csv - różne wartości opadów
        # file_path = os.path.join("data/rain_experiments", "realistic.csv") # eksperymenty - nazwa pliku do podmiany
        df_rain = pd.read_csv(file_path)
        self.rain_intensity_data = df_rain["rain_mm_h"].tolist()

        self.current_rain_intensity = 0.0
        self.current_rain_depth = 0.0
        self.rain_memory_lambda = 0.92

        # --- PRZEPŁYWOMIERZE ---
        self.sensors = {}
        for i, (sensor_id, downstreams) in enumerate(self.graph.items()):
            if sensor_id in ("KP26", "Oczyszczalnia"):
                continue

            mean_flow = mean_flows.get(sensor_id, 50.0)
            if sensor_id in self.coords:
                lat = self.coords[sensor_id]["lat"]
                lon = self.coords[sensor_id]["lon"]
            else:
                lat = 49.68 + i * 0.001
                lon = 19.21 + i * 0.001
            self.sensors[sensor_id] = BaseSensorAgent(
                unique_id=i,
                model=self,
                location_id=sensor_id,
                flow_data=None,
                location=(lat, lon),
                area=df_area.loc[sensor_id]["area_km2"] if df_area is not None and sensor_id in df_area.index else 3.0,
                mean_flow=mean_flow,
                k_sensor=0.8,
                alpha=1.2,
                impervious_factor=df_imp.loc[sensor_id]["impervious"] if df_imp is not None and sensor_id in df_imp.index else 0.5,
                downstream_ids=downstreams,
                pipe_loss=0.95
            )

        self.upstreams = {}
        for src, downstreams in self.graph.items():
            for dst in downstreams:
                if dst not in ("KP26", "Oczyszczalnia"):
                    self.upstreams.setdefault(dst, []).append(src)

        # --- PRZELEW ---
        if "KP26" in self.coords:
            overflow_loc = (self.coords["KP26"]["lat"], self.coords["KP26"]["lon"])
        else:
            overflow_loc = (49.68, 19.22)
        self.overflow_point = OverflowPointAgent(999, self, "KP26", overflow_loc)
        # --- OCZYSZCZALNIA ---
        if "Oczyszczalnia" in self.coords:
            plant_loc = (self.coords["Oczyszczalnia"]["lat"], self.coords["Oczyszczalnia"]["lon"])
        else:
            plant_loc = (49.682, 19.213)
        self.plant = SewagePlantAgent(1000, self, max_capacity, plant_loc, normal_flow=1200)

        # --- KOLEJNOŚĆ topologiczna ---
        self.sensor_order = self._sort_sensors_topologically()

        # --- ZBIERANIE DANYCH ---
        def make_sensor_lambda(sensor_id):
            return lambda m: m.sensors[sensor_id].current_flow

        self.datacollector = DataCollector(
            model_reporters={
                "TotalFlow": lambda m: m.plant.estimated_flow,
                "OverflowActive": lambda m: int(m.overflow_point.active),
                **{f"{sid}_Flow": make_sensor_lambda(sid) for sid in self.sensors}
            }
        )

    # ===============================================
    # Pomocnicze metody
    # ===============================================

    def get_sensor_by_id(self, sensor_id):
        return self.sensors.get(sensor_id)

    # Metoda do sortowania topologicznego przepływomierzy (dzięki niej gdy czujnik liczy swój przepływ ma zsumowane dopływy od poprzedników)
    def _sort_sensors_topologically(self):
        """Prosty topologiczny sort grafu (upstream → downstream)."""
        visited = set()
        order = []

        def dfs(node):
            if node in visited:
                return
            visited.add(node)
            for nxt in self.graph.get(node, []):
                if nxt not in ("KP26", "Oczyszczalnia"):
                    dfs(nxt)
            order.append(node)

        for node in self.graph:
            dfs(node)
        return order[::-1]  # od najdalszego do najbliższego oczyszczalni

    def _select_means_for_hour(self, hour_0_23: int) -> dict:
        if getattr(self, "hourly_means_df", None) is None:
            return self.mean_flows
        df_h = self.hourly_means_df
        row = df_h.loc[df_h["Godzina"] == int(hour_0_23)]
        if row.empty:
            # fallback na 0, jeśli brakuje
            row = df_h.loc[df_h["Godzina"] == 0]
        return row.drop(columns=["Godzina"]).iloc[0].to_dict()

    # do aktualizacji godziny i przepływów dla danej godziny
    def refresh_mean_flows_for_current_hour(self):
        hour_0_23 = (self.current_hour - 1) % 24
        self.mean_flows = self._select_means_for_hour(hour_0_23)

        # 1) Aktualizacja mean_flow na podstawie pliku srednie_godinowe.csv
        for sid, agent in self.sensors.items():
            if sid in self.mean_flows:
                agent.mean_flow = float(self.mean_flows[sid])

        # 2) Obliczenie local_mean_flow na podstawie mean_flow dla danej godziny
        for sid, agent in self.sensors.items():
            upstream_ids = self.upstreams.get(sid, [])
            mean_up = sum(
                self.mean_flows[u] for u in upstream_ids
                if u in self.mean_flows
            )
            agent.local_mean_flow = max(agent.mean_flow - mean_up, 0.0)

    # ===============================================
    # Pojedynczy krok symulacji
    # ===============================================
    def step(self):
        print(f"\n===== Godzina {self.current_hour} =====")

        # --- 1. Reset buforów ---
        for sensor in self.sensors.values():
            sensor.reset_buffers()
        self.plant.reset_buffers()
        self.overflow_point.reset_buffers()

        self.refresh_mean_flows_for_current_hour()

        # --- 2. Ustawiamy warunki pogodowe ---
        if self.current_hour <= len(self.rain_intensity_data):
            #pobieramy intensywność opadów w obecnej godzinie
            self.current_rain_intensity = self.rain_intensity_data[self.current_hour - 1]
            ''' Rain depth - podejście Kozłowskiego - suma z ostatnich N godzin '''
            window = 6
            idx = self.current_hour - 1
            start = max(0, idx - window + 1)
            D = sum(self.rain_intensity_data[start: idx + 1])
            self.current_rain_depth = D

            ''' Alternatywa - w ramach porównania - podejście modelu SWMM - rezerwuar nieliniowy '''
            # lam = self.rain_memory_lambda #do kalibracji (w literaturze typowo 0.9-0.98)
            # self.current_rain_depth = (
            #     self.rain_memory_lambda * self.current_rain_depth + self.current_rain_intensity
            # )
        else:
            self.current_rain_intensity = 0.0
            self.current_rain_depth = 0.0

        # --- 3. Obliczenie przepływów w każdym sensorze (upstream → downstream) ---
        for sid in self.sensor_order:
            sensor = self.sensors[sid]
            sensor.step()   # liczy lokalny przepływ
            sensor.route()  # przekazuje dalej (uwzględnia przelew, straty)

        # --- 4. Obliczenie stanu oczyszczalni i przelewu ---
        self.plant.step()
        self.overflow_point.step()
        if self.overflow_point.active:
            diverted = self.overflow_point.diverted_flow
            total_in = self.plant.inflow_from_graph
            remaining = max(0.0, total_in - self.nominal_capacity - diverted)

            print(f"OCZ → podsumowanie:")
            print(f"  dopływ całkowity: {total_in:.2f}")
            print(f"  nominal: {self.nominal_capacity}")
            print(f"  przelew KP26: {diverted:.2f} m3/h")
            print(f"  nadmiar NIEWYŁADOWANY: {remaining:.2f} m3/h")

        # --- 5. Zebranie danych ---
        self.datacollector.collect(self)

        # --- 6. Aktualizacja godziny ---
        self.current_hour += 1
        if self.current_hour > self.max_hours:
            self.running = False
