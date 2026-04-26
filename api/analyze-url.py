import sys, os, json, re
sys.path.insert(0, os.path.dirname(__file__))
from _lib import build_persona_response, cluster_jobs, _fetch_url
from concurrent.futures import ThreadPoolExecutor, as_completed
from http.server import BaseHTTPRequestHandler

class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(204); self._cors(); self.end_headers()

    def do_POST(self):
        try:
            length = int(self.headers.get('Content-Length', 0))
            body   = json.loads(self.rfile.read(length) or b'{}')
            url    = body.get("url", "").strip()
            if not url:
                self._json({"error": "Provide 'url'"}, 400); return
            raw = _fetch_url(url)
            if not raw:
                self._json({"error": f"Could not scrape {url}"}, 502); return
            blocks = re.split(r"\n{2,}", raw)
            jobs = [{"title": b[:80], "description": b} for b in blocks
                    if 20 < len(b) < 2000 and any(kw in b.lower()
                    for kw in ["engineer","manager","analyst","specialist","nurse","driver","associate","developer"])][:30]
            if not jobs:
                result = build_persona_response(raw[:8000], "careers_page")
                self._json(result); return
            clusters  = cluster_jobs(jobs)
            personas_out = []
            with ThreadPoolExecutor(max_workers=4) as pool:
                futs = {pool.submit(build_persona_response, c["combined_text"], "careers_page"): c for c in clusters[:6]}
                for f in as_completed(futs):
                    try:
                        r = f.result()
                        if r.get("personas"): personas_out.extend(r["personas"])
                    except Exception: pass
            if not personas_out:
                self._json({"error": "Could not extract persona clusters"}, 422); return
            base = build_persona_response(raw[:4000], "careers_page")
            base["personas"] = personas_out; base["source"] = "careers_page"
            self._json(base)
        except Exception as e:
            self._json({"error": str(e)}, 500)

    def _cors(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')

    def _json(self, data, status=200):
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self._cors(); self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def log_message(self, *a): pass
