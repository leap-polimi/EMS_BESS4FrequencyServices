"""
Italian-market Pyomo MILP model for BESS revenue stacking.

This module defines an AbstractModel for a 1 MW battery participating in:
- Day-Ahead Market (DAM) arbitrage;
- Frequency Containment Reserve (FCR / primary reserve);
- automatic Frequency Restoration Reserve (aFRR / secondary reserve);
- manual Frequency Restoration Reserve (mFRR / tertiary reserve).

The model uses a 24-hour horizon with 15-minute resolution and six mFRR acceptance scenarios.
"""

from pyomo.core import *
import pyomo.environ as pyo

model=AbstractModel()

"""
=============================================================================================
                                            SETS
=============================================================================================
"""
#Time-index SETS
model.n_hours=Param(default=24)
model.n_quarter=Param(default=4)
model.n_minutes=Param(default=15)
model.n_seconds=Param(default=60)

model.h=RangeSet(model.n_hours) #da 1 a 24 (non si prende lo 0)
model.qrt=RangeSet(model.n_quarter)
model.min=RangeSet(model.n_minutes)
model.sec=RangeSet(model.n_seconds)

model.H=Set(initialize=model.h, ordered=True)
model.QRT=Set(initialize= model.qrt, ordered=True)
model.MIN=Set(initialize=model.min, ordered=True)
model.SEC=Set(initialize=model.sec, ordered=True)

#Scenarios SETS
model.n_scenarios= Param(default=6)
model.sc=RangeSet(model.n_scenarios)
model.SC=Set(initialize=model.sc,ordered=True)

"""
=============================================================================================
                                        PARAMETERS
=============================================================================================
"""

# Battery Parameters
model.EPR=Param(default=1)

model.BESS_Pmax=Param(default=1) #[MW] 
def E_BESS_definition(model):
    val= model.BESS_Pmax*model.EPR
    return val
model.BESS_capacity=Param(initialize=E_BESS_definition) #[MWh]

#BESS effinciency values in the BESS step model
model.eta_cha_a15=Param(default=0.972)
model.eta_cha_b15=Param(default=0.55)
model.eta_dis_a15=Param(default=0.868)
model.eta_dis_b15=Param(default=0.50)
model.delta_BESS=Param(default=0.15)

model.SOC_min=Param(default=0) 
model.SOC_max=Param(default=100) 
model.SOC_initial=Param(default=50) 

model.bigN=Param(default=100000000) #big Number used in the constraints

model.price_DAM = Param(model.H, within= Reals) #Hourly DAM clearing price
model.price_DAM_historical= Param(default=128) #Average DAM price in 2023

model.price_prim_UP= Param(model.H, within= Reals) #price for upward FCR activated energy [€/MWh]
model.price_prim_DW= Param(model.H, within= Reals) #price for downward FCR activated energy [€/MWh]

model.price_sec_UP= Param(model.H, within= Reals) #price for upward aFRR activated energy [€/MWh]
model.price_sec_DW= Param(model.H, within= Reals) #price for downward aFRR activated energy [€/MWh]

model.offer_ter_UP= Param(model.H, within= Reals) #price for upward mFRR/RR activated energy [€/MWh]
model.offer_ter_DW= Param(model.H, within= Reals) #price for downward mFRR/RR activated energy [€/MWh]

model.perc_band_prim_UP_second=Param(model.H,model.QRT,model.MIN,model.SEC, within=Reals) #Second-level activation of UP-FCR power band
model.perc_band_prim_UP= Param(model.H,model.QRT, within= Reals) #Mean activation of UP-FCR power band on the quarter-of-an-hour
model.perc_band_prim_DW_second=Param(model.H,model.QRT,model.MIN,model.SEC, within=Reals) #Second-level activation of DW-FCR power band
model.perc_band_prim_DW= Param(model.H,model.QRT, within= Reals) #Mean activation of DW-FCR power band on the quarter-of-an-hour

model.perc_band_sec_UP_minute=Param(model.H,model.QRT,model.MIN, within=Reals) #Minute-level activation of UP-aFRR power band
model.perc_band_sec_UP = Param(model.H,model.QRT, within= Reals) #Mean activation of UP-aFRR power band on the quarter-of-an-hour
model.perc_band_sec_DW_minute=Param(model.H,model.QRT,model.MIN, within=Reals) #Minute-level activation of DW-aFRR power band
model.perc_band_sec_DW = Param(model.H,model.QRT, within= Reals) #Mean activation of DW-aFRR power band on the quarter-of-an-hour

