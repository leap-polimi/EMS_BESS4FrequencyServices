# EMS_BESS4FrequencyServices

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.20267236.svg)](https://doi.org/10.5281/zenodo.20267236)

This repository contains Python/Pyomo optimization and simulation models for assessing the revenue potential of utility-scale Battery Energy Storage Systems (BESS) in Italian and German electricity spot and balancing markets.

The models were developed for the paper:

Scrocca, A., Bovera, F., Rancilio, G., and Delfanti, M. (2026).  
**Exploring the true potential of battery revenues stacking in Europe: A comparison of Italian and German electricity spot markets**.  
*Sustainable Energy, Grids and Networks*.

The archived software release is available on Zenodo:

Scrocca, A., & Bovera, F. (2026).  
**EMS_BESS4FrequencyServices** (Version 1.0.0) [Software].  
Zenodo. https://doi.org/10.5281/zenodo.20267236

The code evaluates a front-of-the-meter BESS that stacks:

- Day-Ahead Market (DAM) arbitrage;
- Frequency Containment Reserve (FCR);
- automatic Frequency Restoration Reserve (aFRR);
- manual Frequency Restoration Reserve (mFRR).

The repository includes two country-specific MILP models, one for Italy and one for Germany, reflecting the different market designs, remuneration mechanisms, and balancing-service activation rules.

The modelling framework is composed of two sequential stages:

1. **day-ahead optimization**, where the BESS operator decides the optimal market schedule and reserve capacity allocation;
2. **real-time simulation**, where the day-ahead schedule is tested under realized service activation profiles to evaluate SOC feasibility, imbalance energy, and realized revenues.

---

## Authorship and contributions

This repository is authored by:

- Andrea Scrocca
- Filippo Bovera

Affiliation: Politecnico di Milano, Department of Energy

---

## Citation

If you use this software in scientific work, please cite both the associated paper and the archived software release.

### Associated paper

Scrocca, A., Bovera, F., Rancilio, G., and Delfanti, M. (2026).  
**Exploring the true potential of battery revenues stacking in Europe: A comparison of Italian and German electricity spot markets**.  
*Sustainable Energy, Grids and Networks*.

### Software release

Scrocca, A., & Bovera, F. (2026).  
**BESS Revenue Stacking Models for Italy and Germany** (Version 1.0.0) [Software].  
Zenodo. https://doi.org/10.5281/zenodo.20267236

A machine-readable citation file is available in `CITATION.cff`.

---

## License

This program is distributed under the terms specified in the `LICENSE` file.

---

## Repository structure

```text
BESS_Revenue_Stacking_Models/
|
|-- README.md
|-- requirements.txt
|-- CITATION.cff
|-- LICENSE
|-- .gitignore
|
|-- src/
|   |-- ITA_BESS_optimizer.py
|   |-- ITA_BESS_optimizer_run.py
|   |-- ITA_BESS_simulator.py
|   |-- GER_BESS_optimizer.py
|   |-- GER_BESS_optimizer_run.py
|   `-- GER_BESS_simulator.py
|
|-- data/
|   `-- data_README.md
|
`-- results/
    |-- ITALY/
    |   |-- Optimization_Results/
    |   `-- Simulation_Results/
    |
    `-- GERMANY/
        |-- Optimization_Results/
        `-- Simulation_Results/
```

The repository does **not** include raw market data or data-preparation scripts.  
Input data preparation is assumed to be performed externally. Users should provide the processed Pyomo input files and real-time simulation datasets in the formats described in `data/data_README.md`.

---

# Model overview

The repository contains two optimization models:

- `ITA_BESS_optimizer.py`: Italian electricity-market model;
- `GER_BESS_optimizer.py`: German electricity-market model.

The optimization models are intended to represent the **day-ahead scheduling problem** faced by a BESS operator. At this stage, the model decides how the battery should allocate its available power among the considered markets and services.

In particular, the optimizer determines:

- how much power to sell or purchase in the DAM;
- how much power capacity to reserve for FCR;
- how much upward and downward capacity to reserve for aFRR;
- how much upward and downward capacity to reserve or offer for mFRR;
- the resulting expected BESS charging/discharging profile;
- the expected SOC trajectory.

The optimization time resolution is 15 minutes, but can be adjusted.

The models maximize expected daily market revenues from DAM arbitrage and frequency-service provision, while respecting BESS power limits, SOC limits, service-stacking constraints, and a stepwise efficiency model.

---

## Why a simulation module is needed

The optimization stage represents the schedule that would be prepared before delivery. However, in real operations, the BESS operator cannot know in advance the exact activation of some frequency services.

This is particularly important for:

- **FCR**, whose activation depends on real-time frequency deviations;
- **aFRR**, whose activation depends on real-time balancing needs;
- imbalance settlement, which depends on whether the realized activation profile makes the scheduled operation infeasible with respect to SOC limits.

For this reason, the repository also includes real-time simulation scripts.

The simulation stage takes the optimized day-ahead schedule and applies realized activation and imbalance data. This makes it possible to assess:

- whether the optimized schedule remains physically feasible under real activation profiles;
- whether SOC limits are violated;
- how much imbalance energy is created;
- the economic effect of imbalance settlement;
- the realized revenues after accounting for activation uncertainty.

Therefore, the simulation module is useful for obtaining a more realistic estimate of BESS revenues than the day-ahead optimization alone.

---

## Main modelling assumptions

### Battery model

The BESS is represented through:

- rated power;
- energy capacity, computed from the selected EPR;
- state of charge;
- charge and discharge power;
- power-dependent charge/discharge efficiency;
- charging and discharging mutually exclusive operating states.

The initial SOC is set to 50%.  
The final SOC is not forced to be equal to the initial SOC. Instead, the final SOC is economically valued using a reference DAM price.

---

## Italian model

The Italian model represents a BESS participating in:

- DAM arbitrage in the Italian North bidding zone;
- FCR provision;
- aFRR provision;
- mFRR provision.

The optimization horizon is one day, divided into:

```text
24 hours x 4 quarter-hours = 96 time intervals
```

### Italian market representation

| Service | Modelling approach |
|---|---|
| DAM | Hourly selling and purchasing decisions |
| FCR | Symmetric reserve band; activated according to assumed frequency-deviation profiles |
| aFRR | Upward and downward asymmetric bands; pro-rata activation |
| mFRR | Hourly upward and downward bids with stochastic acceptance scenarios |

The Italian day-ahead optimization determines the optimal allocation of BESS power among DAM, FCR, aFRR, and mFRR. The purpose is to identify where it is most profitable to reserve or offer power capacity, while ensuring that the expected BESS operation remains feasible.

The Italian model includes six mFRR market scenarios.  
Each scenario represents a possible acceptance pattern for upward and downward mFRR bids.
These scenarios should be forecasted using proper models.

The Italian simulation script then evaluates the optimized schedule using realized FCR and aFRR activation profiles and imbalance prices.

---

## German model

The German model represents a BESS participating in:

- DAM arbitrage in the German single price zone;
- FCR capacity market;
- aFRR capacity and energy markets;
- mFRR capacity and energy markets.

The optimization horizon is one day, divided into:

```text
6 reserve-market blocks x 4 hours x 4 quarter-hours = 96 time intervals
```

### German market representation

| Service | Modelling approach |
|---|---|
| DAM | Hourly selling and purchasing decisions |
| FCR | Symmetric capacity band, defined for each 4-hour block |
| aFRR | Upward and downward capacity bands plus energy activation |
| mFRR | Upward and downward capacity bands plus energy activation |

The German day-ahead optimization determines the optimal allocation of BESS power among DAM, FCR, aFRR, and mFRR capacity and energy markets. Since German balancing services are organized in 4-hour blocks, the model decides reserve capacity allocation at block level while preserving 15-minute physical operation.

In the German model, balancing capacity markets are represented through block-level acceptance parameters.  
Energy activation is represented at 15-minute resolution.

The German simulation script then evaluates the optimized schedule using realized FCR activation, realized aFRR energy acceptance, and imbalance prices.

---

# Workflow

The repository is designed to be used in two main steps:

1. **day-ahead optimization under assumed service activation**;
2. **real-time simulation under realized service activation**.

The day-ahead optimization models generate the market schedule and reserve-capacity allocation for each day and EPR value.

The real-time simulation scripts then evaluate the optimized schedules under realized activation and imbalance conditions. This second step is important because FCR and aFRR activation cannot be perfectly known when the day-ahead schedule is created.

---

## 1. Prepare input data

Before running the models, users must prepare the required input files externally.

The repository assumes that the following data are already available:

### Optimization input data

For each day, the user must provide a Pyomo `.dat` file containing the market prices, assumed activation parameters, bid-acceptance parameters, and other model inputs required by the corresponding country model.

Expected folders:

```text
data/Italy/input_data/
data/Germany/input_data/
```

The optimization input data represent the information used when constructing the day-ahead schedule. These inputs are used to decide the optimal allocation of BESS power across DAM and frequency-service markets.

### Simulation input data

The simulators assume that real-time activation and imbalance data are already available in CSV format.

Expected files:

```text
data/Italy/real_time_simulation_inputs.csv
data/Germany/real_time_simulation_inputs.csv
```

The Italian simulation dataset should contain:

```text
date
quarter
fcr_up_activation
fcr_dw_activation
afrr_up_activation
afrr_dw_activation
imbalance_price
```

The German simulation dataset should contain:

```text
date
quarter
fcr_up_activation
fcr_dw_activation
afrr_up_acceptance
afrr_dw_acceptance
imbalance_price
```

The simulation input data represent realized operating conditions. They are used to test whether the day-ahead schedule can actually be followed when real FCR/aFRR activation occurs.

The `date` column should use the format:

```text
YYYY_MM_DD
```

The `quarter` column should go from 1 to 96.

---

## 2. Install dependencies

Create and activate a Python virtual environment:

```bash
python -m venv .venv
```

On Linux/macOS:

```bash
source .venv/bin/activate
```

On Windows:

```bash
.venv\Scripts\activate
```

Install the required Python packages:

```bash
pip install -r requirements.txt
```

A MILP solver is required.  
The original implementation was developed using **Gurobi**.

Other Pyomo-compatible MILP solvers may work, but the full 365-day batch can be computationally demanding.

---

## 3. Run the Italian optimization

Typical command:

```bash
python src/ITA_BESS_optimizer_run.py \
  --input-dir data/Italy/input_data \
  --output-dir results/ITALY/Optimization_Results \
  --solver gurobi \
  --epr-values 1 2 4 6 8
```

The script solves the Italian day-ahead MILP model for each input day and EPR value.

The output files are saved as pickled Pyomo model instances:

```text
results/ITALY/Optimization_Results/ITA_opt_results_YYYY_MM_DD_EPRx.pkl
```

Example:

```text
ITA_opt_results_2023_01_01_EPR1.pkl
```

---

## 4. Run the German optimization

Typical command:

```bash
python src/GER_BESS_optimizer_run.py \
  --input-dir data/Germany/input_data \
  --output-dir results/GERMANY/Optimization_Results \
  --solver gurobi \
  --epr-values 1 2 4 6 8
```

The script solves the German day-ahead MILP model for each input day and EPR value.

The output files are saved as pickled Pyomo model instances:

```text
results/GERMANY/Optimization_Results/GER_opt_results_YYYY_MM_DD_EPRx.pkl
```

Example:

```text
GER_opt_results_2023_01_01_EPR1.pkl
```

---

## 5. Run the Italian real-time simulation

After the Italian optimization has been completed, run:

```bash
python src/ITA_BESS_simulator.py
```

The simulator:

1. loads the optimized day-ahead schedules;
2. reads the realized FCR and aFRR activation profiles;
3. reconstructs the actual BESS power flow;
4. applies SOC limits;
5. computes imbalance energy when SOC limits would be violated;
6. computes the economic effect of imbalance settlement;
7. computes realized daily revenues;
8. saves the results in HDF5 format.

Output files are saved in:

```text
results/ITALY/Simulation_Results/
```

with filenames such as:

```text
ITA_simulation_2023_01_01_EPR1.h5
```

---

## 6. Run the German real-time simulation

After the German optimization has been completed, run:

```bash
python src/GER_BESS_simulator.py
```

The simulator:

1. loads the optimized day-ahead schedules;
2. reads realized FCR activation data;
3. reads realized aFRR energy acceptance data;
4. reconstructs the actual BESS power flow;
5. applies SOC limits;
6. computes imbalance energy when SOC limits would be violated;
7. computes the economic effect of imbalance settlement;
8. computes realized daily revenues;
9. saves the results in HDF5 format.

Output files are saved in:

```text
results/GERMANY/Simulation_Results/
```

with filenames such as:

```text
GER_simulation_2023_01_01_EPR1.h5
```

---

# Output files

## Optimization outputs

The optimization runners generate one `.pkl` file for each day and EPR value.

Each file contains the solved Pyomo model instance and can be inspected to retrieve the day-ahead schedule, including:

- DAM selling and purchasing schedules;
- FCR reserved capacity;
- aFRR reserved capacity;
- mFRR reserved capacity or bids;
- expected BESS charging and discharging power;
- expected SOC trajectory;
- expected objective-function value.

These outputs represent the schedule that the BESS operator would prepare before real-time delivery.

---

## Simulation outputs

The simulation scripts generate one `.h5` file for each day and EPR value.

Each HDF5 file contains the realized outcome of applying the day-ahead schedule to actual activation and imbalance conditions.

Each file contains:

### Vectors

- realized FCR activation;
- realized aFRR activation or acceptance;
- realized FCR power flows;
- realized aFRR power flows;
- imbalance energy.

### Arrays

- realized SOC trajectory.

### Scalars

- realized daily revenue;
- realized specific revenue;
- processed energy;
- number of equivalent cycles;
- daily imbalance energy.

---

# Notes for users

1. Run all commands from the repository root.
2. Input data preparation is not included in this repository.
3. The repository assumes 2023 data and a non-leap year with 365 days.
4. The optimization stage should be interpreted as a day-ahead scheduling problem.
5. The simulation stage should be used to evaluate the effect of real FCR/aFRR activation uncertainty.
6. The model files keep mathematical variable names close to the notation used in the paper.
7. The optimization runners are intended for batch execution over several daily input files.
8. The simulation scripts are intended to be run after the optimization outputs have been generated.
9. Large result folders should not be committed to GitHub unless explicitly needed.
