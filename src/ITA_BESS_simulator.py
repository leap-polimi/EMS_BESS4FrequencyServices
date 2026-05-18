"""
Real-time simulation script for Italian optimization results.

For each optimized daily schedule and EPR value, this script rebuilds actual BESS
power flows using realized FCR/aFRR activation profiles, applies SOC constraints,
settles any imbalance energy, and stores daily metrics in HDF5 files.

This version assumes that real activation profiles and imbalance prices are already
available in a single input dataset.
"""

import os
import cloudpickle
import h5py
import numpy as np
import pandas as pd
import pyomo.environ as pyo


# =============================================================================
# USER SETTINGS
# =============================================================================

EPR_VALUES = [1, 2, 4, 6, 8]

# Folder containing the optimized Pyomo models saved as .pkl files
RESULTS_DIRECTORY = "results/ITALY/Optimization_Results"

# Folder where simulation results will be saved
OUTPUT_DIRECTORY = "results/ITALY/Simulation_Results"

# Dataset containing real activation profiles and imbalance prices
REAL_DATA_FILE = "data/ITALY/real_time_simulation_inputs.csv"

# Expected columns in REAL_DATA_FILE:
#
# date                  string, format YYYY_MM_DD
# quarter               integer from 1 to 96
# fcr_up_activation     upward FCR activation as percentage of reserved band [%]
# fcr_dw_activation     downward FCR activation as percentage of reserved band [%]
# afrr_up_activation    upward aFRR activation as percentage of reserved band [%]
# afrr_dw_activation    downward aFRR activation as percentage of reserved band [%]
# imbalance_price       imbalance price [€/MWh]
#
# Example:
#
# date,quarter,fcr_up_activation,fcr_dw_activation,afrr_up_activation,afrr_dw_activation,imbalance_price
# 2023_01_01,1,0.12,0.00,3.45,0.00,125.4
# 2023_01_01,2,0.00,0.08,0.00,2.10,119.8


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def load_real_time_data(file_path):
    """
    Load the dataset containing real activation profiles and imbalance prices.

    Returns
    -------
    pandas.DataFrame
        Dataset indexed by date and quarter-hour.
    """
    required_columns = [
        "date",
        "quarter",
        "fcr_up_activation",
        "fcr_dw_activation",
        "afrr_up_activation",
        "afrr_dw_activation",
        "imbalance_price",
    ]

    data = pd.read_csv(file_path)

    missing_columns = [col for col in required_columns if col not in data.columns]
    if missing_columns:
        raise ValueError(
            f"The real-time input dataset is missing the following columns: "
            f"{missing_columns}"
        )

    data = data.sort_values(["date", "quarter"]).reset_index(drop=True)

    return data


def get_daily_real_time_inputs(real_time_data, date_name):
    """
    Extract real activation profiles and imbalance prices for one day.

    Parameters
    ----------
    real_time_data : pandas.DataFrame
        Full real-time input dataset.
    date_name : str
        Date string in the format YYYY_MM_DD.

    Returns
    -------
    tuple of lists
        FCR upward activation, FCR downward activation, aFRR upward activation,
        aFRR downward activation, and imbalance prices.
    """
    daily_data = real_time_data[real_time_data["date"] == date_name].copy()

    if len(daily_data) != 96:
        raise ValueError(
            f"Expected 96 quarter-hour rows for {date_name}, "
            f"but found {len(daily_data)}."
        )

    daily_data = daily_data.sort_values("quarter")

    perc_band_prim_up = daily_data["fcr_up_activation"].to_numpy()
    perc_band_prim_dw = daily_data["fcr_dw_activation"].to_numpy()
    perc_band_sec_up = daily_data["afrr_up_activation"].to_numpy()
    perc_band_sec_dw = daily_data["afrr_dw_activation"].to_numpy()
    imbalance_prices = daily_data["imbalance_price"].to_numpy()

    return (
        perc_band_prim_up,
        perc_band_prim_dw,
        perc_band_sec_up,
        perc_band_sec_dw,
        imbalance_prices,
    )


def extract_date_from_filename(file_name):
    """
    Extract the date from an optimization result filename.

    Expected filename format:
    ITA_opt_results_YYYY_MM_DD_EPRx.pkl

    Returns
    -------
    str
        Date string in the format YYYY_MM_DD.
    """
    year_string = file_name.split("_")[3]
    month_string = file_name.split("_")[4]
    day_string = file_name.split("_")[5]

    return f"{year_string}_{month_string}_{day_string}"


