"""Loopback-only private report viewer. No remote execution or credential endpoints."""
import json
import os
import secrets
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware

ROOT = Path(__file__).resolve().parents[1]
DATA = Path(os.getenv('DIAGNOSTIC_DIR', str(ROOT / 'private-data'))).resolve()
TOKEN = os.getenv('APP_TOKEN') or secrets.token_urlsafe(32)
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
    return reports()

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
