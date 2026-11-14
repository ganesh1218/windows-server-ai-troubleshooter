import json
from fastapi.testclient import TestClient
from backend import app as module

client = TestClient(module.app)
headers = {'Authorization': 'Bearer ' + module.TOKEN}

def test_auth_and_origin_boundary():
    assert client.get('/api/reports').status_code == 401
    assert client.get('/api/reports', headers={'Authorization':'Bearer wrong'}).status_code == 401
    assert client.get('/api/reports', headers={**headers, 'Origin':'https://evil.example'}).status_code == 403
    assert client.get('/api/reports', headers={**headers, 'Host':'evil.example'}).status_code == 400

def test_read_reports_and_path_traversal(tmp_path, monkeypatch):
    monkeypatch.setattr(module, 'DATA', tmp_path)
    (tmp_path/'good.json').write_text(json.dumps({'schemaVersion':1,'id':'lab','simulated':True}))
    (tmp_path/'bad.json').write_text('{')
    response=client.get('/api/reports',headers=headers)
    assert response.status_code==200
    assert response.json()==[{'schemaVersion':1,'id':'lab','simulated':False}]
    assert response.headers['cache-control']=='no-store'
    assert client.post('/api/analyze',headers=headers,json={'server_id':'../../secrets'}).status_code==404

def test_empty_report_directory(tmp_path, monkeypatch):
    monkeypatch.setattr(module, 'DATA', tmp_path)
    assert client.get('/api/reports',headers=headers).json()==[]

def test_health_endpoint():
    assert client.get('/api/health').json()=={'status':'ok','mode':'local','application':'Server Health Check'}

def test_no_remote_execution_route():
    assert client.post('/api/collect',headers=headers,json={'computer':'server'}).status_code==404
