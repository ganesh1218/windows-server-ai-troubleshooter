"""Local-only Python connector. Uses Windows' built-in PowerShell collector.

No third-party Python dependencies, credential files, telemetry, or public listener.
"""
from __future__ import annotations

import hmac
import ipaddress
import json
import os
from pathlib import Path
import re
import secrets
import socket
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer

WEBSITE = 'https://wshc.ganesh18.dpdns.org'
HOST, PORT = '127.0.0.1', 8000
ROOT = Path(__file__).resolve().parent
MAX_BODY = 16384
API_PATHS = {'/api/health', '/api/reports', '/api/connect'}
COLLECTION_ERRORS = {
    'script_blocked': 'Windows blocked the bundled PowerShell scripts (script-signing, execution-policy or downloaded-file trust). Review the scripts and follow your organization\'s approved signing/unblocking process, then restart the connector. Do not disable your security policy.',
    'invalid_request': 'The connector could not read the diagnostic request. Update the connector from the website and restart it.',
    'credential_setup': 'Windows could not prepare the supplied credentials. Enter a non-empty username and password; use DOMAIN\\username or SERVERNAME\\username as appropriate.',
    'collector_failed': 'The local PowerShell collector failed before returning a report. Verify the extracted scripts are complete, permitted by your policy, and Windows PowerShell 5.1 is available.',
    'script_parse_error': 'Windows could not parse the bundled PowerShell scripts. Extract a fresh connector package and keep its scripts folder intact.',
    'powershell_missing': 'Windows PowerShell 5.1 could not be started. Run this connector on a Windows management computer with built-in Windows PowerShell available.',
}


def process_failure(result):
    """Classify locally; never return raw stdout/stderr, paths or account names."""
    code = 'collector_failed'
    try:
        supplied = json.loads(result.stdout.decode('utf-8-sig')).get('errorCode')
        if supplied in COLLECTION_ERRORS:
            code = supplied
    except (ValueError, AttributeError, UnicodeError):
        pass
    diagnostic = result.stderr.decode('utf-8', errors='replace')
    if re.search(r'PSSecurityException|running scripts is disabled|not digitally signed', diagnostic, re.I):
        code = 'script_blocked'
    elif re.search(r'ParserError|ParseException', diagnostic, re.I):
        code = 'script_parse_error'
    return {'errorCode': code, 'detail': COLLECTION_ERRORS[code]}


def valid_target(value):
    if not isinstance(value, str) or not 1 <= len(value) <= 253:
        return False
    try:
        ipaddress.ip_address(value)
        return '%' not in value
    except ValueError:
        return all(re.fullmatch(r'[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?', label)
                   for label in value.split('.'))


def validate_payload(data):
    if not isinstance(data, dict) or not valid_target(data.get('target')):
        return False
    return (isinstance(data.get('username'), str) and 1 <= len(data['username']) <= 256
            and isinstance(data.get('password'), str) and 1 <= len(data['password']) <= 4096
            and isinstance(data.get('use_ssl', True), bool))


