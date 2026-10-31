"""Small isolation/error/finalization probe, independent of Django inputs."""
import os
import sys
STATE=[]

def prepare(stage,config):
    if stage=='resource':
        global RESOURCE
        RESOURCE=open(config['resource'],'r')
    elif stage=='thread':
        import threading
        threading.Thread(target=threading.Event().wait,daemon=True).start()

def run(call):
    STATE.append(call['token'])
    return dict(state=STATE,cwd=os.getcwd(),argv=sys.argv,token=os.environ['GAIA_REQUEST_TOKEN'])
