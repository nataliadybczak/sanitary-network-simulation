from __future__ import annotations
import threading
from collections import deque
from typing import Dict, Optional, Tuple, List
import os
import math
import warnings
import csv

os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = "1"
warnings.filterwarnings("ignore", category=UserWarning, message=".*pkg_resources is deprecated.*")
import pygame

from visualisation.map_download import get_map

# Definicje ścieżek
BOUNDS_PATH = os.path.join("data", "map_bounds.csv")
MAP_IMAGE = "visualisation/map.png"


def get_dynamic_map_bounds():
    # 1. Sprawdź czy pliki istnieją
    if not os.path.exists(BOUNDS_PATH) or not os.path.exists(MAP_IMAGE):
        print(f"[INFO] Brak plików mapy ({MAP_IMAGE}) lub granic ({BOUNDS_PATH}).")
        print("[INFO] Uruchamiam automatyczne generowanie mapy...")
        try:
            get_map()
        except Exception as e:
            print(f"[ERROR] Błąd podczas generowania mapy: {e}")
            # Zwracamy domyślne (fallback) jeśli generowanie się nie uda
            return (49.62049, 49.71757, 19.40470, 19.10064)

    # 2. Odczytaj wartości z pliku
    try:
        with open(BOUNDS_PATH, mode='r') as f:
            reader = csv.reader(f)
            header = next(reader)  # Pomiń nagłówek
            row = next(reader)

            # W map_download.py zapisywaliśmy: [south, north, west, east]
            south = float(row[0])
            north = float(row[1])
            west = float(row[2])  # min_lon
            east = float(row[3])  # max_lon

            # Twoja zmienna MAP_BOUNDS w poprzednim pytaniu miała format:
            # (south, north, east, west) <- zwróć uwagę na kolejność East/West
            # więc zwracamy je w takiej kolejności:
            print(f"[INFO] Wczytano granice mapy: S={south}, N={north}, E={east}, W={west}")
            return (south, north, east, west)

    except Exception as e:
        print(f"[ERROR] Błąd odczytu pliku CSV: {e}. Używam wartości domyślnych.")
        return (49.62049, 49.71757, 19.40470, 19.10064)

# === Konfiguracja mapy ===
# # MAP_BOUNDS = (49.6600, 49.7150, 19.2600, 19.1700)
# MAP_BOUNDS = (49.62049, 49.71757, 19.40470, 19.10064)
MAP_BOUNDS = get_dynamic_map_bounds()


# ====== Konfiguracja UI ======
WINDOW_W, WINDOW_H = 1280, 720
FPS = 60
CHART_MAX_POINTS = 600

# Kolory
WHITE = (255, 255, 255)
BLACK = (25, 25, 25)
GRAY = (140, 140, 140)
LIGHT = (236, 240, 245)
RED = (226, 78, 78)
GREEN = (52, 199, 121)
ORANGE = (245, 165, 60)
BLUE = (66, 133, 244)
DARK_RED = (150, 20, 20)
YELLOW = (240, 230, 50)
BROWN = (139, 69, 19)


# ====== Pomocnicze ======
def geo_to_px(lat: float, lon: float, rect: pygame.Rect, bounds=MAP_BOUNDS) -> Tuple[int, int]:
    min_lat, max_lat, min_lon, max_lon = bounds
    nx = (lon - min_lon) / (max_lon - min_lon)
    ny = (max_lat - lat) / (max_lat - min_lat)
    x = int(rect.right - nx * rect.width)
    y = int(rect.top + ny * rect.height)
    return x, y


def draw_arrow(surface, start, end, color, width=2):
    pygame.draw.line(surface, color, start, end, width)
    # Grot strzałki
    rotation = math.degrees(math.atan2(start[1] - end[1], end[0] - start[0])) + 90
    pygame.draw.polygon(surface, color, (
        (end[0] + 5 * math.sin(math.radians(rotation)), end[1] + 5 * math.cos(math.radians(rotation))),
        (end[0] + 5 * math.sin(math.radians(rotation - 120)), end[1] + 5 * math.cos(math.radians(rotation - 120))),
        (end[0] + 5 * math.sin(math.radians(rotation + 120)), end[1] + 5 * math.cos(math.radians(rotation + 120)))
    ))


def draw_triangle(surface, x, y, size, color):
    points = [(x, y - size), (x - size, y + size), (x + size, y + size)]
    pygame.draw.polygon(surface, color, points)


def draw_square(surface, x, y, size, color):
    pygame.draw.rect(surface, color, (x - size, y - size, size * 2, size * 2))


def draw_blob(surface, x, y, radius, color, alpha=100):
    s = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
    pygame.draw.circle(s, (*color, alpha), (radius, radius), radius)
    surface.blit(s, (x - radius, y - radius))


