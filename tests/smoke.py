"""Dependency-free integration tests. Run after dotnet build: python3 tests/smoke.py."""
import json
from datetime import datetime
import os
from pathlib import Path
import subprocess
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = Path(__file__).resolve().parents[1]
DLL = ROOT / 'Hedwig/bin/Debug/net10.0/Hedwig.dll'
requests = []
if '--browser' in sys.argv:
    os.environ['HEDWIG_TEST_BROWSER'] = '1'
    sys.argv.remove('--browser')


class OllamaStub(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def do_GET(self):
        body = b'<html><head><title>Research fixture</title></head><body><main>Verified browser evidence.</main></body></html>'
        self.send_response(200)
        self.send_header('Content-Type', 'text/html')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        request = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        requests.append(request)
        messages = request['messages']
        last = messages[-1]
        if last['role'] == 'tool':
            message = {'role': 'assistant', 'content': 'Tool returned: ' + last['content']}
        elif last['content'] in ('test tool', 'test browser'):
            url = 'file:///invalid' if last['content'] == 'test tool' else f'http://127.0.0.1:{self.server.server_port}/source'
            message = {'role': 'assistant', 'content': '', 'tool_calls': [
                {'function': {'name': 'ReadPage', 'arguments': {'url': url}}}
            ]}
        elif last['content'] == 'test failure':
            self.send_error(503)
            return
        else:
            count = sum(m['role'] == 'user' for m in messages)
            message = {'role': 'assistant', 'content': f'User turns: {count}'}
        body = (json.dumps({'model': request['model'], 'created_at': '2026-10-22T00:00:00Z',
                            'message': message, 'done': True, 'done_reason': 'stop'}) + '\n').encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/x-ndjson')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class SmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), OllamaStub)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def setUp(self):
        requests.clear()

    def run_app(self, prompts):
        env = dict(os.environ, OLLAMA_ENDPOINT=f'http://127.0.0.1:{self.server.server_port}/',
                   OLLAMA_MODEL_NAME='test-model')
        result = subprocess.run(['dotnet', str(DLL)], input=prompts, text=True,
                                capture_output=True, env=env, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout + result.stderr

    def test_history_reset_blank_and_exit(self):
        output = self.run_app('\nhello\nfollow up\n/reset\nnew question\n/exit\n')
        self.assertIn('User turns: 1', output)
        self.assertIn('User turns: 2', output)
        self.assertEqual(len(requests), 3)
        self.assertEqual([sum(m['role'] == 'user' for m in r['messages']) for r in requests], [1, 2, 1])
        self.assertIn('Goodbye.', output)
        for request in requests:
            clocks = [m['content'] for m in request['messages'] if m['role'] == 'system' and 'Current local date and time:' in m['content']]
            self.assertTrue(clocks, 'Each turn must supply the current clock to the model')
            self.assertIn(datetime.now().strftime('%Y-%m-%d'), clocks[-1])

    def test_framework_invokes_tool_and_returns_result_to_model(self):
        output = self.run_app('test tool\n/exit\n')
        self.assertIn('Tool returned:', output)
        self.assertIn('absolute HTTP or HTTPS URL', output)
        self.assertEqual(len(requests), 2)
        tools = {tool['function']['name'] for tool in requests[0]['tools']}
        self.assertEqual(tools, {'SearchWeb', 'ReadPage'})
        for tool in requests[0]['tools']:
            self.assertNotIn('cancellationToken', tool['function']['parameters'].get('properties', {}))

    def test_failure_recovers_with_fresh_session(self):
        output = self.run_app('test failure\nhello\n/exit\n')
        self.assertIn('Request failed:', output)
        self.assertIn('User turns: 1', output)

    def test_eof_exits(self):
        self.assertIn('Goodbye.', self.run_app(''))
        self.assertEqual(len(requests), 0)

    @unittest.skipUnless(os.environ.get('HEDWIG_TEST_BROWSER') == '1', 'Set HEDWIG_TEST_BROWSER=1 to test Chromium')
    def test_browser_reads_source(self):
        output = self.run_app('test browser\n/exit\n')
        self.assertIn('Verified browser evidence.', output)
        self.assertIn('Research fixture', output)
        self.assertNotIn('Browser research failed', output)


if __name__ == '__main__':
    unittest.main()
