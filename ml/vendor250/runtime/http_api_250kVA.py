"""Local REST sidecar: Spring Boot forwards JSON; React receives frontend payloads."""
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from threading import Lock
import argparse,json
from pathlib import Path
from .streaming_runtime_250kVA import DigitalTwinMLRuntime250kVA
from .frontend_adapter_250kVA import to_frontend_payload,validate_frontend_payload
from .input_adapter_250kVA import CompatibilityError

def make_server(host='127.0.0.1',port=8765,runtime=None,allowed_origin=None):
 engine=runtime or DigitalTwinMLRuntime250kVA();lock=Lock()
 class Handler(BaseHTTPRequestHandler):
  def log_message(self,*args):pass
  def send(self,status,payload):
   body=json.dumps(payload,allow_nan=False).encode();self.send_response(status);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(body)))
   if allowed_origin and self.headers.get('Origin')==allowed_origin:self.send_header('Access-Control-Allow-Origin',allowed_origin)
   self.end_headers();self.wfile.write(body)
  def do_GET(self):
   self.send(200,{'status':'READY','modelVersion':engine.config['modelVersion'],'modelStatus':engine.config['modelStatus']}) if self.path=='/health' else self.send(404,{'error':'UNKNOWN_ROUTE'})
  def do_OPTIONS(self):
   self.send_response(204)
   if allowed_origin and self.headers.get('Origin')==allowed_origin:
    self.send_header('Access-Control-Allow-Origin',allowed_origin);self.send_header('Access-Control-Allow-Headers','Content-Type');self.send_header('Access-Control-Allow-Methods','POST, GET, OPTIONS')
   self.end_headers()
  def do_POST(self):
   if self.path!='/v1/250kva/infer':self.send(404,{'error':'UNKNOWN_ROUTE'});return
   try:
    length=int(self.headers.get('Content-Length','0'))
    if not 0<length<=131072:self.send(413,{'error':'BODY_SIZE_INVALID'});return
    row=json.loads(self.rfile.read(length))
    if not isinstance(row,dict):raise ValueError('SCADA_ROW_OBJECT_REQUIRED')
    with lock:result=engine.update(row)
    payload=to_frontend_payload(result);validate_frontend_payload(payload);self.send(200,payload)
   except (ValueError,CompatibilityError,KeyError) as exc:self.send(400,{'error':str(exc)})
 return ThreadingHTTPServer((host,port),Handler)

def main():
 p=argparse.ArgumentParser(description='VoltMind 250-kVA REST sidecar');p.add_argument('--host',default='127.0.0.1');p.add_argument('--port',type=int,default=8765);p.add_argument('--allowed-origin');p.add_argument('--calibration');p.add_argument('--schema');p.add_argument('--units');p.add_argument('--state-in');p.add_argument('--state-out');a=p.parse_args()
 runtime=DigitalTwinMLRuntime250kVA(calibration=a.calibration,schema=json.loads(Path(a.schema).read_text()) if a.schema else None,units=json.loads(Path(a.units).read_text()) if a.units else None)
 server=make_server(a.host,a.port,runtime,a.allowed_origin)
 if a.state_in:runtime.load_state(a.state_in)
 print('VoltMind 250-kVA API listening on '+a.host+':'+str(a.port),flush=True)
 try:server.serve_forever()
 except KeyboardInterrupt:pass
 finally:
  if a.state_out:runtime.save_state(a.state_out)
  server.server_close()
if __name__=='__main__':main()
