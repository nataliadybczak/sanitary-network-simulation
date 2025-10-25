from model.model import SewerSystemModel

model = SewerSystemModel(max_capacity=500, max_hours=7)
while model.running:
    model.step()