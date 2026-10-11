"""Causal, BASIC-only features for the 100 kVA synthetic experiment.

Keys route independent histories; they never enter an estimator. The nominal
oil calculation is an assumption, not a fitted target-transformer calibration.
"""
import numpy as np
import pandas as pd

RAW = ['VR_V', 'VY_V', 'VB_V', 'IR_A', 'IY_A', 'IB_A',
       'ambient_temp_C', 'top_oil_temp_C']
KEYS = ['replay_id', 'timestamp_IST']
IRATED = 100000 / (np.sqrt(3) * 433)
VNOM = 433 / np.sqrt(3)
STATIC = ['mean_phase_voltage_V', 'voltage_imbalance_pct', 'loading_pct',
          'max_phase_loading_pct', 'current_imbalance_pct', 'ambient_temp_C',
          'top_oil_temp_C', 'oil_rise_K']


def persistent_nullable(values, periods):
    """True only for a complete run; incomplete history remains unknown."""
    v = values.astype('Float64')
    count = v.rolling(periods, min_periods=1).count()
    sums = v.rolling(periods, min_periods=periods).sum()
    result = sums.eq(periods).astype('boolean')
    result[count < periods] = pd.NA
    return result


def features(basic, tau_min=150.0):
    missing = set(KEYS + RAW) - set(basic)
    if missing:
        raise ValueError('Missing required columns: ' + ', '.join(sorted(missing)))
    if basic.empty or basic[KEYS].isna().any().any() or basic.duplicated(KEYS).any():
        raise ValueError('Nonempty input with unique, nonmissing replay/timestamp keys required')
    if not np.isfinite(tau_min) or tau_min <= 0:
        raise ValueError('tau_min must be positive and finite')
    # Explicit whitelist makes every optional, derived, and oracle column inert.
    b = basic[KEYS + RAW].copy().reset_index(drop=True)
    for name in RAW:
        b[name] = pd.to_numeric(b[name], errors='raise').replace([np.inf, -np.inf], np.nan)
    for name in RAW[:6]:
        b.loc[b[name] < 0, name] = np.nan
    available = (pd.to_numeric(basic['communication_available'].reset_index(drop=True), errors='raise').eq(1)
                 if 'communication_available' in basic else pd.Series(True, index=b.index))
    b.loc[~available, RAW] = np.nan
    feature_parts, contexts = [], []
    for rid, g in b.groupby('replay_id', sort=False):
        ix = g.index
        t = pd.to_datetime(g.timestamp_IST, utc=True)
        if len(g) > 1 and not t.diff().iloc[1:].eq(pd.Timedelta(minutes=5)).all():
            raise ValueError('Each replay must be ordered on a regular five-minute grid; represent gaps as missing rows')
        v, i = g[RAW[:3]], g[RAW[3:6]]
        vm, im = v.mean(axis=1, skipna=False), i.mean(axis=1, skipna=False)
        vi = v.sub(vm, axis=0).abs().max(axis=1, skipna=False).div(vm.replace(0, np.nan))*100
        ii = i.sub(im, axis=0).abs().max(axis=1, skipna=False).div(im.replace(0, np.nan))*100
        ii.loc[im.eq(0)] = 0
        load = pd.Series((v.to_numpy()*i.to_numpy()).sum(axis=1)/1000, index=ix)
        f = pd.DataFrame({'mean_phase_voltage_V': vm, 'voltage_imbalance_pct': vi,
             'loading_pct': load, 'max_phase_loading_pct': i.max(axis=1, skipna=False)/IRATED*100,
             'current_imbalance_pct': ii, 'ambient_temp_C': g.ambient_temp_C,
             'top_oil_temp_C': g.top_oil_temp_C, 'oil_rise_K': g.top_oil_temp_C-g.ambient_temp_C})
        for minutes in [30, 60]:
            f[f'oil_change_{minutes}min_C'] = g.top_oil_temp_C.diff(minutes//5)
        for minutes in [180, 360]:
            n = minutes//5
            f[f'past_loading_mean_{minutes}min_pct'] = load.shift(1).rolling(n, min_periods=n//2).mean()
            f[f'past_ambient_mean_{minutes}min_C'] = g.ambient_temp_C.shift(1).rolling(n, min_periods=n//2).mean()
        # Drivers are held through short gaps. No future interpolation or profile truth.
        drivers = g[RAW[3:7]].ffill()
        loss = 200 + 1050 * ((drivers[RAW[3:6]]/IRATED)**2).mean(axis=1, skipna=False)
        equilibrium = drivers.ambient_temp_C + 32*(loss/1250)**0.8
        oil = g.top_oil_temp_C.to_numpy()
        expected = np.full(len(g), np.nan)
        for j in range(len(g)):
            if j and np.isfinite(expected[j-1]) and np.isfinite(equilibrium.iloc[j-1]):
                expected[j] = equilibrium.iloc[j-1] + (expected[j-1]-equilibrium.iloc[j-1])*np.exp(-5/tau_min)
            elif np.isfinite(oil[j]) and np.isfinite(equilibrium.iloc[j]):
                expected[j] = oil[j]
        f['nominal_oil_residual_C'] = oil-expected
        valid = g[RAW].notna().all(axis=1) & available.loc[ix]
        # Coarse 1 C readings naturally form plateaus: only flag a 3 h plateau
        # when the nominal model would have moved by more than 3 C.
        plateau = g.top_oil_temp_C.rolling(36).max().eq(g.top_oil_temp_C.rolling(36).min())
        exp = pd.Series(expected, index=ix)
        oil_suspect = g.top_oil_temp_C.diff().abs().gt(4) | (plateau & (exp.rolling(36).max()-exp.rolling(36).min()).gt(3))
        recent_good = (valid & ~oil_suspect).rolling(12, min_periods=12).sum().eq(12)
        initialized = pd.Series(np.cumsum(np.isfinite(expected)) > 288, index=ix)
        assessable = valid & ~oil_suspect & recent_good & initialized
        confidence = pd.Series('NO_ISSUE_DETECTED', index=ix)
        confidence.loc[oil_suspect] = 'REDUCED'
        confidence.loc[~valid] = 'INCOMPLETE_INPUTS'
        confidence.loc[~available.loc[ix]] = 'UNAVAILABLE'
        phase_flags = pd.DataFrame(index=ix)
        for name in RAW[3:6]:
            x = g[name].gt(1.1*IRATED).astype('boolean').mask(g[name].isna())
            phase_flags[name] = persistent_nullable(x, 3)
        phase = phase_flags.any(axis=1).astype('boolean')
        phase.loc[phase_flags.isna().any(axis=1) & ~phase] = pd.NA
        uv = v.lt(.9*VNOM).any(axis=1).astype('boolean')
        uv.loc[v.isna().any(axis=1) & ~uv] = pd.NA
        imbalance = persistent_nullable(ii.gt(40).astype('boolean').mask(ii.isna()), 3)
        residual_screen = persistent_nullable(f.nominal_oil_residual_C.gt(2).astype('boolean').mask(~valid), 6)
        c = pd.DataFrame({'thermal_assessable': assessable, 'data_confidence': confidence,
             'nominal_oil_C': exp, 'phase_loading_screen': phase, 'undervoltage_screen': uv,
             'imbalance_screen': imbalance,
             'engineering_thermal_screen': residual_screen.mask(~assessable)}, index=ix)
        feature_parts.append(f)
        contexts.append(c)
    return pd.concat(feature_parts).sort_index(), pd.concat(contexts).sort_index()


def scores(model, frame, columns):
    from threadpoolctl import threadpool_limits
    estimator = model.steps[-1][1]
    old_jobs = getattr(estimator, 'n_jobs', None)
    if hasattr(estimator, 'n_jobs'):
        estimator.n_jobs = 1
    try:
        with threadpool_limits(limits=4):
            return np.round(model.predict_proba(frame[columns])[:, 1], 12)
    finally:
        if hasattr(estimator, 'n_jobs'):
            estimator.n_jobs = old_jobs
