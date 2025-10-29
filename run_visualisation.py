from visualisation.graphics_functions import *
from model.model import SewerSystemModel
from visualisation.simulation_engine import SimulationThread


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

# ====== Uruchomienie  ======
if __name__ == "__main__":
    print("Tworzę instancję modelu SewerSystemModel")
    model_globalny = SewerSystemModel(max_capacity=2000, max_hours=7)

    print("Uruchamiam Pygame dashboard…")
    run_pygame_dashboard(model_globalny, interval_sec=1.5)

    print("KONIEC — okno zamknięte.")