"""Commissioned synthetic prototype. No hidden profile values are accepted."""
import numpy as np
import pandas as pd
from scipy.signal import lfilter
from scipy.optimize import least_squares
from .base_features import features as base_features, RAW, IRATED


def expected_oil(basic, rise=32., tau=150., bias=0., loss_ratio=200/1250):
    drivers=basic[RAW[3:7]].astype(float).replace([np.inf,-np.inf],np.nan)
    for name in RAW[3:6]:
        drivers.loc[drivers[name]<0,name]=np.nan
    if 'communication_available' in basic:
        drivers.loc[basic.communication_available.ne(1),:]=np.nan
    drivers=drivers.ffill()
    load2=((drivers[RAW[3:6]]/IRATED)**2).mean(axis=1,skipna=False).to_numpy()
    equilibrium=drivers.ambient_temp_C.to_numpy()+rise*(loss_ratio+(1-loss_ratio)*load2)**.8+bias
    initial=float(basic.top_oil_temp_C.iloc[0])
    if not np.isfinite(initial) or not np.isfinite(equilibrium).all():
        raise ValueError('First ambient/current/oil readings must be complete')
    a=np.exp(-5/tau)
    # Filtering previous equilibrium implements the causal pre-interval convention.
    filtered,_=lfilter([1-a],[1,-a],equilibrium[:-1],zi=[a*initial])
    return np.r_[initial,filtered]


def commission(basic, mode, *, verified_healthy=False):
    if not verified_healthy:
        raise ValueError('Independently verified healthy commissioning is required; never assume the first day is healthy')
    if len(basic)<7*288 or basic[RAW].isna().any().any():
        raise ValueError('At least seven complete days of healthy commissioning required')
    if not pd.to_datetime(basic.timestamp_IST,utc=True).diff().iloc[1:].eq(pd.Timedelta(minutes=5)).all():
        raise ValueError('Commissioning must be a regular five-minute series')
    oil=basic.top_oil_temp_C.to_numpy(float)
    if mode=='offset':
        offset=float(np.median((oil-expected_oil(basic))[288:]))
        params=dict(rise=32.,tau=150.,bias=offset,loss_ratio=200/1250)
    elif mode=='thermal_fit':
        # Fit only visible measurements; robust residual loss handles quantization.
        def residual(theta):
            return (expected_oil(basic,*theta)-oil)[288:]
        result=least_squares(residual,[32.,150.,0.,.16],bounds=([20.,75.,-4.,.08],[35.,520.,4.,.25]),
                             loss='soft_l1',f_scale=.5,max_nfev=150)
        params=dict(zip(['rise','tau','bias','loss_ratio'],map(float,result.x)))
        if not result.success:
            raise ValueError('Thermal calibration did not converge')
    else:
        raise ValueError(mode)
    err=(expected_oil(basic,**params)-oil)[288:]
    params['commission_rmse_C']=float(np.sqrt(np.mean(err**2)))
    params['commission_samples']=len(basic)
    params['mode']=mode
    params['verified_healthy_required']=True
    return params


def features(basic, calibration, representation='residual'):
    _,ctx=base_features(basic)
    params={key:calibration[key] for key in ['rise','tau','bias','loss_ratio']}
    exp=expected_oil(basic,**params)
    oil=basic.top_oil_temp_C.reset_index(drop=True)
    res=oil-pd.Series(exp)
    f=pd.DataFrame({'residual_C':res,'residual_mean_30min_C':res.rolling(6,min_periods=3).mean(),
        'residual_mean_60min_C':res.rolling(12,min_periods=6).mean(),
        'residual_change_30min_C':res.diff(6)})
    if representation=='original':
        f,_=base_features(basic)
        # Replace the nominal residual alone: smallest change first.
        f['nominal_oil_residual_C']=res
    ctx['calibrated_expected_oil_C']=exp
    ctx['calibrated_residual_C']=res
    return f,ctx
