from model.model import SewerSystemModel
import pandas as pd

from model.model import SewerSystemModel
import pandas as pd
import itertools

import matplotlib.pyplot as plt
import os

RESULTS_DIR = "results"
os.makedirs(RESULTS_DIR, exist_ok=True)

def make_plots(df, rain_df):
    import matplotlib.dates as mdates

    # ===== 1. SCATTER (model vs real) =====
    # plt.figure()
    # plt.scatter(df["real"], df["model"], alpha=0.5)
    # plt.xlabel("Real flow")
    # plt.ylabel("Model flow")
    # plt.title("Model vs Real (scatter)")

    # linia idealna
    # min_val = min(df["real"].min(), df["model"].min())
    # max_val = max(df["real"].max(), df["model"].max())
    # plt.plot([min_val, max_val], [min_val, max_val])
    #
    # plt.savefig(f"{RESULTS_DIR}/scatter_model_vs_real.png")
    # plt.close()

    # ===== 2. HISTOGRAM BŁĘDÓW =====
    # plt.figure()
    # df["diff"].hist(bins=50)
    # plt.title("Error distribution (model - real)")
    # plt.xlabel("Error")
    # plt.ylabel("Frequency")
    #
    # plt.savefig(f"{RESULTS_DIR}/error_histogram.png")
    # plt.close()

    # ===== 3. ERROR vs FLOW =====
    # plt.figure()
    # plt.scatter(df["real"], df["diff"], alpha=0.5)
    # plt.xlabel("Real flow")
    # plt.ylabel("Error")
    # plt.title("Error vs Flow")
    #
    # plt.axhline(0)
    #
    # plt.savefig(f"{RESULTS_DIR}/error_vs_flow.png")
    # plt.close()

    # ===== 4. TIME SERIES (dla jednego sensora) =====
    sensor = df["sensor"].iloc[1]  # możesz zmienić np. "KP2"

    df_s = df[df["sensor"] == sensor].copy()
    df_s = df_s.merge(rain_df, on="datetime", how="left")

    fig, ax1 = plt.subplots()

    # flow
    ax1.plot(df_s["datetime"], df_s["model"], label="model")
    ax1.plot(df_s["datetime"], df_s["real"], label="real")
    ax1.set_ylabel("Flow [m3/h]")

    ax1.xaxis.set_major_locator(mdates.DayLocator(interval=1))
    ax1.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
    plt.xticks(rotation=45)

    # rain
    ax2 = ax1.twinx()
    ax2.bar(df_s["datetime"], df_s["rain_mm_h"], alpha=0.3)
    ax2.set_ylabel("Rain [mm/h]")

    ax1.legend()
    plt.title(f"{sensor} – model vs real + rain")

    plt.tight_layout()
    plt.savefig(f"{RESULTS_DIR}/timeseries_{sensor}.png")
    plt.close()

    # ===== 5. ERROR W CZASIE =====
    plt.figure()
    plt.plot(df_s["datetime"], df_s["diff"])
    plt.title(f"{sensor} – error over time")
    plt.xticks(rotation=45)

    plt.savefig(f"{RESULTS_DIR}/error_time_{sensor}.png")
    plt.close()


def evaluate_model_global(model):
    df = pd.DataFrame(model.validation_results)

    if df.empty:
        return {
            "rmse_all": float("inf"),
            "rmse_filtered": float("inf"),
            "mae_all": float("inf"),
            "mae_filtered": float("inf"),
            "mape_all": float("inf"),
            "mape_filtered": float("inf")
        }

    df_filtered = df[df["real"] > 30]

    # --- RMSE ---
    rmse_all = ((df["diff"] ** 2).mean()) ** 0.5
    rmse_filtered = ((df_filtered["diff"] ** 2).mean()) ** 0.5 if not df_filtered.empty else float("inf")

    # --- MAE ---
    mae_all = df["diff"].abs().mean()
    mae_filtered = df_filtered["diff"].abs().mean() if not df_filtered.empty else float("inf")

    # --- MAPE ---
    mape_all = df["perc_error"].abs().mean()
    mape_filtered = df_filtered["perc_error"].abs().mean() if not df_filtered.empty else float("inf")

    return {
        "rmse_all": rmse_all,
        "rmse_filtered": rmse_filtered,
        "mae_all": mae_all,
        "mae_filtered": mae_filtered,
        "mape_all": mape_all,
        "mape_filtered": mape_filtered
    }

