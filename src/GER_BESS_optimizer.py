"""
German-market Pyomo MILP model for BESS revenue stacking.

This module defines an AbstractModel for a 1 MW battery participating in:
- Day-Ahead Market (DAM) arbitrage;
- Frequency Containment Reserve (FCR) capacity market;
- automatic Frequency Restoration Reserve (aFRR) capacity and energy markets;
- manual Frequency Restoration Reserve (mFRR) capacity and energy markets.

The model uses six 4-hour reserve-market blocks, each with 15-minute operating resolution.
"""

from pyomo.core import *
import pyomo.environ as pyo

model = AbstractModel()

"""
=============================================================================================
                                            SETS
=============================================================================================
"""

# Time-index sets
model.n_blocks = Param(default=6)
model.n_hours = Param(default=4)
model.n_quarter = Param(default=4)
model.n_minutes = Param(default=15)
model.n_seconds = Param(default=60)

model.bl = RangeSet(model.n_blocks)  # From 1 to 6
model.h = RangeSet(model.n_hours)
model.qrt = RangeSet(model.n_quarter)
model.min = RangeSet(model.n_minutes)
model.sec = RangeSet(model.n_seconds)

model.BL = Set(initialize=model.bl, ordered=True)
model.H = Set(initialize=model.h, ordered=True)
model.QRT = Set(initialize=model.qrt, ordered=True)
model.MIN = Set(initialize=model.min, ordered=True)
model.SEC = Set(initialize=model.sec, ordered=True)


"""
=============================================================================================
                                        PARAMETERS
=============================================================================================
"""

# Battery
model.EPR = Param(default=1)
model.BESS_Pmax = Param(default=1)  # Battery rated power [MW]


def E_BESS_definition(model):
    val = model.BESS_Pmax * model.EPR
    return val


model.BESS_capacity = Param(initialize=E_BESS_definition)  # Battery capacity [MWh]

# BESS efficiency values in the stepwise efficiency model
model.eta_cha_a15 = Param(default=0.972)
model.eta_cha_b15 = Param(default=0.55)
model.eta_dis_a15 = Param(default=0.868)
model.eta_dis_b15 = Param(default=0.50)
model.delta_BESS = Param(default=0.15)

model.SOC_min = Param(default=0)
model.SOC_max = Param(default=100)
model.SOC_initial = Param(default=50)
model.bigN = Param(default=100000000)  # Big-M value used in the constraints

# Market prices and service remuneration parameters
model.price_DAM = Param(model.BL, model.H, within=Reals)  # Hourly DAM clearing price
model.price_DAM_historical = Param(default=95.2)  # Average 2023 DAM price in Germany

model.price_prim_capacity = Param(model.BL, within=Reals)  # FCR capacity price [€/MW/h]

model.price_sec_UP_capacity = Param(model.BL, within=Reals)  # Upward aFRR capacity price offer [€/MW/h]
model.price_sec_DW_capacity = Param(model.BL, within=Reals)  # Downward aFRR capacity price offer [€/MW/h]
model.price_sec_UP_energy = Param(model.BL, model.H, model.QRT, within=Reals)  # Upward aFRR energy price offer [€/MWh]
model.price_sec_DW_energy = Param(model.BL, model.H, model.QRT, within=Reals)  # Downward aFRR energy price offer [€/MWh]

model.price_ter_UP_capacity = Param(model.BL, within=Reals)  # Upward mFRR capacity price offer [€/MW/h]
model.price_ter_DW_capacity = Param(model.BL, within=Reals)  # Downward mFRR capacity price offer [€/MW/h]
model.price_ter_UP_energy = Param(model.BL, model.H, model.QRT, within=Reals)  # Upward mFRR energy price offer [€/MWh]
model.price_ter_DW_energy = Param(model.BL, model.H, model.QRT, within=Reals)  # Downward mFRR energy price offer [€/MWh]