#Tertiary reserve "state"
model.y_ter_UP_par=Param(model.SC, model.H, within=Binary) 
model.y_ter_DW_par=Param(model.SC, model.H, within=Binary) 

model.p_sc=Param(model.SC, within=NonNegativeReals) 

"""
=============================================================================================
                                            VARIABLES
=============================================================================================
"""

#PHYSICAL POWER FLOWS

#BESS power flows
model.P_cha= Var(model.SC, model.H, model.QRT,  within=NonNegativeReals)
model.P_dis= Var(model.SC, model.H, model.QRT,  within=NonNegativeReals)
model.P_BESS_abs= Var(model.SC, model.H, model.QRT,  within=NonNegativeReals)

model.y_cha=Var(model.SC, model.H,model.QRT,within=Binary) 
model.y_dis=Var(model.SC, model.H,model.QRT,within=Binary) 
model.y_BESS=Var(model.SC, model.H,model.QRT,within=Binary) 

#BESS power flows depending on the SOC
model.P_dis_a15=Var(model.SC, model.H,model.QRT,within=NonNegativeReals) #Power discharge above 15[kW]
model.P_dis_b15=Var(model.SC, model.H,model.QRT,within=NonNegativeReals) #Power discharge below 15[kW]
model.P_cha_a15=Var(model.SC, model.H,model.QRT,within=NonNegativeReals) #Power charge above 15[kW]
model.P_cha_b15=Var(model.SC, model.H,model.QRT,within=NonNegativeReals) #Power charge below 15[kW]
model.y_dis_a15=Var(model.SC, model.H,model.QRT,within=Binary) #Binary discharge above 15
model.y_dis_b15=Var(model.SC, model.H,model.QRT,within=Binary) #Binary discharge below 15
model.y_cha_a15=Var(model.SC, model.H,model.QRT,within=Binary) #Binary charge above 15
model.y_cha_b15=Var(model.SC, model.H,model.QRT,within=Binary) #Binary charge below 15

model.SOC=Var(model.SC, model.H,model.QRT,within=NonNegativeReals) #State of Charge [within 0-100%]

#ECONOMIC FLOWS

#DAM program
model.P_purch=Var(model.H, within=NonNegativeReals)
model.P_sold=Var(model.H, within=NonNegativeReals)
model.y_purch=Var(model.H, within=Binary)
model.y_sold=Var(model.H, within=Binary)

#Primary reserve
model.P_band_prim=Var(model.H, within=NonNegativeReals) #symmetric service in ITA
model.P_prim_UP=Var(model.H, model.QRT,  within=NonNegativeReals)
model.P_prim_DW=Var(model.H, model.QRT,  within=NonNegativeReals)

#Secondary reserve
model.P_band_sec_UP=Var(model.H, within=NonNegativeReals) #asymmetric service in ITA
model.P_band_sec_DW=Var(model.H, within=NonNegativeReals)
model.P_sec_UP=Var(model.H, model.QRT, within=NonNegativeReals)
model.P_sec_DW=Var(model.H, model.QRT, within=NonNegativeReals)

#Tertiary reserve
model.P_ter_UP=Var(model.H, within=NonNegativeReals)
model.P_ter_DW=Var(model.H, within=NonNegativeReals)
model.y_ter_UP=Var(model.H, within=Binary) 
model.y_ter_DW=Var(model.H, within=Binary)

"""
=============================================================================================
                                    OBJECTIVE FUNCTION
=============================================================================================
"""

