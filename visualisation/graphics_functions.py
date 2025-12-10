from __future__ import annotations
import threading
from collections import deque
from typing import Dict, Optional, Tuple
import os
import math
import warnings
import sys
import csv

# wyrzucenie komentarzy i warningów z Pygame
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = "1"
warnings.filterwarnings("ignore", category=UserWarning, message=".*pkg_resources is deprecated.*")
import pygame

from visualisation.map_download import get_map

# Ustalanie ścieżek absolutnych
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, '..'))

if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

# Definicje ścieżek do danych (bezwzględne, żeby ściąganie mapki/wczytywanie z pliku działało)
BOUNDS_PATH = os.path.join(PROJECT_ROOT, "data", "map_bounds.csv")
MAP_IMAGE = os.path.join(PROJECT_ROOT, "visualisation", "map.png")

# ściąganie granic mapy
def get_dynamic_map_bounds():
    if not os.path.exists(BOUNDS_PATH) or not os.path.exists(MAP_IMAGE):
        print(f"\n[INFO] Brak mapy lub granic. Rozpoczynam generowanie...")
        try:
            get_map()
        except Exception as e:
            print(f"[CRITICAL ERROR] Nie udało się wygenerować mapy: {e}")
            print("Sprawdź czy plik 'data/wspolrzedne.csv' istnieje i czy masz internet.")
            sys.exit(1)

    try:
        with open(BOUNDS_PATH, mode='r') as f:
            reader = csv.reader(f)
            next(reader)
            row = next(reader)
            return (float(row[0]), float(row[1]), float(row[2]), float(row[3]))
    except Exception as e:
        print(f"[ERROR] Plik granic uszkodzony: {e}")
        print("Usuń plik data/map_bounds.csv i uruchom program ponownie.")
        sys.exit(1)


# === Konfiguracja mapy ===
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
LIGHT_GRAY_BG = (245, 245, 245)
RED = (226, 78, 78)
GREEN = (52, 199, 121)
ORANGE = (245, 165, 60)
BLUE = (66, 133, 244)
DARK_BLUE = (0, 0, 150)
CYAN = (0, 180, 180)
DARK_CYAN = (0, 100, 100)
DARK_RED = (150, 20, 20)
YELLOW = (240, 230, 50)
BROWN = (139, 69, 19)


# ====== Funkcje Pomocnicze ======
def geo_to_px(lat: float, lon: float, rect: pygame.Rect, bounds=MAP_BOUNDS) -> Tuple[int, int]:
    min_lat, max_lat, min_lon, max_lon = bounds
    nx = (lon - min_lon) / (max_lon - min_lon)
    ny = (max_lat - lat) / (max_lat - min_lat)
    x = int(rect.left + nx * rect.width)
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


