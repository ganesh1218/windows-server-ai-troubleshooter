"""Authenticated loopback-only Windows health collection and report viewer."""
import json
import os
import secrets
import ipaddress
import re
import subprocess
import threading
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.concurrency import run_in_threadpool

ROOT = Path(__file__).resolve().parents[1]
DATA = Path(os.getenv('DIAGNOSTIC_DIR', str(ROOT / 'private-data'))).resolve()
TOKEN = os.getenv('APP_TOKEN') or secrets.token_urlsafe(32)
LIVE_REPORTS = {}
COLLECTION_LOCK = threading.Lock()
app = FastAPI(title='ServerScope local API', docs_url=None, redoc_url=None, openapi_url=None)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=['127.0.0.1', 'localhost', 'testserver'])

@app.middleware('http')
async def private_boundary(request: Request, call_next):
    if request.client and request.client.host not in ('127.0.0.1', '::1', 'testclient'):
        return __import__('starlette.responses', fromlist=['JSONResponse']).JSONResponse({'detail':'Loopback clients only'}, status_code=403)
    origin = request.headers.get('origin')
    if origin and origin not in ('http://127.0.0.1:8000', 'http://localhost:8000'):
        return __import__('starlette.responses', fromlist=['JSONResponse']).JSONResponse({'detail':'Origin denied'}, status_code=403)
    response = await call_next(request)
    response.headers['Cache-Control'] = 'no-store'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'"
    return response

def authorize(authorization: str = Header(default='')):
    if not secrets.compare_digest(authorization, 'Bearer ' + TOKEN):
        raise HTTPException(401, 'Enter the local session token shown in the terminal')

def reports():
    result = []
    for path in sorted(DATA.glob('*.json')):
        if path.is_symlink() or path.stat().st_size > 5_000_000:
            continue
        try:
            report = json.loads(path.read_text(encoding='utf-8-sig'))
            if report.get('schemaVersion') == 1 and isinstance(report.get('id'), str):
                report['simulated'] = False
                result.append(report)
        except (ValueError, OSError, AttributeError):
            continue
    return result

@app.get('/api/reports', dependencies=[Depends(authorize)])
def get_reports():
    return list({r['id']: r for r in reports() + list(LIVE_REPORTS.values())}.values())

def valid_target(target):
    try:
        ipaddress.ip_address(target)
        return True
    except ValueError:
        return bool(len(target) <= 253 and all(re.fullmatch(r'[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?', label) for label in target.split('.')))

def run_collection(payload):
    if os.name != 'nt':
        raise HTTPException(503, 'Live collection requires a Windows workstation with PowerShell 5.1.')
    if not COLLECTION_LOCK.acquire(blocking=False):
        raise HTTPException(409, 'A health check is already running. Wait for it to finish.')
    try:
        executable = Path(os.environ.get('SystemRoot', r'C:\Windows')) / 'System32/WindowsPowerShell/v1.0/powershell.exe'
        result = subprocess.run(
            [str(executable), '-NoProfile', '-NonInteractive', '-File', str(ROOT / 'scripts/Invoke-HealthCheck.ps1')],
            input=json.dumps(payload), capture_output=True, text=True, encoding='utf-8',
            timeout=180, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0), check=False)
        if result.returncode:
            raise HTTPException(502, 'Collection failed. Check credentials, PowerShell execution policy, connectivity and remote permissions.')
        report = json.loads(result.stdout.lstrip('\ufeff').strip())
        if report.get('schemaVersion') != 1 or report.get('id') != payload['target']:
            raise ValueError('Invalid collector output')
        if any(e.get('section') == 'connection' for e in report.get('errors', [])):
            raise HTTPException(502, 'Unable to connect using WinRM or DCOM. Verify the server address, credentials, firewall and remote permissions.')
        report['simulated'] = False
        LIVE_REPORTS[report['id']] = report
        return report
    except subprocess.TimeoutExpired:
        raise HTTPException(504, 'Health check timed out after 180 seconds. Verify connectivity and try a shorter event window using the console collector.') from None
    except (OSError, ValueError, AttributeError):
        raise HTTPException(502, 'The Windows collector could not return a valid report.') from None
    finally:
        payload.clear()
        COLLECTION_LOCK.release()

@app.post('/api/connect', dependencies=[Depends(authorize)])
async def connect(request: Request):
    # Parse manually so validation errors never echo submitted passwords.
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > 16384:
            raise HTTPException(413, 'Connection request is too large.')
    try:
        payload = json.loads(body)
        if not isinstance(payload, dict):
            raise ValueError()
        target = payload.get('target', '')
        username = payload.get('username', '')
        password = payload.get('password', '')
        use_ssl = payload.get('use_ssl', True)
        if not isinstance(target, str) or not valid_target(target) or not isinstance(username, str) or not 1 <= len(username) <= 256 or not isinstance(password, str) or not 1 <= len(password) <= 4096 or type(use_ssl) is not bool:
            raise ValueError()
        clean = {'target': target, 'username': username, 'password': password, 'use_ssl': use_ssl}
    except (ValueError, TypeError):
        raise HTTPException(400, 'Enter a valid server name or IP, username, password and connection option.') from None
    finally:
        body.clear()
    return await run_in_threadpool(run_collection, clean)

@app.get('/api/health')
def health():
    return {'status': 'ok', 'mode': 'local', 'application': 'Server Health Check'}

if (ROOT / 'dist/assets').exists():
    app.mount('/assets', StaticFiles(directory=ROOT / 'dist/assets'), name='assets')

@app.get('/')
def index():
    return FileResponse(ROOT / 'dist/index.html')

def main():
    import uvicorn
    print('\nLocal dashboard: http://127.0.0.1:8000/?local=1')
    print('Session token (keep private): ' + TOKEN + '\n')
    uvicorn.run(app, host='127.0.0.1', port=8000, access_log=False)

if __name__ == '__main__':
    main()