def objective_function(model):
    revenue = sum(model.P_sold[h]*model.price_DAM[h]- model.P_purch[h]*model.price_DAM[h] for h in model.H)+\
              sum(model.p_sc[sc]*(sum(model.P_ter_UP[h]*model.offer_ter_UP[h]*model.y_ter_UP_par[sc,h]-model.P_ter_DW[h]*model.offer_ter_DW[h]*model.y_ter_DW_par[sc,h] for h in model.H)) for sc in model.SC)+\
              sum(sum(model.P_sec_UP[h,q]/4*model.price_sec_UP[h]- model.P_sec_DW[h,q]/4*model.price_sec_DW[h] for q in model.QRT) for h in model.H)+\
              sum(sum(model.P_prim_UP[h,q]/4* model.price_prim_UP[h]-model.P_prim_DW[h,q]/4* model.price_prim_DW[h] for q in model.QRT) for h in model.H)+\
              sum(model.p_sc[sc]*((model.SOC[sc,24,4]+((model.P_cha_a15[sc,24,4]*model.eta_cha_a15 + model.P_cha_b15[sc,24,4]*model.eta_cha_b15 - model.P_dis_a15[sc,24,4]/model.eta_dis_a15 - model.P_dis_b15[sc,24,4]/model.eta_dis_b15)/4)/model.BESS_capacity*100-model.SOC_initial)/100*model.BESS_capacity)*model.price_DAM_historical for sc in model.SC)     
    return revenue
model.Objective_function = Objective(rule=objective_function, sense=maximize)

"""
=============================================================================================
                                    CONSTRAINTS
=============================================================================================

"""
#C0NSTRAINTS BESS 

#P_BESS_abs definition
def p_abs_def(model,sc,h,q):
    return model.P_BESS_abs[sc,h,q]==model.P_dis[sc,h,q]+model.P_cha[sc,h,q]
model.P_BESS_abs_def=Constraint(model.SC, model.H, model.QRT,  rule=p_abs_def)

# Constraint BESS power
def Battery_power_limit(model,sc,h,q):
    return model.P_BESS_abs[sc,h,q] <=model.BESS_Pmax 
model.BESS_power_limit = Constraint(model.SC, model.H, model.QRT,  rule=Battery_power_limit)

#computation SOC
#SOC[sc,h,q] represents the SOC at the beginning of the quarter of an hour represented by [h,q]
def soc_comp (model,sc,h,q):
    if h==1 and q==1:
        return model.SOC[sc,h,q] == model.SOC_initial
    elif q!=1:
        return model.SOC[sc,h,q] == model.SOC[sc,h,q-1]+ ((model.P_cha_a15[sc,h,q-1]*model.eta_cha_a15 + model.P_cha_b15[sc,h,q-1]*model.eta_cha_b15 - model.P_dis_a15[sc,h,q-1]/model.eta_dis_a15 - model.P_dis_b15[sc,h,q-1]/model.eta_dis_b15)/4)/model.BESS_capacity*100
    elif q==1 and h!=1:
        return model.SOC[sc,h,q] == model.SOC[sc,h-1,4]+ ((model.P_cha_a15[sc,h-1,4]*model.eta_cha_a15 + model.P_cha_b15[sc,h-1,4]*model.eta_cha_b15 - model.P_dis_a15[sc,h-1,4]/model.eta_dis_a15 - model.P_dis_b15[sc,h-1,4]/model.eta_dis_b15)/4)/model.BESS_capacity*100
model.SOC_Computation=Constraint(model.SC, model.H, model.QRT,  rule=soc_comp) 

#SOC min
def soc_min(model,sc,h,q):
    return model.SOC[sc,h,q]>=model.SOC_min
model.SOC_min_constraint= Constraint(model.SC, model.H, model.QRT,  rule=soc_min)

#SOC max
def soc_max(model,sc,h,q):
    return model.SOC[sc,h,q]<=model.SOC_max
model.SOC_max_constraint= Constraint(model.SC, model.H, model.QRT,  rule=soc_max)

#Pcharge battery
def pch (model,sc,h,q):
    return model.P_cha[sc,h,q] == model.P_cha_a15[sc,h,q]+model.P_cha_b15[sc,h,q]
model.P_cha_constraint=Constraint(model.SC, model.H, model.QRT, rule=pch)

#Pdischarge battery
def pdisch (model,sc,h,q):
    return model.P_dis[sc,h,q] == model.P_dis_a15[sc,h,q]+model.P_dis_b15[sc,h,q]
model.P_dis_constraint=Constraint(model.SC, model.H, model.QRT, rule=pdisch)

#State Pcharge above 15%
def pcha_a15_state (model,sc,h,q):
    return model.P_cha_a15[sc,h,q] <= model.y_cha_a15[sc,h,q]*model.bigN
model.Pcha_a15_state_constraint=Constraint(model.SC, model.H,model.QRT,rule=pcha_a15_state)

