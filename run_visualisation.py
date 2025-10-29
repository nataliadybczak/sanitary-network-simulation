"""
Minimalny front-end Pygame do Twojego istniejącego modelu i funkcji.
Założenia:
- Wszystkie funkcje/klasy użyte w Twoim kodzie (np. SewerSystemModel, struktury sensorów,
  overflow_point, plant, datacollector.get_model_vars_dataframe) JUŻ ISTNIEJĄ.
- Ten plik dodaje wyłącznie warstwę wyświetlania (okno Pygame) + wątek symulacji.
- Mapa po lewej (punkty pomiarowe), wykres scrollowany po prawej (Estimated/Diverted Flow).
- W terminalu wypisuje się wszystko, co wypisuje Twój model/skrypt.

Sterowanie:
  [SPACE] Pauza/Wznów   |   [ESC] Wyjście   |   [X] Zamknij okno
"""
from __future__ import annotations
import threading
import time
from collections import deque
from typing import Dict, Optional, Tuple
import map_download

import pygame
import pandas as pd
from model.model import SewerSystemModel

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
MAP_IMAGE = "map.png"

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

# ====== Wątek symulacji ======
class SimulationThread(threading.Thread):
    def __init__(self, model: SewerSystemModel, interval: float, shared: Dict, lock: threading.Lock,
                 stop_evt: threading.Event, pause_evt: threading.Event):
        super().__init__(daemon=True)
        self.model = model
        self.interval = interval
        self.shared = shared
        self.lock = lock
        self.stop_evt = stop_evt
        self.pause_evt = pause_evt

    def run(self):
        print("[SIM] start")
        try:
            while not self.stop_evt.is_set() and self.model.running:
                if not self.pause_evt.is_set():
                    self.model.step()  # wszystko co wypisuje model, pojawi się w terminalu

                    # Zrzut stanu do współdzielonych danych (wyłącznie odczyty wykorzystywane w UI)
                    df = self.model.datacollector.get_model_vars_dataframe()
                    est = float(df["Estimated Flow"].iloc[-1]) if not df.empty else 0.0
                    div = float(df["Diverted Flow"].iloc[-1]) if (not df.empty and "Diverted Flow" in df.columns) else 0.0

                    snapshot = {
                        "sensors": [(s.location_id, s.location[0], s.location[1], getattr(s, 'current_flow', 0.0), getattr(s, 'status', 'NORMAL')) for s in self.model.sensors],
                        "overflow": (self.model.overflow_point.location_id, self.model.overflow_point.location[0], self.model.overflow_point.location[1], getattr(self.model.overflow_point, 'active', False), getattr(self.model.overflow_point, 'diverted_flow', 0.0)),
                        "plant": (self.model.plant.location[0], self.model.plant.location[1], getattr(self.model.plant, 'estimated_flow', 0.0)),
                        "point": (pd.Timestamp.now().to_pydatetime(), est, div),
                        "max_capacity": self.model.max_capacity,
                        "running": self.model.running,
                        "hour": self.model.current_hour,
                    }
                    with self.lock:
                        self.shared.update(snapshot)
                time.sleep(self.interval)
        except Exception as e:
            print("[SIM] błąd wątku:", e)
        finally:
            print("[SIM] stop")

# ====== Rysowanie wykresu ======

def draw_chart(surface: pygame.Surface, rect: pygame.Rect, points_est: deque, points_div: deque, max_capacity: Optional[float]):
    pygame.draw.rect(surface, LIGHT, rect, border_radius=12)
    pygame.draw.rect(surface, GRAY,  rect, 2, border_radius=12)

    if not points_est:
        return

    pad = 28
    plot = pygame.Rect(rect.left+pad, rect.top+pad, rect.width-2*pad, rect.height-2*pad)
    pygame.draw.rect(surface, WHITE, plot, border_radius=8)
    pygame.draw.rect(surface, (210,210,210), plot, 1, border_radius=8)

    all_vals = [v for _, v in points_est] + ([v for _, v in points_div] if points_div else [])
    if max_capacity is not None:
        all_vals.append(max_capacity)
    vmin, vmax = 0.0, max(10.0, max(all_vals)*1.05)

    def xy_from_index(i: int, val: float, n: int):
        x = plot.left if n<=1 else plot.left + int(i*(plot.width-1)/(n-1))
        y = plot.bottom - int((val - vmin)/(vmax - vmin) * (plot.height-1))
        return x, y

    # siatka
    for frac in [0.0, 0.25, 0.5, 0.75, 1.0]:
        y = plot.bottom - int(frac*(plot.height-1))
        pygame.draw.line(surface, (232,232,232), (plot.left, y), (plot.right, y), 1)

    # linia limitu
    if max_capacity is not None:
        y_lim = plot.bottom - int((max_capacity - vmin)/(vmax - vmin) * (plot.height-1))
        pygame.draw.line(surface, RED, (plot.left, y_lim), (plot.right, y_lim), 2)

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

    font = pygame.font.SysFont(None, 20)
    label = font.render("Przepływ [m³/h] — niebieski: Estimated, pomarańczowy: Diverted", True, BLACK)
    surface.blit(label, (plot.left, rect.top+6))

