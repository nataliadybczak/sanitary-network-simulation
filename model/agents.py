from mesa import Agent
import random

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
        # --- lokalna kalibracja ---
        self.k_local = 1.0
        self.alpha_local = 1.0

        self.impervious_factor = impervious_factor # udział powierzchni nieprzepuszczalnych
        self.local_mean_flow = 0.0 # średni przepływ bez uwzględniania dopływów
        self.storage = 0.0
        # self.rain_buffer = [0.0]
        self.rain_buffer = [0.0] * 3

        # graf
        self.downstream_ids = downstream_ids or [] # sąsiedzi
        self.split = {target: 1.0 / len(self.downstream_ids) for target in self.downstream_ids} # do dopracowania - wykorzystywane w sytuacji przelewu
        self.pipe_loss = pipe_loss # można dodać do wzoru - jeśli zakładamy jakiś współczynnik strat między węzłami

        # bufory na godzinę
        self.inflow_from_upstream = 0.0  # suma dopływu z góry w danej godzinie
        self.local_flow = 0.0            # przepływ wygenerowany lokalnie (baza + deszcz)
        self.current_flow = 0.0          # całkowity przepływ tego węzła (local + inflow)
        self.status = "NORMAL"           # status

        self.noise_state = 0.0
        self.gamma = 0.03

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
        # rain_I = self.rain_buffer.pop(0)  # i(t-1) – używane w Q_rain

        rain_eff = (
                0.6 * self.rain_buffer[-1] +
                0.3 * self.rain_buffer[-2] +
                0.1 * self.rain_buffer[-3]
        )
        self.rain_buffer.pop(0)

        # --- 2. Suchy przepływ + infiltracja ---
        # Q_base = Q_dry + gamma * D
        # gamma = 0.015 #ewentualnie możemy jeszcze dokalibrować
        gamma = self.gamma
        self.storage = 0.9 * self.storage + D
        Q_base = self.local_mean_flow + gamma * self.storage

        # --- 3. Natychmiastowy spływ deszczowy (Rational/SWMM hybrid) ---
        # Q_rain = k * i^alpha * f_imp * area
        # Q_rain = self.k_sensor * (rain_I ** self.alpha) * self.impervious_factor * self.area
        # Q_rain = self.k_sensor * (rain_eff ** self.alpha) * self.impervious_factor * self.area
        if rain_eff < 1.0:
            Q_rain = (
                    self.k_sensor * self.k_local *
                    rain_eff * 0.8 *  # liniowy wpływ (można skalibrować)
                    self.impervious_factor * self.area
            )
        else:
            Q_rain = (
                    self.k_sensor * self.k_local *
                    (rain_eff ** (self.alpha * self.alpha_local)) *
                    self.impervious_factor * self.area
            )

        # --- 4. Lokalny przepływ ---
        # self.local_flow = max(0.0, Q_base + Q_rain)
        # noise = random.gauss(0, 0.1 * Q_base)  # 10% odchylenia
        self.noise_state = 0.8 * self.noise_state + random.gauss(0, 0.05 * Q_base)
        noise = self.noise_state
        self.local_flow = max(0.0, Q_base + Q_rain + noise)

        # --- 5. Rzeczywisty przepływ (z uwzględnieniem dopływów)
        self.current_flow = self.local_flow + self.inflow_from_upstream

        # --- 6. Status (możemy wysyłać ostzreżenie, gdy poziom przepływu będzie znacznie wyższy niż przeciętny) ---
        if self.current_flow > 1.5 * self.mean_flow:
            self.status = "ALERT"
        else:
            self.status = "NORMAL"
####################################################################################
        print(
            f"[{self.location_id}] Rain_now={rain_I_now:.2f} mm/h, Rain_eff={rain_eff:.2f} mm/h, D={D:.2f} mm | "
            f"Q_base={Q_base:.2f}, Q_rain={Q_rain:.2f}, "
            f"Q_inflow={self.inflow_from_upstream:.2f} → Q_tot={self.current_flow:.2f}"
        )
