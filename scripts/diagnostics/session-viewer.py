#!/usr/bin/env python3
"""
Minimal Claude Code Session Viewer.

Replaces @kimuson/claude-code-viewer with a simple Flask app.
Browse, search, and view session transcripts.

Usage:
    session-viewer.py [--port PORT]
    session-viewer.py --daemon start|stop|status
"""
import argparse
import json
import os
import signal
import sys
from datetime import datetime
from pathlib import Path

try:
    from flask import Flask, render_template_string, request, jsonify
except ImportError:
    print("Flask not installed. Run: pip install flask")
    sys.exit(1)

PROJECTS_DIR = Path.home() / ".claude/projects"
PID_FILE = Path.home() / ".claude/data/session-viewer.pid"
DEFAULT_PORT = 5111

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Claude Sessions</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        :root { --bg: #1a1a2e; --fg: #eee; --accent: #7c3aed; --border: #333; --card: #16213e; }
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { font-family: system-ui, sans-serif; background: var(--bg); color: var(--fg); line-height: 1.6; }
        .container { max-width: 1200px; margin: 0 auto; padding: 1rem; }
        header { display: flex; justify-content: space-between; align-items: center; padding: 1rem 0; border-bottom: 1px solid var(--border); margin-bottom: 1rem; }
        h1 { font-size: 1.5rem; color: var(--accent); }
        input[type="search"] { padding: 0.5rem 1rem; border: 1px solid var(--border); border-radius: 4px; background: var(--card); color: var(--fg); width: 300px; }
        .sessions { display: grid; gap: 1rem; }
        .session { background: var(--card); border: 1px solid var(--border); border-radius: 8px; padding: 1rem; cursor: pointer; transition: border-color 0.2s; }
        .session:hover { border-color: var(--accent); }
        .session-header { display: flex; justify-content: space-between; margin-bottom: 0.5rem; }
        .session-id { font-family: monospace; color: var(--accent); }
        .session-date { color: #888; font-size: 0.9rem; }
        .session-preview { color: #aaa; font-size: 0.9rem; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
        .session-stats { display: flex; gap: 1rem; margin-top: 0.5rem; font-size: 0.8rem; color: #666; }
        .modal { display: none; position: fixed; inset: 0; background: rgba(0,0,0,0.8); z-index: 100; overflow-y: auto; }
        .modal.active { display: block; }
        .modal-content { background: var(--card); max-width: 900px; margin: 2rem auto; border-radius: 8px; }
        .modal-header { display: flex; justify-content: space-between; padding: 1rem; border-bottom: 1px solid var(--border); position: sticky; top: 0; background: var(--card); }
        .modal-body { padding: 1rem; max-height: 80vh; overflow-y: auto; }
        .close { background: none; border: none; color: var(--fg); font-size: 1.5rem; cursor: pointer; }
        .message { margin-bottom: 1rem; padding: 0.75rem; border-radius: 4px; }
        .message.user { background: #1e3a5f; border-left: 3px solid #3b82f6; }
        .message.assistant { background: #1e3e1e; border-left: 3px solid #22c55e; }
        .message.tool { background: #3e3e1e; border-left: 3px solid #eab308; font-family: monospace; font-size: 0.85rem; }
        .message-role { font-weight: bold; margin-bottom: 0.25rem; text-transform: capitalize; }
        .message-content { white-space: pre-wrap; word-break: break-word; }
        .tool-name { color: #eab308; }
        .empty { text-align: center; padding: 3rem; color: #666; }
        .loading { text-align: center; padding: 2rem; }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>Claude Sessions</h1>
            <input type="search" id="search" placeholder="Search sessions..." oninput="filterSessions()">
        </header>
        <div id="sessions" class="sessions">
            <div class="loading">Loading sessions...</div>
        </div>
    </div>

    <div id="modal" class="modal" onclick="if(event.target===this)closeModal()">
        <div class="modal-content">
            <div class="modal-header">
                <span id="modal-title"></span>
                <button class="close" onclick="closeModal()">&times;</button>
            </div>
            <div class="modal-body" id="modal-body"></div>
        </div>
    </div>

    <script>
        let allSessions = [];

        async function loadSessions() {
            const res = await fetch('/api/sessions');
            allSessions = await res.json();
            renderSessions(allSessions);
        }

        function renderSessions(sessions) {
            const container = document.getElementById('sessions');
            if (!sessions.length) {
                container.innerHTML = '<div class="empty">No sessions found</div>';
                return;
            }
            container.innerHTML = sessions.map(s => `
                <div class="session" onclick="openSession('${s.id}')">
                    <div class="session-header">
                        <span class="session-id">${s.id.substring(0, 12)}...</span>
                        <span class="session-date">${s.date}</span>
                    </div>
                    <div class="session-preview">${escapeHtml(s.preview || 'No preview')}</div>
                    <div class="session-stats">
                        <span>${s.messages} messages</span>
                        <span>${s.project}</span>
                    </div>
                </div>
            `).join('');
        }

        function filterSessions() {
            const q = document.getElementById('search').value.toLowerCase();
            const filtered = allSessions.filter(s =>
                s.id.toLowerCase().includes(q) ||
                (s.preview || '').toLowerCase().includes(q) ||
                s.project.toLowerCase().includes(q)
            );
            renderSessions(filtered);
        }

        async function openSession(id) {
            document.getElementById('modal-title').textContent = id;
            document.getElementById('modal-body').innerHTML = '<div class="loading">Loading...</div>';
            document.getElementById('modal').classList.add('active');

            const res = await fetch(`/api/session/${id}`);
            const messages = await res.json();

            document.getElementById('modal-body').innerHTML = messages.map(m => `
                <div class="message ${m.role}">
                    <div class="message-role">${m.role}${m.tool ? ` <span class="tool-name">(${m.tool})</span>` : ''}</div>
                    <div class="message-content">${escapeHtml(m.content)}</div>
                </div>
            `).join('');
        }

        function closeModal() {
            document.getElementById('modal').classList.remove('active');
        }

        function escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }

        document.addEventListener('keydown', e => { if (e.key === 'Escape') closeModal(); });
        loadSessions();
    </script>
</body>
</html>
"""


def get_sessions():
    """Get all session files with metadata."""
    sessions = []

    for jsonl_file in PROJECTS_DIR.rglob("*.jsonl"):
        try:
            stat = jsonl_file.stat()
            session_id = jsonl_file.stem
            project = jsonl_file.parent.name

            # Get first user message as preview
            preview = ""
            message_count = 0
            with open(jsonl_file, 'r') as f:
                for line in f:
                    try:
                        data = json.loads(line)
                        if data.get('type') == 'user' or (isinstance(data.get('message'), dict) and data['message'].get('role') == 'user'):
                            message_count += 1
                            if not preview:
                                content = data.get('message', {}).get('content', '') if isinstance(data.get('message'), dict) else data.get('content', '')
                                if isinstance(content, list):
                                    content = ' '.join(c.get('text', '') for c in content if isinstance(c, dict))
                                preview = str(content)[:100]
                        elif data.get('type') == 'assistant' or (isinstance(data.get('message'), dict) and data['message'].get('role') == 'assistant'):
                            message_count += 1
                    except json.JSONDecodeError:
                        continue

            sessions.append({
                'id': session_id,
                'project': project,
                'path': str(jsonl_file),
                'date': datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M'),
                'preview': preview,
                'messages': message_count,
            })
        except (OSError, IOError):
            continue

    return sorted(sessions, key=lambda s: s['date'], reverse=True)


def get_session_messages(session_id: str):
    """Get messages from a specific session."""
    messages = []

    for jsonl_file in PROJECTS_DIR.rglob(f"{session_id}.jsonl"):
        with open(jsonl_file, 'r') as f:
            for line in f:
                try:
                    data = json.loads(line)

                    # Handle different message formats
                    if 'message' in data and isinstance(data['message'], dict):
                        msg = data['message']
                        role = msg.get('role', 'unknown')
                        content = msg.get('content', '')
                        if isinstance(content, list):
                            content = '\n'.join(
                                c.get('text', '') if isinstance(c, dict) else str(c)
                                for c in content
                            )
                        messages.append({'role': role, 'content': str(content)[:2000], 'tool': None})

                    elif data.get('type') == 'tool_result':
                        tool = data.get('tool_name', 'tool')
                        result = data.get('result', '')
                        if isinstance(result, dict):
                            result = json.dumps(result, indent=2)
                        messages.append({'role': 'tool', 'content': str(result)[:1000], 'tool': tool})

                except json.JSONDecodeError:
                    continue
        break

    return messages


@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)


@app.route('/api/sessions')
def api_sessions():
    return jsonify(get_sessions())


@app.route('/api/session/<session_id>')
def api_session(session_id):
    return jsonify(get_session_messages(session_id))


def daemon_start(port: int):
    """Start viewer as daemon."""
    if PID_FILE.exists():
        pid = int(PID_FILE.read_text().strip())
        try:
            os.kill(pid, 0)
            print(f"Viewer already running (PID {pid})")
            return
        except OSError:
            PID_FILE.unlink()

    # Fork to background
    pid = os.fork()
    if pid > 0:
        print(f"Viewer started on http://localhost:{port} (PID {pid})")
        return

    # Child process
    os.setsid()
    PID_FILE.parent.mkdir(parents=True, exist_ok=True)
    PID_FILE.write_text(str(os.getpid()))

    # Redirect stdout/stderr
    sys.stdout = open('/dev/null', 'w')
    sys.stderr = open('/dev/null', 'w')

    app.run(host='127.0.0.1', port=port, debug=False, use_reloader=False)


def daemon_stop():
    """Stop viewer daemon."""
    if not PID_FILE.exists():
        print("Viewer not running")
        return

    pid = int(PID_FILE.read_text().strip())
    try:
        os.kill(pid, signal.SIGTERM)
        PID_FILE.unlink()
        print(f"Viewer stopped (PID {pid})")
    except OSError:
        PID_FILE.unlink()
        print("Viewer was not running")


def daemon_status():
    """Check daemon status."""
    if not PID_FILE.exists():
        print("Viewer not running")
        return

    pid = int(PID_FILE.read_text().strip())
    try:
        os.kill(pid, 0)
        print(f"Viewer running (PID {pid})")
    except OSError:
        PID_FILE.unlink()
        print("Viewer not running (stale PID file removed)")


def main():
    parser = argparse.ArgumentParser(description='Claude Session Viewer')
    parser.add_argument('--port', type=int, default=DEFAULT_PORT, help='Port to run on')
    parser.add_argument('--daemon', choices=['start', 'stop', 'status'], help='Daemon control')
    args = parser.parse_args()

    if args.daemon == 'start':
        daemon_start(args.port)
    elif args.daemon == 'stop':
        daemon_stop()
    elif args.daemon == 'status':
        daemon_status()
    else:
        print(f"Starting viewer on http://localhost:{args.port}")
        app.run(host='127.0.0.1', port=args.port, debug=False)


if __name__ == '__main__':
    main()
