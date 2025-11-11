import pandas as pd
import matplotlib.pyplot as plt

#  Wczytaj dane
df = pd.read_excel("data_all_values.xlsx")

# Upewnij się, że kolumna 'Czas' ma poprawny typ datetime
df['Czas'] = pd.to_datetime(df['Czas'])

# Usuń wiersze bez dopływu
df = df.dropna(subset=['Suma całkowita'])

# Ustaw czas jako indeks (łatwiejsze grupowanie)
df = df.set_index('Czas').sort_index()

# Wykres godzinowy (oryginalne dane)
plt.figure(figsize=(14,6))
plt.plot(df.index, df['Suma całkowita'], label='Dopływ (godzinowo)', color='orange')
plt.title("Godzinowy dopływ do oczyszczalni")
plt.xlabel("Czas")
plt.ylabel("Przepływ [m³/h]")
plt.grid(True)
plt.legend()
plt.tight_layout()
plt.show()

# Agregacja — dobowa, tygodniowa, miesięczna
# Dobowa
daily = df['Suma całkowita'].resample('D').mean()
# Tygodniowa
weekly = df['Suma całkowita'].resample('W').mean()
# Miesięczna
monthly = df['Suma całkowita'].resample('M').mean()

# Wykresy agregowane
fig, axes = plt.subplots(3, 1, figsize=(14, 10), sharey=True)

daily.plot(ax=axes[0], color='tab:blue', title='Średni dopływ - dobowy')
weekly.plot(ax=axes[1], color='tab:green', title='Średni dopływ - tygodniowy')
monthly.plot(ax=axes[2], color='tab:red', title='Średni dopływ - miesięczny')

for ax in axes:
    ax.set_xlabel("Czas")
    ax.set_ylabel("Przepływ [m³/h]")
    ax.grid(True)

plt.tight_layout()
plt.show()

# print(df.columns)

sredni_przeplyw_sucho = df.loc[df['Opady na godzinę'] == 0, 'Suma całkowita'].mean()
print(f"Średni przepływ przy braku opadów: {sredni_przeplyw_sucho:.2f} m³/h")

max_przeplyw_sucho = df.loc[df['Opady na godzinę'] == 0, 'Suma całkowita'].max()
print(f"Maksymalny przepływ przy braku opadów: {max_przeplyw_sucho:.2f} m³/h")
#
# Średni przepływ przy małych opadach (0 < opad < 0.5)
sredni_przeplyw_podczas_opadow = df.loc[
    (df['Opady na godzinę'] > 0) & (df['Opady na godzinę'] < 0.5),
    'Suma całkowita'
].mean()

print(f"Średni przepływ podczas opadów poniżej 0.5 mm: {sredni_przeplyw_podczas_opadow:.2f} m³/h")


max_przeplyw_podczas_opadow = df.loc[
    (df['Opady na godzinę'] > 0) & (df['Opady na godzinę'] < 0.5),
    'Suma całkowita'
].max()

print(f"Maksymalny przepływ podczas opadów poniżej 0.5 mm: {max_przeplyw_podczas_opadow:.2f} m³/h")

# Średni przepływ przy dużych opadach (≥ 0.5)
sredni_przeplyw_podczas_duzych_opadow = df.loc[
    (df['Opady na godzinę'] >= 0.5) & (df['Opady na godzinę'] < 1.0),
    'Suma całkowita'
].mean()

print(f"Średni przepływ podczas opadów od 0.5 mm: {sredni_przeplyw_podczas_duzych_opadow:.2f} m³/h")

max_przeplyw_podczas_duzych_opadow = df.loc[
    (df['Opady na godzinę'] >= 0.5) & (df['Opady na godzinę'] < 1.0),
    'Suma całkowita'
].max()

print(f"Maksymalny przepływ podczas opadów od 0.5 mm: {max_przeplyw_podczas_duzych_opadow:.2f} m³/h")

# Średni przepływ przy dużych opadach (≥ 0.5)
sredni_przeplyw_podczas_bardzo_duzych_opadow = df.loc[
    df['Opady na godzinę'] >= 1.0,
    'Suma całkowita'
].mean()

print(f"Średni przepływ podczas opadów od 1.0 mm: {sredni_przeplyw_podczas_bardzo_duzych_opadow:.2f} m³/h")

max_przeplyw_podczas_bardzo_duzych_opadow = df.loc[
    df['Opady na godzinę'] >= 1.0,
    'Suma całkowita'
].max()

print(f"Maksymalny przepływ podczas opadów od 0.5 mm: {max_przeplyw_podczas_bardzo_duzych_opadow:.2f} m³/h")


