import pandas as pd

df = pd.read_excel("data_all_values.xlsx")
df.columns = df.columns.str.strip()

# Kolumny przepływomierzy
sensor_cols = [c for c in df.columns if c.startswith("Wartość pomiaru ") and 'przelew' not in c.lower()]

# Średnia dla każdej kolumny
srednie = df[sensor_cols].mean()

srednie.index = srednie.index.str.replace("Wartość pomiaru ", "", regex=False)

# Zapis do pliku (index - nazwa sensora)
srednie.to_csv("srednie_przeplywy.csv", header=["Średni przepływ [m³/h]"], encoding="utf-8-sig")

print("Zapisano plik: srednie_przeplywy.csv")
