import pandas as pd
import matplotlib.pyplot as plt

df = pd.read_excel("data_all_values.xlsx")
df['Czas'] = pd.to_datetime(df['Czas'])
df = df.dropna(subset=['Suma całkowita']).set_index('Czas').sort_index()

dzien = '2025-07-28'  # tutaj wpisz dowolną datę
start = f'{dzien} 00:00:00'
end = f'{dzien} 23:59:59'

df_dzien = df.loc[start:end]


fig, ax1 = plt.subplots(figsize=(14,6))

# --- lewa oś: przepływ ---
ax1.plot(df_dzien.index, df_dzien['Suma całkowita'], color='orange', label='Przepływ [m³/h]')
ax1.set_xlabel("Godzina")
ax1.set_ylabel("Przepływ [m³/h]", color='orange')
ax1.tick_params(axis='y', labelcolor='orange')
ax1.grid(True, which='both', linestyle='--', alpha=0.5)

# --- prawa oś: opady ---
if 'Opady na godzinę' in df.columns:
    ax2 = ax1.twinx()  # druga oś Y
    ax2.bar(df_dzien.index, df_dzien['Opady na godzinę'],
            width=0.03, color='blue', alpha=0.2, label='Opady [mm/h]')
    ax2.set_ylabel("Opady [mm/h]", color='blue')
    ax2.tick_params(axis='y', labelcolor='blue')


fig.suptitle(f'Dopływ do oczyszczalni i opady – {dzien}', fontsize=14)
fig.autofmt_xdate()
fig.tight_layout()
plt.show()