model.perc_band_prim_UP_second = Param(model.BL, model.H, model.QRT, model.MIN, model.SEC, within=Reals)  # Second-level upward FCR activation [%]
model.perc_band_prim_UP = Param(model.BL, model.H, model.QRT, within=Reals)  # Mean quarter-hour upward FCR activation [%]
model.perc_band_prim_DW_second = Param(model.BL, model.H, model.QRT, model.MIN, model.SEC, within=Reals)  # Second-level downward FCR activation [%]
model.perc_band_prim_DW = Param(model.BL, model.H, model.QRT, within=Reals)  # Mean quarter-hour downward FCR activation [%]

# Binary and continuous parameters identifying market acceptance states

# FCR capacity bid state: 1 if accepted, 0 otherwise
model.y_prim_capacity = Param(model.BL, within=Binary)

# aFRR capacity bid state: 1 if accepted, 0 otherwise
model.y_sec_UP_capacity = Param(model.BL, within=Binary)
model.y_sec_DW_capacity = Param(model.BL, within=Binary)

# aFRR energy bid state.
# Values may range from 0 to 1 because activation depends on both bid acceptance
# and the share of activated energy in each direction.
model.y_sec_UP_energy = Param(model.BL, model.H, model.QRT, within=Reals)
model.y_sec_DW_energy = Param(model.BL, model.H, model.QRT, within=Reals)

# mFRR capacity bid state: 1 if accepted, 0 otherwise
model.y_ter_UP_capacity = Param(model.BL, within=Binary)
model.y_ter_DW_capacity = Param(model.BL, within=Binary)

# mFRR energy bid state: 1 if accepted, 0 otherwise
model.y_ter_UP_energy = Param(model.BL, model.H, model.QRT, within=Binary)
model.y_ter_DW_energy = Param(model.BL, model.H, model.QRT, within=Binary)


"""
=============================================================================================
                                            VARIABLES
=============================================================================================
"""

# Physical power flows

# BESS power flows
model.P_cha = Var(model.BL, model.H, model.QRT, within=NonNegativeReals)
model.P_dis = Var(model.BL, model.H, model.QRT, within=NonNegativeReals)
model.P_BESS_abs = Var(model.BL, model.H, model.QRT, within=NonNegativeReals)

model.y_cha = Var(model.BL, model.H, model.QRT, within=Binary)  # 1 if the BESS is charging, 0 otherwise
model.y_dis = Var(model.BL, model.H, model.QRT, within=Binary)  # 1 if the BESS is discharging, 0 otherwise
model.y_BESS = Var(model.BL, model.H, model.QRT, within=Binary)  # 1 if the BESS is active, 0 otherwise

# BESS power flows depending on operating power level
model.P_dis_a15 = Var(model.BL, model.H, model.QRT, within=NonNegativeReals)  # Discharge power above 15% of rated power
model.P_dis_b15 = Var(model.BL, model.H, model.QRT, within=NonNegativeReals)  # Discharge power below 15% of rated power
model.P_cha_a15 = Var(model.BL, model.H, model.QRT, within=NonNegativeReals)  # Charge power above 15% of rated power
model.P_cha_b15 = Var(model.BL, model.H, model.QRT, within=NonNegativeReals)  # Charge power below 15% of rated power

model.y_dis_a15 = Var(model.BL, model.H, model.QRT, within=Binary)  # 1 if discharging above 15% of rated power
model.y_dis_b15 = Var(model.BL, model.H, model.QRT, within=Binary)  # 1 if discharging below 15% of rated power
model.y_cha_a15 = Var(model.BL, model.H, model.QRT, within=Binary)  # 1 if charging above 15% of rated power
model.y_cha_b15 = Var(model.BL, model.H, model.QRT, within=Binary)  # 1 if charging below 15% of rated power

model.SOC = Var(model.BL, model.H, model.QRT, within=NonNegativeReals)  # State of charge [%]

# Economic power flows

# DAM schedule
model.P_purch = Var(model.BL, model.H, within=NonNegativeReals)
model.P_sold = Var(model.BL, model.H, within=NonNegativeReals)
model.y_purch = Var(model.BL, model.H, within=Binary)
model.y_sold = Var(model.BL, model.H, within=Binary)

