"""Existing pinned Django fixture; explicit stages keep moved work visible."""
import hashlib
import io
import json
import os
from pathlib import Path
import sys

CONFIG=None
APPLICATION=None

def prepare(stage,config):
    global CONFIG,APPLICATION
    CONFIG=config
    sys.path.insert(0,config['dependencies'])
    os.environ.update(DJANGO_SETTINGS_MODULE='django_fixture.settings',GAIA_DJANGO_SCENARIO=config['scenario'],GAIA_DJANGO_TEMPLATES='filesystem')
    if stage not in ('minimal','imports','framework'):raise ValueError('unknown stage')
    if stage in ('imports','framework'):
        import django.core.wsgi
        import django.core.checks
        import django.db
        import django.template
    if stage=='framework':
        from django.core.wsgi import get_wsgi_application
        APPLICATION=get_wsgi_application()
        from django.db import connections
        if any(c.connection is not None for c in connections.all()):raise RuntimeError('template opened database')

def request(application,path,query='',accept='application/json'):
    response={}
    environ={'REQUEST_METHOD':'GET','SCRIPT_NAME':'','PATH_INFO':path,'QUERY_STRING':query,
             'SERVER_NAME':'testserver','SERVER_PORT':'80','SERVER_PROTOCOL':'HTTP/1.1','HTTP_HOST':'testserver',
             'HTTP_ACCEPT':accept,'REMOTE_ADDR':'127.0.0.1','wsgi.version':(1,0),'wsgi.url_scheme':'http',
             'wsgi.input':io.BytesIO(),'wsgi.errors':io.StringIO(),'wsgi.multithread':False,
             'wsgi.multiprocess':True,'wsgi.run_once':True}
    def start(status,headers,exc_info=None):response['status']=status
    result=application(environ,start)
    try:body=b''.join(result)
    finally:
        if hasattr(result,'close'):result.close()
    if not response['status'].startswith('200 '):raise RuntimeError('bad HTTP status: '+response['status'])
    return body

def run(call):
    if os.environ['GAIA_REQUEST_TOKEN']!=call['token'] or sys.argv[1]!=call['token']:
        raise RuntimeError('request environment/argv binding failed')
    from django.core.wsgi import get_wsgi_application
    application=APPLICATION or get_wsgi_application()
    from django.core.checks import run_checks
    issues=run_checks()
    if issues:raise RuntimeError(str(issues))
    from django.db import connection
    from django_fixture.models import Widget
    try:
        with connection.schema_editor() as editor:editor.create_model(Widget)
        Widget.objects.bulk_create([Widget(name='alpha'),Widget(name='beta')])
        api=json.loads(request(application,'/widgets/','name=alpha'))
        page=request(application,'/admin/login/',accept='text/html')
        if api!=[{'id':1,'name':'alpha'}]:raise RuntimeError('database/request state leaked')
        if not all(s in page for s in (b'Django administration',b'name="username"',b'name="password"')):
            raise RuntimeError('admin response differs')
        versions={}
        for name,expected in CONFIG['versions'].items():
            if CONFIG['scenario']=='core' and name in ('rest_framework','django_filters'):continue
            module=__import__(name);actual=getattr(module,'__version__',None)
            if actual!=expected:raise RuntimeError('wrong package version: '+name)
            versions[name]=actual
        prefixes=tuple(versions)
        controlled={n:m for n,m in sys.modules.items() if any(n==p or n.startswith(p+'.') for p in prefixes)}
        for name,module in controlled.items():
            origin=getattr(getattr(module,'__spec__',None),'origin',None)
            if not origin or not origin.startswith(CONFIG['dependencies']+os.sep):raise RuntimeError('dependency escaped: '+name)
        for resource,digest in CONFIG['resources'].items():
            import importlib.resources
            name,relative=resource.split(':',1)
            if hashlib.sha256(importlib.resources.files(name).joinpath(relative).read_bytes()).hexdigest()!=digest:
                raise RuntimeError('resource differs')
        return dict(api=api,admin_valid=True,versions=versions,modules=sorted(controlled),cwd=os.getcwd(),token=call['token'],rows=Widget.objects.count())
    finally:connection.close()
