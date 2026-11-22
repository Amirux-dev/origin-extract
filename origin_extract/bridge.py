"""Relais optionnel : le Mac envoie un OPJU au PC et reçoit un projet portable."""
from __future__ import annotations

from dataclasses import dataclass, field
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import secrets
import socket
import tempfile
import threading
import time
import traceback
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, quote, urlparse
from urllib.request import Request, urlopen

from .core import Cancelled, check_cancel, convert_windows, load_pack, pack_bytes, safe_name
from .relay_page import WELCOME

MAX_UPLOAD = 512 * 1024 * 1024


@dataclass
class Job:
    id: str
    state: str = 'en_attente'
    messages: list[str] = field(default_factory=list)
    error: str = ''
    result: bytes | None = None
    stop: threading.Event = field(default_factory=threading.Event)


class Bridge:
    def __init__(self, viewer, host='127.0.0.1', port=0, token=None, converter=convert_windows):
        self.viewer = str(viewer)
        self.token = token or secrets.token_urlsafe(32)
        self.jobs = {}
        self.lock = threading.Lock()
        self.conversion_lock = threading.Lock()
        self.converter = converter
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def authenticated(self):
                provided = self.headers.get('Authorization', '')
                return hmac.compare_digest(provided.encode('utf-8'), ('Bearer ' + owner.token).encode('utf-8'))

            def require_key(self):
                if self.authenticated():
                    return True
                message = ('Connection key required. Enter the PC address and key in Origin Extract on your Mac.'
                           if not self.headers.get('Authorization') else
                           'Incorrect connection key. Copy the current key from the Windows PC.')
                self.reply(401, {'error': message})
                return False

            def reply(self, status, payload, binary=False, html=False):
                raw = payload.encode('utf-8') if html else payload if binary else json.dumps(payload, ensure_ascii=False).encode('utf-8')
                self.send_response(status)
                self.send_header('Content-Type', 'text/html; charset=utf-8' if html else 'application/octet-stream' if binary else 'application/json; charset=utf-8')
                self.send_header('Content-Length', str(len(raw)))
                self.send_header('Cache-Control', 'no-store')
                self.send_header('X-Content-Type-Options', 'nosniff')
                self.send_header('Referrer-Policy', 'no-referrer')
                self.send_header('Content-Security-Policy', "default-src 'none'; style-src 'unsafe-inline'; frame-ancestors 'none'")
                self.end_headers()
                try:
                    self.wfile.write(raw)
                except (BrokenPipeError, ConnectionResetError):
                    pass

            def do_GET(self):
                parsed = urlparse(self.path)
                if parsed.path == '/':
                    return self.reply(200, WELCOME, html=True)
                if parsed.path == '/favicon.ico':
                    return self.reply(204, b'', binary=True)
                if not self.require_key():
                    return
                if parsed.path == '/health':
                    return self.reply(200, dict(service='origin-extract', version=1))
                parts = parsed.path.strip('/').split('/')
                if len(parts) not in (2, 3) or parts[0] != 'jobs':
                    return self.reply(404, {'error': 'Unknown address.'})
                with owner.lock:
                    job = owner.jobs.get(parts[1])
                    if job is None:
                        return self.reply(404, {'error': 'Conversion not found.'})
                    if len(parts) == 3 and parts[2] == 'pack':
                        if job.state != 'termine':
                            return self.reply(409, {'error': 'Conversion is still in progress.'})
                        return self.reply(200, job.result, binary=True)
                    if len(parts) == 2:
                        return self.reply(200, dict(id=job.id, state=job.state,
                                                    messages=list(job.messages), error=job.error))
                self.reply(404, {'error': 'Unknown address.'})

            def do_POST(self):
                if not self.require_key():
                    return
                parsed = urlparse(self.path)
                if parsed.path.endswith('/cancel'):
                    parts = parsed.path.strip('/').split('/')
                    if len(parts) != 3 or parts[0] != 'jobs':
                        return self.reply(404, {'error': 'Unknown address.'})
                    with owner.lock:
                        job = owner.jobs.get(parts[1])
                        if job is None:
                            return self.reply(404, {'error': 'Conversion not found.'})
                        job.stop.set()
                    return self.reply(200, {'state': 'arret_demande'})
                if parsed.path != '/convert':
                    return self.reply(404, {'error': 'Unknown address.'})
                try:
                    length = int(self.headers.get('Content-Length', '0'))
                except ValueError:
                    length = 0
                if not 1 <= length <= MAX_UPLOAD:
                    return self.reply(413, {'error': 'Choose a project smaller than 512 MB.'})
                self.connection.settimeout(60)
                body = self.rfile.read(length)
                if len(body) != length or not body.startswith((b'CPYUA', b'CPYA')):
                    return self.reply(400, {'error': 'The file does not look like an Origin project.'})
                name = parse_qs(parsed.query).get('name', ['projet.opju'])[0]
                name = safe_name(name)
                if Path(name).suffix.lower() not in ('.opj', '.opju'):
                    return self.reply(400, {'error': 'Expected an OPJ or OPJU extension.'})
                with owner.lock:
                    if sum(j.state in ('en_attente', 'conversion') for j in owner.jobs.values()) >= 4:
                        return self.reply(429, {'error': 'The PC already has several conversions queued.'})
                    # Retirer les anciens résultats en mémoire, sans toucher aux fichiers utilisateur.
                    if len(owner.jobs) >= 20:
                        for key, old in list(owner.jobs.items()):
                            if old.state not in ('en_attente', 'conversion'):
                                del owner.jobs[key]
                                if len(owner.jobs) < 20:
                                    break
                    job = Job(secrets.token_hex(16))
                    owner.jobs[job.id] = job
                threading.Thread(target=owner.work, args=(job, name, body), daemon=True).start()
                self.reply(202, {'id': job.id})

        self.server = ThreadingHTTPServer((host, port), Handler)
        self.thread = None

    @property
    def port(self):
        return self.server.server_address[1]

    def start(self):
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def close(self):
        with self.lock:
            for job in self.jobs.values():
                job.stop.set()
        self.server.shutdown()
        self.server.server_close()
        if self.thread:
            self.thread.join(timeout=3)

    def work(self, job, name, body):
        def log(message):
            with self.lock:
                job.messages.append(str(message))
                job.messages = job.messages[-300:]
        try:
            with self.conversion_lock:
                check_cancel(job.stop)
                with self.lock:
                    job.state = 'conversion'
                with tempfile.TemporaryDirectory(prefix='OriginExtract-') as folder:
                    path = Path(folder) / name
                    path.write_bytes(body)
                    project = self.converter(path, self.viewer, Path(folder) / 'exports', job.stop, log)
                    result = pack_bytes(project, job.stop)
                    with self.lock:
                        job.result = result
                        job.state = 'termine'
        except Exception as exc:
            log(traceback.format_exc())
            with self.lock:
                job.error = str(exc)
                job.state = 'arrete' if isinstance(exc, Cancelled) or job.stop.is_set() else 'erreur'


