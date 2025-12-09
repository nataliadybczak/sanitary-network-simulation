from __future__ import annotations
import threading
from collections import deque
from typing import Dict, Optional, Tuple, List
import os
import math
import csv
import sys
import warnings

os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = "1"
warnings.filterwarnings("ignore", category=UserWarning, message=".*pkg_resources is deprecated.*")
import pygame

# ====== Konfiguracja UI ======
WINDOW_W, WINDOW_H = 1280, 720
FPS = 60
CHART_MAX_POINTS = 600

# Kolory UI
UI_BG = (240, 240, 240)
UI_BORDER = (180, 180, 180)
BUTTON_HOVER = (220, 225, 230)
BUTTON_ACTIVE = (200, 205, 210)
SLIDER_BG = (200, 200, 200)
SLIDER_FILL = (100, 160, 220)

# Kolory ogólne
WHITE = (255, 255, 255);
BLACK = (25, 25, 25);
GRAY = (140, 140, 140);
LIGHT = (236, 240, 245)
RED = (226, 78, 78);
GREEN = (52, 199, 121);
ORANGE = (245, 165, 60);
BLUE = (66, 133, 244)
DARK_RED = (150, 20, 20);
YELLOW = (240, 230, 50)
BROWN = (139, 69, 19)

# ====== Obsługa Mapy (Lazy Loading) ======
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, '..'))

if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

BOUNDS_PATH = os.path.join(PROJECT_ROOT, "data", "map_bounds.csv")
MAP_IMAGE_PATH = os.path.join(PROJECT_ROOT, "visualisation", "map.png")
_CACHED_BOUNDS = None  # Zmienna globalna do przechowywania załadowanych granic


def ensure_map_ready():
    """Leniwa inicjalizacja: Sprawdza/Generuje mapę tylko wtedy, gdy jest potrzebna."""
    global _CACHED_BOUNDS
    if _CACHED_BOUNDS is not None:
        return _CACHED_BOUNDS

    # Sprawdź czy pliki istnieją
    if not os.path.exists(BOUNDS_PATH) or not os.path.exists(MAP_IMAGE_PATH):
        try:
            # Importujemy tylko w momencie potrzeby generowania
            from map_download import get_map
            print("\n[INFO] Brak mapy lub granic. Rozpoczynam generowanie...")
            get_map()
        except ImportError:
            print("[ERROR] Nie znaleziono pliku map_download.py.")
            sys.exit(1)
        except Exception as e:
            print(f"\n[CRITICAL ERROR] Nie udało się wygenerować mapy: {e}")
            sys.exit(1)

    # Odczytaj wartości
    try:
        with open(BOUNDS_PATH, mode='r') as f:
            reader = csv.reader(f)
            next(reader)  # header
            row = next(reader)
            # Kolejność w map_download: south, north, west, east
            south, north, west, east = float(row[0]), float(row[1]), float(row[2]), float(row[3])
            _CACHED_BOUNDS = (south, north, west, east)
            return _CACHED_BOUNDS
    except Exception as e:
        print(f"[ERROR] Plik granic uszkodzony: {e}")
        sys.exit(1)


# ====== Pomocnicze ======
def geo_to_px(lat: float, lon: float, rect: pygame.Rect) -> Tuple[int, int]:
    # Pobieramy granice "na żądanie"
    bounds = ensure_map_ready()
    min_lat, max_lat, min_lon, max_lon = bounds  # south, north, west, east

    # Uwaga: dla contextily/matplotlib south=min_lat, north=max_lat
    # więc bounds = (min_lat, max_lat, min_lon, max_lon)

    nx = (lon - min_lon) / (max_lon - min_lon)
    ny = (max_lat - lat) / (max_lat - min_lat)

    x = int(rect.left + nx * rect.width)  # Zmienione: mapnik rysuje od lewej (west) do prawej (east)
    y = int(rect.bottom - ny * rect.height)  # Zmienione: Y rośnie w dół, a lat rośnie w górę

    # Korekta: w poprzedniej wersji było odwrotnie, ale contextily daje normalną mapę.
    # Jeśli mapa jest "do góry nogami", odwróćmy 'y'
    # Standardowy układ:
    # x = left + (lon - min_lon)/(range_lon) * width
    # y = bottom - (lat - min_lat)/(range_lat) * height

    return x, y


