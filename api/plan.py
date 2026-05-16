"""
POST /api/plan — corps JSON : { "domain", "angle", "audience?", "seconds?" }
GET /api/plan — aide rapide + statut
"""

from __future__ import annotations

import json
import os
import sys
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from video_agent.planner import build_brief  # noqa: E402


def _send_json(handler: BaseHTTPRequestHandler, status: int, payload: dict) -> None:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def _read_json_body(handler: BaseHTTPRequestHandler) -> dict:
    try:
        length = int(handler.headers.get("Content-Length", 0))
    except ValueError:
        length = 0
    raw = handler.rfile.read(length).decode("utf-8") if length else ""
    if not raw.strip():
        raise ValueError("Corps vide")
    return json.loads(raw)


class handler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args) -> None:  # noqa: A003
        return

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(204)
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        if path not in ("/", "/api/plan"):
            self.send_error(404)
            return

        qs = parse_qs(parsed.query)
        domain = (qs.get("domain") or [""])[0].strip()
        angle = (qs.get("angle") or [""])[0].strip()
        if domain and angle:
            try:
                seconds = float((qs.get("seconds") or ["600"])[0])
            except ValueError:
                _send_json(self, 400, {"error": "seconds invalide"})
                return
            audience = (qs.get("audience") or ["curieux du sujet, niveau intermédiaire"])[0]
            brief = build_brief(domain, angle, audience=audience, total_seconds=seconds)
            _send_json(self, 200, brief.to_dict())
            return

        _send_json(
            self,
            200,
            {
                "ok": True,
                "message": "Brief vidéo ~10 min. POST JSON ou GET ?domain=&angle=",
                "post_example": {
                    "domain": "astrophysique",
                    "angle": "pour débutants absolus",
                    "audience": "lycéens curieux",
                    "seconds": 600,
                },
            },
        )

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path.rstrip("/") or "/"
        if path not in ("/", "/api/plan"):
            self.send_error(404)
            return

        ctype = self.headers.get("Content-Type", "").split(";")[0].strip().lower()
        if ctype and ctype != "application/json":
            _send_json(self, 415, {"error": "Content-Type application/json requis"})
            return

        try:
            data = _read_json_body(self)
        except json.JSONDecodeError:
            _send_json(self, 400, {"error": "JSON invalide"})
            return
        except ValueError as e:
            _send_json(self, 400, {"error": str(e)})
            return

        if not isinstance(data, dict):
            _send_json(self, 400, {"error": "Le corps doit être un objet JSON"})
            return

        domain = str(data.get("domain", "")).strip()
        angle = str(data.get("angle", "")).strip()
        if not domain or not angle:
            _send_json(self, 400, {"error": "Champs requis : domain, angle (chaînes non vides)"})
            return

        audience = str(data.get("audience") or "curieux du sujet, niveau intermédiaire")
        try:
            seconds = float(data.get("seconds", 600))
        except (TypeError, ValueError):
            _send_json(self, 400, {"error": "seconds doit être un nombre"})
            return
        if seconds < 60 or seconds > 3600:
            _send_json(self, 400, {"error": "seconds doit être entre 60 et 3600"})
            return

        brief = build_brief(domain, angle, audience=audience, total_seconds=seconds)
        _send_json(self, 200, brief.to_dict())
