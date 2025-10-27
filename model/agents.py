from mesa import Agent

# punkt pomiarowy -klasa bazowa
class BaseSensorAgent(Agent):
    def __init__(self, unique_id, model, location_id, flow_data, location, normal_limit=500):
        self.unique_id = unique_id
        self.model = model
        self.location_id = location_id
        self.flow_data = flow_data  # lista z danymi dotyczącymi przepływu (co godzinę)
        self.current_flow = 0 # aktualny przepływ
        self.location = location # (lat, lon)
        self.level = None # umożliwia określenie dokładnego typu agenta (ustalany w modelu)
        self.distance_to_plant = None # dystans do oczyszczalni (obliczany w modelu)
        self.normal_limit = normal_limit #standardowa wartość przepływu dla danego punktu pomiarowego (przekroczenie spowoduje, że punkt wyświetli się na czerwono)
        self.status = "NORMAL"


        # Przepływ z danej godziny
    def get_flow_per_hour(self, hour):
        if 0 < hour <= len(self.flow_data):
            return self.flow_data[hour-1]
        return 0

    def step(self):
        self.current_flow = self.get_flow_per_hour(self.model.current_hour)
        if self.current_flow > 1.5 * self.normal_limit:
            self.status = "ALERT"
        else:
            self.status = "NORMAL"

    def advance(self):
        pass

# potrzebujemy średniej różnicy w warunakch normalnych pomiędzy przepływem w tym punkcie a oczyszcalnią
# do tej różnicy musimy doliczyć ewentualną szacowaną wartość w przypadku opadów o danym natężeniu
class SensorAgentLevel1(BaseSensorAgent):
    def step(self):
        super().step()
        plant_flow = getattr(self.model.plant, "normal_flow", 0)
        avg_difference = abs(plant_flow - self.normal_limit)
        self.model.estimated_flow += avg_difference

# punkty pomiarowe poniżej punktu przelewowego
# potrzebujemy średniej różnicy w warunakch normalnych pomiędzy przepływem w tym punkcie a kolejnym
# do tej różnicy musimy doliczyć ewentualną szacowaną wartość w przypadku opadów o danym natężeniu
class SensorAgentLevel2(BaseSensorAgent):
    def step(self):
        super().step()
        next_sensor = self.model.get_next_sensor(self)
        avg_difference = next_sensor.normal_limit - self.normal_limit
        self.model.estimated_flow += avg_difference

    # punkt pomiarowy bezpośrednio nad punktem przelewowym
# odczytana wartość będzie brana do sumy sprawdzającej czy limit zostanie przekroczony
# do sumy będzie też dodawana wartość śrendiej różnicy przepływu między punktem tym a kolejnym
class SensorAgentLevel3(BaseSensorAgent):
    def step(self):
        super().step()
        self.model.estimated_flow += self.current_flow
        next_sensor = self.model.get_next_sensor(self)
        avg_difference = next_sensor.normal_limit - self.normal_limit
        self.model.estimated_flow += avg_difference


# punkty pomiarowe powyżej punktu przelewowego (tylko wyświetlamy wartość przepływu)
# ewentualnie można dodać wyświetlanie na czerwono jeśli przepływ będzie znacznie wyższy od normalnego
class SensorAgentLevel4(BaseSensorAgent):
    def step(self):
        super().step()


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

    def step(self):
        estimated_flow = self.model.estimated_flow

        if estimated_flow <= self.max_capacity:
            print(f"Limit nie zostanie przekroczony. "
                  f"Przewidywany poziom dopływu: {estimated_flow} m³/h")
            overflow = self.model.overflow_point
            overflow.active = False
            overflow.diverted_flow = 0
        else:
            print(f"!!! Limit zostanie przekroczony! "
                  f"Przewidywany poziom dopływu: {estimated_flow} m³/h "
                  f"(limit: {self.max_capacity})")
            overload = estimated_flow - self.max_capacity
            overflow = self.model.overflow_point
            overflow.active = True
            overflow.diverted_flow = overload

    def advance(self):
        pass