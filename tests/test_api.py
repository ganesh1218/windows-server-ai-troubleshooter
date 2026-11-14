import json
import subprocess
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient
from backend import app as module

client = TestClient(module.app)
headers = {'Authorization': 'Bearer ' + module.TOKEN}

@pytest.fixture(autouse=True)
def clear_live_reports():
    module.LIVE_REPORTS.clear()
    yield
    module.LIVE_REPORTS.clear()

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

def test_connection_requires_auth_and_valid_inputs():
    assert client.post('/api/connect',json={}).status_code==401
    for target in ('server;whoami','../secret','https://server','-command','', '1.2.3.4/24'):
        response=client.post('/api/connect',headers=headers,json={'target':target,'username':'LAB\\operator','password':'test-secret'})
        assert response.status_code==400
        assert 'test-secret' not in response.text
    assert client.post('/api/connect',headers=headers,content='not json').status_code==400
    assert client.post('/api/connect',headers=headers,json={'password':'x'*17000}).status_code==413

def test_connection_success_uses_fixed_script_and_stdin_only():
    report={'schemaVersion':1,'id':'server01','name':'server01','errors':[],'cpu':34}
    result=subprocess.CompletedProcess([],0,stdout=json.dumps(report),stderr='')
    with patch.object(module.subprocess,'run',return_value=result) as run:
        response=client.post('/api/connect',headers=headers,json={'target':'server01','username':'LAB\\operator','password':'test-secret','use_ssl':True})
    assert response.status_code==200
    assert response.json()['simulated'] is False
    argv=run.call_args.args[0]
    assert argv[-1].endswith('Invoke-HealthCheck.ps1')
    assert 'test-secret' not in str(argv) and 'server01' not in str(argv)
    assert json.loads(run.call_args.kwargs['input'])['password']=='test-secret'
    assert run.call_args.kwargs['timeout']==180
    assert 'test-secret' not in response.text
    assert client.get('/api/reports',headers=headers).json()[0]['cpu']==34

def test_failed_connections_are_explicit_and_do_not_save_reports():
    result=subprocess.CompletedProcess([],0,stdout=json.dumps({'schemaVersion':1,'id':'server01','errors':[{'section':'connection'}]}),stderr='')
    with patch.object(module.subprocess,'run',return_value=result):
        response=client.post('/api/connect',headers=headers,json={'target':'server01','username':'operator','password':'secret'})
    assert response.status_code==502
    assert module.LIVE_REPORTS=={}
    for side_effect,expected in [(subprocess.TimeoutExpired('powershell',180),504),(OSError('private error'),502)]:
        with patch.object(module.subprocess,'run',side_effect=side_effect):
            result=client.post('/api/connect',headers=headers,json={'target':'server01','username':'operator','password':'secret'})
            assert result.status_code==expected
            assert 'private error' not in result.text

def test_connection_lock_and_valid_address_forms():
    for target in ('server01','server01.example.internal','10.0.0.15','2001:db8::10'):
        assert module.valid_target(target)
    module.COLLECTION_LOCK.acquire()
    try:
        result=client.post('/api/connect',headers=headers,json={'target':'server01','username':'operator','password':'secret'})
        assert result.status_code==409
    finally:
        module.COLLECTION_LOCK.release()

def test_collector_invalid_output_is_rejected():
    for output in ('not JSON','[]',json.dumps({'schemaVersion':1,'id':'other-server'})):
        with patch.object(module.subprocess,'run',return_value=subprocess.CompletedProcess([],0,stdout=output,stderr='')):
            assert client.post('/api/connect',headers=headers,json={'target':'server01','username':'operator','password':'secret'}).status_code==502
