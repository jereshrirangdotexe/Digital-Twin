import json
def serialize(result):return json.dumps(result,allow_nan=False,separators=(',',':'))