def draw_arrow(surface, start, end, color, width=2):
    pygame.draw.line(surface, color, start, end, width)
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
    pygame.draw.rect(surface, LIGHT, rect, border_radius=12)
    pygame.draw.rect(surface, GRAY, rect, 2, border_radius=12)

    if not points_est:
        return

    pad_left, pad_right, pad_top, pad_bottom = 64, 24, 28, 56
    plot = pygame.Rect(rect.left + pad_left, rect.top + pad_top, rect.width - (pad_left + pad_right),
                       rect.height - (pad_top + pad_bottom))

    pygame.draw.rect(surface, WHITE, plot, border_radius=8)
    pygame.draw.rect(surface, (210, 210, 210), plot, 1, border_radius=8)

    all_vals = [v for _, v in points_est] + ([v for _, v in points_div] if points_div else [])
    if max_capacity: all_vals.append(max_capacity)
    vmin, vmax = 0.0, max(10.0, max(all_vals) * 1.1)

    n = len(points_est)

    def xy(i, val, n_pts, y_min, y_max, p_rect):
        if n_pts <= 1:
            x = p_rect.left
        else:
            x = p_rect.left + int(i * (p_rect.width - 1) / (n_pts - 1))

        if y_max == y_min:
            y = p_rect.bottom
        else:
            y = p_rect.bottom - int((val - y_min) / (y_max - y_min) * (p_rect.height - 1))
        return x, y

    # Deszcz
    if points_rain:
        rain_vals = [v for _, v in points_rain]
        max_r = max(1.0, max(rain_vals) * 2)

        for i, (_, val) in enumerate(points_rain):
            if n > 1:
                x = plot.left + int(i * (plot.width - 1) / (n - 1))
            else:
                x = plot.left
            h = int((val / max_r) * (plot.height * 0.3))
            if h > 0:
                pygame.draw.line(surface, (100, 100, 200), (x, plot.top), (x, plot.top + h), 2)

    # Siatka
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

    # Serie
    last_e, last_d = None, None
    for i in range(n):
        pe = xy(i, points_est[i][1], n, vmin, vmax, plot)
        if last_e: pygame.draw.line(surface, BLUE, last_e, pe, 2)
        last_e = pe

        if points_div:
            pd = xy(i, points_div[i][1], n, vmin, vmax, plot)
            if last_d: pygame.draw.line(surface, ORANGE, last_d, pd, 2)
            last_d = pd

    title = pygame.font.SysFont(None, 20).render("Przepływ (Linia) | Deszcz (Słupki z góry)", True, BLACK)
    surface.blit(title, (plot.left, rect.top + 6))


