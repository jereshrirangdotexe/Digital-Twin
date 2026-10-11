from .streaming_runtime_250kVA import DigitalTwinMLRuntime250kVA

class DigitalTwinAdapter250kVA:
 def __init__(self,**options):self.runtime=DigitalTwinMLRuntime250kVA(**options)
 def update(self,row):return self.runtime.update(row)
 def process(self,rows):return self.runtime.predict_batch(rows)

def to_digital_twin_result(result):
 return dict(result,digitalTwin={'healthIndex':None,'healthBand':None,'riskScore':None,'riskLevel':None,'agingState':None,'maintenancePriority':None,'maintenanceRecommendation':None,'explanation':None})