def collect(data):
    """Only a fixed, bundled script runs; credentials travel through stdin."""
    executable = Path(os.environ.get('SystemRoot', r'C:\Windows')) / 'System32/WindowsPowerShell/v1.0/powershell.exe'
    try:
        result = subprocess.run(
            [str(executable), '-NoProfile', '-NonInteractive', '-File',
             str(ROOT / 'scripts/Invoke-HealthCheck.ps1')],
            input=json.dumps(data, ensure_ascii=True).encode('utf-8'),
            capture_output=True, timeout=180, check=False,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        if result.returncode:
            return 502, process_failure(result)
        report = json.loads(result.stdout.decode('utf-8-sig'))
        if (not isinstance(report, dict) or report.get('schemaVersion') != 1
                or report.get('id') != data['target'] or not isinstance(report.get('errors'), list)):
            raise ValueError('Invalid collector output')
        if any(not isinstance(e, dict) or e.get('section') == 'connection' for e in report['errors']):
            return 502, {'detail': 'Unable to connect using WinRM or DCOM. Check the server, credentials, firewall and permissions.'}
        report['simulated'] = False
        return 200, report
    except subprocess.TimeoutExpired:
        return 504, {'detail': 'Health check timed out after 180 seconds.'}
    except FileNotFoundError:
        return 502, {'errorCode': 'powershell_missing', 'detail': COLLECTION_ERRORS['powershell_missing']}
    except (OSError, ValueError, UnicodeError):
        return 502, {'detail': 'The bundled PowerShell collector could not return a valid report.'}
    finally:
        data.clear()


class ConnectorServer(HTTPServer):
    allow_reuse_address = False

    def __init__(self, address=(HOST, PORT), collector=collect):
        self.token = secrets.token_urlsafe(32)
        self.reports = {}
        self.collector = collector
        super().__init__(address, ConnectorHandler)

    def handle_error(self, request, client_address):
        # HTTP parser, request and collector errors must not expose private data.
        pass

    def server_close(self):
        self.reports.clear()
        self.token = ''
        super().server_close()


class ConnectorHandler(BaseHTTPRequestHandler):
    server_version = 'WSHC-Connector/1.0'
    sys_version = ''

    def setup(self):
        super().setup()
        self.connection.settimeout(15)

    def log_message(self, *args):
        pass

    def send_error(self, code, message=None, explain=None):
        self.reply(code, {'detail': 'Request rejected.'})

    def reply(self, status, value):
        body = b'' if status == 204 else json.dumps(value, ensure_ascii=True).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Connection', 'close')
        if self.headers.get('Origin') == WEBSITE and self.path in API_PATHS:
            self.send_header('Access-Control-Allow-Origin', WEBSITE)
            self.send_header('Vary', 'Origin')
            self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
            self.send_header('Access-Control-Allow-Headers', 'Authorization, Content-Type')
            self.send_header('Access-Control-Allow-Private-Network', 'true')
        self.end_headers()
        try:
            self.wfile.write(body)
        except (OSError, socket.timeout):
            pass
        self.close_connection = True

    def allowed(self):
        expected = f'{HOST}:{self.server.server_address[1]}'
        if self.headers.get_all('Host', []) != [expected]:
            self.reply(400, {'detail': 'Unexpected Host header.'})
            return False
        if not ipaddress.ip_address(self.client_address[0]).is_loopback:
            self.reply(403, {'detail': 'Loopback clients only.'})
            return False
        origins = self.headers.get_all('Origin', [])
        if origins and origins != [WEBSITE]:
            self.reply(403, {'detail': 'Origin denied.'})
            return False
        if self.path not in API_PATHS:
            self.reply(404, {'detail': 'Use the dashboard at ' + WEBSITE})
            return False
        return True

    def authenticated(self):
        values = self.headers.get_all('Authorization', [])
        actual = values[0] if len(values) == 1 else ''
        expected = 'Bearer ' + self.server.token
        if not hmac.compare_digest(actual.encode('utf-8'), expected.encode('utf-8')):
            self.reply(401, {'detail': 'Session rejected. Pair using the current connector session code.'})
            return False
        return True

    def do_OPTIONS(self):
        if self.allowed():
            self.reply(204, None)

    def do_GET(self):
        if not self.allowed():
            return
        if self.path == '/api/health':
            self.reply(200, {'status': 'ok', 'mode': 'python', 'application': 'Server Health Check',
                             'version': '1.0.0', 'collector': 'Windows PowerShell 5.1'})
        elif self.authenticated():
            if self.path == '/api/reports':
                self.reply(200, list(self.server.reports.values()))
            else:
                self.reply(405, {'detail': 'Method not allowed.'})

    def do_POST(self):
        if not self.allowed() or not self.authenticated():
            return
        if self.path != '/api/connect':
            self.reply(405, {'detail': 'Method not allowed.'})
            return
        lengths = self.headers.get_all('Content-Length', [])
        if self.headers.get('Transfer-Encoding') or len(lengths) != 1 or len(lengths[0]) > 8 or not lengths[0].isdigit():
            self.reply(400, {'detail': 'A single Content-Length is required.'})
            return
        length = int(lengths[0])
        if not 0 < length <= MAX_BODY:
            # Drain only a bounded small body so Windows can deliver the 413
            # response without resetting a connection with unread TCP data.
            if MAX_BODY < length <= 65536:
                try:
                    self.rfile.read(length)
                except (OSError, socket.timeout):
                    pass
            self.reply(413, {'detail': 'Connection request is too large or empty.'})
            return
        if self.headers.get('Content-Type', '').split(';')[0].strip() != 'application/json':
            self.reply(415, {'detail': 'Use application/json.'})
            return
        data = None
        try:
            raw = self.rfile.read(length)
            if len(raw) != length:
                raise ValueError('Incomplete body')
            data = json.loads(raw)
            raw = None
            if not validate_payload(data):
                raise ValueError('Invalid fields')
            payload = {key: data[key] for key in ('target', 'username', 'password')}
            payload['use_ssl'] = data.get('use_ssl', True)
            target = payload['target']
            data.clear()
        except (ValueError, OSError, socket.timeout):
            if isinstance(data, dict):
                data.clear()
            self.reply(400, {'detail': 'Enter a valid server name/IP, username, password and connection option.'})
            return
        try:
            status, report = self.server.collector(payload)
            if status == 200:
                self.server.reports[target] = report
            self.reply(status, report)
        except Exception:
            self.reply(502, {'detail': 'Collection failed. No raw error details were returned.'})
        finally:
            payload.clear()


def main():
    if sys.version_info < (3, 11) or sys.platform != 'win32':
        print('Use Python 3.11 or newer on a Windows management computer.')
        return 1
    if not all((ROOT / 'scripts' / name).is_file() for name in ('Invoke-HealthCheck.ps1', 'Collect-Diagnostics.ps1')):
        print('Extract the complete connector ZIP before starting it. Bundled collector scripts are missing.')
        return 1
    try:
        server = ConnectorServer()
    except OSError:
        print('Cannot listen on 127.0.0.1:8000. Stop any previous connector or PowerShell web host, then retry.')
        return 1
    print('Windows Server Health Check - Python connector')
    print('Open ' + WEBSITE)
    print('Private session code (paste into the website, never share):')
    print(server.token)
    print('Keep this window open. Ctrl+C stops the connector and clears snapshots.')
    try:
        server.serve_forever(poll_interval=0.25)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