###########################################################################################

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
            f_kp26 = max(0.0, min(getattr(self.model, "kp26_split_factor", 0.0), 1.0))

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

    def set_params(self, k=None, alpha=None, gamma=None, k_local=None, alpha_local=None):
        if k is not None:
            self.k_sensor = k
        if alpha is not None:
            self.alpha = alpha
        if gamma is not None:
            self.gamma = gamma
        if k_local is not None:
            self.k_local = k_local
        if alpha_local is not None:
            self.alpha_local = alpha_local


# === PRZELEW (KP26) ===
class OverflowPointAgent(Agent):
    def __init__(self, unique_id, model, location_id, location, capacity=800):
        self.unique_id = unique_id
        self.model = model
        self.location_id = location_id
        self.location = location

        self.capacity = capacity #wstępnie zakładamy nieograniczoną - wlew do rzeki (w praktyce ze względu na środowisko powinien zostać określony ścisły limit)
        self.inflow_from_graph = 0.0  # dopływ w tej godzinie
        self.active = False
        self.diverted_flow = 0.0      # ile realnie popłynęło do rzeki
        self.unhandled_overflow = 0.0 # ile pozostało nieodprowadzone do rzeki

    def reset_buffers(self):
        self.inflow_from_graph = 0.0
        # self.active = False
        self.diverted_flow = 0.0
        self.unhandled_overflow = 0.0

    def receive(self, flow_value: float):
        if flow_value > 0:
            self.inflow_from_graph += flow_value

    def step(self):
        # KP26 ma NIE działać jeśli oczyszczalnia nie zezwoliła:
        if not self.active:
            self.diverted_flow = 0.0
            self.unhandled_overflow = 0.0
            return

        overflow = min(self.inflow_from_graph, self.capacity)
        self.diverted_flow = overflow
        self.unhandled_overflow = max(0.0, self.inflow_from_graph - self.capacity)

        if overflow > 0:
            print(f"Punkt przelewowy {self.location_id} otwarty → do rzeki {overflow:.2f} m³/h")

        print("\n--- PRZELEW KP26 ---")
        print(f"Dopływ do przelewu: {self.inflow_from_graph:.2f} m3/h")
        print(f"Odprowadzono do rzeki: {self.diverted_flow:.2f} m3/h")
        print(f"Niewyładowany nadmiar: {self.unhandled_overflow:.2f} m3/h")
        print("---------------------\n")