# FCR
model.P_band_prim = Var(model.BL, within=NonNegativeReals)  # Symmetric FCR capacity band, defined for each 4-hour block
model.P_prim_UP = Var(model.BL, model.H, model.QRT, within=NonNegativeReals)
model.P_prim_DW = Var(model.BL, model.H, model.QRT, within=NonNegativeReals)

# aFRR
model.P_band_sec_UP = Var(model.BL, within=NonNegativeReals)  # Upward aFRR capacity band for each 4-hour block
model.P_band_sec_DW = Var(model.BL, within=NonNegativeReals)  # Downward aFRR capacity band for each 4-hour block
model.P_sec_UP = Var(model.BL, model.H, model.QRT, within=NonNegativeReals)
model.P_sec_DW = Var(model.BL, model.H, model.QRT, within=NonNegativeReals)

# mFRR
model.P_band_ter_UP = Var(model.BL, within=NonNegativeReals)  # Upward mFRR capacity band for each 4-hour block
model.P_band_ter_DW = Var(model.BL, within=NonNegativeReals)  # Downward mFRR capacity band for each 4-hour block
model.P_ter_UP = Var(model.BL, model.H, model.QRT, within=NonNegativeReals)
model.P_ter_DW = Var(model.BL, model.H, model.QRT, within=NonNegativeReals)


"""
=============================================================================================
                                    OBJECTIVE FUNCTION
=============================================================================================
"""


def objective_function(model):
    revenue = (
        sum(
            sum(
                model.P_sold[bl, h] * model.price_DAM[bl, h]
                - model.P_purch[bl, h] * model.price_DAM[bl, h]
                for h in model.H
            )
            for bl in model.BL
        )
        + sum(
            model.P_band_ter_UP[bl] * model.price_ter_UP_capacity[bl]
            + model.P_band_ter_DW[bl] * model.price_ter_DW_capacity[bl]
            for bl in model.BL
        )
        + sum(
            sum(
                sum(
                    model.P_ter_UP[bl, h, q] / 4 * model.price_ter_UP_energy[bl, h, q]
                    - model.P_ter_DW[bl, h, q] / 4 * model.price_ter_DW_energy[bl, h, q]
                    for q in model.QRT
                )
                for h in model.H
            )
            for bl in model.BL
        )
        + sum(
            model.P_band_sec_UP[bl] * model.price_sec_UP_capacity[bl]
            + model.P_band_sec_DW[bl] * model.price_sec_DW_capacity[bl]
            for bl in model.BL
        )
        + sum(
            sum(
                sum(
                    model.P_sec_UP[bl, h, q] / 4 * model.price_sec_UP_energy[bl, h, q]
                    - model.P_sec_DW[bl, h, q] / 4 * model.price_sec_DW_energy[bl, h, q]
                    for q in model.QRT
                )
                for h in model.H
            )
            for bl in model.BL
        )
        + sum(
            model.P_band_prim[bl] * model.price_prim_capacity[bl]
            for bl in model.BL
        )
        + (
            (
                model.SOC[6, 4, 4]
                + (
                    (
                        model.P_cha_a15[6, 4, 4] * model.eta_cha_a15
                        + model.P_cha_b15[6, 4, 4] * model.eta_cha_b15
                        - model.P_dis_a15[6, 4, 4] / model.eta_dis_a15
                        - model.P_dis_b15[6, 4, 4] / model.eta_dis_b15
                    )
                    / 4
                )
                / model.BESS_capacity
                * 100
                - model.SOC_initial
            )
            / 100
            * model.BESS_capacity
        )
        * model.price_DAM_historical
    )
    return revenue


model.Objective_function = Objective(rule=objective_function, sense=maximize)


"""
=============================================================================================
                                    CONSTRAINTS
=============================================================================================
"""

# BESS constraints

# Absolute BESS power definition
def p_abs_def(model, bl, h, q):
    return model.P_BESS_abs[bl, h, q] == model.P_dis[bl, h, q] + model.P_cha[bl, h, q]


model.P_BESS_abs_def = Constraint(model.BL, model.H, model.QRT, rule=p_abs_def)


# BESS rated power limit
def Battery_power_limit(model, bl, h, q):
    return model.P_BESS_abs[bl, h, q] <= model.BESS_Pmax


