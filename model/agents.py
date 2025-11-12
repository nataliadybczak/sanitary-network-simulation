from mesa import Agent

# === PUNKT POMIAROWY (węzeł grafu) ===
class BaseSensorAgent(Agent):
    def __init__(
        self, unique_id, model, location_id, flow_data, location,
        mean_flow, k_sensor=0.5, alpha=1.0, impervious_factor=0.5,
        downstream_ids=None,      # lista sąsiadów w dół rzeki
        split=None,               # dict: {target_id: udział [0..1]}  sum=1
        pipe_loss=1.0             # tłumienie na wyjściu (np. 0.95)
    ):
        self.unique_id = unique_id #unikalny numer agenta w modelu mesa
        self.model = model
        self.location_id = location_id # nazwa przepływomierza (np. KP1)

        # dane i stan
        self.base_flow_data = flow_data or [] #ewentualnie do testowania na danych rzeczywistych
        self.location = location  # (lat, lon) - współrzędne GPS

        # progi / parametry hydrologiczne
        self.mean_flow = mean_flow #średni przepływ bazowy (tzw. bazowy przepływ suchy)
        self.k_sensor = k_sensor #współczynnik wpływu deszczu
        self.alpha = alpha # wykładnik nieliniowości
        self.impervious_factor = impervious_factor # udział powierzchni nieprzepuszczalnych

        # graf
        self.downstream_ids = downstream_ids or [] # sąsiedzi
        self.split = {target: 1.0 / len(self.downstream_ids) for target in self.downstream_ids} # do dopracowania - wykorzystywane w sytuacji przelewu
        self.pipe_loss = pipe_loss # można dodać do wzoru - jeśli zakładamy jakiś współczynnik strat między węzłami

        # bufory na godzinę
        self.inflow_from_upstream = 0.0  # suma dopływu z góry w danej godzinie
        self.local_flow = 0.0            # przepływ wygenerowany lokalnie (baza + deszcz)
        self.current_flow = 0.0          # całkowity przepływ tego węzła (local + inflow)
        self.status = "NORMAL"           # status

    # --- pomocnicze / wejściowe ---
    def reset_buffers(self):
        self.inflow_from_upstream = 0.0
        self.local_flow = 0.0
        self.current_flow = 0.0
        self.status = "NORMAL"

    def receive(self, flow_value: float):
        """Wywołuje model/węzeł upstream: dopływ z innych węzłów."""
        if flow_value > 0:
            self.inflow_from_upstream += flow_value

    def get_base_flow_per_hour(self, hour):
        if 0 < hour <= len(self.base_flow_data):
            return self.base_flow_data[hour-1]
        return 0.0

    # --- hydrologia lokalna ---
    def step(self):
        """
        1) wylicz lokalny przepływ wg wzoru:
           Flow_local = BaseFlow(t) - mean(BaseFlow of inflows) + k * RainIntensity(t)^alpha * ImperviousFactor
        2) dodaj dopływ z upstream: current_flow = local + inflow_from_upstream
        3) oceń status (alert gdy >> normal)
        """
        rain_I = self.model.current_rain_intensity
        rain_component = self.k_sensor * (rain_I ** self.alpha) * self.impervious_factor

        # --- dopływy do tego węzła (korzystamy z mapy przygotowanej w modelu) ---
        upstream_ids = self.model.upstreams.get(self.location_id, [])
        upstream_sensors = [self.model.sensors[u] for u in upstream_ids if u in self.model.sensors]

        if upstream_sensors:
            sum_mean_inflows = sum(s.mean_flow for s in upstream_sensors)
            sum_actual_inflows = sum(s.current_flow for s in upstream_sensors)
            sum_delta = sum_actual_inflows - sum_mean_inflows

            self.local_flow = max(0.0, self.mean_flow + sum_delta + rain_component)
        else:
            self.local_flow = self.mean_flow + rain_component

        self.current_flow = self.local_flow

        if self.current_flow > 1.5 * self.mean_flow:
            self.status = "ALERT"
        else:
            self.status = "NORMAL"

        if upstream_sensors:
            print(f"[{self.location_id}] Rain={rain_I:.1f} | Σmean_in={sum_mean_inflows:.1f} | "
                  f"Σactual_in={sum_actual_inflows:.1f} | Δ={sum_actual_inflows - sum_mean_inflows:.1f} | "
                  f"Rain={rain_I:.1f} mm/h (+{rain_component:.2f}) | "
                  f"Local={self.mean_flow:.1f} | Total={self.current_flow:.1f}")
        else:
            print(f"[{self.location_id}] Rain={rain_I:.1f} | no inflows | "
                  f"Rain={rain_I:.1f} mm/h (+{rain_component:.2f}) | "
                  f"Local={self.mean_flow:.1f} | Total={self.current_flow:.1f}")

    # --- routing po grafie ---
    def route(self):
        """
        Wyślij strumień do następców wg 'split' i strat 'pipe_loss'.
        Specjalne węzły:
          - 'Oczyszczalnia' → zwiększ plant.inflow_from_graph
          - 'KP26' (przelew) → zwiększ overflow.inflow_from_graph
        """
        if not self.downstream_ids:
            return

        # straty na wyjściu (np. nieszczelności)
        available = max(0.0, self.current_flow * self.pipe_loss)

        # Specjalna logika TYLKO dla KP16 i KP25 (bo tylko one mogą iść do KP26):
        if self.location_id in ("KP16", "KP25") and "KP26" in self.downstream_ids and "KP2" in self.downstream_ids:
            if not self.model.overflow_point.active:
                # brak przeciążenia → wszystko do KP2
                split = {"KP2": 1.0, "KP26": 0.0}
            else:
                # przeciążenie (wstępnie pół na pół, w wersji finalnej będziemy wyliczać odpowiednią ilość)
                split = {"KP2": 0.5, "KP26": 0.5}
        else:
            # reszta węzłów: jeżeli mają jednego następcę, to wszystko do niego
            if len(self.downstream_ids) == 1:
                split = {self.downstream_ids[0]: 1.0}
            else:
                share = 1.0 / len(self.downstream_ids)
                split = {d: share for d in self.downstream_ids}

        for target_id, frac in split.items():
            portion = max(0.0, available * float(frac))
            if portion <= 0:
                continue
            if target_id == "Oczyszczalnia":
                self.model.plant.receive(portion)
            elif target_id == "KP26":
                self.model.overflow_point.receive(portion)
            else:
                tgt = self.model.get_sensor_by_id(target_id)
                if tgt is not None:
                    tgt.receive(portion)

    def advance(self):
        pass

