from mesa import Model
from .agents import SensorAgent, OverflowPointAgent, SewagePlantAgent
from mesa.datacollection import DataCollector

class SewerSystemModel(Model):
    def __init__(self, max_capacity=500, max_hours=24):
        self.current_hour = 1
        self.max_capacity = max_capacity
        self.max_hours = max_hours
        self.running = True

        # Sensory – ręcznie wpisane dane + pozycje GPS
        self.sensors = [
            SensorAgent(1, self, 1, [100, 120, 150, 300, 520, 580, 430], (49.6801, 19.2045)),
            SensorAgent(2, self, 2, [50, 80, 90, 110, 150, 170, 100], (49.6820, 19.2060))
        ]

        # Przelewy – pozycje
        self.overflow_points = [
            OverflowPointAgent(3, self, "P1", (49.6835, 19.2075)),
            OverflowPointAgent(4, self, "P2", (49.6842, 19.2101))
        ]

        # Oczyszczalnia – pozycja
        self.plant = SewagePlantAgent(5, self, self.max_capacity, (49.6900, 19.2200))

        # self.running = True

        sensor_flows = {
            f"Sensor {i+1} Flow": (lambda idx: lambda m: m.sensors[idx].current_flow)(i)
            for i in range(len(self.sensors))
        }

        self.datacollector = DataCollector(
            model_reporters={
                "Total Flow": lambda agent: agent.plant.total_flow,
                "Overflow Active": lambda m: sum(1 for o in m.overflow_points if o.active),
                **sensor_flows
            }
        )

    def step(self):
        print(f"\n===== Godzina {self.current_hour} =====")

        self.datacollector.collect(self)

        for sensor in self.sensors:
            sensor.step()

        self.plant.step()

        for overflow in self.overflow_points:
            overflow.step()


        self.current_hour += 1
        if self.current_hour > self.max_hours:
            self.running = False
