from pathlib import Path
import json,math
ROOT=Path(__file__).resolve().parents[1]

def reference():return json.loads((ROOT/'calibration/reference_calibration.json').read_text())

def resolve(calibration=None):
 if calibration is None:return reference(),[]
 try:
  data=json.loads(Path(calibration).read_text()) if isinstance(calibration,(str,Path)) else dict(calibration)
  for name,(lo,hi) in {'rating_kva':(250,250),'rise_K':(20,45),'tau_min':(80,600),'bias_C':(-5,5),'p0_W':(100,1000),'pload_W':(500,5000),'exponent':(.5,1.2)}.items():
   v=float(data[name])
   if not math.isfinite(v) or not lo<=v<=hi:raise ValueError('CALIBRATION_BOUND:'+name)
   data[name]=v
  status=data.get('status')
  if status not in ['ASSET_SPECIFIC','VERIFIED_COMMISSIONED','REFERENCE_CALIBRATION']:raise ValueError('CALIBRATION_STATUS_INVALID')
  if status=='VERIFIED_COMMISSIONED' and (not data.get('verified_healthy') or not data.get('valid')):raise ValueError('HEALTHY_ATTESTATION_OR_VALIDITY_MISSING')
  if not data.get('provenance'):raise ValueError('CALIBRATION_PROVENANCE_REQUIRED')
  return data,([] if status=='REFERENCE_CALIBRATION' else ['ML_USES_FROZEN_REFERENCE_FEATURES'])
 except (ValueError,KeyError,TypeError,OSError) as exc:
  return reference(),['INVALID_CALIBRATION_FALLBACK:'+str(exc)]
