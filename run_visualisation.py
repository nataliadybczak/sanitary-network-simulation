from visualisation.graphics_functions import *   # draw_map, draw_chart, kolory, stałe
from model.model import SewerSystemModel
from visualisation.simulation_engine import SimulationThread

import pygame
from collections import deque
import multiprocessing as mp

import os

def place_window(x: int, y: int):
    os.environ["SDL_VIDEO_WINDOW_POS"] = f"{x},{y}"

# ====== Pętla okna MAPY ======
def map_window_loop(shared, lock, pause_evt, stop_evt, pos=(0, 50)):
    place_window(*pos)
    pygame.init()
    pygame.display.set_caption("SewerSystem — MAP")
    WIN_W, WIN_H = 900, 650
    MAP_ONLY_RECT = pygame.Rect(12, 12, WIN_W - 24, WIN_H - 24)

    screen = pygame.display.set_mode((WIN_W, WIN_H))
    clock = pygame.time.Clock()
    font = pygame.font.SysFont(None, 20)

    with lock:
        shared["map_scale"] = shared.get("map_scale", 1.0)
        shared["map_offset"] = shared.get("map_offset", (0, 0))

    dragging = False
    last_pos = None
    running = True
    while running and not stop_evt.is_set():
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_SPACE:
                if pause_evt.is_set():
                    pause_evt.clear(); print("[MAP] Wznawiam symulację")
                else:
                    pause_evt.set(); print("[MAP] Pauzuję symulację")
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and MAP_ONLY_RECT.collidepoint(event.pos):
                dragging = True; last_pos = event.pos
            elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                dragging = False; last_pos = None
            elif event.type == pygame.MOUSEMOTION and dragging:
                mx, my = event.pos; lx, ly = last_pos; dx, dy = mx - lx, my - ly; last_pos = (mx, my)
                with lock:
                    s = shared["map_scale"]; ox, oy = shared["map_offset"]
                    sw, sh = MAP_ONLY_RECT.width * s, MAP_ONLY_RECT.height * s
                    ox = min(0, max(MAP_ONLY_RECT.width - sw, ox + dx))
                    oy = min(0, max(MAP_ONLY_RECT.height - sh, oy + dy))
                    shared["map_offset"] = (ox, oy)
            elif event.type == pygame.MOUSEWHEEL:
                mx, my = pygame.mouse.get_pos()
                if MAP_ONLY_RECT.collidepoint((mx, my)):
                    with lock:
                        s_old = shared["map_scale"]; ox, oy = shared["map_offset"]
                        s_new = min(6.0, max(1.0, s_old * (1.1 if event.y > 0 else 1/1.1)))
                        if s_new != s_old:
                            rx = mx - MAP_ONLY_RECT.left; ry = my - MAP_ONLY_RECT.top
                            u = rx - ox; v = ry - oy
                            ox = rx - u * (s_new / s_old)
                            oy = ry - v * (s_new / s_old)
                            sw, sh = MAP_ONLY_RECT.width * s_new, MAP_ONLY_RECT.height * s_new
                            ox = min(0, max(MAP_ONLY_RECT.width - sw, ox))
                            oy = min(0, max(MAP_ONLY_RECT.height - sh, oy))
                            shared["map_scale"] = s_new
                            shared["map_offset"] = (ox, oy)

        screen.fill((252, 253, 255))
        # rysuj mape
        draw_map(screen, MAP_ONLY_RECT, shared, lock)

        with lock:
            still_running = shared.get("running", True); hour = shared.get("hour", 0)
        info = f"[MAP] hour={hour} | running={still_running} | [SPACE]=pauza/wznów  | zamknij okno krzyżykiem (QUIT)"
        txt = font.render(info, True, BLACK)
        screen.blit(txt, (12, WIN_H - 28))

        pygame.display.flip()
        clock.tick(FPS)

    pygame.quit()


# ====== Pętla okna WYKRESU ======
def chart_window_loop(shared, lock, pause_evt, stop_evt, pos=(980, 50)):
    place_window(*pos)
    pygame.init()
    pygame.display.set_caption("SewerSystem — CHART")
    WIN_W, WIN_H = 900, 650
    CHART_ONLY_RECT = pygame.Rect(12, 12, WIN_W - 24, WIN_H - 24)

    screen = pygame.display.set_mode((WIN_W, WIN_H))
    clock = pygame.time.Clock()
    font = pygame.font.SysFont(None, 20)

    points_est, points_div = deque(maxlen=CHART_MAX_POINTS), deque(maxlen=CHART_MAX_POINTS)

    running = True
    while running and not stop_evt.is_set():
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_SPACE:
                    if pause_evt.is_set():
                        pause_evt.clear()
                        print("[CHART] Wznawiam symulację")
                    else:
                        pause_evt.set()
                        print("[CHART] Pauzuję symulację")

        screen.fill((252, 253, 255))

        # nowy punkt do wykresu
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

        # rysuj wykres na całe okno
        draw_chart(screen, CHART_ONLY_RECT, points_est, points_div, max_capacity)

        status = f"[CHART] hour={hour} | running={still_running} | [SPACE]=pauza/wznów  | zamknij okno krzyżykiem (QUIT)"
        txt = font.render(status, True, BLACK)
        screen.blit(txt, (12, WIN_H - 28))

        pygame.display.flip()
        clock.tick(FPS)

    pygame.quit()


# ====== Uruchomienie symulacji + 2 okna ======
def run_two_windows_dashboard(model_instance: SewerSystemModel, interval_sec: float = 0.5):
    mp.set_start_method("spawn", force=True)

    manager = mp.Manager()
    shared = manager.dict({
        "sensors": [],
        "overflow": None,
        "plant": None,
        "point": None,
        "max_capacity": getattr(model_instance, "max_capacity", None),
        "running": True,
        "hour": 0,
    })
    lock = manager.RLock()
    stop_evt = manager.Event()
    pause_evt = manager.Event()

    # wątek symulacji
    sim_thread = SimulationThread(model_instance, interval_sec, shared, lock, stop_evt, pause_evt)
    sim_thread.start()

    # procesy dla okien
    map_pos = (0, 50)
    chart_pos = (50 + 900 + 30, 50)
    p_map = mp.Process(target=map_window_loop,   args=(shared, lock, pause_evt, stop_evt, map_pos), daemon=True)
    p_ch  = mp.Process(target=chart_window_loop, args=(shared, lock, pause_evt, stop_evt, chart_pos), daemon=True)

    p_map.start()
    p_ch.start()

    try:
        p_map.join()
        p_ch.join()
    except KeyboardInterrupt:
        pass
    finally:
        stop_evt.set()
        sim_thread.join(timeout=2.0)


# ====== Uruchomienie ======
if __name__ == "__main__":
    print("Tworzę instancję modelu SewerSystemModel")
    model = SewerSystemModel(max_capacity=2000, max_hours=7)

    run_two_windows_dashboard(model, interval_sec=1.0)