# === OCZYSZCZALNIA ===
class SewagePlantAgent(Agent):
    def __init__( self,
        unique_id,
        model,
        max_capacity,
        location,
        normal_flow,
        k_rain_depth=0.0,
        nominal_capacity=1700.0,
        accelerated_capacity=2200.0,
        retention_capacity=1000.0,
        retention_release_rate=100.0,
        max_accelerated_hours=6
    ):
        # self.unique_id = unique_id
        # self.model = model
        # self.location = location
        #
        # self.max_capacity = max_capacity
        # self.normal_flow = normal_flow
        #
        # # dopływ z grafu w tej godzinie
        # self.inflow_from_graph = 0.0
        # # szacowany dopływ
        # self.estimated_flow = 0.0
        self.unique_id = unique_id
        self.model = model
        self.location = location

        self.max_capacity = max_capacity
        self.normal_flow = normal_flow
        self.k_rain_depth = k_rain_depth

        self.nominal_capacity = nominal_capacity
        self.accelerated_capacity = accelerated_capacity

        # retencja
        self.retention_capacity = retention_capacity
        self.retention_release_rate = retention_release_rate
        self.retention_volume = 0.0

        # tryb przyspieszonej pracy oczyszczalni
        self.max_accelerated_hours = max_accelerated_hours
        self.accelerated_hours_streak = 0

        # dane godzinowe
        self.inflow_from_graph = 0.0 # dopływ z grafu w tej godzinie
        self.estimated_flow = 0.0 # szacowany dopływ
        self.retained_this_hour = 0.0 # ścieki przekierowane do retencji w danej godzinie
        self.released_from_retention = 0.0 # ścieki, które zostały w danej godzinie przekierowane z retencji do oczyszcania
        self.flooding_volume = 0.0 # przekroczony poziom (zalanie obszarów przy oczyszczalni)
        self.status = "NORMAL"
        self.warning_code = None

        self.k_rain_depth = k_rain_depth

    def reset_buffers(self):
        self.inflow_from_graph = 0.0
        self.estimated_flow = 0.0
        self.retained_this_hour = 0.0
        self.released_from_retention = 0.0
        self.flooding_volume = 0.0
        self.status = "NORMAL"
        self.warning_code = None

    def receive(self, flow_value: float):
        if flow_value > 0:
            self.inflow_from_graph += flow_value

    def step(self):
        """
        Logika pracy oczyszczalni:

        1. Do oczyszczalni trafia dopływ z sieci + opcjonalny składnik zależny od opadu.
        2. Jeżeli dopływ przekracza przepustowość nominalną, nadmiar jest najpierw
           odkładany do zbiornika retencyjnego (do limitu retention_capacity).
        3. Jeżeli w danej godzinie oczyszczalnia ma wolną moc przerobową w zakresie
           nominalnym, może dodatkowo opróżniać retencję z ograniczeniem
           retention_release_rate.
        4. Jeśli po uwzględnieniu retencji dopływ do oczyszczania nadal przekracza
           przepustowość nominalną, oczyszczalnia przechodzi w tryb przyspieszony
           aż do accelerated_capacity.
        5. Dopiero jeśli:
             - retencja jest już niewystarczająca / zapełniona,
             - oczyszczalnia pracuje z maksymalną wydajnością przyspieszoną,
           to nadmiar może zostać skierowany awaryjnie do KP26.
        6. Wartości logowane w każdej godzinie powinny rozróżniać:
             - dopływ do oczyszczalni,
             - ilość oczyszczoną,
             - ilość odłożoną do retencji,
             - ilość pobraną z retencji,
             - ilość skierowaną awaryjnie do KP26.

        Sterowanie KP26 odbywa się przez:
          - self.model.kp26_split_factor   (jaką część przepływu KP16/KP25 można wysłać na KP26)
          - self.model.overflow_point.active (czy w ogóle wolno kierować na przelew)
        """
        rain_depth = getattr(self.model, "current_rain_depth", 0.0)
        inflow = self.inflow_from_graph + self.k_rain_depth * rain_depth

        self.model.overflow_point.active = False

        self.total_inflow_this_hour = inflow

        # =========================
        # 1. RETENCJA – magazynowanie nadmiaru
        # =========================

        # excess = max(0.0, inflow - self.nominal_capacity)
        excess = max(0.0, inflow - self.accelerated_capacity)
        free_retention = max(0.0, self.retention_capacity - self.retention_volume)

        retained = min(excess, free_retention)
        self.retention_volume += retained
        self.retained_this_hour = retained

        # to co trafia bezpośrednio do oczyszczenia
        to_treat = inflow - retained

        # =========================
        # 2. OPRÓŻNIANIE RETENCJI gdy jest zapas mocy
        # =========================

        # spare_capacity = max(0.0, self.nominal_capacity - to_treat)
        spare_capacity = max(0.0, self.accelerated_capacity - to_treat)

        released = min(
            self.retention_volume,
            self.retention_release_rate,
            spare_capacity
        )

        self.retention_volume -= released
        self.released_from_retention = released

        to_treat += released

        # =========================
        # 3. OCZYSZCZANIE
        # =========================

        if to_treat <= self.nominal_capacity:
            self.estimated_flow = to_treat
            self.treated_this_hour = to_treat
            self.accelerated_hours_streak = 0
            self.status = "NORMAL"
####################################################################
            print("\n--- OCZYSZCZALNIA ---")
            print(f"Dopływ całkowity: {inflow:.2f} m3/h")

            print(f"Retencja aktualna: {self.retention_volume:.2f} / {self.retention_capacity} m3")
            print(f"Do retencji w tej godzinie: {self.retained_this_hour:.2f} m3")
            print(f"Z retencji uwolniono: {self.released_from_retention:.2f} m3")

            print(f"Do oczyszczenia: {to_treat:.2f} m3/h")
            print(f"Oczyszczono: {self.treated_this_hour:.2f} m3/h")

            print(f"Tryb pracy: {self.status}")
            print(f"Godzin pracy w trybie przyspieszonym: {self.accelerated_hours_streak}")

            if self.model.overflow_point.active:
                print("PRZELEW KP26: AKTYWNY")
                print(f"Split KP26: {self.model.kp26_split_factor:.2f}")
            else:
                print("PRZELEW KP26: zamknięty")

            if self.warning_code:
                print(f"OSTRZEŻENIE: {self.warning_code}")

            print("----------------------\n")
