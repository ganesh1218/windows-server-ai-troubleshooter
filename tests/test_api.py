import json
from unittest.mock import AsyncMock, patch
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

def test_ollama_failure_is_explicit(tmp_path, monkeypatch):
    monkeypatch.setattr(module,'DATA',tmp_path)
    (tmp_path/'lab.json').write_text(json.dumps({'schemaVersion':1,'id':'lab'}))
    import httpx
    with patch.object(httpx.AsyncClient,'post',new=AsyncMock(side_effect=httpx.ConnectError('offline'))):
        response=client.post('/api/analyze',headers=headers,json={'server_id':'lab'})
        assert response.status_code==503
        assert 'Ollama unavailable' in response.json()['detail']

def test_analysis_fixed_local_destination(tmp_path, monkeypatch):
    monkeypatch.setattr(module,'DATA',tmp_path)
    (tmp_path/'lab.json').write_text(json.dumps({'schemaVersion':1,'id':'lab'}))
    import httpx
    response=httpx.Response(200,json={'response':'Evidence-based next steps'},request=httpx.Request('POST','http://127.0.0.1:11434/api/generate'))
    with patch.object(httpx.AsyncClient,'post',new=AsyncMock(return_value=response)) as post:
        result=client.post('/api/analyze',headers=headers,json={'server_id':'lab'})
        assert result.status_code==200
        assert result.json()['simulated'] is False
        assert post.call_args.args[0]=='http://127.0.0.1:11434/api/generate'
        assert post.call_args.kwargs['json']['stream'] is False

def test_missing_body_and_health():
    assert client.post('/api/analyze',headers=headers,json={}).status_code==422
    assert client.get('/api/health').json()['mode']=='local'

def test_no_remote_execution_route():
    assert client.post('/api/collect',headers=headers,json={'computer':'server'}).status_code==404
