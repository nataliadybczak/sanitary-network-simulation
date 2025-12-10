from __future__ import annotations
import threading
from collections import deque
from typing import Dict, Optional, Tuple, List
import os
import math
import warnings
import sys
import csv

os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = "1"
warnings.filterwarnings("ignore", category=UserWarning, message=".*pkg_resources is deprecated.*")
import pygame

from visualisation.map_download import get_map

# Ustalanie ścieżek absolutnych względem pliku graphics_functions.py
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, '..'))

# Dodaj root do sys.path, aby importować map_download
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

# Definicje ścieżek do danych (bezwzględne)
BOUNDS_PATH = os.path.join(PROJECT_ROOT, "data", "map_bounds.csv")
MAP_IMAGE = os.path.join(PROJECT_ROOT, "visualisation", "map.png")


def get_dynamic_map_bounds():
    """
    Sprawdza czy istnieje plik CSV i obraz mapy.
    Jeśli nie - generuje je.
    Jeśli się nie uda - ZATRZYMUJE PROGRAM.
    """
    if not os.path.exists(BOUNDS_PATH) or not os.path.exists(MAP_IMAGE):
        print(f"\n[INFO] Brak mapy lub granic. Rozpoczynam generowanie...")
        try:
            get_map()
        except Exception as e:
            print(f"[CRITICAL ERROR] Nie udało się wygenerować mapy!")
            print(f"Powód: {e}")
            print("Sprawdź czy plik 'data/wspolrzedne.csv' istnieje i czy masz internet.")
            sys.exit(1)

    try:
        with open(BOUNDS_PATH, mode='r') as f:
            reader = csv.reader(f)
            header = next(reader)
            row = next(reader)
            south, north, west, east = float(row[0]), float(row[1]), float(row[2]), float(row[3])
            print(f"[INFO] Wczytano mapę poprawnie.")
            return (south, north, east, west)
    except Exception as e:
        print(f"[ERROR] Plik granic jest uszkodzony: {e}")
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
RED = (226, 78, 78)
GREEN = (52, 199, 121)
ORANGE = (245, 165, 60)
BLUE = (66, 133, 244)
DARK_BLUE = (0, 0, 150)
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