def update_soc(previous_soc, bess_power, bess_capacity):
    """
    Update the BESS state of charge for one quarter-hour.

    Positive BESS power means discharge.
    Negative BESS power means charge.

    Parameters
    ----------
    previous_soc : float
        SOC at the beginning of the quarter-hour [%].
    bess_power : float
        Net BESS power [MW].
    bess_capacity : float
        BESS energy capacity [MWh].

    Returns
    -------
    float
        SOC at the end of the quarter-hour [%].
    """
    if bess_power >= 0:
        if bess_power >= 0.15:
            return previous_soc - (((bess_power / 0.868) / 4) / bess_capacity) * 100
        return previous_soc - (((bess_power / 0.50) / 4) / bess_capacity) * 100

    if abs(bess_power) >= 0.15:
        return previous_soc + (((-bess_power * 0.972) / 4) / bess_capacity) * 100

    return previous_soc + (((-bess_power * 0.55) / 4) / bess_capacity) * 100


# =============================================================================
# MAIN SCRIPT
# =============================================================================

os.makedirs(OUTPUT_DIRECTORY, exist_ok=True)

real_time_data = load_real_time_data(REAL_DATA_FILE)

pkl_files = [
    file for file in os.listdir(RESULTS_DIRECTORY)
    if file.endswith(".pkl")
]

n_files = len(pkl_files)
n_days = int(n_files / len(EPR_VALUES))

date_names = []

for file in pkl_files:
    date_string = extract_date_from_filename(file)

    if date_string not in date_names:
        date_names.append(date_string)

date_names = sorted(date_names)

print(f"Number of optimization result files: {n_files}")
print(f"Number of simulated days: {n_days}")

count = 0

