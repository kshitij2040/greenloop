"""Vercel entry point; the local server uses the same HTTP adapter."""
import json
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlsplit
from greenloop import APIError, Database, LOG, Service


class handler(BaseHTTPRequestHandler):
    secure = True

    def database(self):
        return Database(remote=True)

    def run_api(self):
        path = urlsplit(self.path).path
        payload, cookie = {}, None
        try:
            if self.command == 'POST':
                origin = self.headers.get('Origin')
                expected = ('https://' if self.secure else 'http://') + self.headers.get('Host', '')
                if (origin and origin != expected) or self.headers.get('Sec-Fetch-Site') in ('cross-site','same-site'):
                    raise APIError(403,'Open Greenloop directly to continue.')
                length = int(self.headers.get('Content-Length','0'))
                if not 0 < length <= 16384 or self.headers.get_content_type() != 'application/json':
                    raise APIError(400,'Invalid request.')
                payload = json.loads(self.rfile.read(length))
                if not isinstance(payload,dict):
                    raise APIError(400,'Invalid request.')
            body,cookie = Service(self.database()).handle(self.command,path,payload,self.headers.get('Cookie'),self.secure)
            status = 200
        except APIError as exc:
            status, body = exc.status, {'error':exc.message}
        except (ValueError,UnicodeError):
            status, body = 400, {'error':'Invalid request.'}
        except Exception as exc:
            LOG.error('API failure (%s)',type(exc).__name__)
            status, body = 503, {'error':'Service unavailable. Try again shortly.'}
        encoded = json.dumps(body,allow_nan=False).encode()
        self.send_response(status)
        self.send_header('Content-Type','application/json; charset=utf-8')
        self.send_header('Cache-Control','no-store')
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Content-Length',str(len(encoded)))
        if cookie:
            self.send_header('Set-Cookie',cookie)
        self.end_headers()
        self.wfile.write(encoded)

    do_GET = run_api
    do_POST = run_api
