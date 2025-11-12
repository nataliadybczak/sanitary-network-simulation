import pandas as pd

df = pd.read_excel("../data_final.xlsx")
df.columns = df.columns.str.strip()

df['Czas'] = pd.to_datetime(df['Czas'], errors='coerce')
df = df.dropna(subset=['Czas'])

sensor_cols = [c for c in df.columns if c.startswith("Wartość pomiaru ") and 'przelew' not in c.lower()]

df['Godzina'] = df['Czas'].dt.hour

hourly_means = df.groupby('Godzina')[sensor_cols].mean()

hourly_means.columns = hourly_means.columns.str.replace("Wartość pomiaru ", "", regex=False)

hourly_means.to_csv("srednie_godzinowe.csv", encoding="utf-8-sig")

print("Zapisano plik: srednie_godzinowe.csv")
print(hourly_means.head())

# import pandas as pd
#
# df = pd.read_excel("../data_all_values.xlsx")
# df.columns = df.columns.str.strip()
#
# # 🔹 tylko jeśli kolumna jest liczbowa (np. 45666.04), konwertuj z origin
# if pd.api.types.is_numeric_dtype(df["Czas"]):
#     df["Czas"] = pd.to_datetime(df["Czas"], unit="D", origin="1899-12-30")
# else:
#     df["Czas"] = pd.to_datetime(df["Czas"], errors="coerce")
#
# df = df.dropna(subset=["Czas"])
#
#
# # 3️⃣ Kolumny czujników
# sensor_cols = [c for c in df.columns if c.startswith("Wartość pomiaru ") and 'przelew' not in c.lower()]
#
# # 4️⃣ Wyodrębnienie godziny
# df['Godzina'] = df['Czas'].dt.hour
#
# # 5️⃣ Grupowanie po godzinie
# hourly_means = df.groupby('Godzina')[sensor_cols].mean()
#
# # 6️⃣ Uproszczenie nazw kolumn
# hourly_means.columns = hourly_means.columns.str.replace("Wartość pomiaru ", "", regex=False)
#
# # 7️⃣ Zapis
# hourly_means.to_csv("srednie_godzinowe_przeplywy.csv", encoding="utf-8-sig")
#
# print("Zapisano plik: srednie_godzinowe_przeplywy.csv")
# print(hourly_means.head())