def local_addresses(port):
    addresses = []
    try:
        for item in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            address = item[4][0]
            if not address.startswith('127.') and address not in addresses:
                addresses.append(address)
    except OSError:
        pass
    return [f'http://{address}:{port}' for address in addresses] or [f'http://127.0.0.1:{port}']


def request(base, token, path, data=None, timeout=30, binary=False):
    url = base.rstrip('/') + path
    parsed = urlparse(url)
    if parsed.scheme not in ('http', 'https') or not parsed.hostname:
        raise ValueError('Enter an http:// or https:// address for the Windows PC.')
    req = Request(url, data=data, headers={'Authorization': 'Bearer ' + token,
                                         'Content-Type': 'application/octet-stream'})
    try:
        with urlopen(req, timeout=timeout) as response:
            body = response.read(MAX_UPLOAD + 1)
            if len(body) > MAX_UPLOAD:
                raise ValueError('The relay response exceeds 512 MB.')
            return body if binary else json.loads(body.decode('utf-8'))
    except HTTPError as exc:
        try:
            message = json.loads(exc.read().decode('utf-8')).get('error')
        except Exception:
            message = None
        raise RuntimeError(message or f'The relay returned HTTP error {exc.code}.') from exc
    except URLError as exc:
        raise RuntimeError("Cannot reach the Windows PC. Check the address, network, and that the relay is running.") from exc


def convert_remote(project, base, token, stop=None, log=lambda message: None):
    check_cancel(stop)
    path = Path(project)
    if path.stat().st_size > MAX_UPLOAD:
        raise ValueError('The project exceeds 512 MB.')
    health = request(base, token, '/health')
    if health.get('service') != 'origin-extract':
        raise RuntimeError("The address does not point to an Origin Extract relay.")
    log('Sending project to Windows PC…')
    job = request(base, token, '/convert?name=' + quote(path.name), path.read_bytes(), timeout=90)
    job_path = '/jobs/' + job['id']
    seen = 0
    try:
        while True:
            check_cancel(stop)
            state = request(base, token, job_path)
            messages = state.get('messages', [])
            for message in messages[seen:]:
                log(message)
            seen = len(messages)
            if state['state'] == 'termine':
                log('Receiving portable project…')
                return load_pack(request(base, token, job_path + '/pack', binary=True, timeout=90), stop)
            if state['state'] in ('erreur', 'arrete'):
                raise RuntimeError(state.get('error') or 'Conversion interrupted on the Windows PC.')
            if stop is not None:
                stop.wait(0.75)
            else:
                time.sleep(0.75)
    except Cancelled:
        try:
            request(base, token, job_path + '/cancel', b'', timeout=5)
        except Exception:
            pass
        raise