model.BESS_power_limit = Constraint(model.BL, model.H, model.QRT, rule=Battery_power_limit)


# SOC computation
def soc_comp(model, bl, h, q):
    if bl == 1 and h == 1 and q == 1:
        return model.SOC[bl, h, q] == model.SOC_initial
    elif q != 1:
        return model.SOC[bl, h, q] == model.SOC[bl, h, q - 1] + (
            (
                model.P_cha_a15[bl, h, q - 1] * model.eta_cha_a15
                + model.P_cha_b15[bl, h, q - 1] * model.eta_cha_b15
                - model.P_dis_a15[bl, h, q - 1] / model.eta_dis_a15
                - model.P_dis_b15[bl, h, q - 1] / model.eta_dis_b15
            )
            / 4
        ) / model.BESS_capacity * 100
    elif q == 1 and h != 1:
        return model.SOC[bl, h, q] == model.SOC[bl, h - 1, 4] + (
            (
                model.P_cha_a15[bl, h - 1, 4] * model.eta_cha_a15
                + model.P_cha_b15[bl, h - 1, 4] * model.eta_cha_b15
                - model.P_dis_a15[bl, h - 1, 4] / model.eta_dis_a15
                - model.P_dis_b15[bl, h - 1, 4] / model.eta_dis_b15
            )
            / 4
        ) / model.BESS_capacity * 100
    elif q == 1 and h == 1 and bl != 1:
        return model.SOC[bl, h, q] == model.SOC[bl - 1, 4, 4] + (
            (
                model.P_cha_a15[bl - 1, 4, 4] * model.eta_cha_a15
                + model.P_cha_b15[bl - 1, 4, 4] * model.eta_cha_b15
                - model.P_dis_a15[bl - 1, 4, 4] / model.eta_dis_a15
                - model.P_dis_b15[bl - 1, 4, 4] / model.eta_dis_b15
            )
            / 4
        ) / model.BESS_capacity * 100


model.SOC_Computation = Constraint(model.BL, model.H, model.QRT, rule=soc_comp)

# No final SOC equality constraint is imposed, otherwise mFRR participation
# could make the optimization problem infeasible.

# SOC lower bound
def soc_min(model, bl, h, q):
    return model.SOC[bl, h, q] >= model.SOC_min


model.SOC_min_constraint = Constraint(model.BL, model.H, model.QRT, rule=soc_min)


# SOC upper bound
def soc_max(model, bl, h, q):
    return model.SOC[bl, h, q] <= model.SOC_max


model.SOC_max_constraint = Constraint(model.BL, model.H, model.QRT, rule=soc_max)


# Total charging power definition
def pch(model, bl, h, q):
    return model.P_cha[bl, h, q] == model.P_cha_a15[bl, h, q] + model.P_cha_b15[bl, h, q]


model.P_cha_constraint = Constraint(model.BL, model.H, model.QRT, rule=pch)


# Total discharging power definition
def pdisch(model, bl, h, q):
    return model.P_dis[bl, h, q] == model.P_dis_a15[bl, h, q] + model.P_dis_b15[bl, h, q]


model.P_dis_constraint = Constraint(model.BL, model.H, model.QRT, rule=pdisch)


# Charging above 15% of rated power activation state
def pcha_a15_state(model, bl, h, q):
    return model.P_cha_a15[bl, h, q] <= model.y_cha_a15[bl, h, q] * model.bigN


model.Pcha_a15_state_constraint = Constraint(model.BL, model.H, model.QRT, rule=pcha_a15_state)


# Charging below 15% of rated power activation state
def pcha_b15_state(model, bl, h, q):
    return model.P_cha_b15[bl, h, q] <= model.y_cha_b15[bl, h, q] * model.bigN


model.Pcha_b15_state_constraint = Constraint(model.BL, model.H, model.QRT, rule=pcha_b15_state)


# Discharging above 15% of rated power activation state
def pdis_a15_state(model, bl, h, q):
    return model.P_dis_a15[bl, h, q] <= model.y_dis_a15[bl, h, q] * model.bigN


