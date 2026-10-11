"""Owns only processes launched for this extracted package; no global services."""
from pathlib import Path
import argparse,ctypes,json,os,re,shutil,socket,subprocess,sys,time,urllib.request,uuid,webbrowser
ROOT=Path(__file__).resolve().parents[1]
STATE=ROOT/'.state';MANIFEST=STATE/'processes.json'
URL='http://127.0.0.1:5173'

def creation(pid):
    if os.name!='nt': return None
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.OpenProcess.restype=ctypes.c_void_p
    handle=kernel.OpenProcess(0x1000,False,pid)
    if not handle:return None
    times=[ctypes.c_ulonglong() for _ in range(4)]
    ok=kernel.GetProcessTimes(ctypes.c_void_p(handle),*[ctypes.byref(t) for t in times])
    kernel.CloseHandle(ctypes.c_void_p(handle))
    return times[0].value if ok else None

def stop():
    if not MANIFEST.exists():print('No package-owned running processes recorded.');return
    state=json.loads(MANIFEST.read_text())
    if state.get('root')!=str(ROOT):raise RuntimeError('Process manifest belongs to a different package directory')
    for process in reversed(state['processes']):
        if creation(process['pid'])!=process['created'] or process['created'] is None:continue
        # Creation time verification prevents terminating a recycled PID.
        result=subprocess.run(['taskkill','/PID',str(process['pid']),'/T','/F'],capture_output=True,text=True)
        if result.returncode and creation(process['pid']) is not None:raise RuntimeError('Could not stop owned '+process['name']+' process: '+result.stderr.strip())
    MANIFEST.unlink(missing_ok=True)
    print('VoltMind services stopped.')

def free(port):
    with socket.socket() as sock:
        return sock.connect_ex(('127.0.0.1',port))!=0

def get(url):
    with urllib.request.urlopen(url,timeout=2) as response:return json.load(response)

def java_executable():
    java=shutil.which('java')
    if not java:return None
    # Windows vendor PATH shims can spawn an unrecorded child. Launch the real JDK executable.
    settings=subprocess.run([java,'-XshowSettings:properties','-version'],capture_output=True,text=True,timeout=15)
    home=re.search(r'^\s*java\.home\s*=\s*(.+)$',settings.stdout+'\n'+settings.stderr,re.MULTILINE)
    if home:
        actual=Path(home.group(1).strip())/'bin'/('java.exe' if os.name=='nt' else 'java')
        if actual.is_file():return str(actual)
    raise RuntimeError('Could not identify the Java runtime executable. Install a JDK and check java -version.')

def start(no_browser=False,ml_port=8765,backend_port=8080,frontend_port=5173):
    if len({ml_port,backend_port,frontend_port})!=3 or any(not 1024<=p<=65535 for p in [ml_port,backend_port,frontend_port]):raise RuntimeError('Choose three distinct ports between 1024 and 65535')
    url=f'http://127.0.0.1:{frontend_port}'
    for port in [ml_port,backend_port,frontend_port]:
        if not free(port):raise RuntimeError(f'Port {port} is occupied. Stop the existing VoltMind instance or the application using this port, then retry.')
    python=ROOT/'.venv/Scripts/python.exe';jar=ROOT/'backend/target/DTBackend-0.0.1-SNAPSHOT.jar';vite=ROOT/'frontend/node_modules/vite/bin/vite.js'
    if not all(p.exists() for p in [python,jar,vite]):raise RuntimeError('Run install_voltmind.bat once before starting this extracted package.')
    java=java_executable();node=shutil.which('node')
    if not java or not node:raise RuntimeError('Java and Node.js must be available on PATH. See START_HERE.md.')
    STATE.mkdir(exist_ok=True);logs=STATE/'logs';logs.mkdir(exist_ok=True)
    instance=uuid.uuid4().hex
    commands=[('ml',[str(python),str(ROOT/'ml/main.py'),'--serve','--port',str(ml_port),'--instance-id',instance],ROOT),
              ('backend',[java,'-jar',str(jar),f'--server.port={backend_port}',f'--voltmind.worker-url=http://127.0.0.1:{ml_port}'],ROOT/'backend'),
              ('frontend',[node,str(vite),'--host','127.0.0.1','--port',str(frontend_port)],ROOT/'frontend')]
    child_environment=os.environ.copy();child_environment['VOLTMIND_BACKEND_URL']=f'http://127.0.0.1:{backend_port}'
    state={'root':str(ROOT),'instanceId':instance,'processes':[]}
    try:
        for name,command,cwd in commands:
            with (logs/(name+'.log')).open('w',encoding='utf-8') as log:
                p=subprocess.Popen(command,cwd=cwd,stdout=log,stderr=subprocess.STDOUT,env=child_environment,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
            state['processes'].append({'name':name,'pid':p.pid,'created':creation(p.pid)})
            MANIFEST.write_text(json.dumps(state,indent=2))
        for _ in range(120):
            if any(creation(p['pid']) is None for p in state['processes']):raise RuntimeError('A service exited during startup. See .state/logs.')
            try:
                health=get(f'http://127.0.0.1:{backend_port}/api/health')
                with urllib.request.urlopen(url,timeout=2) as r:ready=r.status==200
                if health.get('instanceId')==instance and ready:break
            except Exception:pass
            time.sleep(.5)
        else:raise RuntimeError('Startup timed out. See .state/logs.')
        print('VoltMind ready: '+url+' (opens idle; choose a data source).')
        if not no_browser:webbrowser.open(url)
    except Exception:
        stop();raise

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['start','stop']);parser.add_argument('--no-browser',action='store_true')
    parser.add_argument('--ml-port',type=int,default=8765);parser.add_argument('--backend-port',type=int,default=8080);parser.add_argument('--frontend-port',type=int,default=5173);args=parser.parse_args()
    try:start(args.no_browser,args.ml_port,args.backend_port,args.frontend_port) if args.action=='start' else stop()
    except Exception as e:print('ERROR: '+str(e));sys.exit(1)
