from mesa import Model
from .agents import OverflowPointAgent, SewagePlantAgent, SensorAgentLevel1, SensorAgentLevel2, SensorAgentLevel3, SensorAgentLevel4
from mesa.datacollection import DataCollector
import math

# Odległość punktów pomiarowych od oczyszczalni
def _calculate_distance(loc1, loc2):
    lat1, lon1 = loc1
    lat2, lon2 = loc2
    return math.sqrt((lat1 - lat2) ** 2 + (lon1 - lon2) ** 2)


class SewerSystemModel(Model):
    def __init__(self, max_capacity=20000, max_hours=24):
        self.max_capacity = max_capacity
        self.max_hours = max_hours
        self.current_hour = 1
        self.running = True

        # Dane dot. intensywności opadów
        #długość min. jak max_hours
        self.rain_intensity_data = [0, 0, 10, 25, 15, 5, 0]  # Przykładowe natężenie opadu [mm/h]
        self.rain_depth_data = [0, 0, 10, 35, 50, 55, 55]  # Przykładowa skumulowana suma opadu [mm]

        self.current_rain_intensity = 0
        self.current_rain_depth = 0

        # === PARAMETRY ZE WZORU ===
        self.c = 1.2  # Przykładowy współczynnik 'c'
        self.tau = 3  # Przykładowe 'τ' (akumulacja z 3 ostatnich godzin)


        self.sensors = [

            SensorAgentLevel4(1, self, "S1",
                              [180, 200, 220, 260, 280, 300, 270],
                              (49.685, 19.210),
                              normal_limit=300),

            SensorAgentLevel3(2, self, "S2",
                              [400, 450, 550, 650, 800, 900, 1550],
                              (49.684, 19.211),
                              normal_limit=900),

            SensorAgentLevel1(3, self, "S3",
                              [700, 800, 950, 1200, 1600, 2000, 2500],
                              (49.683, 19.212),
                              normal_limit=1200),
        ]

        self.overflow_point = OverflowPointAgent(10, self, "O1", (49.6845, 19.2115))

        self.plant = SewagePlantAgent(20, self, max_capacity, (49.682, 19.213), normal_flow=1600)

        for sensor in self.sensors:
            sensor.distance_to_plant = _calculate_distance(sensor.location, self.plant.location)

        # Sortujemy czujniki po odległości (od najdalszego do najbliższego oczyszczalni)
        self.sensors.sort(key=lambda s: s.distance_to_plant, reverse=True)

        sensor_flows = {
            f"Sensor {i + 1} Flow": (lambda idx: lambda m: m.sensors[idx].current_flow)(i)
            for i in range(len(self.sensors))
        }

        self.datacollector = DataCollector(
            model_reporters={
                "Estimated Flow": lambda m: getattr(m.plant, 'estimated_flow', 0),
                "Overflow Active": lambda m: int(m.overflow_point.active),
                **sensor_flows
            }
        )

    def get_next_sensor(self, sensor):
        for i, s in enumerate(self.sensors):
            if s == sensor and i < len(self.sensors) - 1:
                return self.sensors[i + 1]
        return None

    def step(self):
        print(f"\n===== Godzina {self.current_hour} =====")

        # 1. Ustawiane aktualne warunki pogodowe dla tego kroku
        if 0 < self.current_hour <= len(self.rain_intensity_data):
            self.current_rain_intensity = self.rain_intensity_data[self.current_hour - 1]
            self.current_rain_depth = self.rain_depth_data[self.current_hour - 1]
        else:
            self.current_rain_intensity = 0
            self.current_rain_depth = 0  # lub ostatnia znana wartość


        # 2. Aktywacja sensowrów (liczą wg wzoru 1)
        for sensor in self.sensors:
            sensor.step()

        # 3. Aktywuj oczyszczalnię (obliczy 'estimated_flow' wg formuły 2 i podejmie decyzję)
        self.plant.step()

        # 4. Aktywuj punkt przelewowy (zareaguje na decyzję oczyszczalni)
        self.overflow_point.step()

        # 5. Zbierz dane
        self.datacollector.collect(self)

        self.current_hour += 1
        if self.current_hour > self.max_hours:
            self.running = False