model.Pdis_a15_state_constraint = Constraint(model.BL, model.H, model.QRT, rule=pdis_a15_state)


# Discharging below 15% of rated power activation state
def pdis_b15_state(model, bl, h, q):
    return model.P_dis_b15[bl, h, q] <= model.y_dis_b15[bl, h, q] * model.bigN


model.Pdis_b15_state_constraint = Constraint(model.BL, model.H, model.QRT, rule=pdis_b15_state)


# Charging power-level state selection
def pcha_state(model, bl, h, q):
    return model.y_cha_a15[bl, h, q] + model.y_cha_b15[bl, h, q] == model.y_cha[bl, h, q]


model.Pcha_state_constraint = Constraint(model.BL, model.H, model.QRT, rule=pcha_state)


# Discharging power-level state selection
def pdis_state(model, bl, h, q):
    return model.y_dis_a15[bl, h, q] + model.y_dis_b15[bl, h, q] == model.y_dis[bl, h, q]


model.Pdis_state_constraint = Constraint(model.BL, model.H, model.QRT, rule=pdis_state)


# Mutually exclusive charging/discharging state
def p_bess_state(model, bl, h, q):
    return model.y_cha[bl, h, q] + model.y_dis[bl, h, q] == model.y_BESS[bl, h, q]


model.P_BESS_state = Constraint(model.BL, model.H, model.QRT, rule=p_bess_state)


# Charging below 15% of rated power definition
def pcha_b15(model, bl, h, q):
    return model.P_cha_b15[bl, h, q] <= model.BESS_Pmax * model.delta_BESS


model.Pcha_b15_constraint = Constraint(model.BL, model.H, model.QRT, rule=pcha_b15)


# Discharging below 15% of rated power definition
def pdis_b15(model, bl, h, q):
    return model.P_dis_b15[bl, h, q] <= model.BESS_Pmax * model.delta_BESS


model.Pdis_b15_constraint = Constraint(model.BL, model.H, model.QRT, rule=pdis_b15)


# Charging above 15% of rated power definition
def pcha_a15(model, bl, h, q):
    return model.P_cha_a15[bl, h, q] >= (
        model.BESS_Pmax * model.delta_BESS
        - model.bigN * (1 - model.y_cha_a15[bl, h, q])
    )


model.Pcha_a15_constraint = Constraint(model.BL, model.H, model.QRT, rule=pcha_a15)


# Discharging above 15% of rated power definition
def pdis_a15(model, bl, h, q):
    return model.P_dis_a15[bl, h, q] >= (
        model.BESS_Pmax * model.delta_BESS
        - model.bigN * (1 - model.y_dis_a15[bl, h, q])
    )


model.Pdis_a15_constraint = Constraint(model.BL, model.H, model.QRT, rule=pdis_a15)


# BESS activity state
def bess_op(model, bl, h, q):
    return model.y_BESS[bl, h, q] <= model.P_BESS_abs[bl, h, q] * model.bigN


model.BESS_op_constraint = Constraint(model.BL, model.H, model.QRT, rule=bess_op)


# =============================================================================
# FCR CONSTRAINTS
# =============================================================================

# FCR capacity band must be zero if the capacity bid is not accepted
def P_pr_band_acc(model, bl):
    return model.P_band_prim[bl] <= model.y_prim_capacity[bl] * model.bigN


model.Primary_reserve_band_acceptance = Constraint(model.BL, rule=P_pr_band_acc)


# Upward FCR power flow from activation percentage and reserved capacity band
def P_pr_up_def(model, bl, h, q):
    return model.P_prim_UP[bl, h, q] == (
        model.perc_band_prim_UP[bl, h, q] / 100 * model.P_band_prim[bl]
    )


model.Primary_reserve_UP_flow = Constraint(model.BL, model.H, model.QRT, rule=P_pr_up_def)


# Downward FCR power flow from activation percentage and reserved capacity band
def P_pr_dw_def(model, bl, h, q):
    return model.P_prim_DW[bl, h, q] == (
        model.perc_band_prim_DW[bl, h, q] / 100 * model.P_band_prim[bl]
    )


