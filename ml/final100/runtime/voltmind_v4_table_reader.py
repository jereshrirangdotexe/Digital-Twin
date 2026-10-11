from pathlib import Path
import csv, io, json, zipfile
import pandas as pd
MAX_ROWS=300000
MAX_BYTES=100*1024*1024
class CompatibilityError(ValueError):pass

def read_table(source,filename=None,*,sheet=None,delimiter=None,decimal='.',encoding='utf-8-sig'):
    raw=source if isinstance(source,bytes) else Path(source).read_bytes()
    if len(raw)>MAX_BYTES:raise CompatibilityError('File exceeds 100 MB input limit')
    suffix=Path(filename or str(source)).suffix.lower() if not isinstance(source,bytes) or filename else '.csv'
    if suffix=='.xlsx':
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            if sum(x.file_size for x in z.infolist())>300*1024*1024:raise CompatibilityError('Workbook expands beyond the supported size limit')
        try:
            book=pd.ExcelFile(io.BytesIO(raw),engine='openpyxl')
            if sheet is None and len(book.sheet_names)!=1:raise CompatibilityError('Workbook has multiple sheets; choose datasetInput.sheet explicitly')
            chosen=sheet if sheet is not None else book.sheet_names[0]
            table=pd.read_excel(book,sheet_name=chosen,header=None,nrows=MAX_ROWS+2)
        except ImportError as e:raise CompatibilityError('Excel input requires openpyxl; install project requirements') from e
        if table.empty:raise CompatibilityError('EMPTY_INPUT: workbook has no readings')
        header=table.iloc[0].tolist();frame=table.iloc[1:].copy();frame.columns=header;frame=frame.reset_index(drop=True)
    elif suffix in ['.json','.jsonl','.ndjson']:
        text=raw.decode(encoding)
        if suffix=='.json':
            value=json.loads(text)
            if isinstance(value,dict) and set(value)=={'records'}:value=value['records']
        else:value=[json.loads(line) for line in text.splitlines() if line.strip()]
        if not isinstance(value,list) or not all(isinstance(x,dict) for x in value):raise CompatibilityError('JSON must contain an array of row objects, a records array, or JSON Lines')
        frame=pd.DataFrame(value);header=frame.columns.tolist()
    elif suffix in ['.csv','.tsv','.txt']:
        text=raw.decode(encoding)
        if delimiter is None:
            try:delimiter=csv.Sniffer().sniff(text[:65536],delimiters=',;\t|').delimiter
            except csv.Error:delimiter='\t' if suffix=='.tsv' else ','
        if delimiter not in [',',';','\t','|']:raise CompatibilityError('Delimiter must be comma, semicolon, tab or pipe')
        header=next(csv.reader(io.StringIO(text),delimiter=delimiter),[])
        frame=pd.read_csv(io.StringIO(text),sep=delimiter,decimal=decimal,nrows=MAX_ROWS+1)
    else:raise CompatibilityError('Supported files: CSV, TSV, TXT, XLSX, JSON, JSONL, NDJSON')
    if any(pd.isna(x) or not str(x).strip() for x in header):raise CompatibilityError('Header contains empty names; use a single table with measured signal names in the first row')
    if len(set(map(str,header)))!=len(header):raise CompatibilityError('Duplicate column names; select distinct measured signals before importing')
    if frame.empty:raise CompatibilityError('EMPTY_INPUT: no reading rows')
    if len(frame)>MAX_ROWS or len(frame.columns)>1000:raise CompatibilityError('Input exceeds 300,000 rows or 1,000 columns')
    frame.columns=[str(x) for x in frame.columns]
    return frame
