from visualisation.graphics_functions import *
from model.model import SewerSystemModel
from visualisation.simulation_engine import SimulationThread

import os
import warnings

os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = "1"
warnings.filterwarnings("ignore", category=UserWarning, message=".*pkg_resources is deprecated.*")

import pygame
from collections import deque
import multiprocessing as mp

# ====== KONFIGURACJA PRĘDKOŚCI SYMULACJI ======
MIN_INTERVAL = 0.05
MAX_INTERVAL = 1.5
DEFAULT_INTERVAL = 0.5


def place_window(x: int, y: int):
    os.environ["SDL_VIDEO_WINDOW_POS"] = f"{x},{y}"


# ====== Pętla okna MAPY ======
def map_window_loop(shared, lock, pause_evt, stop_evt, pos=(0, 50)):
    place_window(*pos)
    pygame.init()
    pygame.display.set_caption("SewerSystem — MAP & CONTROL")
    WIN_W, WIN_H = 900, 650
    MAP_ONLY_RECT = pygame.Rect(12, 12, WIN_W - 24, WIN_H - 100)

    screen = pygame.display.set_mode((WIN_W, WIN_H))
    clock = pygame.time.Clock()
    font = pygame.font.SysFont(None, 20)

    with lock:
        shared["map_scale"] = shared.get("map_scale", 1.0)
        shared["map_offset"] = shared.get("map_offset", (0, 0))
        shared["ui_slider_val"] = 0.5
        shared["sim_interval"] = MAX_INTERVAL - 0.5 * (MAX_INTERVAL - MIN_INTERVAL)

    dragging = False
    last_pos = None
    ui_elements = (None, None, None)

    running = True
    while running and not stop_evt.is_set():
        events = pygame.event.get()
        for event in events:
            if event.type == pygame.QUIT:
                running = False

            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if ui_elements[0] is not None:
                    handle_ui_click(event, ui_elements[0], ui_elements[1], ui_elements[2], shared, pause_evt)

            if event.type == pygame.KEYDOWN and event.key == pygame.K_SPACE:
                if pause_evt.is_set():
                    pause_evt.clear();
                    print("[MAP] Wznawiam (Spacja)")
                else:
                    pause_evt.set();
                    print("[MAP] Pauza (Spacja)")

            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if MAP_ONLY_RECT.collidepoint(event.pos):
                    dragging = True;
                    last_pos = event.pos
            elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                dragging = False;
                last_pos = None
            elif event.type == pygame.MOUSEMOTION and dragging:
                mx, my = event.pos;
                lx, ly = last_pos;
                dx, dy = mx - lx, my - ly;
                last_pos = (mx, my)
                with lock:
                    s = shared["map_scale"];
                    ox, oy = shared["map_offset"]
                    sw, sh = MAP_ONLY_RECT.width * s, MAP_ONLY_RECT.height * s
                    ox = min(0, max(MAP_ONLY_RECT.width - sw, ox + dx))
                    oy = min(0, max(MAP_ONLY_RECT.height - sh, oy + dy))
                    shared["map_offset"] = (ox, oy)
            elif event.type == pygame.MOUSEWHEEL:
                mx, my = pygame.mouse.get_pos()
                if MAP_ONLY_RECT.collidepoint((mx, my)):
                    with lock:
                        s_old = shared["map_scale"];
                        ox, oy = shared["map_offset"]
                        s_new = min(6.0, max(1.0, s_old * (1.1 if event.y > 0 else 1 / 1.1)))
                        if s_new != s_old:
                            rx = mx - MAP_ONLY_RECT.left;
                            ry = my - MAP_ONLY_RECT.top
                            u = rx - ox;
                            v = ry - oy
                            ox = rx - u * (s_new / s_old)
                            oy = ry - v * (s_new / s_old)
                            sw, sh = MAP_ONLY_RECT.width * s_new, MAP_ONLY_RECT.height * s_new
                            ox = min(0, max(MAP_ONLY_RECT.width - sw, ox))
                            oy = min(0, max(MAP_ONLY_RECT.height - sh, oy))
                            shared["map_scale"] = s_new
                            shared["map_offset"] = (ox, oy)

        screen.fill((252, 253, 255))
        draw_map(screen, MAP_ONLY_RECT, shared, lock)
        ui_elements = draw_control_bar(screen, screen.get_rect(), shared, pause_evt, stop_evt, MIN_INTERVAL,
                                       MAX_INTERVAL)
        pygame.display.flip()
        clock.tick(FPS)

    pygame.quit()