# ====== Rysowanie mapy ======

def draw_map(surface: pygame.Surface, rect: pygame.Rect, shared: Dict, lock: threading.Lock):
    pygame.draw.rect(surface, (244,247,252), rect)
    pygame.draw.rect(surface, GRAY, rect, 2, border_radius=12)
    bg_img = pygame.image.load(MAP_IMAGE).convert()
    img = pygame.transform.smoothscale(bg_img, (MAP_RECT.width, MAP_RECT.height))
    surface.blit(img, MAP_RECT.topleft)

    font = pygame.font.SysFont(None, 18)
    with lock:
        sensors = shared.get("sensors", [])
        overflow = shared.get("overflow", None)
        plant = shared.get("plant", None)

    # sensory
    for sid, lat, lon, flow, status in sensors:
        x, y = geo_to_px(lat, lon, rect)
        color = GREEN if status == "NORMAL" else RED
        pygame.draw.circle(surface, color, (x, y), 7)
        txt = font.render(f"{sid} {flow:.0f} m³/h", True, BLACK)
        surface.blit(txt, (x+10, y-8))

    # przelew
    if overflow:
        oid, lat, lon, active, diverted = overflow
        x, y = geo_to_px(lat, lon, rect)
        pygame.draw.circle(surface, RED if active else GRAY, (x, y), 8)
        txt = font.render(f"Overflow {oid} {diverted:.0f} m³/h", True, BLACK)
        surface.blit(txt, (x+10, y-8))

    # oczyszczalnia
    if plant:
        plat, plon, est = plant
        x, y = geo_to_px(plat, plon, rect)
        pygame.draw.rect(surface, BLACK, (x-6, y-6, 12, 12))
        txt = font.render(f"Sewage Plant {est:.0f} m³/h", True, BLACK)
        surface.blit(txt, (x+10, y-8))

# ====== Główna pętla Pygame ======

def run_pygame_dashboard(model_instance: SewerSystemModel, interval_sec: float = 0.5):
    # Współdzielony stan
    shared: Dict = {
        "sensors": [],
        "overflow": None,
        "plant": None,
        "point": None,
        "max_capacity": getattr(model_instance, "max_capacity", None),
        "running": True,
        "hour": 0,
    }
    lock = threading.Lock()
    stop_evt = threading.Event()
    pause_evt = threading.Event()

    # Bufory wykresu
    points_est, points_div = deque(maxlen=CHART_MAX_POINTS), deque(maxlen=CHART_MAX_POINTS)

    # Wątek symulacji (wykorzystuje istniejące metody modelu)
    sim_thread = SimulationThread(model_instance, interval_sec, shared, lock, stop_evt, pause_evt)
    sim_thread.start()

    # Okno
    pygame.init()
    pygame.display.set_caption("SewerSystem — Pygame Dashboard")
    screen = pygame.display.set_mode((WINDOW_W, WINDOW_H))
    clock = pygame.time.Clock()
    font = pygame.font.SysFont(None, 22)

    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_SPACE:
                    if pause_evt.is_set():
                        pause_evt.clear()
                        print("[MAIN] Wznawiam symulację")
                    else:
                        pause_evt.set()
                        print("[MAIN] Pauzuję symulację")

        screen.fill((252,253,255))

        # Nowy punkt na wykres
        with lock:
            pt = shared.get("point")
            max_capacity = shared.get("max_capacity")
            still_running = shared.get("running", True)
            hour = shared.get("hour", 0)
        if pt is not None:
            ts, est, div = pt
            if not points_est or points_est[-1][0] != ts:
                points_est.append((ts, est))
                points_div.append((ts, div))

        # Rysowanie
        draw_map(screen, MAP_RECT, shared, lock)
        draw_chart(screen, CHART_RECT, points_est, points_div, max_capacity)

        # Pasek statusu
        status = f"[SPACE] pauza/wznów | hour={hour} | running={still_running}"
        txt = font.render(status, True, BLACK)
        # screen.blit(txt, (MARGIN, WINDOW_H - 28))
        screen.blit(txt, (MARGIN, MARGIN))

        pygame.display.flip()
        clock.tick(FPS)

        # if not still_running and not pause_evt.is_set():
        #     time.sleep(0.2)
        #     running = False

    stop_evt.set()
    sim_thread.join(timeout=2.0)
    pygame.quit()
    print("[MAIN] zakończono")

# ====== Uruchomienie (odwzorowuje Twój schemat) ======
if __name__ == "__main__":
    print("Tworzę instancję modelu SewerSystemModel (max_hours=7)…")
    model_globalny = SewerSystemModel(max_capacity=2000, max_hours=7)

    print("Uruchamiam Pygame dashboard…")
    run_pygame_dashboard(model_globalny, interval_sec=1.5)

    print("KONIEC — okno zamknięte.")