#State Pcharge below 15%
def pcha_b15_state (model,sc,h,q):
    return model.P_cha_b15[sc,h,q] <= model.y_cha_b15[sc,h,q]*model.bigN
model.Pcha_b15_state_constraint=Constraint(model.SC, model.H,model.QRT,rule=pcha_b15_state)

#Sate Pdischarge above 15%
def pdis_a15_state (model,sc,h,q):
    return model.P_dis_a15[sc,h,q] <= model.y_dis_a15[sc,h,q]*model.bigN
model.Pdis_a15_state_constraint=Constraint(model.SC, model.H,model.QRT,rule=pdis_a15_state)

#State Pdischarge below 15%
def pdis_b15_state (model,sc,h,q):
    return model.P_dis_b15[sc,h,q] <= model.y_dis_b15[sc,h,q]*model.bigN
model.Pdis_b15_state_constraint=Constraint(model.SC, model.H,model.QRT,rule=pdis_b15_state)

#Charge above or below 15%
def pcha_state (model,sc,h,q):
    return model.y_cha_a15[sc,h,q]+model.y_cha_b15[sc,h,q] == model.y_cha[sc,h,q]
model.Pcha_state_constraint=Constraint(model.SC, model.H,model.QRT,rule=pcha_state)

#Discharge above or below 15%
def pdis_state (model,sc,h,q):
    return model.y_dis_a15[sc,h,q]+model.y_dis_b15[sc,h,q] == model.y_dis[sc,h,q]
model.Pdis_state_constraint=Constraint(model.SC, model.H,model.QRT,rule=pdis_state)

#Charge or discharge
def p_bess_state (model,sc,h,q):
    return model.y_cha[sc,h,q]+model.y_dis[sc,h,q] == model.y_BESS[sc,h,q]
model.P_BESS_state=Constraint(model.SC, model.H, model.QRT, rule=p_bess_state)

#Pcharge below 15 "definition"
def pcha_b15 (model,sc,h,q):
    return model.P_cha_b15[sc,h,q] <= model.BESS_Pmax*model.delta_BESS 
model.Pcha_b15_constraint=Constraint(model.SC, model.H,model.QRT,rule=pcha_b15) 

#Pdischarge below 15 "definition"
def pdis_b15 (model,sc,h,q):
    return model.P_dis_b15[sc,h,q] <= model.BESS_Pmax*model.delta_BESS 
model.Pdis_b15_constraint=Constraint(model.SC, model.H,model.QRT,rule=pdis_b15) 

#Pcharge above 15 "definition"
def pcha_a15 (model,sc,h,q):
    return model.P_cha_a15[sc,h,q] >= model.BESS_Pmax*model.delta_BESS-model.bigN*(1-model.y_cha_a15[sc,h,q])  #il secondo termine permette a P_cha_a15 di essere zero quando non sto caricando con potenza>15%Pmax
model.Pcha_a15_constraint=Constraint(model.SC, model.H,model.QRT,rule=pcha_a15) 

#Pdischarge above 15 "definition"
def pdis_a15 (model,sc,h,q):
    return model.P_dis_a15[sc,h,q] >= model.BESS_Pmax*model.delta_BESS-model.bigN*(1-model.y_dis_a15[sc,h,q]) 
model.Pdis_a15_constraint=Constraint(model.SC, model.H,model.QRT,rule=pdis_a15) 

#BESS Operation
def bess_op (model,sc,h,q):
    return  model.y_BESS[sc,h,q] <=  model.P_BESS_abs[sc,h,q]*model.bigN
model.BESS_op_constraint=Constraint(model.SC, model.H,model.QRT,rule=bess_op) 


#=============================================================================================
#PRIMARY RESERVE CONSTRAINTS

def primary_band_constant (model,h):
    if h==1:
        return Constraint.Skip
    else:
        return model.P_band_prim[h]==model.P_band_prim[h-1]
model.P_band_prim_constant_constraint=Constraint(model.H, rule=primary_band_constant)

#Primary reserve power flow based on frequency+droop curve
def P_pr_up_def (model,h,q):
    return model.P_prim_UP[h,q]== model.perc_band_prim_UP[h,q]/100*model.P_band_prim[h]
model.Primary_reserve_UP_flow=Constraint(model.H,model.QRT,rule=P_pr_up_def)

