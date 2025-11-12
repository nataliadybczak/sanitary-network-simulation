from __future__ import annotations
import threading
from collections import deque
from typing import Dict, Optional, Tuple
import pygame

# ====== Konfiguracja UI ======
WINDOW_W, WINDOW_H = 1280, 720
LEFT_W = int(WINDOW_W * 0.62)
RIGHT_W = WINDOW_W - LEFT_W
MARGIN = 12
MAP_RECT   = pygame.Rect(MARGIN, MARGIN, LEFT_W - 2*MARGIN,  WINDOW_H - 2*MARGIN)
CHART_RECT = pygame.Rect(LEFT_W + MARGIN, MARGIN, RIGHT_W - 2*MARGIN, WINDOW_H - 2*MARGIN)
FPS = 60
CHART_MAX_POINTS = 600

# Zakres geograficzny mapy (dopasuj do swoich współrzędnych)
# (min_lat, max_lat, min_lon, max_lon)
# MAP_BOUNDS = (49.6700, 49.7000, 19.1900, 19.2300)
# map_download.get_map(*MAP_BOUNDS)
MAP_BOUNDS = ( 49.6600,49.7150, 19.2600 ,19.1700)
MAP_IMAGE = "visualisation/map.png"

# Kolory
WHITE=(255,255,255); BLACK=(25,25,25); GRAY=(140,140,140); LIGHT=(236,240,245)
RED=(226,78,78); GREEN=(52,199,121); ORANGE=(245,165,60); BLUE=(66,133,244)

# ====== Pomocnicze ======
def geo_to_px(lat: float, lon: float, rect: pygame.Rect, bounds=MAP_BOUNDS) -> Tuple[int, int]:
    min_lat, max_lat, min_lon, max_lon = bounds
    nx = (lon - min_lon) / (max_lon - min_lon)
    ny = (max_lat - lat) / (max_lat - min_lat)
    x = int(rect.right - nx * rect.width)
    y = int(rect.top  + ny * rect.height)
    return x, y


