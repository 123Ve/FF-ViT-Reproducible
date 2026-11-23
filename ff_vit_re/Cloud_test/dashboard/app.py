"""Flask application exposing read-only E06 session evidence."""

from __future__ import annotations
import json

from flask import Flask, jsonify, render_template, request

from Cloud_test.cloud.session_store import SessionStore


def create_app(store: SessionStore, measurements_root=None) -> Flask:
    """Create the offline dashboard bound to an existing session store."""
    if not isinstance(store, SessionStore):
        raise ValueError("store must be a SessionStore")

    app = Flask(__name__)
    app.url_map.merge_slashes = False
    measurement_directory = (store.root.parent / 'stream_measurements'
                             if measurements_root is None else measurements_root)

    @app.errorhandler(404)
    def api_session_path_not_found(error):
        if request.path.startswith("/api/sessions/"):
            return jsonify(error="invalid_session_id"), 400
        return error

    @app.after_request
    def secure_local_response(response):
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; connect-src 'self'; object-src 'none'; "
            "base-uri 'none'; frame-ancestors 'none'"
        )
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.get("/api/sessions")
    def sessions():
        return jsonify(sessions=store.list_sessions())

    @app.get("/api/sessions/<path:session_id>")
    def session_detail(session_id: str):
        try:
            snapshot = store.snapshot(session_id)
        except ValueError:
            return jsonify(error="invalid_session_id"), 400
        except KeyError:
            return jsonify(error="session_not_found"), 404
        return jsonify(snapshot)

    @app.get("/api/health")
    def health():
        available = store.list_sessions()
        latest = available[0] if available else None
        return jsonify(
            status="ok",
            collector_state=(latest["connection_state"] if latest else "waiting_for_board"),
            phase=(latest["phase"] if latest else None),
            latest_phase=(latest["phase"] if latest else None),
            session_count=len(available),
        )

    @app.get("/api/measurements/latest")
    def latest_measurements():
        root = measurement_directory
        reports = sorted(root.glob('*/report.json'), reverse=True)
        for path in reports:
            if path.is_symlink() or path.parent.is_symlink():
                continue
            try:
                value = json.loads(path.read_text(encoding='utf-8'))
                result = {key: value[key] for key in ('source', 'status', 'experiments', 'modes',
                          'comparison', 'active_stage', 'limits', 'failure', 'live', 'live_history',
                          'identity', 'session_id', 'board_benchmark') if key in value}
                result['measurement_id'] = path.parent.name
                return jsonify(result)
            except (OSError, ValueError, TypeError):
                continue
        return jsonify(status='NOT_RUN', experiments=[])

    return app
