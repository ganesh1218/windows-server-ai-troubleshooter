import hashlib
import http.client
import importlib.util
import json
from pathlib import Path
import subprocess
import threading
import tempfile
import sys
import unittest
from unittest.mock import patch
import zipfile

from connector.connector import ConnectorServer, WEBSITE, collect, process_failure

ROOT = Path(__file__).resolve().parents[1]


class ConnectorTests(unittest.TestCase):
    def setUp(self):
        self.calls = []

        def collector(payload):
            self.calls.append(dict(payload))
            return 200, {'schemaVersion': 1, 'id': payload['target'], 'simulated': False, 'errors': []}

        self.server = ConnectorServer(('127.0.0.1', 0), collector=collector)
        self.thread = threading.Thread(target=self.server.serve_forever, kwargs={'poll_interval': .01}, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.thread.join()
        self.server.server_close()

    def request(self, method='GET', path='/api/reports', body=None, auth=True, headers=None):
        port = self.server.server_address[1]
        connection = http.client.HTTPConnection('127.0.0.1', port, timeout=3)
        values = {'Host': f'127.0.0.1:{port}', 'Origin': WEBSITE}
        if auth:
            values['Authorization'] = 'Bearer ' + self.server.token
        if body is not None:
            values['Content-Type'] = 'application/json'
            body = json.dumps(body)
        values.update(headers or {})
        connection.request(method, path, body, values)
        response = connection.getresponse()
        status, response_headers, raw = response.status, dict(response.getheaders()), response.read()
        connection.close()
        return status, response_headers, json.loads(raw) if raw else None

    def test_health_identifies_python_without_disclosing_token(self):
        status, headers, data = self.request(path='/api/health', auth=False)
        self.assertEqual(status, 200)
        self.assertEqual(data['mode'], 'python')
        self.assertNotIn(self.server.token, json.dumps(data))
        self.assertEqual(headers['Cache-Control'], 'no-store')

    def test_pairing_required_and_current_code_works(self):
        self.assertEqual(self.request(auth=False)[0], 401)
        self.assertEqual(self.request(headers={'Authorization': 'Bearer wrong'})[0], 401)
        self.assertEqual(self.request()[2], [])

    def test_preflight_allows_only_website_without_exposing_reports(self):
        status, headers, data = self.request('OPTIONS', auth=False)
        self.assertEqual(status, 204)
        self.assertEqual(headers['Access-Control-Allow-Origin'], WEBSITE)
        self.assertEqual(headers['Access-Control-Allow-Private-Network'], 'true')
        self.assertIsNone(data)
        for origin in ('https://evil.example', WEBSITE + '.evil.example', 'null'):
            status, headers, _ = self.request('OPTIONS', auth=False, headers={'Origin': origin})
            self.assertEqual(status, 403)
            self.assertNotIn('Access-Control-Allow-Origin', headers)

    def test_host_validation_and_no_file_or_bootstrap_routes(self):
        self.assertEqual(self.request(headers={'Host': 'evil.example'})[0], 400)
        for path in ('/', '/connector.py', '/scripts/Collect-Diagnostics.ps1', '/api/token'):
            self.assertEqual(self.request(path=path)[0], 404)

    def test_success_returns_live_report_and_keeps_only_report(self):
        payload = {'target': 'server01', 'username': 'LAB\\operator', 'password': 'dummy-secret', 'use_ssl': True}
        status, _, data = self.request('POST', '/api/connect', payload)
        self.assertEqual(status, 200)
        self.assertFalse(data['simulated'])
        self.assertEqual(self.calls, [payload])
        reports = self.request()[2]
        self.assertEqual(reports[0]['id'], 'server01')
        self.assertNotIn('dummy-secret', json.dumps(reports))

    def test_invalid_payloads_never_invoke_collector(self):
        for target in ('server;whoami', '../secret', 'https://server', '', '-command'):
            status, _, data = self.request('POST', '/api/connect', {'target': target, 'username': 'user', 'password': 'dummy-secret'})
            self.assertEqual(status, 400)
            self.assertNotIn('dummy-secret', json.dumps(data))
        self.assertEqual(self.request('POST', '/api/connect', {'target': 'server', 'username': 'user', 'password': 'x', 'use_ssl': 'false'})[0], 400)
        self.assertFalse(self.calls)

    def test_oversize_and_wrong_content_type_rejected(self):
        self.assertEqual(self.request('POST', '/api/connect', {'password': 'x' * 17000})[0], 413)
        self.assertEqual(self.request('POST', '/api/connect', {}, headers={'Content-Type': 'text/plain'})[0], 415)

    def test_shutdown_discards_reports_and_code(self):
        token = self.server.token
        self.server.reports['private'] = {'id': 'private'}
        self.server.shutdown()
        self.server.server_close()
        self.assertFalse(self.server.reports)
        self.assertFalse(self.server.token)
        self.assertGreater(len(token), 32)


class CollectorTests(unittest.TestCase):
    def test_policy_and_parse_errors_are_classified_without_leaking_stderr(self):
        for diagnostic, expected in ((b'PSSecurityException: private path LAB\\operator dummy-secret', 'script_blocked'),
                                     (b'ParserError: private script path dummy-secret', 'script_parse_error')):
            result = process_failure(subprocess.CompletedProcess([], 1, b'', diagnostic))
            self.assertEqual(result['errorCode'], expected)
            self.assertNotIn('dummy-secret', json.dumps(result))
            self.assertNotIn('LAB', json.dumps(result))
        result = process_failure(subprocess.CompletedProcess([], 1, b'{"errorCode":"credential_setup"}', b''))
        self.assertEqual(result['errorCode'], 'credential_setup')
        result = process_failure(subprocess.CompletedProcess([], 1, b'{"errorCode":"dummy-secret"}', b''))
        self.assertEqual(result['errorCode'], 'collector_failed')
        result = process_failure(subprocess.CompletedProcess([], 1, b'{"errorCode":"collector_failed","exceptionType":"System.InvalidOperationException","script":"Collect-Diagnostics.ps1","line":23,"password":"dummy-secret"}', b''))
        self.assertIn('System.InvalidOperationException', result['detail'])
        self.assertIn('23', result['detail'])
        self.assertNotIn('dummy-secret', json.dumps(result))
        result = process_failure(subprocess.CompletedProcess([], 1, b'{"errorCode":{},"exceptionType":"dummy-secret","script":"private-path","line":"dummy-secret"}', b''))
        self.assertNotIn('dummy-secret', json.dumps(result))
        self.assertNotIn('private-path', json.dumps(result))

    def payload(self):
        return {'target': 'server01', 'username': 'LAB\\test', 'password': 'dummy-secret', 'use_ssl': True}

    @patch('connector.connector.subprocess.run')
    def test_fixed_script_stdin_credentials_timeout_and_memory_cleanup(self, run):
        run.return_value = subprocess.CompletedProcess([], 0, b'{"schemaVersion":1,"id":"server01","errors":[]}', b'')
        payload = self.payload()
        status, data = collect(payload)
        self.assertEqual(status, 200)
        self.assertFalse(data['simulated'])
        self.assertFalse(payload)
        args = run.call_args
        self.assertNotIn('dummy-secret', str(args.args[0]))
        self.assertIn(b'dummy-secret', args.kwargs['input'])
        self.assertEqual(args.kwargs['timeout'], 180)
        self.assertNotIn('shell', args.kwargs)
        self.assertFalse(any(key.upper() == 'PSMODULEPATH' for key in args.kwargs['env']))
        self.assertTrue(args.args[0][-1].endswith('Invoke-HealthCheck.ps1'))

    @patch('connector.connector.subprocess.run')
    def test_failure_timeout_and_invalid_reports_sanitized(self, run):
        run.side_effect = subprocess.TimeoutExpired('fixed-script', 180)
        self.assertEqual(collect(self.payload())[0], 504)
        run.side_effect = None
        for code, output in ((1, b'dummy-secret'), (0, b'invalid'), (0, b'{"schemaVersion":1,"id":"wrong","errors":[]}'),
                             (0, b'{"schemaVersion":1,"id":"server01","errors":[{"section":"connection"}]}')):
            run.return_value = subprocess.CompletedProcess([], code, output, b'private raw error')
            status, data = collect(self.payload())
            self.assertEqual(status, 502)
            self.assertNotIn('dummy-secret', json.dumps(data))
            self.assertNotIn('private raw error', json.dumps(data))


class PackageTests(unittest.TestCase):
    @unittest.skipUnless(sys.platform == 'win32', 'Built-in PowerShell readiness check requires Windows')
    def test_packaged_diagnostic_mode_needs_no_server_or_credentials(self):
        archive = ROOT / 'public/downloads/windows-server-health-check-connector.zip'
        with tempfile.TemporaryDirectory() as folder:
            with zipfile.ZipFile(archive) as package:
                for name in ('connector.py', 'scripts/Test-ConnectorEnvironment.ps1',
                             'scripts/Invoke-HealthCheck.ps1', 'scripts/Collect-Diagnostics.ps1'):
                    destination = Path(folder) / name
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    destination.write_bytes(package.read(name))
            result = subprocess.run([sys.executable, str(Path(folder) / 'connector.py'), '--diagnose'],
                                    capture_output=True, timeout=35)
            self.assertEqual(result.returncode, 0, result.stdout)
            output = result.stdout.decode()
            data = json.loads(output[output.index('{'):])
            self.assertEqual(data['connectorVersion'], '1.0.2')
            self.assertEqual(next(item for item in data['checks'] if item['check'] == 'Collect-Diagnostics.ps1')['status'], 'parse-ok')
            self.assertNotIn(folder, output)
            self.assertNotIn('session code', output)

    @unittest.skipUnless(sys.platform == 'win32', 'Built-in PowerShell bridge requires Windows')
    def test_real_collector_with_mocked_remote_commands(self):
        with tempfile.TemporaryDirectory() as folder:
            scripts = Path(folder) / 'scripts'
            scripts.mkdir()
            for name in ('Invoke-HealthCheck.ps1', 'Collect-Diagnostics.ps1'):
                destination = scripts / (name if name.startswith('Invoke') else 'Actual-Diagnostics.ps1')
                destination.write_bytes((ROOT / 'scripts' / name).read_bytes())
            (scripts / 'Collect-Diagnostics.ps1').write_text(
                "param($ComputerName,$Credential,[switch]$UseSSL,$Days,[switch]$NoPersist)\n"
                "function New-CimSessionOption {param($Protocol,[switch]$UseSsl) @{}}\n"
                "function New-CimSession {param($ComputerName,$Credential,$Authentication,$SessionOption,$OperationTimeoutSec) @{}}\n"
                "function Remove-CimSession {param($CimSession)}\n"
                "function Test-NetConnection {param($ComputerName,$Port,$InformationLevel,$WarningAction) $false}\n"
                "function Get-CimInstance {param($ClassName,$CimSession,$ErrorAction,$Namespace,$Filter) "
                "if($ClassName -eq 'Win32_OperatingSystem'){[pscustomobject]@{TotalVisibleMemorySize=1000000;FreePhysicalMemory=500000}}}\n"
                "& (Join-Path $PSScriptRoot 'Actual-Diagnostics.ps1') -ComputerName $ComputerName -Credential $Credential -UseSSL:$UseSSL -Days $Days -NoPersist\n")
            with patch('connector.connector.ROOT', Path(folder)):
                status, data = collect({'target': 'fixture-server', 'username': 'TEST\\fixture',
                                        'password': 'dummy-secret', 'use_ssl': True})
            self.assertEqual(status, 200, data)
            self.assertEqual(data['memory']['usedPercent'], 50)
            self.assertFalse(data['simulated'])

    @unittest.skipUnless(sys.platform == 'win32', 'Built-in PowerShell bridge requires Windows')
    def test_real_bridge_success_with_harmless_collector_fixture(self):
        with tempfile.TemporaryDirectory() as folder:
            scripts = Path(folder) / 'scripts'
            scripts.mkdir()
            bridge = scripts / 'Invoke-HealthCheck.ps1'
            bridge.write_bytes((ROOT / 'scripts/Invoke-HealthCheck.ps1').read_bytes())
            (scripts / 'Collect-Diagnostics.ps1').write_text(
                "param($ComputerName,$Credential,[switch]$UseSSL,$Days,[switch]$NoPersist)\n"
                "if ($Credential.GetNetworkCredential().Password -ne 'dummy-secret') {throw 'Fixture credential mismatch'}\n"
                "@{schemaVersion=1;id=$ComputerName;errors=@()} | ConvertTo-Json -Compress\n")
            with patch('connector.connector.ROOT', Path(folder)):
                status, data = collect({'target': 'fixture-server', 'username': 'TEST\\fixture',
                                        'password': 'dummy-secret', 'use_ssl': True})
            self.assertEqual(status, 200, data)
            self.assertEqual(data['id'], 'fixture-server')
            self.assertFalse(data['simulated'])

    @unittest.skipUnless(sys.platform == 'win32', 'Built-in PowerShell bridge requires Windows')
    def test_extracted_package_can_run_fixed_bridge_without_remote_contact(self):
        archive = ROOT / 'public/downloads/windows-server-health-check-connector.zip'
        with tempfile.TemporaryDirectory() as folder:
            with zipfile.ZipFile(archive) as package:
                for name in ('connector.py', 'scripts/Invoke-HealthCheck.ps1', 'scripts/Collect-Diagnostics.ps1'):
                    destination = Path(folder) / name
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    destination.write_bytes(package.read(name))
            spec = importlib.util.spec_from_file_location('packaged_connector', Path(folder) / 'connector.py')
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            # Invalid target is rejected by PowerShell's parameter validation
            # before any remote session can be attempted. No real credentials.
            status, data = module.collect({'target': 'invalid;target', 'username': 'TEST\\fixture',
                                           'password': 'dummy-secret', 'use_ssl': True})
            self.assertEqual(status, 502)
            self.assertNotIn('dummy-secret', json.dumps(data))

    def test_download_archive_is_complete_current_and_private_data_free(self):
        archive = ROOT / 'public/downloads/windows-server-health-check-connector.zip'
        mapping = {'connector.py': 'connector/connector.py', 'SETUP.md': 'connector/SETUP.md',
                   'scripts/Invoke-HealthCheck.ps1': 'scripts/Invoke-HealthCheck.ps1',
                   'scripts/Collect-Diagnostics.ps1': 'scripts/Collect-Diagnostics.ps1', 'LICENSE': 'LICENSE'}
        mapping['scripts/Test-ConnectorEnvironment.ps1'] = 'scripts/Test-ConnectorEnvironment.ps1'
        with zipfile.ZipFile(archive) as package:
            self.assertIsNone(package.testzip())
            self.assertEqual(set(package.namelist()), set(mapping))
            for name, source in mapping.items():
                self.assertEqual(package.read(name), (ROOT / source).read_bytes())
        expected = Path(str(archive) + '.sha256').read_text().split()[0]
        self.assertEqual(hashlib.sha256(archive.read_bytes()).hexdigest(), expected)


if __name__ == '__main__':
    unittest.main()
