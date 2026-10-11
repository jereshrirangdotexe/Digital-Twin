import argparse,csv,json
from pathlib import Path
from streaming_runtime import DigitalTwinMLRuntime630kVA
from frontend_adapter import serialize
def main():
    p=argparse.ArgumentParser();p.add_argument('--input');p.add_argument('--output');p.add_argument('--schema');p.add_argument('--units');p.add_argument('--timezone');p.add_argument('--calibration',default='reference');p.add_argument('--asset-id',default='EXTERNAL-630');p.add_argument('--config');p.add_argument('--serve',action='store_true');p.add_argument('--port',type=int,default=8766);p.add_argument('--commissioning',action='store_true');p.add_argument('--verified-healthy',action='store_true')
    a=p.parse_args()
    if a.serve:
        from service import serve
        serve(a.port);return
    if not a.input or not a.output:p.error('--input and --output are required for batch mode')
    if a.commissioning:
        from commissioning import commission
        commission(a.input,a.output,a.asset_id,a.verified_healthy,a.timezone);return
    read=lambda f:json.loads(Path(f).read_text(encoding='utf-8')) if f else None
    runtime=DigitalTwinMLRuntime630kVA(calibration=a.calibration,schema=read(a.schema),units=read(a.units),tz=a.timezone,asset_id=a.asset_id,config_path=a.config)
    with open(a.input,encoding='utf-8-sig',newline='') as f,open(a.output,'w',encoding='utf-8',newline='') as o:
        writer=None
        for row in csv.DictReader(f):
            r=runtime.update(row,dict(mode='BATCH',filename=Path(a.input).name,replayId=row.get('replay_id')))
            if a.output.endswith('.jsonl'):o.write(serialize(r)+'\n')
            else:
                flat={'timestamp':r['timestamp'],'asset_id':r['asset']['id'],**r['ml']}
                for k,v in list(flat.items()):
                    if isinstance(v,list):flat[k]=json.dumps(v)
                if writer is None:writer=csv.DictWriter(o,fieldnames=list(flat));writer.writeheader()
                writer.writerow(flat)
if __name__=='__main__':main()
