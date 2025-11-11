import pandas as pd


df = pd.read_excel("data_all_values.xlsx")
df.columns = df.columns.str.strip()

col_opady = next((c for c in df.columns if c.startswith("Opady")), None)
if col_opady is None:
    raise ValueError("Nie znaleziono kolumny z opadami!")

if "Czas" in df.columns:
    df["Czas"] = pd.to_datetime(df["Czas"])

df_opady = df[["Czas", col_opady]].dropna()

df_opady.to_csv("opady_godzinowe.csv", index=False, header=["Data", "Opady [mm/h]"], encoding="utf-8-sig")

print("Zapisano plik: opady_godzinowe.csv")
