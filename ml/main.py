"""The one authoritative ML entry point: CLI inference or persistent service."""
from pathlib import Path
import sys,argparse

# Original deployment imports are preserved verbatim, including their package names.
ML_ROOT=Path(__file__).resolve().parent
if str(ML_ROOT) not in sys.path: sys.path.insert(0,str(ML_ROOT))
from runtime.streaming_runtime_100kVA import DigitalTwinMLRuntime100kVA
from runtime.run_voltmind_100kVA import predict_batch
from runtime.frontend_adapter_100kVA import to_frontend_payload

def main():
    if '--serve' in sys.argv:
        parser=argparse.ArgumentParser(description='Persistent VoltMind 100/250/630-kVA worker')
        parser.add_argument('--serve',action='store_true');parser.add_argument('--port',type=int,default=8765)
        parser.add_argument('--instance-id',default='manual');parser.add_argument('--data',type=Path)
        parser.add_argument('--state-dir',type=Path)
        args=parser.parse_args()
        from service import serve
        serve(args.port,args.instance_id,args.data,args.state_dir)
    else:
        from integration100 import cli
        cli()

if __name__=='__main__': main()