#############################################################
            return

        # =========================
        # 4. TRYB PRZYSPIESZONY
        # =========================

        if to_treat <= self.accelerated_capacity:

            self.estimated_flow = to_treat
            self.treated_this_hour = to_treat
            self.accelerated_hours_streak += 1
            self.status = "ACCELERATED"

            if self.accelerated_hours_streak >= self.max_accelerated_hours:
                self.warning_code = "ENV_ACCEL_TOO_LONG"
#####################################################################################################
            print("\n--- OCZYSZCZALNIA ---")
            print(f"Dopływ całkowity: {inflow:.2f} m3/h")

            print(f"Retencja aktualna: {self.retention_volume:.2f} / {self.retention_capacity} m3")
            print(f"Do retencji w tej godzinie: {self.retained_this_hour:.2f} m3")
            print(f"Z retencji uwolniono: {self.released_from_retention:.2f} m3")

            print(f"Do oczyszczenia: {to_treat:.2f} m3/h")
            print(f"Oczyszczono: {self.treated_this_hour:.2f} m3/h")

            print(f"Tryb pracy: {self.status}")
            print(f"Godzin pracy w trybie przyspieszonym: {self.accelerated_hours_streak}")

            if self.model.overflow_point.active:
                print("PRZELEW KP26: AKTYWNY")
                print(f"Split KP26: {self.model.kp26_split_factor:.2f}")
            else:
                print("PRZELEW KP26: zamknięty")

            if self.warning_code:
                print(f"OSTRZEŻENIE: {self.warning_code}")

            print("----------------------\n")
#########################################################################################################
            return

        # =========================
        # 5. NADMIAR → PRZELEW
        # =========================

        self.estimated_flow = self.accelerated_capacity
        self.treated_this_hour = self.accelerated_capacity
        self.accelerated_hours_streak += 1

        excess_after_treatment = to_treat - self.accelerated_capacity

        if excess_after_treatment > 0:
            kp16_agent = self.model.sensors.get("KP16")
            kp25_agent = self.model.sensors.get("KP25")

            kp16_available = kp16_agent.current_flow * kp16_agent.pipe_loss if kp16_agent else 0.0
            kp25_available = kp25_agent.current_flow * kp25_agent.pipe_loss if kp25_agent else 0.0
            available_for_diversion = kp16_available + kp25_available

            self.model.overflow_point.active = True

            if available_for_diversion > 0:
                split = excess_after_treatment / available_for_diversion
                self.model.kp26_split_factor = max(0.0, min(split, 1.0))
            else:
                self.model.kp26_split_factor = 0.0

            self.status = "EMERGENCY_OVERFLOW"
        else:
            self.model.kp26_split_factor = 0.0

        if self.accelerated_hours_streak >= self.max_accelerated_hours:
            self.warning_code = "ENV_ACCEL_TOO_LONG"
########################################################################################################
        print("\n--- OCZYSZCZALNIA ---")
        print(f"Dopływ całkowity: {inflow:.2f} m3/h")

        print(f"Retencja aktualna: {self.retention_volume:.2f} / {self.retention_capacity} m3")
        print(f"Do retencji w tej godzinie: {self.retained_this_hour:.2f} m3")
        print(f"Z retencji uwolniono: {self.released_from_retention:.2f} m3")

        print(f"Do oczyszczenia: {to_treat:.2f} m3/h")
        print(f"Oczyszczono: {self.treated_this_hour:.2f} m3/h")

        print(f"Tryb pracy: {self.status}")
        print(f"Godzin pracy w trybie przyspieszonym: {self.accelerated_hours_streak}")

        if self.model.overflow_point.active:
            print("PRZELEW KP26: AKTYWNY")
            print(f"Split KP26: {self.model.kp26_split_factor:.2f}")
        else:
            print("PRZELEW KP26: zamknięty")

        if self.warning_code:
            print(f"OSTRZEŻENIE: {self.warning_code}")

        print("----------------------\n")
###################################################################################