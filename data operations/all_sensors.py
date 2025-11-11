import pandas as pd
import matplotlib.pyplot as plt

df = pd.read_excel("data_all_values.xlsx")
df['Czas'] = pd.to_datetime(df['Czas'])
df = df.dropna(subset=['Suma całkowita']).set_index('Czas').sort_index()
df.rename(columns={"Warość pomiaru ŁPA-P1": "Wartość pomiaru ŁPA-P1"}, inplace=True)


dzien = '2025-07-28'
start = f'{dzien} 00:00:00'
end   = f'{dzien} 23:59:59'
df_dzien = df.loc[start:end]

sensor_cols = [
    c for c in df_dzien.columns
    if c.startswith('Wartość pomiaru ')
    and 'przelew' not in c.lower()
]

fig, ax1 = plt.subplots(figsize=(14, 6))

for c in sensor_cols:
    label = c.replace('Wartość pomiaru ', '')
    ax1.plot(df_dzien.index, df_dzien[c], linewidth=1, alpha=0.7, label=label)

ax1.plot(df_dzien.index, df_dzien['Suma całkowita'], linewidth=2.5, label='Suma całkowita')

ax1.set_xlabel("Godzina")
ax1.set_ylabel("Przepływ [m³/h]")
ax1.grid(True, which='both', linestyle='--', alpha=0.5)


rain_col = next((c for c in df.columns if c.strip().startswith('Opady')), None)
if rain_col is not None:
    ax2 = ax1.twinx()
    ax2.bar(df_dzien.index, df_dzien[rain_col], width=0.03, alpha=0.2, label='Opady [mm/h]')
    ax2.set_ylabel("Opady [mm/h]")

ax1.legend(ncol=3, loc='upper left', fontsize=9)  # dostosuj ncol jeśli dużo linii

fig.suptitle(f'Dopływy z wszystkich przepływomierzy + suma i opady — {dzien}', fontsize=14)
fig.autofmt_xdate()
fig.tight_layout()
plt.show()
