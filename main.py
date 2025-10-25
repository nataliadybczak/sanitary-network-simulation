from model.model import SewerSystemModel

model = SewerSystemModel(max_capacity=2000, max_hours=7)
while model.running:
    model.step()