def P_pr_dw_def (model,h,q):
    return model.P_prim_DW[h,q]== model.perc_band_prim_DW[h,q]/100*model.P_band_prim[h]
model.Primary_reserve_DW_flow=Constraint(model.H,model.QRT,rule=P_pr_dw_def)

#=============================================================================================
#SECONDARY RESERVE CONSTRAINTS

def secondary_UP_band_constant (model,h):
    if h==1:
        return Constraint.Skip
    else:
        return model.P_band_sec_UP[h]==model.P_band_sec_UP[h-1]
model.P_band_sec_UP_constant_constraint=Constraint(model.H, rule=secondary_UP_band_constant)

def secondary_DW_band_constant (model,h):
    if h==1:
        return Constraint.Skip
    else:
        return model.P_band_sec_DW[h]==model.P_band_sec_DW[h-1]
model.P_band_sec_DW_constant_constraint=Constraint(model.H, rule=secondary_DW_band_constant)

#Secondary reserve power flow based on signal level
def P_sr_up_def (model,h,q):
    return model.P_sec_UP[h,q]== model.perc_band_sec_UP[h,q]/100*model.P_band_sec_UP[h]
model.Secondary_reserve_UP_flow=Constraint(model.H,model.QRT,rule=P_sr_up_def)

def P_sr_dw_def (model,h,q):
    return model.P_sec_DW[h,q]== model.perc_band_sec_DW[h,q]/100*model.P_band_sec_DW[h]
model.Secondary_reserve_DW_flow=Constraint(model.H,model.QRT,rule=P_sr_dw_def)

#=============================================================================================

#TERTIARY RESERVE CONSTRAINTS
def P_ter_up_h_cons (model,h):
    return model.P_ter_UP[h]<= model.y_ter_UP[h]*model.bigN
model.Tertiary_reserve_UP_h_cons=Constraint(model.H,rule=P_ter_up_h_cons)

def P_ter_dw_h_cons (model,h):
    return model.P_ter_DW[h]<= model.y_ter_DW[h]*model.bigN
model.Tertiary_reserve_DW_h_cons=Constraint(model.H,rule=P_ter_dw_h_cons)

def P_ter_state (model,h):
    return model.y_ter_UP[h]+model.y_ter_DW[h]<=1
model.Tertiary_reserve_state=Constraint(model.H, rule=P_ter_state)

#=============================================================================================
#DAM CONSTRAINTS

def P_sold_cons (model,h):
    return model.P_sold[h]<= model.y_sold[h]*model.bigN
model.DAM_sold_cons=Constraint(model.H,rule=P_sold_cons)

def P_purch_cons (model,h):
    return model.P_purch[h]<= model.y_purch[h]*model.bigN
model.DAM_purch_cons=Constraint(model.H,rule=P_purch_cons)

def P_dam_state (model,h):
    return model.y_sold[h]+model.y_purch[h]<=1
model.DAM_state=Constraint(model.H,rule=P_dam_state)

#=============================================================================================
#MARKET CONSTRAINTS

def max_up_offer(model,h):
    return model.P_band_prim[h]+model.P_band_sec_UP[h]+model.P_ter_UP[h]+ model.P_sold[h]<= model.BESS_Pmax
model.max_UP_offer_constr=Constraint(model.H,rule=max_up_offer)

def max_dw_offer(model,h):
    return model.P_band_prim[h]+model.P_band_sec_DW[h]+model.P_ter_DW[h]+ model.P_purch[h]<= model.BESS_Pmax
model.max_DW_offer_constr=Constraint(model.H,rule=max_dw_offer)


#===================================================================================================
#ELECTRICAL BALANCE CONSTRAINT

def external_eb (model,sc,h,q):
    phy_exc=model.P_dis[sc,h,q]-model.P_cha[sc,h,q] 
    dam_exc=model.P_sold[h]-model.P_purch[h]
    PR_exc=model.P_prim_UP[h,q]-model.P_prim_DW[h,q]
    SR_exc=model.P_sec_UP[h,q]-model.P_sec_DW[h,q]
    TR_exc=model.P_ter_UP[h]*model.y_ter_UP_par[sc,h]-model.P_ter_DW[h]*model.y_ter_DW_par[sc,h]
    return phy_exc == dam_exc+PR_exc+SR_exc+TR_exc
model.external_energy_balance=Constraint(model.SC,model.H,model.QRT, rule=external_eb)