# ====== Rysowanie mapy ======
def draw_map(surface: pygame.Surface, rect: pygame.Rect, shared: Dict, lock: threading.Lock):
    ensure_map_ready()  # Upewniamy się, że mapa jest załadowana

    if not hasattr(draw_map, "_bg"):
        if os.path.exists(MAP_IMAGE_PATH):
            draw_map._bg = pygame.image.load(MAP_IMAGE_PATH).convert()
        else:
            # Fallback (czarne tło jeśli brak pliku)
            draw_map._bg = pygame.Surface((800, 600))

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

    # 1.5. Extra points (nieaktywne)
    for pid, lat, lon in extra_points:
        x, y = apply_view(lat, lon)
        pygame.draw.circle(surface, (180, 180, 180), (x, y), 5)
        pygame.draw.circle(surface, (100, 100, 100), (x, y), 5, 1)
        lbl = font_small.render(str(pid), True, (100, 100, 100))
        surface.blit(lbl, (x + 6, y - 6))

    # 2. Sensory
    for sid, lat, lon, flow, status in sensors:
        x, y = apply_view(lat, lon)
        color = GREEN if status == "NORMAL" else RED
        pygame.draw.circle(surface, color, (x, y), 7)
        pygame.draw.circle(surface, BLACK, (x, y), 7, 1)
        lbl = font.render(f"{sid}", True, BLACK)
        surface.blit(lbl, (x + 8, y - 8))
        lbl_flow = font.render(f"{flow:.0f}", True, (50, 50, 50))
        surface.blit(lbl_flow, (x + 8, y + 4))

    # 3. Przelew
    if overflow:
        oid, lat, lon, active, diverted = overflow
        x, y = apply_view(lat, lon)
        if diverted > 0: draw_blob(surface, x, y, 40, BLUE, alpha=80)
        col = ORANGE if active else GRAY
        draw_triangle(surface, x, y, 9, col)
        pygame.draw.polygon(surface, BLACK, [(x, y - 9), (x - 9, y + 9), (x + 9, y + 9)], 1)
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
        draw_square(surface, x, y, 10, p_col)
        pygame.draw.rect(surface, BLACK, (x - 10, y - 10, 20, 20), 1)

        # Pasek napełnienia
        bar_h, bar_w = 40, 6
        fill_pct = min(1.0, est / (hyd * 1.2))
        bx, by = x + 15, y - 10
        pygame.draw.rect(surface, WHITE, (bx, by, bar_w, bar_h))
        pygame.draw.rect(surface, BLACK, (bx, by, bar_w, bar_h), 1)
        fill_h = int(fill_pct * bar_h)
        pygame.draw.rect(surface, p_col, (bx + 1, by + bar_h - fill_h, bar_w - 2, fill_h))
        surface.blit(font.render(f"OCZ: {est:.0f}", True, BLACK), (x - 20, y + 14))

    surface.set_clip(None)
    pygame.draw.rect(surface, GRAY, rect, 2, border_radius=12)

    # HUD Deszczu
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

    if r_int > 0.1:
        col_rain = (0, 0, 150) if r_int > 5.0 else BLUE
        pygame.draw.circle(surface, col_rain, (hud_x + 55, hud_y + 80), 10 if r_int <= 5.0 else 6)
    else:
        pygame.draw.circle(surface, GRAY, (hud_x + 55, hud_y + 80), 10, 1)


# ====== UI CONTROLS ======
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

    # 1. Reset
    btn_reset = pygame.Rect(panel_rect.left + 20, panel_rect.centery - 15, 30, 30)
    col_reset = BUTTON_HOVER if btn_reset.collidepoint(mouse_pos) else UI_BG
    pygame.draw.rect(surface, col_reset, btn_reset, border_radius=5)
    pygame.draw.rect(surface, BLACK, btn_reset, 2, border_radius=5)
    pygame.draw.rect(surface, RED, (btn_reset.centerx - 6, btn_reset.centery - 6, 12, 12))

    # 2. Play/Pause
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

    # 3. Slider
    slider_val = shared.get("ui_slider_val", 0.5)
    slider_rect = pygame.Rect(panel_rect.left + 130, panel_rect.centery - 4, 180, 8)
    pygame.draw.rect(surface, SLIDER_BG, slider_rect, border_radius=4)
    handle_x = slider_rect.left + int(slider_val * slider_rect.width)
    pygame.draw.rect(surface, SLIDER_FILL,
                     (slider_rect.left, slider_rect.top, handle_x - slider_rect.left, slider_rect.height),
                     border_radius=4)
    handle_rect = pygame.Rect(handle_x - 8, slider_rect.centery - 8, 16, 16)
    pygame.draw.circle(surface, BLUE, handle_rect.center, 8)
    pygame.draw.circle(surface, BLACK, handle_rect.center, 8, 1)

    font_small = pygame.font.SysFont(None, 16)
    surface.blit(font_small.render("Wolno", True, GRAY), (slider_rect.left, slider_rect.bottom + 5))
    surface.blit(font_small.render("Szybko", True, GRAY), (slider_rect.right - 35, slider_rect.bottom + 5))

    # 4. Text
    hour = shared.get("hour", 0)
    max_h = shared.get("max_hours", 168)
    font_status = pygame.font.SysFont(None, 24, bold=True)
    status_text = f"Godzina: {hour} / {max_h}"
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