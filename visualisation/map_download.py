import pandas as pd
import contextily as cx
import matplotlib.pyplot as plt
import os
import csv


def get_map():
    # 1. Ustal folder, w którym fizycznie leży ten skrypt (czyli folder 'visualisation')
    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

    # 2. Ustal folder główny projektu (wychodzimy piętro wyżej: visualisation -> root)
    PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, '..'))

    # 3. Buduj poprawne ścieżki
    # Dane wejściowe są w głównym folderze w 'data'
    csv_path = os.path.join(PROJECT_ROOT, "data", "wspolrzedne.csv")

    # Mapa ma zostać zapisana w folderze skryptu (visualisation)
    map_output_path = os.path.join(SCRIPT_DIR, "map.png")

    # Granice mapy zapisujemy w folderze data (głównym)
    bounds_output_path = os.path.join(PROJECT_ROOT, "data", "map_bounds.csv")

    print(f"[MAPA] Szukam pliku CSV tutaj: {csv_path}")

    if not os.path.exists(csv_path):
        # Diagnostyka
        data_dir = os.path.dirname(csv_path)
        print(f"[DEBUG] Folder data istnieje? {os.path.exists(data_dir)}")
        if os.path.exists(data_dir):
            print(f"[DEBUG] Zawartość folderu data: {os.listdir(data_dir)}")
        raise FileNotFoundError(f"Błąd krytyczny: Nie znaleziono pliku {csv_path}")

    print(f"[MAPA] Wczytuję dane z: {csv_path}")
    df = pd.read_csv(csv_path)

    # Znajdź skrajne punkty
    min_lat = df["lat"].min()
    max_lat = df["lat"].max()
    min_lon = df["lon"].min()
    max_lon = df["lon"].max()

    # Margines
    margin = 0.01
    south = min_lat - margin
    north = max_lat + margin
    west = min_lon - margin
    east = max_lon + margin

    print(f"[MAPA] Generuję mapę dla zakresu Lat: {south:.4f}-{north:.4f}, Lon: {west:.4f}-{east:.4f}")

    # Pobieranie mapy
    fig, ax = plt.subplots(figsize=(12, 8))
    ax.set_xlim([west, east])
    ax.set_ylim([south, north])

    try:
        cx.add_basemap(ax, crs="EPSG:4326", source=cx.providers.OpenStreetMap.Mapnik, zoom=14)
    except Exception as e:
        print(f"[MAPA] Błąd pobierania kafelków: {e}")
        # Rzucamy błąd dalej, żeby zatrzymać program główny
        raise e

    ax.axis('off')
    plt.tight_layout(pad=0)

    # Zapis mapy
    os.makedirs(os.path.dirname(map_output_path), exist_ok=True)
    plt.savefig(map_output_path, dpi=150, bbox_inches="tight", pad_inches=0)
    plt.close(fig)  # Zamknij figurę, żeby zwolnić pamięć

    # Zapis granic do CSV
    with open(bounds_output_path, mode='w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['south', 'north', 'east', 'west'])
        writer.writerow([south, north, west, east])

    print(f"[MAPA] Sukces! Mapa zapisana w: {map_output_path}")
    print(f"[MAPA] Granice zapisane w: {bounds_output_path}")


if __name__ == "__main__":
    try:
        get_map()
    except Exception as e:
        print(f"BŁĄD: {e}")