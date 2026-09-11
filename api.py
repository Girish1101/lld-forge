import json
import os
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Dict, Any
from models import SubmissionPayload
from service import PracticePlatformService

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")

MIME_TYPES = {
    ".html": "text/html",
    ".css": "text/css",
    ".js": "application/javascript",
    ".json": "application/json",
    ".svg": "image/svg+xml",
    ".ico": "image/x-icon",
}


class LLDPracticeHTTPHandler(BaseHTTPRequestHandler):
    """Lightweight HTTP REST API Controller using standard library http.server."""
    service: PracticePlatformService = None  # Injected before server startup

    def log_message(self, format, *args):
        # Suppress default noisy request logs
        pass

    def _send_json(self, status_code: int, payload: Any):
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(json.dumps(payload, default=str).encode("utf-8"))

    def _send_file(self, filepath: str):
        ext = os.path.splitext(filepath)[1]
        mime = MIME_TYPES.get(ext, "application/octet-stream")
        try:
            with open(filepath, "rb") as f:
                content = f.read()
            self.send_response(200)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
        except FileNotFoundError:
            self._send_json(404, {"error": "Static file not found."})

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        path = self.path.split("?")[0]

        # Serve frontend SPA
        if path == "/" or path == "/index.html":
            self._send_file(os.path.join(STATIC_DIR, "index.html"))
            return

        if path.startswith("/static/"):
            relative = path[len("/static/"):]
            self._send_file(os.path.join(STATIC_DIR, relative))
            return

        if path == "/api/problems":
            problems = self.service.list_problems()
            data = [
                {
                    "id": p.id,
                    "title": p.title,
                    "description": p.description,
                    "required_interfaces": p.required_interfaces,
                    "starter_code": p.starter_code,
                    "rubric": [
                        {"name": r.name, "weight": r.weight, "description": r.description}
                        for r in p.rubric
                    ]
                }
                for p in problems
            ]
            self._send_json(200, {"problems": data})
            return

        if path.startswith("/api/problems/") and path.endswith("/history"):
            problem_id = path.split("/")[3]
            attempts = self.service.get_problem_history(problem_id)
            history = [
                {
                    "attempt_id": a.id,
                    "version": a.version,
                    "learner_id": a.learner_id,
                    "status": a.status.value,
                    "score": a.feedback.overall_score if a.feedback else None,
                    "created_at": a.created_at.isoformat()
                }
                for a in attempts
            ]
            self._send_json(200, {"problem_id": problem_id, "history": history})
            return

        if path.startswith("/api/problems/"):
            problem_id = path.split("/")[3]
            problem = self.service.get_problem(problem_id)
            if not problem:
                self._send_json(404, {"error": f"Problem '{problem_id}' not found."})
                return
            self._send_json(200, {
                "id": problem.id,
                "title": problem.title,
                "description": problem.description,
                "required_interfaces": problem.required_interfaces,
                "starter_code": problem.starter_code,
                "rubric": [
                    {"name": r.name, "weight": r.weight, "description": r.description}
                    for r in problem.rubric
                ]
            })
            return

        # GET /api/history?learner_id=<id>&problem_id=<pid> — learner-scoped history
        if path == "/api/history":
            query = self.path.split("?", 1)[1] if "?" in self.path else ""
            params: Dict[str, str] = {}
            for pair in query.split("&"):
                if "=" in pair:
                    k, v = pair.split("=", 1)
                    params[k] = v
            learner_id = params.get("learner_id", "anonymous")
            problem_id = params.get("problem_id", "")
            if not problem_id:
                self._send_json(400, {"error": "Missing 'problem_id' query parameter."})
                return
            attempts = self.service.get_learner_history(learner_id, problem_id)
            history = [
                {
                    "attempt_id": a.id,
                    "version": a.version,
                    "status": a.status.value,
                    "score": a.feedback.overall_score if a.feedback else None,
                    "deterministic_passed": a.feedback.deterministic_passed if a.feedback else None,
                    "critiques": [
                        {
                            "rule_name": c.rule_name,
                            "passed": c.passed,
                            "score": c.score,
                            "summary": c.summary,
                            "suggestions": c.suggestions
                        }
                        for c in (a.feedback.critiques if a.feedback else [])
                    ],
                    "created_at": a.created_at.isoformat()
                }
                for a in attempts
            ]
            self._send_json(200, {"learner_id": learner_id, "problem_id": problem_id, "history": history})
            return

        if path.startswith("/api/attempts/"):
            attempt_id = path.split("/")[3]
            attempt = self.service.get_attempt(attempt_id)
            if not attempt:
                self._send_json(404, {"error": f"Attempt '{attempt_id}' not found."})
                return
            self._send_json(200, {
                "id": attempt.id,
                "problem_id": attempt.problem_id,
                "learner_id": attempt.learner_id,
                "version": attempt.version,
                "status": attempt.status.value,
                "feedback": {
                    "score": attempt.feedback.overall_score,
                    "deterministic_passed": attempt.feedback.deterministic_passed,
                    "critiques": [
                        {
                            "rule": c.rule_name,
                            "passed": c.passed,
                            "score": c.score,
                            "summary": c.summary,
                            "suggestions": c.suggestions
                        } for c in attempt.feedback.critiques
                    ]
                } if attempt.feedback else None
            })
            return

        self._send_json(404, {"error": "Endpoint not found."})

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body_bytes = self.rfile.read(content_length) if content_length > 0 else b"{}"
        try:
            body = json.loads(body_bytes.decode("utf-8"))
        except Exception:
            body = {}

        path = self.path.split("?")[0]

        if path == "/api/attempts":
            problem_id = body.get("problem_id")
            learner_id = body.get("learner_id", "anonymous")
            if not problem_id:
                self._send_json(400, {"error": "Missing 'problem_id' in body."})
                return
            try:
                attempt = self.service.start_new_attempt(problem_id, learner_id=learner_id)
                self._send_json(201, {
                    "attempt_id": attempt.id,
                    "problem_id": attempt.problem_id,
                    "learner_id": attempt.learner_id,
                    "version": attempt.version,
                    "status": attempt.status.value
                })
            except ValueError as e:
                self._send_json(400, {"error": str(e)})
            return

        if path.startswith("/api/attempts/") and path.endswith("/submit"):
            attempt_id = path.split("/")[3]
            payload = SubmissionPayload(
                source_code=body.get("source_code", ""),
                language=body.get("language", "python"),
                pattern_rationale=body.get("pattern_rationale", ""),
                tradeoffs_rationale=body.get("tradeoffs_rationale", "")
            )
            try:
                attempt = self.service.submit_and_evaluate(attempt_id, payload)
                self._send_json(200, {
                    "attempt_id": attempt.id,
                    "status": attempt.status.value,
                    "overall_score": attempt.feedback.overall_score if attempt.feedback else 0.0,
                    "deterministic_passed": attempt.feedback.deterministic_passed if attempt.feedback else False,
                    "critiques": [
                        {
                            "rule_name": c.rule_name,
                            "passed": c.passed,
                            "score": c.score,
                            "summary": c.summary,
                            "suggestions": c.suggestions
                        } for c in (attempt.feedback.critiques if attempt.feedback else [])
                    ]
                })
            except ValueError as e:
                self._send_json(400, {"error": str(e)})
            return

        if path.startswith("/api/attempts/") and path.endswith("/iterate"):
            attempt_id = path.split("/")[3]
            try:
                new_attempt = self.service.iterate_attempt(attempt_id)
                self._send_json(201, {
                    "attempt_id": new_attempt.id,
                    "problem_id": new_attempt.problem_id,
                    "learner_id": new_attempt.learner_id,
                    "version": new_attempt.version,
                    "status": new_attempt.status.value
                })
            except ValueError as e:
                self._send_json(400, {"error": str(e)})
            return

        self._send_json(404, {"error": "Endpoint not found."})


def create_http_server(service: PracticePlatformService, port: int = 8080) -> HTTPServer:
    class InjectedHandler(LLDPracticeHTTPHandler):
        pass
    InjectedHandler.service = service
    return HTTPServer(("0.0.0.0", port), InjectedHandler)