model.Primary_reserve_DW_flow = Constraint(model.BL, model.H, model.QRT, rule=P_pr_dw_def)


# =============================================================================
# aFRR CONSTRAINTS
# =============================================================================

# Upward aFRR capacity band must be zero if the capacity bid is not accepted
def P_sr_up_band_acc(model, bl):
    return model.P_band_sec_UP[bl] <= model.y_sec_UP_capacity[bl] * model.bigN


model.Secondary_reserve_UP_band_acceptance = Constraint(model.BL, rule=P_sr_up_band_acc)


# Downward aFRR capacity band must be zero if the capacity bid is not accepted
def P_sr_dw_band_acc(model, bl):
    return model.P_band_sec_DW[bl] <= model.y_sec_DW_capacity[bl] * model.bigN


model.Secondary_reserve_DW_band_acceptance = Constraint(model.BL, rule=P_sr_dw_band_acc)


# Upward aFRR power flow based on capacity and energy market acceptance
def P_sr_up_def1(model, bl, h, q):
    return model.P_sec_UP[bl, h, q] >= (
        model.P_band_sec_UP[bl] * model.y_sec_UP_energy[bl, h, q]
    )


model.Secondary_reserve_UP_flow1 = Constraint(model.BL, model.H, model.QRT, rule=P_sr_up_def1)


def P_sr_up_def2(model, bl, h, q):
    return model.P_sec_UP[bl, h, q] <= (
        model.BESS_Pmax * model.y_sec_UP_energy[bl, h, q]
    )


model.Secondary_reserve_UP_flow2 = Constraint(model.BL, model.H, model.QRT, rule=P_sr_up_def2)


# Downward aFRR power flow based on capacity and energy market acceptance
def P_sr_dw_def1(model, bl, h, q):
    return model.P_sec_DW[bl, h, q] >= (
        model.P_band_sec_DW[bl] * model.y_sec_DW_energy[bl, h, q]
    )


model.Secondary_reserve_DW_flow1 = Constraint(model.BL, model.H, model.QRT, rule=P_sr_dw_def1)


def P_sr_dw_def2(model, bl, h, q):
    return model.P_sec_DW[bl, h, q] <= (
        model.BESS_Pmax * model.y_sec_DW_energy[bl, h, q]
    )


model.Secondary_reserve_DW_flow2 = Constraint(model.BL, model.H, model.QRT, rule=P_sr_dw_def2)


# =============================================================================
# mFRR CONSTRAINTS
# =============================================================================

# Upward mFRR capacity band must be zero if the capacity bid is not accepted
def P_tr_up_band_acc(model, bl):
    return model.P_band_ter_UP[bl] <= model.y_ter_UP_capacity[bl] * model.bigN


model.Tertiary_reserve_UP_band_acceptance = Constraint(model.BL, rule=P_tr_up_band_acc)


# Downward mFRR capacity band must be zero if the capacity bid is not accepted
def P_tr_dw_band_acc(model, bl):
    return model.P_band_ter_DW[bl] <= model.y_ter_DW_capacity[bl] * model.bigN


model.Tertiary_reserve_DW_band_acceptance = Constraint(model.BL, rule=P_tr_dw_band_acc)


# Upward mFRR power flow based on capacity and energy market acceptance
def P_tr_up_def1(model, bl, h, q):
    return model.P_ter_UP[bl, h, q] >= (
        model.P_band_ter_UP[bl] * model.y_ter_UP_energy[bl, h, q]
    )


model.Tertiary_reserve_UP_flow1 = Constraint(model.BL, model.H, model.QRT, rule=P_tr_up_def1)


def P_tr_up_def2(model, bl, h, q):
    return model.P_ter_UP[bl, h, q] <= (
        model.BESS_Pmax * model.y_ter_UP_energy[bl, h, q]
    )


model.Tertiary_reserve_UP_flow2 = Constraint(model.BL, model.H, model.QRT, rule=P_tr_up_def2)


# Downward mFRR power flow based on capacity and energy market acceptance
def P_tr_dw_def1(model, bl, h, q):
    return model.P_ter_DW[bl, h, q] >= (
        model.P_band_ter_DW[bl] * model.y_ter_DW_energy[bl, h, q]
    )


