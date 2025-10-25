from mesa import Agent

# punkt pomiarowy
class SensorAgent(Agent):
    def __init__(self, unique_id, model, location_id, flow_data, location):
        self.unique_id = unique_id
        self.model = model
        self.location_id = location_id
        self.flow_data = flow_data  # lista: [flow1, flow2, ...]
        self.current_flow = 0
        self.location = location

    def step(self):
        hour = self.model.current_hour
        if hour <= len(self.flow_data):
            self.current_flow = self.flow_data[hour - 1]
        else:
            self.current_flow = 0

    def advance(self):
        pass


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
        pass

    def advance(self):
        if self.active:
            print(f"Punkt przelewowy {self.unique_id} otwarty → "
                  f"Do rzeki wpłynęło {self.diverted_flow} m³/h")


# oczyszczalnia
class SewagePlantAgent(Agent):
    def __init__(self, unique_id, model, max_capacity, location):
        # ZAMIANA
        self.unique_id = unique_id
        self.model = model
        self.max_capacity = max_capacity
        self.total_flow = 0  # suma z wszystkich czujników
        self.location = location

    def step(self):
        self.total_flow = sum(sensor.current_flow for sensor in self.model.sensors)

        if self.total_flow <= self.max_capacity:
            print(f"Limit nie zostanie przekroczony. "
                  f"Poziom dopływu: {self.total_flow} m³/h")
            for over in self.model.overflow_points:
                over.active = False
                over.diverted_flow = 0
        else:
            print(f"Przekroczono limit! Przepływ: {self.total_flow} m³/h "
                  f"(limit: {self.max_capacity})")
            overload = self.total_flow - self.max_capacity
            per_overflow = overload // len(self.model.overflow_points)
            for over in self.model.overflow_points:
                over.active = True
                over.diverted_flow = per_overflow

    def advance(self):
        pass
