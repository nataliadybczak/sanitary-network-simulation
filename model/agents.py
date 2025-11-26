from mesa import Agent

# === PUNKT POMIAROWY (węzeł grafu) ===
class BaseSensorAgent(Agent):
    def __init__(
        self, unique_id, model, location_id, flow_data, location, area,
        mean_flow, k_sensor=0.5, alpha=1.0, impervious_factor=0.5,
        downstream_ids=None,      # lista sąsiadów w dół rzeki
        split=None,               # dict: {target_id: udział [0..1]}  sum=1
        pipe_loss=1.0             # tłumienie na wyjściu (np. 0.95)
    ):
        self.unique_id = unique_id #unikalny numer agenta w modelu mesa
        self.model = model
        self.location_id = location_id # nazwa przepływomierza (np. KP1)
        self.area = area or 3.0

        # dane i stan
        self.base_flow_data = flow_data or [] #ewentualnie do testowania na danych rzeczywistych
        self.location = location  # (lat, lon) - współrzędne GPS

        # progi / parametry hydrologiczne
        self.mean_flow = mean_flow #średni przepływ bazowy (tzw. bazowy przepływ suchy)
        self.k_sensor = k_sensor #współczynnik wpływu deszczu
        self.alpha = alpha # wykładnik nieliniowości
        self.impervious_factor = impervious_factor # udział powierzchni nieprzepuszczalnych
        self.local_mean_flow = 0.0 # średni przepływ bez uwzględniania dopływów
        self.storage = 0.0
        self.rain_buffer = [0.0]

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
            Hydrologia lokalna:
               Q_total = Q_base(mean_flow, D) + Q_rain(i) + inflow_from_upstream
        """
        # --- 1. Pobranie danych o opadach ---
        # rain_I = self.model.current_rain_intensity # intensywność i(t)
        # D = self.model.current_rain_depth # skumulowana głębokość opadu
        rain_I_now = self.model.current_rain_intensity  # i(t)
        D = self.model.current_rain_depth  # D(t) – zostawiamy bez laga

        # bufor 1-godzinny dla spływu powierzchniowego
        self.rain_buffer.append(rain_I_now)
        rain_I = self.rain_buffer.pop(0)  # i(t-1) – używane w Q_rain

        # --- 2. Suchy przepływ + infiltracja ---
        # Q_base = Q_dry + gamma * D
        gamma = 0.015 #ewentualnie możemy jeszcze dokalibrować
        self.storage = 0.9 * self.storage + D
        Q_base = self.local_mean_flow + gamma * self.storage

        # --- 3. Natychmiastowy spływ deszczowy (Rational/SWMM hybrid) ---
        # Q_rain = k * i^alpha * f_imp * area
        Q_rain = self.k_sensor * (rain_I ** self.alpha) * self.impervious_factor * self.area

        # --- 4. Lokalny przepływ ---
        self.local_flow = max(0.0, Q_base + Q_rain)

        # --- 5. Rzeczywisty przepływ (z uwzględnieniem dopływów)
        self.current_flow = self.local_flow + self.inflow_from_upstream

        # --- 6. Status (możemy wysyłać ostzreżenie, gdy poziom przepływu będzie znacznie wyższy niż przeciętny) ---
        if self.current_flow > 1.5 * self.mean_flow:
            self.status = "ALERT"
        else:
            self.status = "NORMAL"

        print(
            f"[{self.location_id}] Rain_now={rain_I_now:.1f} mm/h, Rain_eff={rain_I:.1f} mm/h, D={D:.1f} mm | "
            f"Q_base={Q_base:.1f}, Q_rain={Q_rain:.1f}, "
            f"Q_inflow={self.inflow_from_upstream:.1f} → Q_tot={self.current_flow:.1f}"
        )

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
            # korzystamy z info z poprzedniej godziny:
            f_kp26 = getattr(self.model, "kp26_split_factor", 0.0)

            if not self.model.overflow_point.active or f_kp26 <= 0.0:
                # brak przeciążenia w poprzedniej godzinie → wszystko do KP2
                split = {"KP2": 1.0, "KP26": 0.0}
            else:
                # część przepływu kierujemy na KP26, resztę do KP2
                split = {"KP2": 1.0 - f_kp26, "KP26": f_kp26}
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

        self.capacity = capacity #wstępnie zakładamy nieograniczoną - wlew do rzeki (w praktyce ze względu na środowisko powinien zostać określony ścisły limit)
        self.inflow_from_graph = 0.0  # dopływ w tej godzinie
        self.active = False
        self.diverted_flow = 0.0      # ile realnie popłynęło do rzeki

    def reset_buffers(self):
        self.inflow_from_graph = 0.0
        # self.active = False
        self.diverted_flow = 0.0

    def receive(self, flow_value: float):
        if flow_value > 0:
            self.inflow_from_graph += flow_value

    def step(self):
        # KP26 ma NIE działać jeśli oczyszczalnia nie zezwoliła:
        if not self.active:
            self.diverted_flow = 0.0
            return

        overflow = min(self.inflow_from_graph, self.capacity)
        self.diverted_flow = overflow

        if overflow > 0:
            print(f"Punkt przelewowy {self.location_id} otwarty → do rzeki {overflow:.2f} m³/h")


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
        """
        Logika oparta na 4 progach:
          - nominal_capacity         – normalna praca
          - warning_threshold        – przeciążenie, ale bez przelewu
          - hydraulic_capacity       – maksymalny ciągły odbiór
          - hydraulic_capacity+1000  – chwilowe przeciążenie możliwe do zmagazynowania
          - > hydraulic_capacity+1000 – awaria układu

        Sterowanie KP26 odbywa się przez:
          - self.model.kp26_split_factor   (jaką część przepływu KP16/KP25 można wysłać na KP26)
          - self.model.overflow_point.active (czy w ogóle wolno kierować na przelew)
        """
        rain_depth = getattr(self.model, "current_rain_depth", 0.0)
        total_in = self.inflow_from_graph + self.k_rain_depth * rain_depth

        # Progi z modelu
        nominal = getattr(self.model, "nominal_capacity", self.max_capacity)
        warning = getattr(self.model, "warning_threshold", nominal)
        hydraulic = getattr(self.model, "hydraulic_capacity", warning)
        retention_limit = hydraulic + 1000

        # Domyślnie na początku każdej godziny brak odciążania na KP26
        self.model.kp26_split_factor = 0.0
        self.model.overflow_point.active = False

        # 1) NORMAL – wszystko poniżej nominalnej przepustowości
        if total_in <= nominal:
            self.estimated_flow = total_in
            print(f"OCZ: OK ({total_in:.1f} m3/h)")
            return

        # 2) WARNING – przeciążenie, ale jeszcze bez przelewu (tylko informacja)
        if total_in <= warning:
            self.estimated_flow = total_in
            overload = total_in - nominal       # ile ponad „komfortową” pracę (tutaj oczyszcalnia jest zmuszona do pracy w trybie przyspieszonym)
            print(
                f"OCZ: PRZECIĄŻENIE (bez przelewu): "
                f"in={total_in:.1f}, overload={overload:.1f}"
            )
            return

        # 3) CRITICAL – zaczynamy otwierać KP26 stopniowo
        if total_in <= hydraulic:
            self.estimated_flow = total_in
            overload = total_in - nominal

            if hydraulic > warning:
                frac = (total_in - warning) / (hydraulic - warning)
            else:
                frac = 1.0
            frac = max(0.0, min(frac, 1.0))

            self.model.kp26_split_factor = frac
            self.model.overflow_point.active = True

            print(
                f"OCZ: KRYTYCZNE ({total_in:.1f} m3/h) – otwieranie KP26, "
                f"split={frac:.2f}, overload={overload:.1f}"
            )
            return

        # 4) FAILURE_SOFT – powyżej hydraulicznego, ale w granicach retencji
        if total_in <= retention_limit:
            self.estimated_flow = hydraulic
            overload = total_in - nominal

            self.model.kp26_split_factor = 1.0
            self.model.overflow_point.active = True

            print(
                f"OCZ: PRZECIĄŻENIE CHWILOWE ({total_in:.1f} m3/h) – "
                f"odbiór max={hydraulic}, reszta do retencji"
            )
            return

        # 5) FAILURE_HARD – powyżej retencji – awaria
        self.estimated_flow = hydraulic
        overload = total_in - nominal

        self.model.kp26_split_factor = 1.0
        self.model.overflow_point.active = True

        print(
            f"OCZ: AWARIA OCZYSZCZALNI! in={total_in:.1f} m3/h > {retention_limit} "
            f"→ pełne otwarcie KP26, brak możliwości oczyszcaenia ani zmagazynowania całości ścieków"
        )