# ====== Rysowanie wykresu ======
def draw_chart(surface: pygame.Surface, rect: pygame.Rect, points_est: deque, points_div: deque, points_rain: deque,
               max_capacity: Optional[float]):
    # Tło panelu
    pygame.draw.rect(surface, LIGHT, rect, border_radius=12)
    pygame.draw.rect(surface, GRAY, rect, 2, border_radius=12)

    if not points_est:
        return

    pad_left, pad_right, pad_top, pad_bottom = 64, 24, 28, 56
    plot = pygame.Rect(rect.left + pad_left, rect.top + pad_top, rect.width - (pad_left + pad_right),
                       rect.height - (pad_top + pad_bottom))

    pygame.draw.rect(surface, WHITE, plot, border_radius=8)
    pygame.draw.rect(surface, (210, 210, 210), plot, 1, border_radius=8)

    # Skalowanie Y
    all_vals = [v for _, v in points_est] + ([v for _, v in points_div] if points_div else [])
    if max_capacity: all_vals.append(max_capacity)
    vmin, vmax = 0.0, max(10.0, max(all_vals) * 1.1)

    n = len(points_est)

    # Pomocnicza funkcja do skalowania (zawiera zabezpieczenie n <= 1)
    def xy(i, val, n_pts, y_min, y_max, p_rect):
        if n_pts <= 1:
            x = p_rect.left
        else:
            x = p_rect.left + int(i * (p_rect.width - 1) / (n_pts - 1))

        # Zabezpieczenie przed dzieleniem przez zero przy y_max == y_min
        if y_max == y_min:
            y = p_rect.bottom
        else:
            y = p_rect.bottom - int((val - y_min) / (y_max - y_min) * (p_rect.height - 1))
        return x, y

    # --- Wykres deszczu (górny pasek, odwrócony) ---
    if points_rain:
        rain_vals = [v for _, v in points_rain]
        max_r = max(1.0, max(rain_vals) * 2)  # skala deszczu

        for i, (_, val) in enumerate(points_rain):
            # POPRAWKA: Zabezpieczenie przed dzieleniem przez zero gdy n=1
            if n > 1:
                x = plot.left + int(i * (plot.width - 1) / (n - 1))
            else:
                x = plot.left

            # Rysujemy deszcz jako słupki od góry
            h = int((val / max_r) * (plot.height * 0.3))  # max 30% wysokości
            if h > 0:
                pygame.draw.line(surface, (100, 100, 200), (x, plot.top), (x, plot.top + h), 2)

    # --- Linie i siatka ---
    y_ticks = 5
    font = pygame.font.SysFont(None, 18)
    for j in range(y_ticks + 1):
        frac = j / y_ticks
        y = plot.bottom - int(frac * (plot.height - 1))
        pygame.draw.line(surface, (232, 232, 232), (plot.left, y), (plot.right, y), 1)
        val = vmin + frac * (vmax - vmin)
        label = font.render(f"{val:.0f}", True, BLACK)
        surface.blit(label, (plot.left - 8 - label.get_width(), y - label.get_height() // 2))

    if max_capacity and vmax > vmin:
        y_lim = plot.bottom - int((max_capacity - vmin) / (vmax - vmin) * (plot.height - 1))
        pygame.draw.line(surface, RED, (plot.left, y_lim), (plot.right, y_lim), 2)

    # Serie danych
    last_e, last_d = None, None
    for i in range(n):
        pe = xy(i, points_est[i][1], n, vmin, vmax, plot)
        if last_e: pygame.draw.line(surface, BLUE, last_e, pe, 2)
        last_e = pe

        if points_div:
            pd = xy(i, points_div[i][1], n, vmin, vmax, plot)
            if last_d: pygame.draw.line(surface, ORANGE, last_d, pd, 2)
            last_d = pd

    # Tytuł
    title = pygame.font.SysFont(None, 20).render("Przepływ (Linia) | Deszcz (Słupki z góry)", True, BLACK)
    surface.blit(title, (plot.left, rect.top + 6))


# ====== Rysowanie mapy ======
def draw_map(surface: pygame.Surface, rect: pygame.Rect, shared: Dict, lock: threading.Lock):
    if not hasattr(draw_map, "_bg"):
        draw_map._bg = pygame.image.load(MAP_IMAGE).convert()
    srf = draw_map._bg

    with lock:
        s = shared.get("map_scale", 1.0)
        ox, oy = shared.get("map_offset", (0, 0))
        sensors = shared.get("sensors", [])
        overflow = shared.get("overflow", None)
        plant = shared.get("plant", None)
        connections = shared.get("connections", [])
        rain = shared.get("rain", {})
        plant_params = shared.get("plant_params", {})

    sw, sh = int(rect.width * s), int(rect.height * s)
    img = pygame.transform.smoothscale(srf, (sw, sh))
    surface.fill((244, 247, 252), rect)

    # Clipowanie rysowania do prostokąta mapy
    surface.set_clip(rect)
    surface.blit(img, (rect.left + ox, rect.top + oy))

    def apply_view(lat, lon):
        x0, y0 = geo_to_px(lat, lon, rect)
        x = rect.left + ox + int((x0 - rect.left) * s)
        y = rect.top + oy + int((y0 - rect.top) * s)
        return x, y

    # 1. Rysowanie połączeń (strzałek)
    for (start_loc, end_loc, flow) in connections:
        sx, sy = apply_view(*start_loc)
        ex, ey = apply_view(*end_loc)
        # Kolor połączenia: niebieski jeśli płynie, szary jeśli sucho
        col = (50, 50, 200) if flow > 1.0 else (180, 180, 180)
        thick = 2 if flow > 1.0 else 1
        draw_arrow(surface, (sx, sy), (ex, ey), col, thick)

    font = pygame.font.SysFont(None, 16)

    # 2. Sensory (Kółka)
    for sid, lat, lon, flow, status in sensors:
        x, y = apply_view(lat, lon)
        color = GREEN if status == "NORMAL" else RED
        draw_shape_fn = pygame.draw.circle
        draw_shape_fn(surface, color, (x, y), 7)
        pygame.draw.circle(surface, BLACK, (x, y), 7, 1)  # obrys

        # Etykieta
        lbl = font.render(f"{sid}", True, BLACK)
        surface.blit(lbl, (x + 8, y - 8))
        lbl_flow = font.render(f"{flow:.0f}", True, (50, 50, 50))
        surface.blit(lbl_flow, (x + 8, y + 4))

    # 3. Przelew KP26 (Trójkąt)
    if overflow:
        oid, lat, lon, active, diverted = overflow
        x, y = apply_view(lat, lon)

        # Plama przelewu
        if diverted > 0:
            draw_blob(surface, x, y, 40, BLUE, alpha=80)

        col = ORANGE if active else GRAY
        draw_triangle(surface, x, y, 9, col)
        pygame.draw.polygon(surface, BLACK, [(x, y - 9), (x - 9, y + 9), (x + 9, y + 9)], 1)  # obrys

        lbl = font.render(f"KP26: {diverted:.0f}", True, BLACK)
        surface.blit(lbl, (x + 12, y - 5))

    # 4. Oczyszczalnia (Kwadrat)
    if plant:
        plat, plon, est = plant
        x, y = apply_view(plat, plon)

        # Logika kolorów oczyszczalni
        nom = plant_params.get("nominal", 1700)
        warn = plant_params.get("warning", 2000)
        hyd = plant_params.get("hydraulic", 2200)

        p_col = GREEN
        if est > hyd + 1000:
            p_col = DARK_RED  # Awaria twarda
        elif est > hyd:
            p_col = RED  # Przeciążenie hydrauliczne (retencja)
        elif est > warn:
            p_col = ORANGE  # Krytyczne
        elif est > nom:
            p_col = YELLOW  # Ostrzeżenie

        # Plama awarii
        if est > hyd:
            draw_blob(surface, x, y, 50, BROWN, alpha=100)

        draw_square(surface, x, y, 10, p_col)
        pygame.draw.rect(surface, BLACK, (x - 10, y - 10, 20, 20), 1)

        # Pasek napełnienia przy oczyszczalni
        bar_h = 40;
        bar_w = 6
        fill_pct = min(1.0, est / (hyd * 1.2))
        bx, by = x + 15, y - 10
        pygame.draw.rect(surface, WHITE, (bx, by, bar_w, bar_h))
        pygame.draw.rect(surface, BLACK, (bx, by, bar_w, bar_h), 1)
        fill_h = int(fill_pct * bar_h)
        pygame.draw.rect(surface, p_col, (bx + 1, by + bar_h - fill_h, bar_w - 2, fill_h))

        surface.blit(font.render(f"OCZ: {est:.0f}", True, BLACK), (x - 20, y + 14))

    surface.set_clip(None)  # Koniec clipowania mapy
    pygame.draw.rect(surface, GRAY, rect, 2, border_radius=12)

    # 5. Panel informacyjny (HUD) na mapie
    # Panel deszczu
    hud_x, hud_y = rect.right - 130, rect.top + 20
    pygame.draw.rect(surface, (255, 255, 255, 200), (hud_x, hud_y, 110, 100), border_radius=8)
    pygame.draw.rect(surface, GRAY, (hud_x, hud_y, 110, 100), 1, border_radius=8)

    r_int = rain.get("intensity", 0.0)
    r_dep = rain.get("depth", 0.0)

    title_f = pygame.font.SysFont(None, 18, bold=True)
    val_f = pygame.font.SysFont(None, 18)

    surface.blit(title_f.render("DESZCZ", True, BLACK), (hud_x + 30, hud_y + 5))
    surface.blit(val_f.render(f"Int: {r_int:.1f} mm/h", True, BLACK), (hud_x + 10, hud_y + 25))
    surface.blit(val_f.render(f"Sum: {r_dep:.1f} mm", True, BLACK), (hud_x + 10, hud_y + 45))

    # Wizualizacja deszczu (kropla/kolor)
    if r_int > 0.1:
        pygame.draw.circle(surface, BLUE, (hud_x + 55, hud_y + 80), 10)
        if r_int > 5.0:  # ulewa
            pygame.draw.circle(surface, (0, 0, 150), (hud_x + 55, hud_y + 80), 6)
    else:
        pygame.draw.circle(surface, GRAY, (hud_x + 55, hud_y + 80), 10, 1)