# ====== Rysowanie wykresów ======
def draw_chart(surface: pygame.Surface, rect: pygame.Rect, points_est: deque, points_div: deque, points_rain: deque,
               max_capacity: Optional[float], current_hour: int):
    """
    Rysuje dwa osobne wykresy:
    1. Górny: Opady (Deszcz) - słupki od dołu
    2. Dolny: Przepływy (Oczyszczalnia + Przelew) - linie
    """
    # Tło całego panelu
    pygame.draw.rect(surface, LIGHT, rect, border_radius=12)
    pygame.draw.rect(surface, GRAY, rect, 2, border_radius=12)

    if not points_est:
        return

    n_points = len(points_est)

    # Marginesy wewnątrz panelu
    margin_left = 60
    margin_right = 20
    margin_top = 40
    margin_bottom = 50
    gap = 50  # Przerwa między wykresami

    # Obliczenie wysokości wykresów
    avail_h = rect.height - margin_top - margin_bottom - gap
    h_rain = int(avail_h * 0.30)  # 30% na deszcz
    h_flow = int(avail_h * 0.70)  # 70% na przepływy

    # Prostokąty wykresów
    rect_rain = pygame.Rect(rect.left + margin_left, rect.top + margin_top,
                            rect.width - margin_left - margin_right, h_rain)

    rect_flow = pygame.Rect(rect.left + margin_left, rect_rain.bottom + gap,
                            rect.width - margin_left - margin_right, h_flow)

    # Tło wykresów
    pygame.draw.rect(surface, WHITE, rect_rain)
    pygame.draw.rect(surface, WHITE, rect_flow)
    pygame.draw.rect(surface, (200, 200, 200), rect_rain, 1)
    pygame.draw.rect(surface, (200, 200, 200), rect_flow, 1)

    # Czcionki
    font_title = pygame.font.SysFont(None, 20, bold=True)
    font_label = pygame.font.SysFont(None, 16)
    font_unit = pygame.font.SysFont(None, 16, bold=True)

    # --- OŚ X (Wspólna) ---
    start_hour = max(0, current_hour - n_points + 1)
    end_hour = current_hour
    hour_range = end_hour - start_hour

    if hour_range <= 0: hour_range = 1

    # Dynamiczna podziałka X
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

    current_tick = first_tick
    while current_tick <= end_hour:
        rel_pos = (current_tick - start_hour) / hour_range
        px = rect_flow.left + int(rel_pos * rect_flow.width)

        # Linie siatki pionowej
        pygame.draw.line(surface, (240, 240, 240), (px, rect_rain.top), (px, rect_rain.bottom), 1)
        pygame.draw.line(surface, (240, 240, 240), (px, rect_flow.top), (px, rect_flow.bottom), 1)

        # Etykieta na dole
        pygame.draw.line(surface, BLACK, (px, rect_flow.bottom), (px, rect_flow.bottom + 5), 1)
        lbl = font_label.render(str(current_tick), True, BLACK)
        surface.blit(lbl, (px - lbl.get_width() // 2, rect_flow.bottom + 8))

        # Opcjonalnie: Tick na wykresie deszczu
        pygame.draw.line(surface, BLACK, (px, rect_rain.bottom), (px, rect_rain.bottom + 5), 1)

        current_tick += step_x

    # Opis osi X
    lbl_x_unit = font_unit.render("Czas symulacji [h]", True, BLACK)
    surface.blit(lbl_x_unit, (rect_flow.centerx - lbl_x_unit.get_width() // 2, rect_flow.bottom + 25))

    # === WYKRES 1: DESZCZ (GÓRNY) ===
    # Tytuł i Jednostka
    surface.blit(font_title.render("Opady", True, BLACK), (rect_rain.left, rect_rain.top - 20))
    surface.blit(font_unit.render("[mm/h]", True, BLACK), (rect_rain.left - 45, rect_rain.top + 20))

    # Skala Y Deszczu
    rain_vals = [v for _, v in points_rain]
    max_rain = max(10.0, max(rain_vals) * 1.2) if rain_vals else 10.0

    # Siatka Y Deszczu (3 linie) - RYSOWANA OD DOŁU
    for i in range(4):
        val = max_rain * (i / 3.0)
        # 0 na dole (bottom), max na górze (top)
        py = rect_rain.bottom - int((val / max_rain) * rect_rain.height)

        pygame.draw.line(surface, (230, 230, 230), (rect_rain.left, py), (rect_rain.right, py))
        lbl = font_label.render(f"{val:.1f}", True, GRAY)
        surface.blit(lbl, (rect_rain.left - lbl.get_width() - 5, py - lbl.get_height() // 2))

    # Rysowanie danych deszczu (Słupki od dołu)
    if n_points > 1:
        for i, (_, val) in enumerate(points_rain):
            rel_x = i / (n_points - 1)
            px = rect_rain.left + int(rel_x * rect_rain.width)
            h = int((val / max_rain) * rect_rain.height)
            if h > 0:
                # Rysujemy od dołu w górę
                pygame.draw.line(surface, DARK_BLUE, (px, rect_rain.bottom), (px, rect_rain.bottom - h), 2)

    # === WYKRES 2: PRZEPŁYWY (DOLNY) ===
    # Tytuł i Jednostka
    surface.blit(font_title.render("Przepływ", True, BLACK), (rect_flow.left, rect_flow.top - 20))
    surface.blit(font_unit.render("[m3/h]", True, BLACK), (rect_flow.left - 45, rect_flow.top + 20))

    # Skala Y Przepływów
    flow_est_vals = [v for _, v in points_est]
    flow_div_vals = [v for _, v in points_div]
    all_flows = flow_est_vals + flow_div_vals
    if max_capacity: all_flows.append(max_capacity)

    # Dynamiczna skala
    max_flow = max(100.0, max(all_flows) * 1.1)

    # Siatka Y Przepływów (5 linii)
    for i in range(5):
        val = max_flow * (i / 4.0)
        py = rect_flow.bottom - int((val / max_flow) * rect_flow.height)
        pygame.draw.line(surface, (230, 230, 230), (rect_flow.left, py), (rect_flow.right, py))
        lbl = font_label.render(f"{val:.0f}", True, GRAY)
        surface.blit(lbl, (rect_flow.left - lbl.get_width() - 5, py - lbl.get_height() // 2))

    # Linia Max Capacity
    if max_capacity:
        py_cap = rect_flow.bottom - int((max_capacity / max_flow) * rect_flow.height)
        if rect_flow.top <= py_cap <= rect_flow.bottom:
            pygame.draw.line(surface, RED, (rect_flow.left, py_cap), (rect_flow.right, py_cap), 1)
            lbl_cap = font_label.render("Limit", True, RED)
            surface.blit(lbl_cap, (rect_flow.right - lbl_cap.get_width() - 5, py_cap - 12))

    # Funkcja mapująca punkt (i -> x, val -> y)
    def get_pt(idx, val, r, max_v):
        rel_x = idx / (n_points - 1) if n_points > 1 else 0
        px = r.left + int(rel_x * r.width)
        py = r.bottom - int((val / max_v) * r.height)
        return px, py

    # Rysowanie linii Est (Oczyszczalnia)
    if n_points > 1:
        pts_est = [get_pt(i, v, rect_flow, max_flow) for i, (_, v) in enumerate(points_est)]
        pygame.draw.lines(surface, BLUE, False, pts_est, 2)

        # Rysowanie linii Div (Przelew) - jeśli są jakiekolwiek wartości
        if any(v > 0 for _, v in points_div):
            pts_div = [get_pt(i, v, rect_flow, max_flow) for i, (_, v) in enumerate(points_div)]
            pygame.draw.lines(surface, ORANGE, False, pts_div, 2)

    # Legenda (wewnątrz wykresu przepływów)
    leg_x = rect_flow.right - 120
    leg_y = rect_flow.top + 10

    # Oczyszczalnia
    pygame.draw.line(surface, BLUE, (leg_x, leg_y), (leg_x + 20, leg_y), 2)
    surface.blit(font_label.render("Oczyszczalnia", True, BLACK), (leg_x + 25, leg_y - 5))

    # Przelew
    pygame.draw.line(surface, ORANGE, (leg_x, leg_y + 20), (leg_x + 20, leg_y + 20), 2)
    surface.blit(font_label.render("Przelew", True, BLACK), (leg_x + 25, leg_y + 15))


# ====== Rysowanie mapy (Bez zmian) ======
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

    # 1. Rysowanie połączeń (strzałek)
    for (start_loc, end_loc, flow) in connections:
        sx, sy = apply_view(*start_loc)
        ex, ey = apply_view(*end_loc)
        col = (50, 50, 200) if flow > 1.0 else (180, 180, 180)
        thick = 2 if flow > 1.0 else 1
        draw_arrow(surface, (sx, sy), (ex, ey), col, thick)

    font = pygame.font.SysFont(None, 16)
    font_small = pygame.font.SysFont(None, 14)

    # 1.5. Extra points (nieaktywne)
    for pid, lat, lon in extra_points:
        x, y = apply_view(lat, lon)
        pygame.draw.circle(surface, (180, 180, 180), (x, y), 5)
        # Nazwa punktu
        lbl = font_small.render(str(pid), True, (100, 100, 100))
        surface.blit(lbl, (x + 6, y - 6))

    # 2. Sensory (Kółka)
    SENSOR_RADIUS = 7
    for sid, lat, lon, flow, status in sensors:
        x, y = apply_view(lat, lon)
        color = GREEN if status == "NORMAL" else RED

        # Tylko kółko w kolorze statusu
        pygame.draw.circle(surface, color, (x, y), SENSOR_RADIUS)

        # Etykieta
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

    # 4. Oczyszczalnia (Kwadrat)
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

        if est > hyd:
            draw_blob(surface, x, y, 50, BROWN, alpha=100)

        # IKONA OCZYSZCZALNI
        PLANT_RADIUS = 12
        # 1. Białe tło
        pygame.draw.circle(surface, WHITE, (x, y), PLANT_RADIUS)
        # 2. Zewnętrzny pierścień
        pygame.draw.circle(surface, p_col, (x, y), PLANT_RADIUS, 3)
        # 3. Wewnętrzne kółko
        pygame.draw.circle(surface, p_col, (x, y), PLANT_RADIUS - 5)

        # PASEK POSTĘPU PO PRAWEJ
        bar_h = 36
        bar_w = 8
        fill_pct = min(1.0, est / (hyd * 1.2))

        bx = x + PLANT_RADIUS + 6
        by = y - (bar_h // 2)

        pygame.draw.rect(surface, WHITE, (bx, by, bar_w, bar_h))
        pygame.draw.rect(surface, BLACK, (bx, by, bar_w, bar_h), 1)
        fill_h = int(fill_pct * bar_h)
        pygame.draw.rect(surface, p_col, (bx + 1, by + bar_h - fill_h, bar_w - 2, fill_h))

        # Etykieta pod ikoną
        lbl_ocz = font.render(f"OCZ: {est:.0f}", True, BLACK)
        lbl_x = x - (lbl_ocz.get_width() // 2)
        lbl_y = y + PLANT_RADIUS + 4
        surface.blit(lbl_ocz, (lbl_x, lbl_y))

    surface.set_clip(None)
    pygame.draw.rect(surface, GRAY, rect, 2, border_radius=12)

    # 5. Panel informacyjny (HUD) na mapie - DESZCZ
    hud_w, hud_h = 160, 110
    hud_x, hud_y = rect.right - hud_w - 20, rect.top + 20

    # Tło panelu
    pygame.draw.rect(surface, (255, 255, 255, 230), (hud_x, hud_y, hud_w, hud_h), border_radius=8)
    pygame.draw.rect(surface, GRAY, (hud_x, hud_y, hud_w, hud_h), 1, border_radius=8)

    r_int = rain.get("intensity", 0.0)
    r_dep = rain.get("depth", 0.0)

    # --- TEXT (Lewa strona) ---
    title_f = pygame.font.SysFont(None, 20, bold=True)
    val_f = pygame.font.SysFont(None, 18)

    surface.blit(title_f.render("Opady", True, BLACK), (hud_x + 10, hud_y + 10))

    # Aktualne
    lbl_cur = val_f.render(f"Akt.: {r_int:.1f}", True, BLACK)
    surface.blit(lbl_cur, (hud_x + 10, hud_y + 35))
    surface.blit(val_f.render("mm/h", True, GRAY), (hud_x + 10, hud_y + 50))

    # Sumaryczne
    lbl_sum = val_f.render(f"Sum.: {r_dep:.1f}", True, BLACK)
    surface.blit(lbl_sum, (hud_x + 10, hud_y + 70))
    surface.blit(val_f.render("mm", True, GRAY), (hud_x + 10, hud_y + 85))

    # --- SUWAK / GAUGE (Prawa strona) ---
    bar_x = hud_x + 100
    bar_y = hud_y + 15
    bar_w = 15
    bar_h = 80
    max_val = 40.0

    # 1. Rysowanie Gradientu (AliceBlue -> Navy)
    c_start = (240, 248, 255)
    c_end = (0, 0, 128)

    for i in range(bar_h):
        t = i / bar_h
        r = int(c_start[0] + (c_end[0] - c_start[0]) * t)
        g = int(c_start[1] + (c_end[1] - c_start[1]) * t)
        b = int(c_start[2] + (c_end[2] - c_start[2]) * t)

        line_y = bar_y + bar_h - i
        pygame.draw.line(surface, (r, g, b), (bar_x, line_y), (bar_x + bar_w, line_y))

    pygame.draw.rect(surface, BLACK, (bar_x, bar_y, bar_w, bar_h), 1)

    # 2. Znaczniki (Progi) po prawej
    font_tiny = pygame.font.SysFont(None, 14)
    steps = [0, 10, 20, 30, 40]
    for val in steps:
        pct = val / max_val
        py = bar_y + bar_h - int(pct * bar_h)
        pygame.draw.line(surface, BLACK, (bar_x + bar_w, py), (bar_x + bar_w + 4, py))
        lbl = font_tiny.render(str(val), True, BLACK)
        surface.blit(lbl, (bar_x + bar_w + 6, py - 4))

    # 3. Trójkącik wskaźnika
    curr_val = max(0.0, min(max_val, r_int))
    curr_pct = curr_val / max_val
    curr_y = bar_y + bar_h - int(curr_pct * bar_h)

    tri_pts = [
        (bar_x, curr_y),
        (bar_x - 6, curr_y - 4),
        (bar_x - 6, curr_y + 4)
    ]
    pygame.draw.polygon(surface, RED, tri_pts)
    pygame.draw.polygon(surface, BLACK, tri_pts, 1)


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
    panel_rect = pygame.Rect(rect.centerx - 250, rect.bottom - 70, 500, 60)
    pygame.draw.rect(surface, UI_BG, panel_rect, border_radius=15)
    pygame.draw.rect(surface, UI_BORDER, panel_rect, 2, border_radius=15)

    mouse_pos = pygame.mouse.get_pos()
    is_paused = pause_evt.is_set()

    # Reset
    btn_reset = pygame.Rect(panel_rect.left + 20, panel_rect.centery - 15, 30, 30)
    col_reset = BUTTON_HOVER if btn_reset.collidepoint(mouse_pos) else UI_BG
    pygame.draw.rect(surface, col_reset, btn_reset, border_radius=5)
    pygame.draw.rect(surface, BLACK, btn_reset, 2, border_radius=5)
    pygame.draw.rect(surface, RED, (btn_reset.centerx - 6, btn_reset.centery - 6, 12, 12))

    # Play/Pause
    btn_play = pygame.Rect(panel_rect.left + 65, panel_rect.centery - 20, 40, 40)
    col_play = BUTTON_HOVER if btn_play.collidepoint(mouse_pos) else UI_BG
    pygame.draw.circle(surface, col_play, btn_play.center, 20)
    pygame.draw.circle(surface, BLACK, btn_play.center, 20, 2)

    if is_paused:
        pts = [(btn_play.centerx - 5, btn_play.centery - 8),
               (btn_play.centerx - 5, btn_play.centery + 8),
               (btn_play.centerx + 8, btn_play.centery)]
        pygame.draw.polygon(surface, GREEN, pts)
    else:
        pygame.draw.rect(surface, BLACK, (btn_play.centerx - 6, btn_play.centery - 8, 4, 16))
        pygame.draw.rect(surface, BLACK, (btn_play.centerx + 2, btn_play.centery - 8, 4, 16))

    # Slider
    slider_val = shared.get("ui_slider_val", 0.5)
    slider_rect = pygame.Rect(panel_rect.left + 130, panel_rect.centery - 4, 180, 8)
    pygame.draw.rect(surface, SLIDER_BG, slider_rect, border_radius=4)
    handle_x = slider_rect.left + int(slider_val * slider_rect.width)
    fill_rect = pygame.Rect(slider_rect.left, slider_rect.top, handle_x - slider_rect.left, slider_rect.height)
    pygame.draw.rect(surface, SLIDER_FILL, fill_rect, border_radius=4)

    handle_rect = pygame.Rect(handle_x - 8, slider_rect.centery - 8, 16, 16)
    pygame.draw.circle(surface, BLUE, handle_rect.center, 8)
    pygame.draw.circle(surface, BLACK, handle_rect.center, 8, 1)

    font_small = pygame.font.SysFont(None, 16)
    surface.blit(font_small.render("Wolno", True, GRAY), (slider_rect.left, slider_rect.bottom + 5))
    surface.blit(font_small.render("Szybko", True, GRAY), (slider_rect.right - 35, slider_rect.bottom + 5))

    # Status
    hour = shared.get("hour", 0)
    max_h = shared.get("max_hours", 168)
    font_status = pygame.font.SysFont(None, 24, bold=True)
    status_text = f"Godzina: {hour} / {max_h + 1}"
    txt_surf = font_status.render(status_text, True, BLACK)
    surface.blit(txt_surf,
                 (panel_rect.right - 10 - txt_surf.get_width(), panel_rect.centery - txt_surf.get_height() // 2))

    if _ui_state.dragging_slider:
        if not pygame.mouse.get_pressed()[0]:
            _ui_state.dragging_slider = False
        else:
            mx = min(max(mouse_pos[0], slider_rect.left), slider_rect.right)
            new_val = (mx - slider_rect.left) / slider_rect.width
            shared["ui_slider_val"] = new_val
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