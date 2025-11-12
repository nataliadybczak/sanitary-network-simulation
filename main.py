from model.model import SewerSystemModel

model = SewerSystemModel(max_capacity=1700, max_hours=24)

while model.running:
    model.step()

print("\n=== Symulacja zakończona ===")

results = model.datacollector.get_model_vars_dataframe()
print("\n=== Podsumowanie danych ===")
print(results.head(10))

results.to_csv("data/debug_output.csv")
print("Zapisano debug_output.csv")