# ====== Rysowanie wykresów ======
def draw_chart(surface: pygame.Surface, rect: pygame.Rect, points_est: deque, points_div: deque,
               points_rain_int: deque, points_rain_dep: deque,
               max_capacity: Optional[float], current_hour: int):
    """
    Rysuje TRZY wykresy:
    1. Intensywność Opady [mm/h]
    2. Suma Opady (Depth) [mm]
    3. Przepływy [m3/h]
    """
    # Tło panelu
    pygame.draw.rect(surface, LIGHT, rect, border_radius=12)
    pygame.draw.rect(surface, GRAY, rect, 2, border_radius=12)

    if not points_est:
        return

    n_points = len(points_est)

    # Marginesy
    margin_left = 60
    margin_right = 20
    margin_top = 30
    margin_bottom = 50
    gap = 50  # Przerwa między wykresami

    # Wysokość dostępna na wykresy
    total_h = rect.height - margin_top - margin_bottom - (2 * gap)
    # Podział wysokości: np. 25% Int, 25% Dep, 50% Flow
    h_int = int(total_h * 0.25)
    h_dep = int(total_h * 0.25)
    h_flow = int(total_h * 0.50)

    # Definicje prostokątów
    rect_int = pygame.Rect(rect.left + margin_left, rect.top + margin_top,
                           rect.width - margin_left - margin_right, h_int)

    rect_dep = pygame.Rect(rect.left + margin_left, rect_int.bottom + gap,
                           rect.width - margin_left - margin_right, h_dep)

    rect_flow = pygame.Rect(rect.left + margin_left, rect_dep.bottom + gap,
                            rect.width - margin_left - margin_right, h_flow)

    # Funkcja pomocnicza: Tło dni
    def draw_bg(target_rect, start_h, end_h):
        pygame.draw.rect(surface, WHITE, target_rect)
        if end_h <= start_h: return
        hour_range = end_h - start_h

        # Paski co 24h (co drugi dzień)
        # Zakładamy start symulacji = godzina 0
        curr = start_h
        while curr <= end_h:
            day_num = curr // 24
            if day_num % 2 != 0:  # Co drugi dzień na szaro
                # Początek paska
                rel_x1 = (curr - start_h) / hour_range
                # Koniec godziny
                rel_x2 = (curr + 1 - start_h) / hour_range

                px1 = target_rect.left + int(rel_x1 * target_rect.width)
                px2 = target_rect.left + int(rel_x2 * target_rect.width)

                px1 = max(target_rect.left, min(target_rect.right, px1))
                px2 = max(target_rect.left, min(target_rect.right, px2))

                if px2 > px1:
                    pygame.draw.rect(surface, LIGHT_GRAY_BG, (px1, target_rect.top, px2 - px1, target_rect.height))
            curr += 1

        pygame.draw.rect(surface, (200, 200, 200), target_rect, 1)

    start_hour = max(0, current_hour - n_points + 1)
    end_hour = current_hour
    hour_range = max(1, end_hour - start_hour)

    draw_bg(rect_int, start_hour, end_hour)
    draw_bg(rect_dep, start_hour, end_hour)
    draw_bg(rect_flow, start_hour, end_hour)

    font_title = pygame.font.SysFont(None, 18, bold=True)
    font_label = pygame.font.SysFont(None, 14)
    font_unit = pygame.font.SysFont(None, 14, bold=True)

    # === OŚ X - podziałka ===
    if hour_range < 24:
        step_x = 2
    elif hour_range < 48:
        step_x = 4
    elif hour_range < 100:
        step_x = 10
    elif hour_range < 200:
        step_x = 20
    elif hour_range < 500:
        step_x = 50
    else:
        step_x = 100

    # Rysowanie siatki X i etykiet
    first_tick = (start_hour // step_x) * step_x
    if first_tick < start_hour: first_tick += step_x

    curr_tick = first_tick
    while curr_tick <= end_hour:
        rel_pos = (curr_tick - start_hour) / hour_range
        px = rect_flow.left + int(rel_pos * rect_flow.width)

        # Linie pionowe przez wszystkie wykresy
        col_grid = (235, 235, 235)
        pygame.draw.line(surface, col_grid, (px, rect_int.top), (px, rect_int.bottom), 1)
        pygame.draw.line(surface, col_grid, (px, rect_dep.top), (px, rect_dep.bottom), 1)
        pygame.draw.line(surface, col_grid, (px, rect_flow.top), (px, rect_flow.bottom), 1)

        # podziałki i etykiety
        pygame.draw.line(surface, BLACK, (px, rect_int.bottom), (px, rect_int.bottom + 4), 1)
        lbl = font_label.render(str(curr_tick), True, BLACK)
        surface.blit(lbl, (px - lbl.get_width() // 2, rect_int.bottom + 6))
        pygame.draw.line(surface, BLACK, (px, rect_dep.bottom), (px, rect_dep.bottom + 4), 1)
        lbl = font_label.render(str(curr_tick), True, BLACK)
        surface.blit(lbl, (px - lbl.get_width() // 2, rect_dep.bottom + 6))
        pygame.draw.line(surface, BLACK, (px, rect_flow.bottom), (px, rect_flow.bottom + 4), 1)
        lbl = font_label.render(str(curr_tick), True, BLACK)
        surface.blit(lbl, (px - lbl.get_width() // 2, rect_flow.bottom + 6))

        curr_tick += step_x

    lbl_x = font_unit.render("Czas symulacji [h]", True, BLACK)
    surface.blit(lbl_x, (rect_flow.centerx - lbl_x.get_width() // 2, rect_flow.bottom + 20))

    # --- Funkcja pomocnicza do mapowania Y ---
    def draw_y_grid(r, max_v, steps=4, format_str="{:.1f}"):
        for i in range(steps + 1):
            val = max_v * (i / steps)
            y = r.bottom - int((val / max_v) * r.height)
            pygame.draw.line(surface, (235, 235, 235), (r.left, y), (r.right, y))
            lbl = font_label.render(format_str.format(val), True, GRAY)
            surface.blit(lbl, (r.left - lbl.get_width() - 5, y - lbl.get_height() // 2))

    # === WYKRES 1: INTENSYWNOŚĆ (INT) ===
    vals_int = [v for _, v in points_rain_int]
    max_int = max(10.0, max(vals_int) * 1.2) if vals_int else 10.0

    surface.blit(font_title.render("Intensywność", True, BLACK), (rect_int.left, rect_int.top - 18))
    surface.blit(font_unit.render("[mm/h]", True, DARK_BLUE), (rect_int.left - 45, rect_int.top + 10))

    draw_y_grid(rect_int, max_int)

    if n_points > 1:
        for i, (_, val) in enumerate(points_rain_int):
            rel_x = i / (n_points - 1)
            px = rect_int.left + int(rel_x * rect_int.width)
            h = int((val / max_int) * rect_int.height)
            if h > 0:
                pygame.draw.line(surface, DARK_BLUE, (px, rect_int.bottom), (px, rect_int.bottom - h), 2)

    # === WYKRES 2: GŁĘBOKOŚĆ (DEPTH) ===
    vals_dep = [v for _, v in points_rain_dep]
    max_dep = max(10.0, max(vals_dep) * 1.1) if vals_dep else 10.0

    surface.blit(font_title.render("Poziom deszczu (na ziemi)", True, BLACK), (rect_dep.left, rect_dep.top - 18))
    surface.blit(font_unit.render("[mm]", True, DARK_CYAN), (rect_dep.left - 45, rect_dep.top + 10))

    draw_y_grid(rect_dep, max_dep)

    if n_points > 1:
        # Rysowanie jako wypełniony obszar pod wykresem
        poly_points = [(rect_dep.left, rect_dep.bottom)]
        for i, (_, val) in enumerate(points_rain_dep):
            rel_x = i / (n_points - 1)
            px = rect_dep.left + int(rel_x * rect_dep.width)
            py = rect_dep.bottom - int((val / max_dep) * rect_dep.height)
            poly_points.append((px, py))
        poly_points.append((rect_dep.right, rect_dep.bottom))

        if len(poly_points) > 2:
            pygame.draw.polygon(surface, (180, 240, 240), poly_points)  # Wypełnienie
            pygame.draw.lines(surface, DARK_CYAN, False, poly_points[1:-1], 2)  # Obrys

    # === WYKRES 3: PRZEPŁYWY (FLOW) ===
    vals_est = [v for _, v in points_est]
    vals_div = [v for _, v in points_div]
    all_f = vals_est + vals_div
    if max_capacity: all_f.append(max_capacity)
    max_flow = max(100.0, max(all_f) * 1.1) if all_f else 2000.0

    surface.blit(font_title.render("Przepływ", True, BLACK), (rect_flow.left, rect_flow.top - 18))
    surface.blit(font_unit.render("[m3/h]", True, BLACK), (rect_flow.left - 45, rect_flow.top + 10))

    draw_y_grid(rect_flow, max_flow, steps=5, format_str="{:.0f}")

    # Linia limitu
    if max_capacity:
        y_cap = rect_flow.bottom - int((max_capacity / max_flow) * rect_flow.height)
        if rect_flow.top <= y_cap <= rect_flow.bottom:
            pygame.draw.line(surface, RED, (rect_flow.left, y_cap), (rect_flow.right, y_cap), 1)
            lbl = font_label.render("Limit", True, RED)
            surface.blit(lbl, (rect_flow.right - lbl.get_width() - 5, y_cap - 12))

    # Rysowanie linii Est (Oczyszczalnia)
    if n_points > 1:
        pts_est = []
        pts_div = []
        for i in range(n_points):
            rel_x = i / (n_points - 1)
            px = rect_flow.left + int(rel_x * rect_flow.width)

            v_est = points_est[i][1]
            py_est = rect_flow.bottom - int((v_est / max_flow) * rect_flow.height)
            pts_est.append((px, py_est))

            v_div = points_div[i][1]
            if v_div > 0:
                py_div = rect_flow.bottom - int((v_div / max_flow) * rect_flow.height)
                pts_div.append((px, py_div))
            else:
                # Przerwa w linii, jeśli 0?
                # Dla uproszczenia rysujemy 0 na dole
                pts_div.append((px, rect_flow.bottom))

        pygame.draw.lines(surface, BLUE, False, pts_est, 2)
        if any(v > 0 for _, v in points_div):
            pygame.draw.lines(surface, ORANGE, False, pts_div, 2)

    # Legenda
    lx = rect_flow.right - 120
    ly = rect_flow.top + 10
    pygame.draw.line(surface, BLUE, (lx, ly), (lx + 20, ly), 2)
    surface.blit(font_label.render("Oczyszczalnia", True, BLACK), (lx + 25, ly - 5))
    pygame.draw.line(surface, ORANGE, (lx, ly + 20), (lx + 20, ly + 20), 2)
    surface.blit(font_label.render("Przelew", True, BLACK), (lx + 25, ly + 15))


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
        extra_points = shared.get("extra_points", [])

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

    # 1. Połączenia
    for (start_loc, end_loc, flow) in connections:
        sx, sy = apply_view(*start_loc)
        ex, ey = apply_view(*end_loc)
        col = (50, 50, 200) if flow > 1.0 else (180, 180, 180)
        thick = 2 if flow > 1.0 else 1
        draw_arrow(surface, (sx, sy), (ex, ey), col, thick)

    font = pygame.font.SysFont(None, 16)
    font_small = pygame.font.SysFont(None, 14)

    # 1.5 Extra Points
    for pid, lat, lon in extra_points:
        x, y = apply_view(lat, lon)
        pygame.draw.circle(surface, (180, 180, 180), (x, y), 5)
        lbl = font_small.render(str(pid), True, (100, 100, 100))
        surface.blit(lbl, (x + 6, y - 6))

    # 2. Sensory (Kółka)
    SENSOR_RADIUS = 7
    for sid, lat, lon, flow, status in sensors:
        x, y = apply_view(lat, lon)
        color = GREEN if status == "NORMAL" else RED
        pygame.draw.circle(surface, color, (x, y), SENSOR_RADIUS)
        lbl = font.render(f"{sid}", True, BLACK)
        surface.blit(lbl, (x + 8, y - 8))
        lbl_flow = font.render(f"{flow:.0f}", True, (50, 50, 50))
        surface.blit(lbl_flow, (x + 8, y + 4))

    # 3. Przelew KP26 (Trójkąt)
    if overflow:
        oid, lat, lon, active, diverted = overflow
        x, y = apply_view(lat, lon)

        if diverted > 0:
            draw_blob(surface, x, y, 40, BLUE, alpha=80)

        col = ORANGE if active else GRAY
        draw_triangle(surface, x, y, 9, col)

        lbl = font.render(f"KP26: {diverted:.0f}", True, BLACK)
        surface.blit(lbl, (x + 12, y - 5))

    # 4. Oczyszczalnia
    if plant:
        plat, plon, est = plant
        x, y = apply_view(plat, plon)

        nom = plant_params.get("nominal", 1700)
        warn = plant_params.get("warning", 2000)
        hyd = plant_params.get("hydraulic", 2200)

        p_col = GREEN
        if est > hyd + 1000:
            p_col = DARK_RED
        elif est > hyd:
            p_col = RED
        elif est > warn:
            p_col = ORANGE
        elif est > nom:
            p_col = YELLOW

        if est > hyd: draw_blob(surface, x, y, 50, BROWN, alpha=100)

        # IKONA OCZYSZCZALNI
        PLANT_RADIUS = 12
        # 1. Białe tło
        pygame.draw.circle(surface, WHITE, (x, y), PLANT_RADIUS)
        # 2. Zewnętrzny pierścień
        pygame.draw.circle(surface, p_col, (x, y), PLANT_RADIUS, 3)
        # 3. Wewnętrzne kółko
        pygame.draw.circle(surface, p_col, (x, y), PLANT_RADIUS - 5)

        # PASEK WYPEŁNIENIA PO PRAWEJ
        bar_h = 36
        bar_w = 8
        fill_pct = min(1.0, est / (hyd * 1.2))
        bx, by = x + PLANT_RADIUS + 6, y - (bar_h // 2)
        pygame.draw.rect(surface, WHITE, (bx, by, bar_w, bar_h))
        pygame.draw.rect(surface, BLACK, (bx, by, bar_w, bar_h), 1)
        fill_h = int(fill_pct * bar_h)
        pygame.draw.rect(surface, p_col, (bx + 1, by + bar_h - fill_h, bar_w - 2, fill_h))

        # Etykieta pod ikoną
        lbl_ocz = font.render(f"OCZ: {est:.0f}", True, BLACK)
        surface.blit(lbl_ocz, (x - (lbl_ocz.get_width() // 2), y + PLANT_RADIUS + 4))

    surface.set_clip(None)
    pygame.draw.rect(surface, GRAY, rect, 2, border_radius=12)

    # === 5. HUD DESZCZU (DWA SUWAKI) ===
    hud_w, hud_h = 180, 130
    hud_x, hud_y = rect.right - hud_w - 20, rect.top + 20

    pygame.draw.rect(surface, (255, 255, 255, 230), (hud_x, hud_y, hud_w, hud_h), border_radius=8)
    pygame.draw.rect(surface, GRAY, (hud_x, hud_y, hud_w, hud_h), 1, border_radius=8)

    r_int = rain.get("intensity", 0.0)
    r_dep = rain.get("depth", 0.0)

    # czcionki
    title_f = pygame.font.SysFont(None, 20, bold=True)
    val_f = pygame.font.SysFont(None, 14)

    surface.blit(title_f.render("Opady deszczu", True, BLACK), (hud_x + 10, hud_y + 10))

    # Funkcja rysująca pojedynczy pasek
    def draw_gauge(x, y, w, h, val, max_v, c_start, c_end, title, unit):
        # Tytuł i wartość
        surface.blit(val_f.render(title, True, BLACK), (x, y))
        val_txt = f"{val:.1f} {unit}"
        surface.blit(val_f.render(val_txt, True, BLACK), (x + w - 50, y))  # Wartość po prawej

        # Pasek
        bar_y = y + 20
        pygame.draw.rect(surface, WHITE, (x, bar_y, w, h))

        # Gradient
        for i in range(w):
            t = i / w
            r = int(c_start[0] + (c_end[0] - c_start[0]) * t)
            g = int(c_start[1] + (c_end[1] - c_start[1]) * t)
            b = int(c_start[2] + (c_end[2] - c_start[2]) * t)
            pygame.draw.line(surface, (r, g, b), (x + i, bar_y), (x + i, bar_y + h))

        pygame.draw.rect(surface, BLACK, (x, bar_y, w, h), 1)

        # Trójkąt wskaźnika
        pct = max(0.0, min(1.0, val / max_v))
        tx = x + int(pct * w)
        tri_pts = [(tx, bar_y + h), (tx - 5, bar_y + h + 6), (tx + 5, bar_y + h + 6)]
        pygame.draw.polygon(surface, RED, tri_pts)
        pygame.draw.polygon(surface, BLACK, tri_pts, 1)

    # 1. Gauge Intensywności (mm/h)
    draw_gauge(hud_x + 10, hud_y + 35, 160, 10, r_int, 40.0,
               (240, 248, 255), (0, 0, 128), "Intensywność", "mm/h")

    # 2. Gauge Głębokości (mm)
    draw_gauge(hud_x + 10, hud_y + 80, 160, 10, r_dep, 60.0,
               (220, 255, 255), (0, 100, 100), "Poziom deszczu", "mm")


# ====== UI CONTROLS ======
UI_BG = (240, 240, 240)
UI_BORDER = (180, 180, 180)
BUTTON_HOVER = (220, 225, 230)
SLIDER_BG = (200, 200, 200)
SLIDER_FILL = (100, 160, 220)


class UIState:
    def __init__(self):
        self.dragging_slider = False


_ui_state = UIState()


def draw_control_bar(surface: pygame.Surface, rect: pygame.Rect, shared: Dict,
                     pause_evt: threading.Event, stop_evt: threading.Event,
                     min_interval: float, max_interval: float):
    # Wymiary i pozycja panelu
    panel_w, panel_h = 700, 85
    panel_rect = pygame.Rect(rect.centerx - panel_w // 2, rect.bottom - panel_h - 20, panel_w, panel_h)

    # Tło
    pygame.draw.rect(surface, LIGHT , panel_rect, border_radius=12)
    pygame.draw.rect(surface, GRAY, panel_rect, 1, border_radius=12)  # Cieńsza ramka

    mouse_pos = pygame.mouse.get_pos()
    is_paused = pause_evt.is_set()

    # Czcionki
    font_ui = pygame.font.SysFont(None, 20)
    font_bold = pygame.font.SysFont(None, 20, bold=True)
    font_small = pygame.font.SysFont(None, 16)

    # === SEKCJA 1: PRZYCISKI  ===
    btn_w, btn_h = 80, 34
    spacing = 15
    start_x = panel_rect.left + 20
    center_y = panel_rect.centery + 5  # lekkie przesunięcie w dół bo nad przyciskami nic nie ma

    # Przycisk RESET
    btn_reset = pygame.Rect(start_x, center_y - btn_h // 2, btn_w, btn_h)
    col_reset = LIGHT if btn_reset.collidepoint(mouse_pos) else WHITE

    pygame.draw.rect(surface, col_reset, btn_reset, border_radius=6)
    pygame.draw.rect(surface, GRAY, btn_reset, 1, border_radius=6)

    # Ikonka i tekst Reset
    pygame.draw.rect(surface, RED, (btn_reset.left + 10, btn_reset.centery - 4, 8, 8))
    lbl_reset = font_ui.render("Reset", True, BLACK)
    surface.blit(lbl_reset, (btn_reset.left + 26, btn_reset.centery - lbl_reset.get_height() // 2))

    # Przycisk PLAY/PAUSE
    btn_play = pygame.Rect(btn_reset.right + spacing, center_y - btn_h // 2, btn_w, btn_h)
    col_play = LIGHT if btn_play.collidepoint(mouse_pos) else WHITE

    pygame.draw.rect(surface, col_play, btn_play, border_radius=6)
    pygame.draw.rect(surface, GRAY, btn_play, 1, border_radius=6)

    if is_paused:
        # Ikonka Play (Trójkąt)
        pts = [(btn_play.left + 12, btn_play.centery - 5),
               (btn_play.left + 12, btn_play.centery + 5),
               (btn_play.left + 20, btn_play.centery)]
        pygame.draw.polygon(surface, GREEN, pts)
        lbl_play = font_ui.render("Start", True, BLACK)
    else:
        # Ikonka Pauza (Dwie kreski)
        pygame.draw.rect(surface, BLACK, (btn_play.left + 12, btn_play.centery - 5, 3, 10))
        pygame.draw.rect(surface, BLACK, (btn_play.left + 17, btn_play.centery - 5, 3, 10))
        lbl_play = font_ui.render("Pauza", True, BLACK)

    surface.blit(lbl_play, (btn_play.left + 28, btn_play.centery - lbl_play.get_height() // 2))

    # === SEKCJA 2: SUWAK PRĘDKOŚCI ===
    slider_x = btn_play.right + 40
    slider_w = 280
    slider_y = panel_rect.centery + 8

    # Etykieta nad suwakiem
    lbl_speed_title = font_bold.render("Prędkość symulacji", True, BLACK)
    surface.blit(lbl_speed_title, (slider_x + slider_w // 2 - lbl_speed_title.get_width() // 2, panel_rect.top + 15))

    # Pasek suwaka
    slider_rect = pygame.Rect(slider_x, slider_y, slider_w, 6)
    pygame.draw.rect(surface, (220, 220, 220), slider_rect, border_radius=3)  # Tło paska

    slider_val = shared.get("ui_slider_val", 0.5)
    handle_x = slider_rect.left + int(slider_val * slider_rect.width)

    # Wypełnienie aktywne
    fill_rect = pygame.Rect(slider_rect.left, slider_rect.top, handle_x - slider_rect.left, slider_rect.height)
    pygame.draw.rect(surface, DARK_BLUE, fill_rect, border_radius=3)

    # Uchwyt
    handle_rect = pygame.Rect(handle_x - 8, slider_rect.centery - 8, 16, 16)
    pygame.draw.circle(surface, WHITE, handle_rect.center, 8)
    pygame.draw.circle(surface, DARK_BLUE, handle_rect.center, 8, 3)

    # Podpisy pod suwakiem
    # Wolno = max_interval, Szybko = min_interval
    lbl_slow = font_small.render(f"Wolno ({max_interval}s)", True, GRAY)
    lbl_fast = font_small.render(f"Szybko ({min_interval}s)", True, GRAY)

    surface.blit(lbl_slow, (slider_rect.left, slider_rect.bottom + 5))
    surface.blit(lbl_fast, (slider_rect.right - lbl_fast.get_width(), slider_rect.bottom + 5))

    # === SEKCJA 3: CZAS ===
    time_x = slider_rect.right + 40

    # Etykieta
    lbl_time_title = font_bold.render("Czas symulacji", True, BLACK)
    surface.blit(lbl_time_title, (time_x, panel_rect.top + 15))

    # Wartość
    hour = shared.get("hour", 0)
    max_h = shared.get("max_hours", 168)

    time_str = f"{hour} / {max_h + 1} [h]"
    lbl_time_val = font_ui.render(time_str, True, DARK_BLUE)  # Kolor akcentu
    surface.blit(lbl_time_val, (time_x, panel_rect.centery + 5))

    # === LOGIKA INTERAKCJI SUWAKA ===
    if _ui_state.dragging_slider:
        if not pygame.mouse.get_pressed()[0]:
            _ui_state.dragging_slider = False
        else:
            mx = min(max(mouse_pos[0], slider_rect.left), slider_rect.right)
            new_val = (mx - slider_rect.left) / slider_rect.width
            shared["ui_slider_val"] = new_val

            # Przelicz interwał
            new_interval = max_interval - new_val * (max_interval - min_interval)
            shared["sim_interval"] = new_interval

    return btn_reset, btn_play, slider_rect, handle_rect


def handle_ui_click(event, btn_reset, btn_play, slider_rect, shared, pause_evt):
    if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
        mx, my = event.pos
        if btn_reset.collidepoint((mx, my)):
            print("[UI] Kliknięto RESET")
            shared["reset_cmd"] = True
            pause_evt.set()
        elif btn_play.collidepoint((mx, my)):
            if pause_evt.is_set():
                pause_evt.clear();
                print("[UI] Wznowienie")
            else:
                pause_evt.set();
                print("[UI] Pauza")
        elif slider_rect.inflate(10, 10).collidepoint((mx, my)):
            _ui_state.dragging_slider = True
            new_val = (mx - slider_rect.left) / slider_rect.width
            shared["ui_slider_val"] = max(0.0, min(1.0, new_val))