"""Stable plain-dictionary API for upstream Digital Twin signals."""
import copy

def to_digital_twin_result(result):
    out=copy.deepcopy(result)
    out.pop('_features',None)
    # Higher-level health/risk/RUL are deliberately left for the consuming twin.
    return out
