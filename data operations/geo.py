import pandas as pd
from io import StringIO

# dane które wkleiłaś
data = """G-T1_wgs84 49.70757176 19.25299195
KP10_wgs84 49.70543420 19.11064015
KP11_wgs84 49.67081894 19.15859707
KP13_wgs84 49.69279531 19.17908062
KP16_wgs84 49.65814756 19.30308067
KP1_wgs84 49.66515271 19.23091042
KP25_wgs84 49.65909294 19.30620470
KP26_wgs84 49.66911040 19.24837659
KP2_wgs84 49.66907155 19.24832613
KP4_wgs84 49.67443818 19.15760132
KP6_wgs84 49.66048201 19.17873420
KP7_wgs84 49.63048522 19.39470225
KP9_wgs84 49.68976617 19.13222012
LBT1_wgs84 49.69087539 19.12122499
ŁPA-P1_wgs84 49.69316904 19.17891973
M1 49.683693 19.683883
Oczyszczalnia 49.68333333 19.68333333"""

# wczytanie do DataFrame
df = pd.read_csv(StringIO(data), sep=r"\s+", header=None, names=["ID", "lat", "lon"])

df["ID"] = df["ID"].str.replace("_wgs84", "", regex=False)
df.to_csv("wspolrzedne.csv", index=False, encoding="utf-8-sig")

print("Zapisano plik: wspolrzedne.csv")
print(df.head())
