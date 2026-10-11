"""Reduced first-order top-oil model. Provisional parameters, no hotspot inference."""
import math
def rated_current(config): return config['rating_kva']*1000/(math.sqrt(3)*config['secondary_line_V'])
def equilibrium(ambient,load,config):
    r=config['load_loss_W_at_75C']/config['no_load_loss_W']
    return ambient+config['nominal_top_oil_rise_K']*((1+r*load*load)/(1+r))**config['oil_exponent']
def step(temp,ambient,load,minutes,config):
    target=equilibrium(ambient,load,config)
    tau=config['tau_heat_min'] if target>=temp else config['tau_cool_min']
    return target+(temp-target)*math.exp(-minutes/tau)
