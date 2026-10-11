"""Frozen v3 decision only. No training or evaluation dependencies."""
import numpy as np
from threadpoolctl import threadpool_limits

def decision_margin(artifact,frame):
    with threadpool_limits(limits=4):
        return np.round(artifact['model'].decision_function(frame[artifact['features']]),12)
