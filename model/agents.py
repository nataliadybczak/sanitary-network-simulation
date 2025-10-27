from mesa import Agent

# punkt pomiarowy -klasa bazowa
class BaseSensorAgent(Agent):
    def __init__(self, unique_id, model, location_id, flow_data, location, normal_limit=500, k_sensor=0.5, alpha=1.0, impervious_factor=0.5):
        self.unique_id = unique_id
        self.model = model
        self.location_id = location_id
        self.base_flow_data = flow_data  # lista z danymi dotyczącymi przepływu (co godzinę)
        self.current_flow = 0 # aktualny przepływ
        self.location = location # (lat, lon)
        self.level = None # umożliwia określenie dokładnego typu agenta (ustalany w modelu)
        self.distance_to_plant = None # dystans do oczyszczalni (obliczany w modelu)
        self.normal_limit = normal_limit #standardowa wartość przepływu dla danego punktu pomiarowego (przekroczenie spowoduje, że punkt wyświetli się na czerwono)
        self.status = "NORMAL"

        # === NOWE PARAMETRY WZORU ===
        self.k_sensor = k_sensor
        self.aplha = alpha
        self.impervious_factor = impervious_factor


        # Przepływ z danej godziny
    def get_base_flow_per_hour(self, hour):
        if 0 < hour <= len(self.base_flow_data):
            return self.base_flow_data[hour-1]
        return 0

    def step(self):
        # === IMPLEMENTACJA FORMUŁY 1 ===
        # Flow_sensor(t) = BaseFlow_sensor(t) + k_sensor * (RainIntensity(t))^α * ImperviousFactor
        base_flow = self.get_base_flow_per_hour(self.model.current_hour)
        rain_intensity = self.model.current_rain_intensity

        rain_component = self.k_sensor * (rain_intensity ** self.aplha) * self.impervious_factor

        self.current_flow = base_flow + rain_component
        if self.current_flow > 1.5 * self.normal_limit:
            self.status = "ALERT"
        else:
            self.status = "NORMAL"

    def advance(self):
        pass

# # potrzebujemy średniej różnicy w warunakch normalnych pomiędzy przepływem w tym punkcie a oczyszcalnią
# # do tej różnicy musimy doliczyć ewentualną szacowaną wartość w przypadku opadów o danym natężeniu
# class SensorAgentLevel1(BaseSensorAgent):
#     def step(self):
#         super().step()
#         plant_flow = getattr(self.model.plant, "normal_flow", 0)
#         avg_difference = abs(plant_flow - self.normal_limit)
#         self.model.estimated_flow += avg_difference
#
# # punkty pomiarowe poniżej punktu przelewowego
# # potrzebujemy średniej różnicy w warunakch normalnych pomiędzy przepływem w tym punkcie a kolejnym
# # do tej różnicy musimy doliczyć ewentualną szacowaną wartość w przypadku opadów o danym natężeniu
# class SensorAgentLevel2(BaseSensorAgent):
#     def step(self):
#         super().step()
#         next_sensor = self.model.get_next_sensor(self)
#         avg_difference = next_sensor.normal_limit - self.normal_limit
#         self.model.estimated_flow += avg_difference
#
#     # punkt pomiarowy bezpośrednio nad punktem przelewowym
# # odczytana wartość będzie brana do sumy sprawdzającej czy limit zostanie przekroczony
# # do sumy będzie też dodawana wartość śrendiej różnicy przepływu między punktem tym a kolejnym
# class SensorAgentLevel3(BaseSensorAgent):
#     def step(self):
#         super().step()
#         self.model.estimated_flow += self.current_flow
#         next_sensor = self.model.get_next_sensor(self)
#         avg_difference = next_sensor.normal_limit - self.normal_limit
#         self.model.estimated_flow += avg_difference
#
#
# # punkty pomiarowe powyżej punktu przelewowego (tylko wyświetlamy wartość przepływu)
# # ewentualnie można dodać wyświetlanie na czerwono jeśli przepływ będzie znacznie wyższy od normalnego
# class SensorAgentLevel4(BaseSensorAgent):
#     def step(self):
#         super().step()

class SensorAgentLevel1(BaseSensorAgent):
    def step(self):
        super().step() # Tylko oblicza swój 'current_flow'

class SensorAgentLevel2(BaseSensorAgent):
    def step(self):
        super().step() # Tylko oblicza swój 'current_flow'

class SensorAgentLevel3(BaseSensorAgent):
    def step(self):
        super().step() # Tylko oblicza swój 'current_flow'

class SensorAgentLevel4(BaseSensorAgent):
    def step(self):
        super().step() # Tylko oblicza swój 'current_flow'

# punkt przelewowy
class OverflowPointAgent(Agent):
    def __init__(self, unique_id, model, location_id, location):
        self.unique_id = unique_id
        self.model = model
        self.location_id = location_id
        self.active = False
        self.diverted_flow = 0
        self.location = location

    def step(self):
        if self.active:
            print(f"Punkt przelewowy {self.unique_id} otwarty → "
                  f"Do rzeki wpłynie {self.diverted_flow} m³/h")


# oczyszczalnia
class SewagePlantAgent(Agent):
    def __init__(self, unique_id, model, max_capacity, location, normal_flow):
        self.unique_id = unique_id
        self.model = model
        self.max_capacity = max_capacity
        self.total_flow = 0  # przepływ w danym momencie (z danych)
        self.location = location
        self.normal_flow = normal_flow
        self.estimated_flow = 0

    def step(self):
        # === IMPLEMENTACJA WZORU 2 ===
        # EstimatedFlow_plant(t) = Σ Flow_sensor(t) [relevant] + c * Σ RainDepth(t-j) [j=0 do τ]

        # --- Część 1: Σ Flow_sensor(t) [sensors i relevant] ---
        # Musimy zdefiniować, które sensory są "relevant".
        # Na podstawie Twojego starego kodu, Level 4 NIE był wliczany do estymacji.

        sum_relevant_sensors = 0

        for sensor in self.model.sensors:
            # Zakładamy, że "relevant" to wszystkie OPRÓCZ Level4
            if not isinstance(sensor, SensorAgentLevel4):
                sum_relevant_sensors += sensor.current_flow

        # --- Część 2: c * Σ RainDepth(t-j) [j=0 do τ] ---

        c = self.model.c
        tau = self.model.tau
        current_t_index = self.model.current_hour - 1

        # Pobieramy historię opadów od 't' do 't-τ'
        # np. jeśli t=5 (index 4), tau=3, potrzebujemy indeksów 4, 3, 2, 1 (czyli t, t-1, t-2, t-3)
        start_idx = max(0, current_t_index - tau)
        end_idx = current_t_index + 1

        rain_history = self.model.rain_depth_data[start_idx:end_idx]
        rain_accumulation = sum(rain_history)

        self.estimated_flow = sum_relevant_sensors + c * rain_accumulation

        if self.estimated_flow <= self.max_capacity:
            print(f"Limit nie zostanie przekroczony. "
                  f"Przewidywany poziom dopływu: {self.estimated_flow} m³/h")
            overflow = self.model.overflow_point
            overflow.active = False
            overflow.diverted_flow = 0
        else:
            print(f"!!! Limit zostanie przekroczony! "
                  f"Przewidywany poziom dopływu: {self.estimated_flow} m³/h "
                  f"(limit: {self.max_capacity})")
            overload = self.estimated_flow - self.max_capacity
            overflow = self.model.overflow_point
            overflow.active = True
            overflow.diverted_flow = overload

    def advance(self):
        pass