# ====== Pętla okna WYKRESU ======
def chart_window_loop(shared, lock, pause_evt, stop_evt, pos=(980, 50)):
    place_window(*pos)
    pygame.init()
    pygame.display.set_caption("SewerSystem — CHART & RAIN")
    WIN_W, WIN_H = 900, 650
    CHART_ONLY_RECT = pygame.Rect(12, 12, WIN_W - 24, WIN_H - 24)

    screen = pygame.display.set_mode((WIN_W, WIN_H))
    clock = pygame.time.Clock()

    points_est, points_div = deque(maxlen=CHART_MAX_POINTS), deque(maxlen=CHART_MAX_POINTS)
    points_rain = deque(maxlen=CHART_MAX_POINTS)
    last_hour_check = -1

    running = True
    while running and not stop_evt.is_set():
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_SPACE:
                if pause_evt.is_set():
                    pause_evt.clear()
                else:
                    pause_evt.set()

        screen.fill((252, 253, 255))

        with lock:
            pt = shared.get("point")
            max_capacity = shared.get("max_capacity")
            rain_data = shared.get("rain", {"depth": 0.0})
            hour = shared.get("hour", 0)

        # Wykrywanie RESETU
        if hour < last_hour_check:
            points_est.clear();
            points_div.clear();
            points_rain.clear()
        last_hour_check = hour

        if pt is not None:
            ts, est, div = pt
            if not points_est or points_est[-1][0] != ts:
                points_est.append((ts, est))
                points_div.append((ts, div))
                points_rain.append((ts, rain_data.get("depth", 0.0)))

        # Przekazujemy 'hour' do funkcji rysującej
        draw_chart(screen, CHART_ONLY_RECT, points_est, points_div, points_rain, max_capacity, hour)

        pygame.display.flip()
        clock.tick(FPS)

    pygame.quit()


# ====== Uruchomienie ======
def run_two_windows_dashboard(interval_sec: float = DEFAULT_INTERVAL, rain_file = "data/rain.csv"):
    mp.set_start_method("spawn", force=True)

    manager = mp.Manager()
    shared = manager.dict({
        "sensors": [],
        "overflow": None,
        "plant": None,
        "point": None,
        "plant_params": {},
        "rain": {"intensity": 0.0, "depth": 0.0},
        "connections": [],
        "extra_points": [],
        "max_capacity": 1700,
        "running": True,
        "hour": 0,
        "max_hours": 168,
        "reset_cmd": False,
        "sim_interval": interval_sec,
        "ui_slider_val": 0.5
    })
    lock = manager.RLock()
    stop_evt = manager.Event()
    pause_evt = manager.Event()

    pause_evt.set()

    def model_factory():
        return SewerSystemModel(max_capacity=2000, max_hours=168, rain_file=rain_file)

    temp_model = model_factory()
    shared["max_capacity"] = temp_model.max_capacity
    del temp_model

    sim_thread = SimulationThread(model_factory, interval_sec, shared, lock, stop_evt, pause_evt)
    sim_thread.start()

    map_pos = (0, 50)
    chart_pos = (50 + 900 + 30, 50)
    p_map = mp.Process(target=map_window_loop, args=(shared, lock, pause_evt, stop_evt, map_pos), daemon=True)
    p_ch = mp.Process(target=chart_window_loop, args=(shared, lock, pause_evt, stop_evt, chart_pos), daemon=True)

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


if __name__ == "__main__":
    print("\n=== Symulacja rozpoczęta ===")
    # run_two_windows_dashboard(interval_sec=DEFAULT_INTERVAL, rain_file="data/rain_experiments/realistic.csv")
    run_two_windows_dashboard(interval_sec=DEFAULT_INTERVAL)
    print("\n=== Symulacja zakończona ===")