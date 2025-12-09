import pandas as pd
import contextily as cx
import matplotlib.pyplot as plt
import os
import csv


def get_map():
    # 1. Wczytaj współrzędne wszystkich punktów
    csv_path = os.path.join("../data", "wspolrzedne.csv")
    if not os.path.exists(csv_path):
        print(f"Błąd: Nie znaleziono pliku {csv_path}")
        return

    df = pd.read_csv(csv_path)

    # 2. Znajdź skrajne punkty (min/max)
    min_lat = df["lat"].min()
    max_lat = df["lat"].max()
    min_lon = df["lon"].min()
    max_lon = df["lon"].max()

    # 3. Dodaj margines (bufor), żeby punkty nie były na samej krawędzi
    # 0.005 stopnia to około 300-500 metrów marginesu
    margin = 0.01

    south = min_lat - margin
    north = max_lat + margin
    west = min_lon - margin
    east = max_lon + margin

    print(f"Generuję mapę dla zakresu:")
    print(f"Lat: {south:.4f} - {north:.4f}")
    print(f"Lon: {west:.4f} - {east:.4f}")

    # 4. Pobierz i zapisz mapę
    fig, ax = plt.subplots(figsize=(12, 8))  # Większa rozdzielczość bazowa

    # Ustawienie zakresu osi (WGS84)
    ax.set_xlim([west, east])
    ax.set_ylim([south, north])

    # Pobranie kafelków mapy (OpenStreetMap)
    try:
        cx.add_basemap(ax, crs="EPSG:4326", source=cx.providers.OpenStreetMap.Mapnik, zoom=14)
    except Exception as e:
        print("Błąd pobierania mapy (sprawdź internet):", e)
        return

    ax.axis('off')
    plt.tight_layout(pad=0)

    output_path = os.path.join("../visualisation", "map.png")
    # Zapisujemy z nadpisaniem starej mapy
    plt.savefig(output_path, dpi=150, bbox_inches="tight", pad_inches=0)

    MAP_BOUNDS = (south, north, east, west)
    bounds_path = os.path.join("data", "map_bounds.csv")

    # Zapisujemy wartości MAP_BOUNDS do CSV : south, north, east, west
    with open(bounds_path, mode='w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['south', 'north', 'east', 'west'])  # Nagłówek
        writer.writerow([south, north, west, east])  # Wartości

    print(f"Zapisano granice mapy do pliku: {bounds_path}")

    print("\n" + "=" * 50)
    print("Nowa mapa została zapisana w visualization/map.png")
    print("Nowe współrzędne graniczne:")
    print(f"MAP_BOUNDS = ({south:.5f}, {north:.5f}, {east:.5f}, {west:.5f})")
    print("=" * 50)


if __name__ == "__main__":
    get_map()