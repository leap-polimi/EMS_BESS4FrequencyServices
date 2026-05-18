# Data folder

This folder is intended to contain the processed input data required by the optimization and simulation scripts.

Raw market data and data-preparation scripts are not included in this repository. Users are expected to prepare the input datasets externally and place them in the folder structure described below.

Two example Pyomo `.dat` files are provided in the repository to clarify the expected format of the optimization inputs:

```text
data/Italy/input_data/ITA_input_data_2023_01_15.dat
data/Germany/input_data/GER_input_data_2023_01_15.dat
```

These files correspond to one example day, 15 January 2023, and can be used as templates for preparing the full yearly dataset.

---

## Expected folder structure

```text
data/
|
|-- Italy/
|   |-- input_data/
|   |   |-- ITA_input_data_YYYY_MM_DD.dat
|   |   `-- ...
|   |
|   `-- real_time_simulation_inputs.csv
|
|-- Germany/
|   |-- input_data/
|   |   |-- GER_input_data_YYYY_MM_DD.dat
|   |   `-- ...
|   |
|   `-- real_time_simulation_inputs.csv
|
`-- README.md
```

The optimization runners expect one `.dat` file per simulated day. The recommended naming convention is:

```text
ITA_input_data_YYYY_MM_DD.dat
GER_input_data_YYYY_MM_DD.dat
```

For example:

```text
ITA_input_data_2023_01_15.dat
GER_input_data_2023_01_15.dat
```

The date format must be consistent with the naming convention used by the optimization runners, because the scripts extract the year, month, and day directly from the file name.

---

# Optimization input files

The optimization models use Pyomo `DataPortal` input files. Each `.dat` file defines the numerical values of the model parameters for one day.

The files should follow the standard Pyomo `.dat` syntax:

```text
param parameter_name :=
index_1 value_1
index_2 value_2
...
;
```

For multi-index parameters, each row contains all indices followed by the parameter value:

```text
param parameter_name :=
index_1 index_2 value
...
;
```

or:

```text
param parameter_name :=
index_1 index_2 index_3 value
...
;
```

---

## Italian optimization input file

Example file:

```text
examples/ITA_input_data_2023_01_15.dat
```

This file is used by:

```text
src/ITA_BESS_optimizer.py
src/ITA_BESS_optimizer_run.py
```

The Italian model uses:

- 24 hourly intervals;
- 4 quarter-hours per hour;
- 6 mFRR bid-acceptance scenarios.

Therefore, the main index sets are:

```text
h  = 1,...,24
q  = 1,...,4
sc = 1,...,6
```

### Required Italian parameters

| Parameter | Indices | Description | Unit / meaning |
|---|---:|---|---|
| `price_DAM` | `h` | Day-Ahead Market price | €/MWh |
| `price_prim_UP` | `h` | Upward FCR energy remuneration price | €/MWh |
| `price_prim_DW` | `h` | Downward FCR energy remuneration price | €/MWh |
| `price_sec_UP` | `h` | Upward aFRR energy remuneration price | €/MWh |
| `price_sec_DW` | `h` | Downward aFRR energy remuneration price | €/MWh |
| `offer_ter_UP` | `h` | Upward mFRR energy bid price | €/MWh |
| `offer_ter_DW` | `h` | Downward mFRR energy bid price | €/MWh |
| `perc_band_prim_UP` | `h, q` | Mean upward FCR activation in each quarter-hour | % of reserved band |
| `perc_band_prim_DW` | `h, q` | Mean downward FCR activation in each quarter-hour | % of reserved band |
| `perc_band_sec_UP` | `h, q` | Mean upward aFRR activation in each quarter-hour | % of reserved band |
| `perc_band_sec_DW` | `h, q` | Mean downward aFRR activation in each quarter-hour | % of reserved band |
| `y_ter_UP_par` | `sc, h` | Upward mFRR bid-acceptance state | 1 if accepted, 0 otherwise |
| `y_ter_DW_par` | `sc, h` | Downward mFRR bid-acceptance state | 1 if accepted, 0 otherwise |
| `p_sc` | `sc` | Probability of each mFRR scenario | Probability, sum should be 1 |
| `perc_band_prim_UP_second` | `h, q, min, sec` | Second-level upward FCR activation | % of reserved band |
| `perc_band_prim_DW_second` | `h, q, min, sec` | Second-level downward FCR activation | % of reserved band |
| `perc_band_sec_UP_minute` | `h, q, min` | Minute-level upward aFRR activation | % of reserved band |
| `perc_band_sec_DW_minute` | `h, q, min` | Minute-level downward aFRR activation | % of reserved band |

The second-level and minute-level activation parameters are included because they are part of the model input structure. If a simplified model version does not use these parameters directly, they should still be provided unless the corresponding Pyomo parameters are removed from the model.

### Example: hourly parameter

```text
param price_DAM :=
1 155.6
2 146.3
...
24 115.0
;
```

### Example: quarter-hour parameter

```text
param perc_band_prim_UP :=
1 1 0.0
1 2 0.1
...
24 4 0.0
;
```

### Example: scenario-dependent parameter

```text
param y_ter_UP_par :=
1 1 0
1 2 0
...
6 24 1
;
```

---

## German optimization input file

Example file:

```text
examples/GER_input_data_2023_01_15.dat
```

This file is used by:

```text
src/GER_BESS_optimizer.py
src/GER_BESS_optimizer_run.py
```

The German model uses:

- 6 reserve-market blocks;
- 4 hours per block;
- 4 quarter-hours per hour.

Therefore, the main index sets are:

```text
bl = 1,...,6
h  = 1,...,4
q  = 1,...,4
```

### Required German parameters

| Parameter | Indices | Description | Unit / meaning |
|---|---:|---|---|
| `price_DAM` | `bl, h` | Day-Ahead Market price | €/MWh |
| `price_prim_capacity` | `bl` | FCR capacity price | €/MW/block or model-consistent capacity price |
| `y_prim_capacity` | `bl` | FCR capacity bid-acceptance state | 1 if accepted, 0 otherwise |
| `price_sec_UP_capacity` | `bl` | Upward aFRR capacity price offer | €/MW/block or model-consistent capacity price |
| `y_sec_UP_capacity` | `bl` | Upward aFRR capacity bid-acceptance state | 1 if accepted, 0 otherwise |
| `price_sec_DW_capacity` | `bl` | Downward aFRR capacity price offer | €/MW/block or model-consistent capacity price |
| `y_sec_DW_capacity` | `bl` | Downward aFRR capacity bid-acceptance state | 1 if accepted, 0 otherwise |
| `price_ter_UP_capacity` | `bl` | Upward mFRR capacity price offer | €/MW/block or model-consistent capacity price |
| `y_ter_UP_capacity` | `bl` | Upward mFRR capacity bid-acceptance state | 1 if accepted, 0 otherwise |
| `price_ter_DW_capacity` | `bl` | Downward mFRR capacity price offer | €/MW/block or model-consistent capacity price |
| `y_ter_DW_capacity` | `bl` | Downward mFRR capacity bid-acceptance state | 1 if accepted, 0 otherwise |
| `price_sec_UP_energy` | `bl, h, q` | Upward aFRR energy price offer | €/MWh |
| `y_sec_UP_energy` | `bl, h, q` | Upward aFRR energy acceptance/activation factor | 0 to 1 |
| `price_sec_DW_energy` | `bl, h, q` | Downward aFRR energy price offer | €/MWh |
| `y_sec_DW_energy` | `bl, h, q` | Downward aFRR energy acceptance/activation factor | 0 to 1 |
| `price_ter_UP_energy` | `bl, h, q` | Upward mFRR energy price offer | €/MWh |
| `y_ter_UP_energy` | `bl, h, q` | Upward mFRR energy bid-acceptance state | 1 if accepted, 0 otherwise |
| `price_ter_DW_energy` | `bl, h, q` | Downward mFRR energy price offer | €/MWh |
| `y_ter_DW_energy` | `bl, h, q` | Downward mFRR energy bid-acceptance state | 1 if accepted, 0 otherwise |
| `perc_band_prim_UP` | `bl, h, q` | Mean upward FCR activation in each quarter-hour | % of reserved band |
| `perc_band_prim_UP_second` | `bl, h, q, min, sec` | Second-level upward FCR activation | % of reserved band |
| `perc_band_prim_DW` | `bl, h, q` | Mean downward FCR activation in each quarter-hour | % of reserved band |
| `perc_band_prim_DW_second` | `bl, h, q, min, sec` | Second-level downward FCR activation | % of reserved band |

### Example: block-hour parameter

```text
param price_DAM :=
1 1 3.94
1 2 1.71
...
6 4 37.47
;
```

### Example: block-level parameter

```text
param price_prim_capacity :=
1 100
2 86.9
...
6 65.91
;
```

### Example: block-hour-quarter parameter

```text
param price_sec_UP_energy :=
1 1 1 0.0
1 1 2 0.0
...
6 4 4 25.0
;
```

---

# Simulation input files

After running the optimization, the real-time simulation scripts require one CSV file per country containing realized activation, acceptance, and imbalance-price data.

These files are not Pyomo `.dat` files. They are standard CSV files used by:

```text
src/ITA_BESS_simulator.py
src/GER_BESS_simulator.py
```

---

## Italian simulation CSV

Expected file:

```text
data/Italy/real_time_simulation_inputs.csv
```

Expected columns:

| Column | Description | Unit / meaning |
|---|---|---|
| `date` | Day identifier | `YYYY_MM_DD` |
| `quarter` | Quarter-hour of the day | 1 to 96 |
| `fcr_up_activation` | Real upward FCR activation | % of reserved band |
| `fcr_dw_activation` | Real downward FCR activation | % of reserved band |
| `afrr_up_activation` | Real upward aFRR activation | % of reserved band |
| `afrr_dw_activation` | Real downward aFRR activation | % of reserved band |
| `imbalance_price` | Imbalance settlement price | €/MWh |

Example:

```csv
date,quarter,fcr_up_activation,fcr_dw_activation,afrr_up_activation,afrr_dw_activation,imbalance_price
2023_01_15,1,0.12,0.00,3.45,0.00,125.4
2023_01_15,2,0.00,0.08,0.00,2.10,119.8
```

---

## German simulation CSV

Expected file:

```text
data/Germany/real_time_simulation_inputs.csv
```

Expected columns:

| Column | Description | Unit / meaning |
|---|---|---|
| `date` | Day identifier | `YYYY_MM_DD` |
| `quarter` | Quarter-hour of the day | 1 to 96 |
| `fcr_up_activation` | Real upward FCR activation | % of reserved band |
| `fcr_dw_activation` | Real downward FCR activation | % of reserved band |
| `afrr_up_acceptance` | Real upward aFRR energy acceptance or activation factor | 0 to 1 |
| `afrr_dw_acceptance` | Real downward aFRR energy acceptance or activation factor | 0 to 1 |
| `imbalance_price` | Imbalance settlement price | €/MWh |

Example:

```csv
date,quarter,fcr_up_activation,fcr_dw_activation,afrr_up_acceptance,afrr_dw_acceptance,imbalance_price
2023_01_15,1,0.12,0.00,1.00,0.00,125.4
2023_01_15,2,0.00,0.08,0.00,1.00,119.8
```

For the German simulator:

- if only upward aFRR is accepted, set `afrr_up_acceptance = 1` and `afrr_dw_acceptance = 0`;
- if only downward aFRR is accepted, set `afrr_up_acceptance = 0` and `afrr_dw_acceptance = 1`;
- if neither direction is accepted, set both equal to `0`;
- if both directions are accepted, use fractional values representing the activated share in each direction.

---

# Notes

1. The repository assumes 2023 data and a non-leap year with 365 days.
2. All time series should contain 96 quarter-hour values per day, except hourly or block-level optimization parameters.
3. The optimization runners extract the date from the `.dat` file names, so the naming convention should not be changed unless the runner scripts are modified accordingly.
4. Input prices and activation values must be expressed consistently with the units used in the Pyomo models.
5. Large raw datasets should not be committed to the repository.
6. The example `.dat` files are intended as templates and quick references for formatting; they are not a complete dataset for reproducing the full yearly analysis.