# ====== Rysowanie wykresu ======
def draw_chart(surface: pygame.Surface, rect: pygame.Rect, points_est: deque, points_div: deque, max_capacity: Optional[float]):
    # Tło panelu
    pygame.draw.rect(surface, LIGHT, rect, border_radius=12)
    pygame.draw.rect(surface, GRAY,  rect, 2, border_radius=12)

    if not points_est:
        return

    # Marginesy pod osie i opisy
    pad_left   = 64
    pad_right  = 24
    pad_top    = 28
    pad_bottom = 56

    plot = pygame.Rect(
        rect.left + pad_left,
        rect.top  + pad_top,
        rect.width  - (pad_left + pad_right),
        rect.height - (pad_top   + pad_bottom)
    )

    pygame.draw.rect(surface, WHITE, plot, border_radius=8)
    pygame.draw.rect(surface, (210,210,210), plot, 1, border_radius=8)

    # Zakres Y
    all_vals = [v for _, v in points_est] + ([v for _, v in points_div] if points_div else [])
    if max_capacity is not None:
        all_vals.append(max_capacity)
    vmin, vmax = 0.0, max(10.0, max(all_vals) * 1.05)

    # Mapa punktów do pikseli
    def xy_from_index(i: int, val: float, n: int):
        x = plot.left if n <= 1 else plot.left + int(i * (plot.width - 1) / (n - 1))
        y = plot.bottom - int((val - vmin) / (vmax - vmin) * (plot.height - 1))
        return x, y

    # Siatka + podziałka osi Y (5 poziomów)
    font_ticks = pygame.font.SysFont(None, 18)
    y_ticks = 5
    for j in range(y_ticks + 1):
        frac = j / y_ticks  # 0..1
        y = plot.bottom - int(frac * (plot.height - 1))
        pygame.draw.line(surface, (232, 232, 232), (plot.left, y), (plot.right, y), 1)
        # Etykieta Y
        val = vmin + frac * (vmax - vmin)
        label = font_ticks.render(f"{val:.0f}", True, BLACK)
        surface.blit(label, (plot.left - 8 - label.get_width(), y - label.get_height() // 2))

    # Linia limitu
    if max_capacity is not None and vmax > vmin:
        y_lim = plot.bottom - int((max_capacity - vmin) / (vmax - vmin) * (plot.height - 1))
        pygame.draw.line(surface, RED, (plot.left, y_lim), (plot.right, y_lim), 2)

    # Serie
    n = len(points_est)
    # Estimated (niebieski)
    last = None
    for i, (_, val) in enumerate(points_est):
        p = xy_from_index(i, val, n)
        if last:
            pygame.draw.line(surface, BLUE, last, p, 2)
        last = p
    # Diverted (pomarańczowy)
    if points_div:
        last = None
        for i, (_, val) in enumerate(points_div):
            p = xy_from_index(i, val, n)
            if last:
                pygame.draw.line(surface, ORANGE, last, p, 2)
            last = p

    # Oś X
    x_tick_font = font_ticks
    x_ticks = min(6, max(2, n))
    if x_ticks > 2:
        step = (n - 1) / (x_ticks - 1)
        tick_idx = [int(round(i * step)) for i in range(x_ticks)]
    else:
        tick_idx = [0, n - 1]
    tick_idx = sorted(set([0, n - 1] + tick_idx))

    for i in tick_idx:
        x, _ = xy_from_index(i, vmin, n)  # y nieistotne do kreski
        pygame.draw.line(surface, (180, 180, 180), (x, plot.bottom), (x, plot.bottom + 6), 2)
        lbl = x_tick_font.render(str(i), True, BLACK)
        surface.blit(lbl, (x - lbl.get_width() // 2, plot.bottom + 8))

    # Osie
    font_axis = pygame.font.SysFont(None, 20)
    x_label = font_axis.render("Czas [h]", True, BLACK)
    surface.blit(x_label, (plot.centerx - x_label.get_width() // 2, rect.bottom - pad_bottom + 28))
    y_label = font_axis.render("Przepływ [m³/h]", True, BLACK)
    y_label_rot = pygame.transform.rotate(y_label, 90)
    surface.blit(y_label_rot, (rect.left + 12, plot.centery - y_label_rot.get_height() // 2))

    # Tytuł
    font_title = pygame.font.SysFont(None, 20)
    # title = font_title.render("Przepływ — Estimated (nieb.) / Diverted (pomar.)", True, BLACK)
    title = font_title.render("Przepływ w czasie", True, BLACK)
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

    sw, sh = int(rect.width * s), int(rect.height * s)
    img = pygame.transform.smoothscale(srf, (sw, sh))
    surface.fill((244, 247, 252), rect)
    surface.blit(img, (rect.left + ox, rect.top + oy))
    pygame.draw.rect(surface, GRAY, rect, 2, border_radius=12)

    font = pygame.font.SysFont(None, 18)

    def apply_view(x, y):
        x = rect.left + ox + int((x - rect.left) * s)
        y = rect.top + oy + int((y - rect.top) * s)
        return x, y

    for sid, lat, lon, flow, status in sensors:
        x0, y0 = geo_to_px(lat, lon, rect)
        x, y = apply_view(x0, y0)
        color = GREEN if status == "NORMAL" else RED
        pygame.draw.circle(surface, color, (x, y), 7)
        surface.blit(font.render(f"{sid} {flow:.0f} m³/h", True, BLACK), (x + 10, y - 8))

    if overflow:
        oid, lat, lon, active, diverted = overflow
        x0, y0 = geo_to_px(lat, lon, rect)
        x, y = apply_view(x0, y0)
        pygame.draw.circle(surface, RED if active else GRAY, (x, y), 8)
        surface.blit(font.render(f"Overflow {oid} {diverted:.0f} m³/h", True, BLACK), (x + 10, y - 8))

    if plant:
        plat, plon, est = plant
        x0, y0 = geo_to_px(plat, plon, rect)
        x, y = apply_view(x0, y0)
        pygame.draw.rect(surface, BLACK, (x - 6, y - 6, 12, 12))
        surface.blit(font.render(f"Sewage Plant {est:.0f} m³/h", True, BLACK), (x + 10, y - 8))