model.Tertiary_reserve_DW_flow1 = Constraint(model.BL, model.H, model.QRT, rule=P_tr_dw_def1)


def P_tr_dw_def2(model, bl, h, q):
    return model.P_ter_DW[bl, h, q] <= (
        model.BESS_Pmax * model.y_ter_DW_energy[bl, h, q]
    )


model.Tertiary_reserve_DW_flow2 = Constraint(model.BL, model.H, model.QRT, rule=P_tr_dw_def2)


# =============================================================================
# DAM CONSTRAINTS
# =============================================================================

# The BESS cannot sell and purchase energy on the DAM at the same time
def P_sold_cons(model, bl, h):
    return model.P_sold[bl, h] <= model.y_sold[bl, h] * model.bigN


model.DAM_sold_cons = Constraint(model.BL, model.H, rule=P_sold_cons)


def P_purch_cons(model, bl, h):
    return model.P_purch[bl, h] <= model.y_purch[bl, h] * model.bigN


model.DAM_purch_cons = Constraint(model.BL, model.H, rule=P_purch_cons)


def P_dam_state(model, bl, h):
    return model.y_sold[bl, h] + model.y_purch[bl, h] <= 1


model.DAM_state = Constraint(model.BL, model.H, rule=P_dam_state)


# =============================================================================
# MARKET STACKING CONSTRAINTS
# =============================================================================

# The hourly upward commercial position cannot exceed the rated BESS power
def max_up_offer(model, bl, h):
    return (
        model.P_band_prim[bl]
        + model.P_band_sec_UP[bl]
        + model.P_band_ter_UP[bl]
        + model.P_sold[bl, h]
        <= model.BESS_Pmax
    )


model.max_UP_offer_constr = Constraint(model.BL, model.H, rule=max_up_offer)


# The hourly downward commercial position cannot exceed the rated BESS power
def max_dw_offer(model, bl, h):
    return (
        model.P_band_prim[bl]
        + model.P_band_sec_DW[bl]
        + model.P_band_ter_DW[bl]
        + model.P_purch[bl, h]
        <= model.BESS_Pmax
    )


model.max_DW_offer_constr = Constraint(model.BL, model.H, rule=max_dw_offer)


# Quarter-hour upward activated power plus DAM position cannot exceed rated BESS power
def max_up_qrt_offer(model, bl, h, q):
    return (
        model.P_prim_UP[bl, h, q]
        + model.P_sec_UP[bl, h, q]
        + model.P_ter_UP[bl, h, q]
        + model.P_sold[bl, h]
        <= model.BESS_Pmax
    )


model.max_UP_qrt_offer_constr = Constraint(model.BL, model.H, model.QRT, rule=max_up_qrt_offer)


# Quarter-hour downward activated power plus DAM position cannot exceed rated BESS power
def max_dw_qrt_offer(model, bl, h, q):
    return (
        model.P_prim_DW[bl, h, q]
        + model.P_sec_DW[bl, h, q]
        + model.P_ter_DW[bl, h, q]
        + model.P_purch[bl, h]
        <= model.BESS_Pmax
    )


model.max_DW_qrt_offer_constr = Constraint(model.BL, model.H, model.QRT, rule=max_dw_qrt_offer)


# Power balance at the external grid connection point
def external_eb(model, bl, h, q):
    physical_exchange = model.P_dis[bl, h, q] - model.P_cha[bl, h, q]
    dam_exchange = model.P_sold[bl, h] - model.P_purch[bl, h]
    fcr_exchange = model.P_prim_UP[bl, h, q] - model.P_prim_DW[bl, h, q]
    afrr_exchange = model.P_sec_UP[bl, h, q] - model.P_sec_DW[bl, h, q]
    mfrr_exchange = model.P_ter_UP[bl, h, q] - model.P_ter_DW[bl, h, q]

    return physical_exchange == dam_exchange + fcr_exchange + afrr_exchange + mfrr_exchange


model.external_energy_balance = Constraint(model.BL, model.H, model.QRT, rule=external_eb)