"""
Real-time simulation script for German optimization results.

For each optimized daily schedule and EPR value, this script rebuilds actual BESS
power flows using realized FCR activation profiles, aFRR energy acceptance data,
applies SOC constraints, settles any imbalance energy, and stores daily metrics
in HDF5 files.

This version assumes that real activation profiles, aFRR energy acceptance values,
and imbalance prices are already available in a single input dataset. Therefore,
no external helper module is needed.
"""

import os
import cloudpickle
import numpy as np
import pandas as pd
import pyomo.environ as pyo


# =============================================================================
# USER SETTINGS
# =============================================================================

EPR_VALUES = [1, 2, 4, 6, 8]

# Folder containing the optimized Pyomo models saved as .pkl files
RESULTS_DIRECTORY = "results/GERMANY/Optimization_Results"

# Folder where simulation results will be saved
OUTPUT_DIRECTORY = "results/GERMANY/Simulation_Results"

# Dataset containing real activation profiles, aFRR energy acceptance, and imbalance prices
REAL_DATA_FILE = "data/GERMANY/real_time_simulation_inputs.csv"

# Expected columns in REAL_DATA_FILE:
#
# date                 string, format YYYY_MM_DD
# quarter              integer from 1 to 96
# fcr_up_activation    upward FCR activation as percentage of reserved band [%]
# fcr_dw_activation    downward FCR activation as percentage of reserved band [%]
# afrr_up_acceptance   upward aFRR energy acceptance factor [-]
# afrr_dw_acceptance   downward aFRR energy acceptance factor [-]
# imbalance_price      imbalance price [€/MWh]
#
# Notes:
# - afrr_up_acceptance and afrr_dw_acceptance should be between 0 and 1.
# - If only upward aFRR is accepted, use afrr_up_acceptance = 1 and afrr_dw_acceptance = 0.
# - If only downward aFRR is accepted, use afrr_up_acceptance = 0 and afrr_dw_acceptance = 1.
# - If neither direction is accepted, use both equal to 0.
# - If both directions are accepted, use fractional values representing the activated share
#   in each direction.
#
# Example:
#
# date,quarter,fcr_up_activation,fcr_dw_activation,afrr_up_acceptance,afrr_dw_acceptance,imbalance_price
# 2023_01_01,1,0.12,0.00,1.00,0.00,125.4
# 2023_01_01,2,0.00,0.08,0.00,1.00,119.8


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def load_real_time_data(file_path):
    """
    Load the dataset containing real FCR activation, aFRR acceptance, and imbalance prices.

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
        "afrr_up_acceptance",
        "afrr_dw_acceptance",
        "imbalance_price",
    ]

    data = pd.read_csv(file_path)

    missing_columns = [column for column in required_columns if column not in data.columns]
    if missing_columns:
        raise ValueError(
            "The real-time input dataset is missing the following columns: "
            f"{missing_columns}"
        )

    data = data.sort_values(["date", "quarter"]).reset_index(drop=True)

    return data


def get_daily_real_time_inputs(real_time_data, date_name):
    """
    Extract real simulation inputs for one day.

    Parameters
    ----------
    real_time_data : pandas.DataFrame
        Full real-time input dataset.
    date_name : str
        Date string in the format YYYY_MM_DD.

    Returns
    -------
    tuple of numpy.ndarray
        FCR upward activation, FCR downward activation, aFRR upward acceptance,
        aFRR downward acceptance, and imbalance prices.
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
    secondary_up_acc = daily_data["afrr_up_acceptance"].to_numpy()
    secondary_dw_acc = daily_data["afrr_dw_acceptance"].to_numpy()
    imbalance_prices = daily_data["imbalance_price"].to_numpy()

    return (
        perc_band_prim_up,
        perc_band_prim_dw,
        secondary_up_acc,
        secondary_dw_acc,
        imbalance_prices,
    )


