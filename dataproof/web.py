"""Local web interface; launch with python -m dataproof.web."""
import cgi
import html
import json
import os
import tempfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .core import AnalysisError, Config, load_table, run

PAGE = """<!doctype html><html lang='en'><meta charset='utf-8'><meta name='viewport' content='width=device-width, initial-scale=1'>
<title>DataProof</title><style>body{font:16px system-ui;max-width:850px;margin:50px auto;padding:0 18px;color:#172334;background:#f7f9fc}main{background:white;padding:30px;border-radius:16px;box-shadow:0 8px 30px #15243a14}h1{margin-top:0}label{display:block;margin:18px 0 7px;font-weight:650}input,textarea,select,button{font:inherit;padding:10px;border:1px solid #b6c5d4;border-radius:8px}textarea{width:95%;min-height:85px}button{background:#19476d;color:white;cursor:pointer;margin-top:18px}pre{white-space:pre-wrap;background:#edf3f7;padding:14px;border-radius:8px;overflow:auto}.note{color:#526579}</style>
<main><h1>DataProof</h1><p class='note'>Upload a CSV or XLSX file and ask one tabular question. Data stays on this machine; the schema and question are sent to Groq when Groq mode is selected.</p>
<form method='post' enctype='multipart/form-data'><label>Dataset</label><input type='file' name='file' accept='.csv,.xlsx' required>
<label>Question</label><textarea name='question' required placeholder='What is the average revenue?'></textarea>
<label>Planner</label><select name='provider'><option value='groq'>Groq API</option><option value='heuristic'>Offline limited baseline</option></select><br><button>Analyze</button></form>{result}</main></html>"""


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.respond(PAGE.replace("{result}", ""))

    def do_POST(self):
        if int(self.headers.get("Content-Length", "0")) > 20_000_000:
            return self.respond(PAGE.replace("{result}", "<p>File exceeds 20 MB.</p>"), 413)
        form = cgi.FieldStorage(fp=self.rfile, headers=self.headers, environ={"REQUEST_METHOD": "POST",
                                "CONTENT_TYPE": self.headers.get("Content-Type", "")})
        item = form["file"] if "file" in form else None
        if item is None or not getattr(item, "filename", ""):
            return self.respond(PAGE.replace("{result}", "<p>Select a file.</p>"), 400)
        suffix = Path(item.filename).suffix.lower()
        if suffix not in {".csv", ".xlsx"}:
            return self.respond(PAGE.replace("{result}", "<p>CSV or XLSX only.</p>"), 400)
        temp = None
        try:
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as stream:
                temp = Path(stream.name)
                stream.write(item.file.read(20_000_001))
            frame = load_table(temp)
            result = run(form.getfirst("question", ""), frame,
                         Config(provider=form.getfirst("provider", "groq")))
            Path("logs").mkdir(exist_ok=True)
            import uuid
            trace_id = uuid.uuid4().hex
            Path("logs", trace_id + ".json").write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
            rendered = "<h2>Result</h2><pre>" + html.escape(json.dumps({"trace_id": trace_id, **result}, indent=2, default=str)) + "</pre>"
            self.respond(PAGE.replace("{result}", rendered))
        except (AnalysisError, ValueError, OSError) as exc:
            self.respond(PAGE.replace("{result}", "<p>" + html.escape(str(exc)) + "</p>"), 400)
        finally:
            if temp is not None:
                temp.unlink(missing_ok=True)

    def respond(self, body, status=200):
        data = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


if __name__ == "__main__":
    host = os.getenv("DATAPROOF_HOST", "127.0.0.1")
    port = int(os.getenv("DATAPROOF_PORT", "8000"))
    print(f"DataProof at http://{host}:{port}")
    ThreadingHTTPServer((host, port), Handler).serve_forever()