def evaluate_sensor(model, sensor_id):
    df = pd.DataFrame(model.validation_results)
    df = df[df["sensor"] == sensor_id]

    if df.empty:
        return float("inf")

    rmse = ((df["diff"] ** 2).mean()) ** 0.5
    return rmse


def run_model_local(
    rain_file,
    validation_file,
    global_params,
    local_params,
    debug=True
):
    model = SewerSystemModel(rain_file=rain_file, debug=debug)
    model.load_real_flows(validation_file)

    for s in model.sensors.values():
        s.set_params(
            k=global_params["k"],
            alpha=global_params["alpha"],
            gamma=global_params["gamma"]
        )

    for sid, params in local_params.items():
        if sid in model.sensors:
            model.sensors[sid].set_params(
                k_local=params.get("k_local"),
                alpha_local=params.get("alpha_local")
            )

    while model.running:
        model.step()

    return model


import itertools

def calibrate_sensor(sensor_id, rain_file, validation_file, global_params, current_local_params):

    k_local_values = [0.7, 1.0, 1.3]
    alpha_local_values = [0.8, 1.0, 1.2]

    best_score = float("inf")
    best_params = None

    for k_loc, a_loc in itertools.product(k_local_values, alpha_local_values):
        print(f"[{sensor_id}] TEST k_local={k_loc}, alpha_local={a_loc}")

        local_params = current_local_params.copy()

        local_params[sensor_id] = {
            "k_local": k_loc,
            "alpha_local": a_loc
        }

        model = run_model_local(
            rain_file,
            validation_file,
            global_params,
            local_params,
            debug=True
        )

        score = evaluate_sensor(model, sensor_id)

        print(f"RMSE = {score:.2f}")

        if score < best_score:
            best_score = score
            best_params = {
                "k_local": k_loc,
                "alpha_local": a_loc
            }

            print(f"NEW BEST for {sensor_id}: {best_params}")

    return best_params


def calibrate_all_sensors(rain_file, validation_file):
    global_params = {
        "k": 0.6,
        "alpha": 1.1,
        "gamma": 0.03
    }

    temp_model = SewerSystemModel(rain_file=rain_file, debug=True)
    sensor_ids = [
        sid for sid in temp_model.sensor_order
        if sid not in ("M1", "LBT1")
    ]

    results = {}

    for sid in sensor_ids:
        print(f"\n==== CALIBRATING {sid} ====")

        best = calibrate_sensor(
            sid,
            rain_file,
            validation_file,
            global_params,
            results
        )

        results[sid] = best

        print(f"UPDATED PARAMS: {results}")

    return results

LOCAL_PARAMS = {
    'ŁPA-P1': {'k_local': 0.7, 'alpha_local': 0.8},
    'G-T1': {'k_local': 1.3, 'alpha_local': 0.8},
    'KP25': {'k_local': 0.7, 'alpha_local': 0.8},
    'KP11': {'k_local': 0.7, 'alpha_local': 0.8},
    'KP10': {'k_local': 0.7, 'alpha_local': 0.8},
    'KP9': {'k_local': 0.7, 'alpha_local': 0.8},
    'KP8': {'k_local': 0.7, 'alpha_local': 0.8},
    'KP7': {'k_local': 1.3, 'alpha_local': 1.0},
    'KP16': {'k_local': 1.3, 'alpha_local': 0.8},
    'KP6': {'k_local': 1.3, 'alpha_local': 0.8},
    'KP4': {'k_local': 1.3, 'alpha_local': 1.0},
    'KP2': {'k_local': 0.7, 'alpha_local': 0.8},
    'KP1': {'k_local': 1.3, 'alpha_local': 1.2},
    'LBT1': {'k_local': 0.7, 'alpha_local': 0.8},
    'M1': {'k_local': 1.3, 'alpha_local': 1.2}
}


def run_model_with_params(
    rain_file,
    validation_file,
    k,
    alpha,
    gamma,
    local_params=None,
    debug=True
):
    model = SewerSystemModel(rain_file=rain_file, debug=debug)
    model.load_real_flows(validation_file)

    for sid, sensor in model.sensors.items():
        sensor.set_params(k=k, alpha=alpha, gamma=gamma)

        if sid in LOCAL_PARAMS:
            sensor.set_params(
                k_local=LOCAL_PARAMS[sid]["k_local"],
                alpha_local=LOCAL_PARAMS[sid]["alpha_local"]
            )

    while model.running:
        model.step()

    return model