# === PRZELEW (KP26) ===
class OverflowPointAgent(Agent):
    def __init__(self, unique_id, model, location_id, location, capacity=float("inf")):
        self.unique_id = unique_id
        self.model = model
        self.location_id = location_id
        self.location = location

        self.capacity = capacity #wstępnie zakłądamy nieograniczoną - wlew do rzeki (w praktyce ze względu na środowisko powinien zostać określony ścisły limit)
        self.inflow_from_graph = 0.0  # dopływ w tej godzinie
        self.active = False
        self.diverted_flow = 0.0      # ile realnie popłynęło do rzeki

    def reset_buffers(self):
        self.inflow_from_graph = 0.0
        self.active = False
        self.diverted_flow = 0.0

    def receive(self, flow_value: float):
        if flow_value > 0:
            self.inflow_from_graph += flow_value

    def step(self):
        # tu ewentualnie logika ograniczeń przelewu, na razie wszystko co dopływa = odprowadzone
        overflow = min(self.inflow_from_graph, self.capacity)
        self.diverted_flow = overflow
        self.active = self.diverted_flow > 0.0
        if self.active:
            print(f"Punkt przelewowy {self.location_id} otwarty → do rzeki {self.diverted_flow:.2f} m³/h")


# === OCZYSZCZALNIA ===
class SewagePlantAgent(Agent):
    def __init__(self, unique_id, model, max_capacity, location, normal_flow, k_rain_depth=0.0):
        self.unique_id = unique_id
        self.model = model
        self.location = location

        self.max_capacity = max_capacity
        self.normal_flow = normal_flow

        # dopływ z grafu w tej godzinie
        self.inflow_from_graph = 0.0
        # szacowany dopływ
        self.estimated_flow = 0.0

        # składnik deszczowy na końcu - opcjonalnie
        self.k_rain_depth = k_rain_depth

    def reset_buffers(self):
        self.inflow_from_graph = 0.0
        self.estimated_flow = 0.0

    def receive(self, flow_value: float):
        if flow_value > 0:
            self.inflow_from_graph += flow_value

    def step(self):
        # Dopływ do oczyszczalni pochodzi z grafu (sumowany przez sensory .route())
        rain_depth = getattr(self.model, "current_rain_depth", 0.0)
        self.estimated_flow = self.inflow_from_graph + self.k_rain_depth * rain_depth

        if self.estimated_flow <= self.max_capacity:
            print(f"OCZ: OK. Dopływ={self.estimated_flow:.2f} m³/h (limit {self.max_capacity})")
            self.model.overflow_point.active = False
        else:
            overload = self.estimated_flow - self.max_capacity
            print(f"OCZ: PRZEKROCZENIE LIMITU! Dopływ={self.estimated_flow:.2f} m³/h (>{self.max_capacity}) → nadmiar {overload:.2f} m³/h")