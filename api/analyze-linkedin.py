import sys, os, json
sys.path.insert(0, os.path.dirname(__file__))
from _lib import build_persona_response, _fetch_url
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler

def _brightdata_li(linkedin_url):
    import urllib.request
    token = os.environ.get("BRIGHTDATA_API_TOKEN","")
    if not token: return {"name":"","description":"","headcount":"Unknown","growth":"Unknown","industries":[],"colleges":[],"skills":[],"source":"none"}
    try:
        req_body = json.dumps([{"url": linkedin_url, "type": "company"}]).encode()
        req = urllib.request.Request(
            "https://api.brightdata.com/datasets/v3/trigger?dataset_id=gd_l1viktl72bvl7bjuj0&format=json",
            data=req_body, headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"}, method="POST"
        )
        with urllib.request.urlopen(req, timeout=20) as r:
            snap = json.loads(r.read()).get("snapshot_id")
        if snap:
            import time
            for _ in range(6):
                time.sleep(3)
                req2 = urllib.request.Request(f"https://api.brightdata.com/datasets/v3/snapshot/{snap}", headers={"Authorization": f"Bearer {token}"})
                with urllib.request.urlopen(req2, timeout=10) as r2:
                    data = json.loads(r2.read())
                    if isinstance(data, list) and data:
                        item = data[0]
                        return {
                            "name": item.get("name",""), "description": item.get("about",""),
                            "headcount": str(item.get("employee_count","Unknown")), "growth": str(item.get("employee_count_growth","Unknown")),
                            "industries": [{"name": i.get("name",i) if isinstance(i,dict) else str(i), "pct": i.get("pct",0) if isinstance(i,dict) else 0} for i in (item.get("employees_by_function") or item.get("industries",[]))[:8]],
                            "colleges":   [{"name": c.get("name",c) if isinstance(c,dict) else str(c), "pct": c.get("pct",0) if isinstance(c,dict) else 0} for c in (item.get("school_employees") or item.get("top_schools",[]))[:8]],
                            "skills":     [s.get("name",s) if isinstance(s,dict) else str(s) for s in (item.get("specialties") or item.get("top_skills",[]))[:12]],
                            "source": "bright_data",
                        }
    except Exception as e:
        pass
    return {"name":"","description":"","headcount":"Unknown","growth":"Unknown","industries":[],"colleges":[],"skills":[],"source":"none"}

class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(204); self._cors(); self.end_headers()

    def do_POST(self):
        try:
            length = int(self.headers.get('Content-Length', 0))
            body   = json.loads(self.rfile.read(length) or b'{}')
            li_url = body.get("linkedin_url","").strip()
            ca_url = body.get("careers_url","").strip()
            if not li_url:
                self._json({"error": "Provide 'linkedin_url'"}, 400); return
            with ThreadPoolExecutor(max_workers=2) as pool:
                lf = pool.submit(_brightdata_li, li_url)
                cf = pool.submit(_fetch_url, ca_url) if ca_url else None
                li_signals   = lf.result()
                careers_text = cf.result() if cf else ""
            li_text = " ".join([
                " ".join(i.get("name","") for i in li_signals.get("industries",[])),
                " ".join(li_signals.get("skills",[])),
                li_signals.get("description",""),
            ])
            combined = f"{li_text} {careers_text}"[:8000]
            if not combined.strip():
                self._json({"error": "Could not extract signals"}, 502); return
            result = build_persona_response(combined, "linkedin", li_signals=li_signals)
            if li_signals.get("name"): result["company_name"] = li_signals["name"]
            self._json(result)
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