def calibrate_global(rain_file, validation_file):
    k_values = [0.6, 0.8, 1.0, 1.2, 1.4]
    alpha_values = [1.1, 1.3, 1.5, 1.7]
    gamma_values = [0.005, 0.01, 0.02, 0.03]

    best_score = float("inf")
    best_params = None

    for k, alpha, gamma in itertools.product(k_values, alpha_values, gamma_values):
        print(f"TEST global: k={k}, alpha={alpha}, gamma={gamma}")

        model = run_model_with_params(
            rain_file=rain_file,
            validation_file=validation_file,
            k=k,
            alpha=alpha,
            gamma=gamma,
            debug=True
        )

        # score = evaluate_model_global(model, min_real_flow=50)

        # print(f"RMSE(filtered) = {score:.3f}")
        metrics = evaluate_model_global(model)

        print(
            f"RMSE(all)={metrics['rmse_all']:.2f} | "
            f"RMSE(>30)={metrics['rmse_filtered']:.2f} | "
            f"MAE={metrics['mae']:.2f} | "
            f"MAPE={metrics['mape']:.2f}"
        )

        score = metrics["rmse_filtered"]

        if score < best_score:
            best_score = score
            best_params = {"k": k, "alpha": alpha, "gamma": gamma}
            print(f"NEW BEST GLOBAL: {best_params}, RMSE={best_score:.3f}")

    return best_params, best_score


if __name__ == "__main__":

    GLOBAL_PARAMS = {
        "k": 0.6,
        "alpha": 1.1,
        "gamma": 0.03
    }

    model = SewerSystemModel(
        rain_file="data/experiments_new/moderate_rain/months/rain_month_10.csv",
        debug=False
    )

    # ustaw parametry
    for sid, sensor in model.sensors.items():
        sensor.set_params(
            k=GLOBAL_PARAMS["k"],
            alpha=GLOBAL_PARAMS["alpha"],
            gamma=GLOBAL_PARAMS["gamma"]
        )

        if sid in LOCAL_PARAMS:
            sensor.set_params(
                k_local=LOCAL_PARAMS[sid]["k_local"],
                alpha_local=LOCAL_PARAMS[sid]["alpha_local"]
            )

    # run
    while model.running:
        model.step()

    print("\n=== SIMULATION FINISHED ===")

    # zapis wyników modelu (bez real)
    results = model.datacollector.get_model_vars_dataframe()
    results.to_csv("data/experiments_new/moderate_rain/results/october.csv")

    print("Saved: simulation_results.csv")

# if __name__ == "__main__":
#
#     GLOBAL_PARAMS = {
#         "k": 0.6,
#         "alpha": 1.1,
#         "gamma": 0.03
#     }
#
#     model = SewerSystemModel(
#         rain_file="data/rain_clean.csv",
#         debug=True
#     )
#
#     model.load_real_flows("data/full_validation.csv")
#
#     # ustaw global + local
#     for sid, sensor in model.sensors.items():
#         sensor.set_params(
#             k=GLOBAL_PARAMS["k"],
#             alpha=GLOBAL_PARAMS["alpha"],
#             gamma=GLOBAL_PARAMS["gamma"]
#         )
#
#         if sid in LOCAL_PARAMS:
#             sensor.set_params(
#                 k_local=LOCAL_PARAMS[sid]["k_local"],
#                 alpha_local=LOCAL_PARAMS[sid]["alpha_local"]
#             )
#
#     # run
#     while model.running:
#         model.step()
#
#     # ===== METRYKI =====
#     metrics = evaluate_model_global(model)
#
#     print("\n=== FINAL METRICS ===")
#     print(
#         f"RMSE(all)={metrics['rmse_all']:.2f} | "
#         f"RMSE(>30)={metrics['rmse_filtered']:.2f} | "
#         f"MAE(all)={metrics['mae_all']:.2f} | "
#         f"MAE(>30)={metrics['mae_filtered']:.2f} | "
#         f"MAPE(all)={metrics['mape_all']:.2f} | "
#         f"MAPE(>30)={metrics['mape_filtered']:.2f}"
#     )
#
#     # zapis
#     df = pd.DataFrame(model.validation_results)
#     df.to_csv("data/final_validation_results.csv", index=False)
#
#     # ===== WYKRESY =====
#     make_plots(df, model.rain_df)
#
#     print(f"\nWykresy zapisane w folderze: {RESULTS_DIR}")