def extract_date_from_filename(file_name):
    """
    Extract the date from an optimization result filename.

    Expected filename format:
    GER_opt_results_YYYY_MM_DD_EPRx.pkl

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
            f"GER_opt_results_{date_name}_EPR{epr}.pkl"
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
            secondary_up_acc,
            secondary_dw_acc,
            imbalance_prices,
        ) = get_daily_real_time_inputs(real_time_data, date_name)

        p_prim_up_real = []
        p_prim_dw_real = []
        p_sec_up_real = []
        p_sec_dw_real = []
        p_bess_real = []

        soc_real = np.zeros(97)
        e_unbalanced = np.zeros(96)

        bess_capacity = pyo.value(results.BESS_capacity)

        for bl in range(1, 7):
            for h in range(1, 5):
                for q in range(1, 5):
                    index = (bl - 1) * 16 + (h - 1) * 4 + q - 1

                    p_prim_up_real.append(
                        pyo.value(results.P_band_prim[bl])
                        * perc_band_prim_up[index]
                        / 100
                    )

                    p_prim_dw_real.append(
                        pyo.value(results.P_band_prim[bl])
                        * perc_band_prim_dw[index]
                        / 100
                    )

                    if secondary_up_acc[index] == 1:
                        p_sec_up_real.append(pyo.value(results.P_band_sec_UP[bl]))
                        p_sec_dw_real.append(0)

                    elif secondary_dw_acc[index] == 1:
                        p_sec_dw_real.append(pyo.value(results.P_band_sec_DW[bl]))
                        p_sec_up_real.append(0)

                    elif secondary_up_acc[index] + secondary_dw_acc[index] == 0:
                        p_sec_up_real.append(0)
                        p_sec_dw_real.append(0)

                    else:
                        p_sec_up_real.append(
                            pyo.value(results.P_band_sec_UP[bl])
                            * secondary_up_acc[index]
                        )
                        p_sec_dw_real.append(
                            pyo.value(results.P_band_sec_DW[bl])
                            * secondary_dw_acc[index]
                        )

        soc_real[0] = 50

        for bl in range(1, 7):
            for h in range(1, 5):
                for q in range(1, 5):
                    index = (bl - 1) * 16 + (h - 1) * 4 + q - 1

                    p_dis = (
                        p_prim_up_real[index]
                        + p_sec_up_real[index]
                        + pyo.value(results.P_ter_UP[bl, h, q] + results.P_sold[bl, h])
                    )

                    p_cha = (
                        p_prim_dw_real[index]
                        + p_sec_dw_real[index]
                        + pyo.value(results.P_ter_DW[bl, h, q] + results.P_purch[bl, h])
                    )

                    bess_power = p_dis - p_cha
                    p_bess_real.append(bess_power)

                    soc_real[index + 1] = update_soc(
                        previous_soc=soc_real[index],
                        bess_power=bess_power,
                        bess_capacity=bess_capacity,
                    )

                    if soc_real[index + 1] > 100:
                        e_unbalanced[index] = (
                            (soc_real[index + 1] - 100)
                            / 100
                            * bess_capacity
                        )
                        soc_real[index + 1] = 100

                    if soc_real[index + 1] < 0:
                        e_unbalanced[index] = (
                            soc_real[index + 1]
                            / 100
                            * bess_capacity
                        )
                        soc_real[index + 1] = 0

        e_daily_unbalanced = 0

        for t in range(96):
            e_daily_unbalanced += abs(e_unbalanced[t])

        rev_prim_capacity = 0
        rev_sec_capacity = 0
        rev_sec_energy = 0
        rev_ter_capacity = 0
        rev_ter_energy = 0
        rev_dam = 0
        rev_soc = 0
        rev_unbalancing = 0

        rev_soc = pyo.value(
            (soc_real[96] - results.SOC_initial)
            / 100
            * results.BESS_capacity
            * results.price_DAM_historical
        )

        for bl in range(1, 7):
            rev_prim_capacity += pyo.value(
                results.P_band_prim[bl]
                * results.price_prim_capacity[bl]
            )

            rev_sec_capacity += pyo.value(
                results.P_band_sec_UP[bl]
                * results.price_sec_UP_capacity[bl]
            )
            rev_sec_capacity += pyo.value(
                results.P_band_sec_DW[bl]
                * results.price_sec_DW_capacity[bl]
            )

            rev_ter_capacity += pyo.value(
                results.P_band_ter_UP[bl]
                * results.price_ter_UP_capacity[bl]
            )
            rev_ter_capacity += pyo.value(
                results.P_band_ter_DW[bl]
                * results.price_ter_DW_capacity[bl]
            )

            for h in range(1, 5):
                rev_dam += pyo.value(
                    (results.P_sold[bl, h] - results.P_purch[bl, h])
                    * results.price_DAM[bl, h]
                )

                for q in range(1, 5):
                    index = (bl - 1) * 16 + (h - 1) * 4 + q - 1

                    rev_sec_energy += pyo.value(
                        p_sec_up_real[index]
                        / 4
                        * results.price_sec_UP_energy[bl, h, q]
                    )
                    rev_sec_energy -= pyo.value(
                        p_sec_dw_real[index]
                        / 4
                        * results.price_sec_DW_energy[bl, h, q]
                    )

                    rev_ter_energy += pyo.value(
                        results.P_ter_UP[bl, h, q]
                        / 4
                        * results.price_ter_UP_energy[bl, h, q]
                    )
                    rev_ter_energy -= pyo.value(
                        results.P_ter_DW[bl, h, q]
                        / 4
                        * results.price_ter_DW_energy[bl, h, q]
                    )

                    rev_unbalancing += (
                        e_unbalanced[index]
                        * imbalance_prices[index]
                    )

        print(f"Imbalance revenue: {rev_unbalancing} €")

        rev_tot = pyo.value(
            rev_prim_capacity
            + rev_sec_capacity
            + rev_ter_capacity
            + rev_sec_energy
            + rev_ter_energy
            + rev_dam
            + rev_soc
            + rev_unbalancing
        )

        print(f"Total revenue: {rev_tot} €")

        specific_rev_tot = rev_tot / bess_capacity

        e_processed = 0

        for bl in range(1, 7):
            for h in range(1, 5):
                for q in range(1, 5):
                    index = (bl - 1) * 16 + (h - 1) * 4 + q - 1
                    e_processed += abs(
                        p_bess_real[index] / 4
                        + e_unbalanced[index]
                    )

        print(f"EPR={epr}; day={date_name}:")
        print(f"Processed energy = {e_processed} MWh")
        print(f"Unbalanced energy = {e_daily_unbalanced} MWh")

        n_cycles = e_processed / bess_capacity

        output_file = (
            f"{OUTPUT_DIRECTORY}/"
            f"GER_simulation_{date_name}_EPR{epr}.h5"
        )

        with h5py.File(output_file, "w") as file:
            print(output_file)

            vectors_group = file.create_group("vectors")
            scalars_group = file.create_group("scalars")

            vectors_group.create_dataset("perc_prim_DW", data=perc_band_prim_dw)
            vectors_group.create_dataset("perc_prim_UP", data=perc_band_prim_up)
            vectors_group.create_dataset("acc_sec_DW", data=secondary_dw_acc)
            vectors_group.create_dataset("acc_sec_UP", data=secondary_up_acc)
            vectors_group.create_dataset("P_prim_DW", data=p_prim_dw_real)
            vectors_group.create_dataset("P_prim_UP", data=p_prim_up_real)
            vectors_group.create_dataset("P_sec_DW", data=p_sec_dw_real)
            vectors_group.create_dataset("P_sec_UP", data=p_sec_up_real)
            vectors_group.create_dataset("E_qrt_unbalanced", data=e_unbalanced)
            vectors_group.create_dataset("SOC", data=soc_real)

            scalars_group.create_dataset("E_daily_unbalanced", data=e_daily_unbalanced)
            scalars_group.create_dataset("Revenues_EUR", data=rev_tot)
            scalars_group.create_dataset("Specific_Revenues_EUR_per_MWh", data=specific_rev_tot)
            scalars_group.create_dataset("E_processed", data=e_processed)
            scalars_group.create_dataset("N_cycles", data=n_cycles)

        count += 1

print(f"{count} files have been processed.")