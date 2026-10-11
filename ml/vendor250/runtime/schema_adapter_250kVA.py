from .input_adapter_250kVA import InputAdapter250kVA,CompatibilityError,CANONICAL,ALIASES

def normalize_scada_row(row,**options):return InputAdapter250kVA(**options).normalize(row)