for epr in EPR_VALUES:
    for date_name in date_names:

        filename = (
            f"{RESULTS_DIRECTORY}/"
            f"ITA_opt_results_{date_name}_EPR{epr}.pkl"
        )

        print(filename)

        try:
            with open(filename, "rb") as file:
                results = cloudpickle.load(file)
        except Exception as error:
            print(f"An error occurred while loading {filename}: {error}")
            continue

        (
            perc_band_prim_up,
            perc_band_prim_dw,
            perc_band_sec_up,
            perc_band_sec_dw,
            imbalance_prices,
        ) = get_daily_real_time_inputs(real_time_data, date_name)

        p_prim_up_real = []
        p_prim_dw_real = []
        p_sec_up_real = []
        p_sec_dw_real = []

        p_bess_real = np.zeros((96, 6))
        soc_real = np.zeros((97, 6))
        e_unbalanced = np.zeros((96, 6))

        bess_capacity = pyo.value(results.BESS_capacity)

        for h in range(1, 25):
            for q in range(1, 5):
                index = (h - 1) * 4 + q - 1

                p_prim_up_real.append(
                    pyo.value(results.P_band_prim[1])
                    * perc_band_prim_up[index]
                    / 100
                )

                p_prim_dw_real.append(
                    pyo.value(results.P_band_prim[1])
                    * perc_band_prim_dw[index]
                    / 100
                )

                p_sec_up_real.append(
                    pyo.value(results.P_band_sec_UP[1])
                    * perc_band_sec_up[index]
                    / 100
                )

                p_sec_dw_real.append(
                    pyo.value(results.P_band_sec_DW[1])
                    * perc_band_sec_dw[index]
                    / 100
                )

        for sc in range(1, 7):
            soc_real[0, sc - 1] = 50

        for h in range(1, 25):
            for q in range(1, 5):
                for sc in range(1, 7):
                    index = (h - 1) * 4 + q - 1

                    p_dis = (
                        p_prim_up_real[index]
                        + p_sec_up_real[index]
                        + pyo.value(
                            results.P_ter_UP[h]
                            * results.y_ter_UP_par[sc, h]
                            + results.P_sold[h]
                        )
                    )

                    p_cha = (
                        p_prim_dw_real[index]
                        + p_sec_dw_real[index]
                        + pyo.value(
                            results.P_ter_DW[h]
                            * results.y_ter_DW_par[sc, h]
                            + results.P_purch[h]
                        )
                    )

                    p_bess_real[index, sc - 1] = p_dis - p_cha

                    soc_real[index + 1, sc - 1] = update_soc(
                        previous_soc=soc_real[index, sc - 1],
                        bess_power=p_bess_real[index, sc - 1],
                        bess_capacity=bess_capacity,
                    )

                    if soc_real[index + 1, sc - 1] > 100:
                        e_unbalanced[index, sc - 1] = (
                            (soc_real[index + 1, sc - 1] - 100)
                            / 100
                            * bess_capacity
                        )
                        soc_real[index + 1, sc - 1] = 100

                    if soc_real[index + 1, sc - 1] < 0:
                        e_unbalanced[index, sc - 1] = (
                            soc_real[index + 1, sc - 1]
                            / 100
                            * bess_capacity
                        )
                        soc_real[index + 1, sc - 1] = 0

        e_qrt_unbalanced = np.zeros(96)
        e_daily_unbalanced = 0

        for t in range(96):
            for sc in range(1, 7):
                e_qrt_unbalanced[t] += (
                    e_unbalanced[t, sc - 1]
                    * pyo.value(results.p_sc[sc])
                )

            e_daily_unbalanced += abs(e_qrt_unbalanced[t])

        rev_prim = 0
        rev_sec = 0
        rev_ter = 0
        rev_dam = 0
        rev_soc = 0
        rev_unbalancing = 0

        rev_soc = sum(
            pyo.value(results.p_sc[sc])
            * (soc_real[96, sc - 1] - pyo.value(results.SOC_initial))
            / 100
            * bess_capacity
            * pyo.value(results.price_DAM_historical)
            for sc in range(1, 7)
        )

        for h in range(1, 25):
            rev_ter += sum(
                pyo.value(
                    results.p_sc[sc]
                    * (
                        results.P_ter_UP[h]
                        * results.y_ter_UP_par[sc, h]
                        * results.offer_ter_UP[h]
                        - results.P_ter_DW[h]
                        * results.y_ter_DW_par[sc, h]
                        * results.offer_ter_DW[h]
                    )
                )
                for sc in range(1, 7)
            )

            rev_dam += pyo.value(
                (results.P_sold[h] - results.P_purch[h])
                * results.price_DAM[h]
            )

            for q in range(1, 5):
                index = (h - 1) * 4 + q - 1

                rev_prim += pyo.value(
                    p_prim_up_real[index] / 4 * results.price_prim_UP[h]
                    - p_prim_dw_real[index] / 4 * results.price_prim_DW[h]
                )

                rev_sec += pyo.value(
                    p_sec_up_real[index] / 4 * results.price_sec_UP[h]
                    - p_sec_dw_real[index] / 4 * results.price_sec_DW[h]
                )

                rev_unbalancing += (
                    e_qrt_unbalanced[index]
                    * imbalance_prices[index]
                )

        print(f"Imbalance revenue: {rev_unbalancing} €")

        rev_tot = pyo.value(
            rev_prim
            + rev_sec
            + rev_ter
            + rev_dam
            + rev_soc
            + rev_unbalancing
        )

        print(f"Total revenue: {rev_tot} €")

        specific_rev_tot = rev_tot / bess_capacity

        e_processed = 0

        for h in range(1, 25):
            for q in range(1, 5):
                index = (h - 1) * 4 + q - 1

                e_processed += abs(
                    sum(
                        pyo.value(results.p_sc[sc])
                        * (
                            p_bess_real[index, sc - 1] / 4
                            + e_unbalanced[index, sc - 1]
                        )
                        for sc in range(1, 7)
                    )
                )

        print(f"EPR={epr}; day={date_name}:")
        print(f"Processed energy = {e_processed} MWh")
        print(f"Unbalanced energy = {e_daily_unbalanced} MWh")

        n_cycles = e_processed / bess_capacity

        output_file = (
            f"{OUTPUT_DIRECTORY}/"
            f"ITA_simulation_{date_name}_EPR{epr}.h5"
        )

        with h5py.File(output_file, "w") as file:
            print(output_file)

            vectors_group = file.create_group("vectors")
            arrays_group = file.create_group("arrays")
            scalars_group = file.create_group("scalars")

            vectors_group.create_dataset("perc_prim_DW", data=perc_band_prim_dw)
            vectors_group.create_dataset("perc_prim_UP", data=perc_band_prim_up)
            vectors_group.create_dataset("perc_sec_DW", data=perc_band_sec_dw)
            vectors_group.create_dataset("perc_sec_UP", data=perc_band_sec_up)
            vectors_group.create_dataset("P_prim_DW", data=p_prim_dw_real)
            vectors_group.create_dataset("P_prim_UP", data=p_prim_up_real)
            vectors_group.create_dataset("P_sec_DW", data=p_sec_dw_real)
            vectors_group.create_dataset("P_sec_UP", data=p_sec_up_real)
            vectors_group.create_dataset("E_qrt_unbalanced", data=e_qrt_unbalanced)

            arrays_group.create_dataset("SOC", data=soc_real)

            scalars_group.create_dataset("E_daily_unbalanced", data=e_daily_unbalanced)
            scalars_group.create_dataset("Revenues_EUR", data=rev_tot)
            scalars_group.create_dataset("Specific_Revenues_EUR_per_MWh", data=specific_rev_tot)
            scalars_group.create_dataset("E_processed", data=e_processed)
            scalars_group.create_dataset("N_cycles", data=n_cycles)

        count += 1

print(f"{count} files have been processed.")