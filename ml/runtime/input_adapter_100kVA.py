"""CSV/row ingress without truth, events, profiles or filename-derived features."""
import csv
import pandas as pd
from .schema_adapter_100kVA import SchemaAdapter100kVA, CompatibilityError

def read_csv(path):
    with open(path,encoding='utf-8-sig',newline='') as f:
        header=next(csv.reader(f),None)
    if not header:
        raise CompatibilityError('EMPTY_INPUT: CSV has no header')
    if len(header)!=len(set(header)):
        raise CompatibilityError('Duplicate CSV column names require explicit source cleanup')
    frame=pd.read_csv(path)
    if frame.empty:
        raise CompatibilityError('EMPTY_INPUT: CSV contains no rows')
    return frame

def normalize_frame(frame,**options):
    adapter=SchemaAdapter100kVA(**options)
    if frame.empty: raise CompatibilityError('EMPTY_INPUT: no rows')
    return pd.DataFrame([adapter.normalize(row) for row in frame.to_dict('records')])