# model = SewerSystemModel(rain_file="data/rain_clean.csv")
# model.load_real_flows("data/full_validation.csv")
# model = SewerSystemModel(rain_file="data/rain_valid.csv")
# model.load_real_flows("data/valid.csv")
# model = SewerSystemModel(rain_file="data/rain_oct.csv")
# model.load_real_flows("data/validation_data_oct.csv")
# model = SewerSystemModel(rain_file="data/rain_short.csv")
# model.load_real_flows("data/validation_data.csv")
# for s in model.sensors.values():
#     s.set_params(k=0.6, alpha=1.1, gamma=0.03)
# while model.running:
#     model.step()

# if __name__ == "__main__":
#     local_params = calibrate_all_sensors(
#         rain_file="data/rain_clean.csv",
#         validation_file="data/full_validation.csv"
#     )
#
#     print("\n=== LOCAL PARAMS ===")
#     print(local_params)
#     pd.DataFrame(local_params).T.to_csv("data/local_params.csv")

# if __name__ == "__main__":
#     best_params, best_score = calibrate_global(
#         rain_file="data/rain_clean.csv",
#         validation_file="data/full_validation.csv"
#     )
#
#     print("\n=== BEST GLOBAL ===")
#     print(best_params)
#     print("BEST RMSE:", best_score)



# print("\n=== Symulacja zakończona ===")

# results = model.datacollector.get_model_vars_dataframe()
# print("\n=== Podsumowanie danych ===")
# print(results.head(10))
#
# results.to_csv("data/debug_output.csv")
# print("Zapisano debug_output.csv")
#
# df_val = pd.DataFrame(model.validation_results)
# print("MAE:", (df_val["diff"].abs()).mean())
# print("RMSE:", ((df_val["diff"]**2).mean())**0.5)
# print("MAPE:", df_val["perc_error"].abs().mean())
#
# df_val_filtered = df_val[df_val["real"] > 50]
# print("======================")
# print("Filtered:\n")
# print("MAE:", (df_val_filtered["diff"].abs()).mean())
# print("RMSE:", ((df_val_filtered["diff"]**2).mean())**0.5)
# print("MAPE:", df_val_filtered["perc_error"].abs().mean())
# import matplotlib.pyplot as plt
# import matplotlib.dates as mdates
#
# sensor = "KP2"  # wybierz
#
# df_s = df_val[df_val["sensor"] == sensor]
#
# fig, ax1 = plt.subplots()
#
# df_plot = df_s.merge(model.rain_df, on="datetime", how="left")
#
# # --- flow ---
# ax1.plot(df_plot["datetime"], df_plot["model"], label="model", color="orange")
# ax1.plot(df_plot["datetime"], df_plot["real"], label="real", color="red")
# ax1.set_ylabel("Flow [m3/h]")
# ax1.xaxis.set_major_locator(mdates.DayLocator(interval=1))  # co 1 dzień
# ax1.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
# plt.xticks(rotation=45, ha="right")
# # --- rain ---
# ax2 = ax1.twinx()
# ax2.bar(
#     df_plot["datetime"],
#     df_plot["rain_mm_h"],
#     alpha=0.8,
#     width=0.02
# )
# ax2.set_ylabel("Rain [mm/h]")
#
# ax1.legend()
#
# plt.title(f"{sensor} – model vs rzeczywistość + opad")
# plt.xticks(rotation=45)
#
# plt.tight_layout()
# plt.show()
#
# plt.figure()
# plt.scatter(df_val["real"], df_val["model"])
# plt.xlabel("real")
# plt.ylabel("model")
# plt.title("Model vs real (scatter)")
# plt.show()
#
# plt.figure()
# df_val["diff"].hist(bins=50)
# plt.title("Rozkład błędów")
# plt.show()
#
# plt.figure()
# plt.plot(df_s["datetime"], df_s["diff"])
# plt.title(f"{sensor} – błąd w czasie")
# plt.xticks(rotation=45)
# plt.show()