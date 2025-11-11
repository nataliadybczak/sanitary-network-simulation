import pandas as pd
import matplotlib.pyplot as plt

df = pd.read_excel("data_all_values.xlsx")
df['Czas'] = pd.to_datetime(df['Czas'])
df = df.dropna(subset=['Suma całkowita']).set_index('Czas').sort_index()

# Zakres tygodnia
start = '2025-07-28'
end = '2025-08-03'
df_tydzien = df.loc[start:end]

fig, ax1 = plt.subplots(figsize=(14,6))

# --- lewa oś: przepływ ---
ax1.plot(df_tydzien.index, df_tydzien['Suma całkowita'], color='orange', label='Przepływ [m³/h]')
ax1.set_xlabel("Data i godzina")
ax1.set_ylabel("Przepływ [m³/h]", color='orange')
ax1.tick_params(axis='y', labelcolor='orange')
ax1.grid(True, which='both', linestyle='--', alpha=0.5)

# --- prawa oś: opady ---
if 'Opady na godzinę' in df.columns:
    ax2 = ax1.twinx()  # druga oś Y
    ax2.bar(df_tydzien.index, df_tydzien['Opady na godzinę'],
            width=0.03, color='blue', alpha=0.4, label='Opady [mm/h]')
    ax2.set_ylabel("Opady [mm/h]", color='blue')
    ax2.tick_params(axis='y', labelcolor='blue')

fig.suptitle(f'Dopływ do oczyszczalni i opady – tydzień {start} → {end}', fontsize=14)
fig.autofmt_xdate()
fig.tight_layout()
plt.show()
