"""
Nexus Notes — Backend v2.0
Flask + SQLite. Runs locally. Serves the frontend + REST API.
Package to .exe with: pyinstaller nexus.spec

New in v2:
  - Bookmarks system
  - Mindmap storage
  - Painter canvas storage
  - Duck.ai chat integration
  - Settings persistence
"""

import os
import sys
import json
import sqlite3
import hashlib
import threading
import webbrowser
import re
import shutil
import subprocess
import time
import ctypes
import html
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from flask import Flask, g, jsonify, request, send_from_directory, send_file, abort, Response, stream_with_context
from flask_cors import CORS
import requests

# ── PATHS ──
if getattr(sys, 'frozen', False):
    BASE_DIR = Path(sys._MEIPASS)
    DATA_DIR = Path(os.path.expanduser("~")) / "NexusNotes"
else:
    BASE_DIR = Path(__file__).parent.parent
    DATA_DIR = BASE_DIR / "data"

DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "nexus.db"
FRONTEND_DIR = BASE_DIR / "frontend"
WINDOWS_APP_ID = "NexusNotes.App.1"

# ── DUCK.AI ──
DUCKAI_STATUS_URL = 'https://duckduckgo.com/duckchat/v1/status'
DUCKAI_CHAT_URL   = 'https://duckduckgo.com/duckchat/v1/chat'
DUCKAI_WEB_URL    = 'https://duck.ai/'
DUCKAI_MODEL      = 'gpt-4o-mini'  # free tier model
DUCKAI_UA         = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'

if getattr(sys, 'frozen', False):
    log_path = DATA_DIR / "nexus.log"
    sys.stdout = open(log_path, 'a', encoding='utf-8')
    sys.stderr = sys.stdout

app = Flask(__name__, static_folder=str(FRONTEND_DIR / "static"))
CORS(app)

SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS notes (
    id          TEXT PRIMARY KEY,
    title       TEXT NOT NULL DEFAULT 'Untitled',
    content     TEXT NOT NULL DEFAULT '',
    properties  TEXT NOT NULL DEFAULT '{}',
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL,
    is_deleted  INTEGER NOT NULL DEFAULT 0,
    word_count  INTEGER NOT NULL DEFAULT 0,
    folder      TEXT NOT NULL DEFAULT 'Notes'
);
CREATE TABLE IF NOT EXISTS tags (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    note_id TEXT NOT NULL REFERENCES notes(id) ON DELETE CASCADE,
    tag     TEXT NOT NULL,
    UNIQUE(note_id, tag)
);
CREATE TABLE IF NOT EXISTS versions (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    note_id    TEXT NOT NULL REFERENCES notes(id) ON DELETE CASCADE,
    title      TEXT NOT NULL,
    content    TEXT NOT NULL,
    saved_at   TEXT NOT NULL,
    word_count INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS backlinks (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id    TEXT NOT NULL REFERENCES notes(id) ON DELETE CASCADE,
    target_title TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS note_links (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id    TEXT NOT NULL REFERENCES notes(id) ON DELETE CASCADE,
    target_id    TEXT REFERENCES notes(id) ON DELETE CASCADE,
    target_title TEXT NOT NULL DEFAULT '',
    UNIQUE(source_id, target_id, target_title)
);
CREATE TABLE IF NOT EXISTS bookmarks (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    note_id    TEXT NOT NULL REFERENCES notes(id) ON DELETE CASCADE,
    label      TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    UNIQUE(note_id)
);
CREATE TABLE IF NOT EXISTS mindmaps (
    id         TEXT PRIMARY KEY,
    title      TEXT NOT NULL DEFAULT 'Untitled Map',
    data       TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS painter_saves (
    id         TEXT PRIMARY KEY,
    title      TEXT NOT NULL DEFAULT 'Untitled Drawing',
    image_data TEXT NOT NULL DEFAULT '',
    vector_data TEXT NOT NULL DEFAULT '{}',
    metadata   TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS folders (
    name       TEXT PRIMARY KEY,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE VIRTUAL TABLE IF NOT EXISTS notes_fts USING fts5(
    id UNINDEXED, title, content,
    content='notes', content_rowid='rowid'
);
CREATE TRIGGER IF NOT EXISTS notes_ai AFTER INSERT ON notes BEGIN
    INSERT INTO notes_fts(rowid,id,title,content) VALUES (new.rowid,new.id,new.title,new.content);
END;
CREATE TRIGGER IF NOT EXISTS notes_au AFTER UPDATE ON notes BEGIN
    INSERT INTO notes_fts(notes_fts,rowid,id,title,content) VALUES ('delete',old.rowid,old.id,old.title,old.content);
    INSERT INTO notes_fts(rowid,id,title,content) VALUES (new.rowid,new.id,new.title,new.content);
END;
CREATE TRIGGER IF NOT EXISTS notes_ad AFTER DELETE ON notes BEGIN
    INSERT INTO notes_fts(notes_fts,rowid,id,title,content) VALUES ('delete',old.rowid,old.id,old.title,old.content);
END;
"""

SEED_NOTES = [
    {"id":"systems-thinking","title":"Systems Thinking Notes","folder":"Research",
     "content":"## What is Systems Thinking?\n\nSystems thinking is a holistic approach that focuses on how a system's parts interrelate over time.\n\nUnlike reductionist thinking, **systems thinking considers the whole as greater than the sum of its parts.**\n\nSee [[ML Research Log]] for connections to machine learning.\n\n## Key Archetypes\n\n- **Limits to Growth** — reinforcing loop + limiting factor\n- **Shifting the Burden** — symptomatic solution undermines fundamental fix\n- **Tragedy of the Commons** — individual gain depletes shared resource",
     "tags":["research","systems","mental-models"]},
    {"id":"ml-research","title":"ML Research Log","folder":"Research",
     "content":"## Transformer Architecture\n\nSelf-attention allows the model to weigh input tokens when producing each output.\n\n**Core equation:** `Attention(Q,K,V) = softmax(QK^T / sqrt(d_k)) * V`\n\n## Gradient Descent as Feedback\n\nViewed through [[Systems Thinking Notes]]:\n- Loss function = sensor\n- Optimizer = controller\n- Weight updates = actuator",
     "tags":["ml","research","transformers"]},
    {"id":"q1-strategy","title":"Meeting — Q1 Strategy","folder":"Meetings",
     "content":"## Q1 Strategy Session\n\n### Decisions\n1. Ship mindmap view by end of Q1\n2. Focus on retention over acquisition\n3. Add OLLAMA AI integration\n\n### Action Items\n- [ ] Finalize CRDT sync architecture\n- [ ] User interviews x10\n- [ ] Performance profiling",
     "tags":["meeting","strategy","q1"]},
    {"id":"project-architecture","title":"Project Nexus — Architecture","folder":"Dev",
     "content":"## Architecture Overview\n\n**Storage:** SQLite local-first\n**Editor:** Rich content with mindmaps, painter, tables\n**AI:** OLLAMA local AI, no API key needed\n\n## Tech Stack\n\n- Backend: Python / Flask → .exe via PyInstaller\n- Frontend: Vanilla JS + CSS\n- DB: SQLite with FTS5\n- Packaging: PyInstaller --onefile",
     "tags":["dev","architecture","nexus"]},
    {"id":"reading-list","title":"Reading List 2024","folder":"Personal",
     "content":"## Books\n\n- [ ] Thinking in Systems — Donella Meadows\n- [x] The Fifth Discipline — Peter Senge\n- [ ] How Minds Change — David McRaney\n\n## Papers\n\n- [x] Attention Is All You Need (Vaswani et al.)\n- [ ] Constitutional AI (Anthropic)",
     "tags":["reading","books","personal"]}
]


def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(str(DB_PATH), check_same_thread=False)
        db.row_factory = sqlite3.Row
        db.executescript("PRAGMA journal_mode=WAL; PRAGMA foreign_keys=ON;")
    return db

@app.teardown_appcontext
def close_db(exc):
    db = getattr(g, '_database', None)
    if db is not None: db.close()

def init_db():
    con = sqlite3.connect(str(DB_PATH))
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    ensure_runtime_schema(con)
    count = con.execute("SELECT COUNT(*) FROM notes").fetchone()[0]
    if count == 0:
        now = datetime.utcnow().isoformat()
        for n in SEED_NOTES:
            wc = len(n["content"].split())
            con.execute("INSERT INTO notes (id,title,content,properties,created_at,updated_at,word_count,folder) VALUES (?,?,?,?,?,?,?,?)",
                        (n["id"],n["title"],n["content"],json.dumps({}),now,now,wc,n["folder"]))
            for tag in n.get("tags",[]):
                con.execute("INSERT OR IGNORE INTO tags (note_id,tag) VALUES (?,?)", (n["id"],tag))
    ensure_folder_exists('Notes', con)
    ensure_folder_exists('Inbox', con)
    sync_folders(con)
    rebuild_all_links(con)
    con.commit()
    con.close()

def ensure_runtime_schema(con):
    """Additive migrations for users with an existing Nexus DB."""
    note_columns = {row['name'] for row in con.execute("PRAGMA table_info(notes)").fetchall()}
    if 'properties' not in note_columns:
        con.execute("ALTER TABLE notes ADD COLUMN properties TEXT NOT NULL DEFAULT '{}'")
    painter_columns = {row['name'] for row in con.execute("PRAGMA table_info(painter_saves)").fetchall()}
    if 'vector_data' not in painter_columns:
        con.execute("ALTER TABLE painter_saves ADD COLUMN vector_data TEXT NOT NULL DEFAULT '{}'")
    if 'metadata' not in painter_columns:
        con.execute("ALTER TABLE painter_saves ADD COLUMN metadata TEXT NOT NULL DEFAULT '{}'")
    con.execute("""
        CREATE TABLE IF NOT EXISTS note_links (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            source_id    TEXT NOT NULL REFERENCES notes(id) ON DELETE CASCADE,
            target_id    TEXT REFERENCES notes(id) ON DELETE CASCADE,
            target_title TEXT NOT NULL DEFAULT '',
            UNIQUE(source_id, target_id, target_title)
        )
    """)

def generate_id(title):
    ts = datetime.utcnow().isoformat()
    return hashlib.sha1(f"{title}-{ts}".encode()).hexdigest()[:12]

def count_words(text):
    text = re.sub(r'<[^>]+>',' ',text)
    text = re.sub(r'#{1,6}\s','',text)
    text = re.sub(r'\*{1,2}|_{1,2}|`{1,3}','',text)
    return len(text.split())

def parse_backlinks(content):
    return re.findall(r'\[\[(.+?)\]\]', content)

def normalize_properties(data):
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except Exception:
            data = {}
    if not isinstance(data, dict):
        data = {}
    props = dict(data)
    props.setdefault('status', '')
    props.setdefault('type', '')
    props.setdefault('due_date', '')
    props.setdefault('source_url', '')
    props.setdefault('calendar_event_id', '')
    props.setdefault('template_id', '')
    props.setdefault('captured_via', '')
    props.setdefault('captured_at', '')
    return props

def parse_note_links(content):
    return [match.strip() for match in re.findall(r'\[\[(.+?)\]\]', content or '') if match.strip()]

def extract_tasks(content):
    raw = content or ''
    tasks = []
    # HTML checklist support from the current rich editor.
    for match in re.finditer(r'<li[^>]*>\s*(?:<input[^>]*type=["\']checkbox["\'][^>]*?(checked)?[^>]*>)?([\s\S]*?)</li>', raw, flags=re.IGNORECASE):
        checked = bool(match.group(1))
        label = strip_markup(match.group(2))
        if label:
            tasks.append({'label': label, 'done': checked})
    # Markdown fallback support for imported/plain content.
    for line in raw.splitlines():
        md = re.match(r'^\s*-\s*\[( |x|X)\]\s+(.+)$', line.strip())
        if md:
            label = strip_markup(md.group(2))
            if label:
                tasks.append({'label': label, 'done': md.group(1).lower() == 'x'})
    deduped = []
    seen = set()
    for task in tasks:
        key = (task['label'].lower(), task['done'])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(task)
    return deduped

def resolve_link_target(db, raw_target):
    if not raw_target:
        return None
    by_id = db.execute("SELECT id,title FROM notes WHERE id=? AND is_deleted=0", (raw_target,)).fetchone()
    if by_id:
        return dict(by_id)
    by_title = db.execute(
        "SELECT id,title FROM notes WHERE LOWER(title)=LOWER(?) AND is_deleted=0 ORDER BY updated_at DESC LIMIT 1",
        (raw_target,)
    ).fetchone()
    return dict(by_title) if by_title else None

def rebuild_note_links(db, note_id, content):
    db.execute("DELETE FROM backlinks WHERE source_id=?", (note_id,))
    db.execute("DELETE FROM note_links WHERE source_id=?", (note_id,))
    for raw_target in parse_note_links(content):
        db.execute("INSERT INTO backlinks (source_id,target_title) VALUES (?,?)", (note_id, raw_target))
        resolved = resolve_link_target(db, raw_target)
        target_id = resolved['id'] if resolved else None
        target_title = resolved['title'] if resolved else raw_target
        db.execute(
            "INSERT OR IGNORE INTO note_links (source_id,target_id,target_title) VALUES (?,?,?)",
            (note_id, target_id, target_title)
        )

def rebuild_all_links(db):
    rows = db.execute("SELECT id,content FROM notes WHERE is_deleted=0").fetchall()
    db.execute("DELETE FROM backlinks")
    db.execute("DELETE FROM note_links")
    for row in rows:
        rebuild_note_links(db, row['id'], row['content'])

def note_to_dict(row, tags=None, db=None):
    d = dict(row)
    d['properties'] = normalize_properties(d.get('properties'))
    if tags is not None: d['tags'] = tags
    elif db: d['tags'] = [r['tag'] for r in db.execute("SELECT tag FROM tags WHERE note_id=?",(d['id'],))]
    else: d['tags'] = []
    tasks = extract_tasks(d.get('content', ''))
    d['tasks'] = tasks
    d['task_count'] = len(tasks)
    d['open_task_count'] = len([task for task in tasks if not task['done']])
    if db:
        d['links'] = [dict(r) for r in db.execute(
            "SELECT target_id,target_title FROM note_links WHERE source_id=? ORDER BY target_title COLLATE NOCASE",
            (d['id'],)
        ).fetchall()]
    else:
        d['links'] = []
    return d

def ensure_folder_exists(folder_name, db):
    name = (folder_name or 'Notes').strip() or 'Notes'
    now = datetime.utcnow().isoformat()
    db.execute("INSERT OR IGNORE INTO folders (name,created_at) VALUES (?,?)", (name, now))
    return name

def sync_folders(db):
    ensure_folder_exists('Notes', db)
    ensure_folder_exists('Inbox', db)
    rows = db.execute("SELECT DISTINCT folder FROM notes").fetchall()
    for row in rows:
        ensure_folder_exists(row['folder'], db)

def create_note_record(db, title='Untitled', content='', folder='Notes', tags=None, properties=None, note_id=None, created_at=None, updated_at=None):
    tags = tags or []
    title = (title or 'Untitled').strip() or 'Untitled'
    folder = ensure_folder_exists(folder, db)
    properties = normalize_properties(properties)
    now = datetime.utcnow().isoformat()
    note_id = (note_id or generate_id(title)).strip()
    created_at = created_at or now
    updated_at = updated_at or created_at
    wc = count_words(content)
    db.execute(
        "INSERT INTO notes (id,title,content,properties,created_at,updated_at,word_count,folder) VALUES (?,?,?,?,?,?,?,?)",
        (note_id, title, content, json.dumps(properties), created_at, updated_at, wc, folder)
    )
    for tag in tags:
        clean_tag = str(tag).strip().lower()
        if clean_tag:
            db.execute("INSERT OR IGNORE INTO tags (note_id,tag) VALUES (?,?)", (note_id, clean_tag))
    rebuild_note_links(db, note_id, content)
    row = db.execute("SELECT * FROM notes WHERE id=?", (note_id,)).fetchone()
    return note_to_dict(row, tags=[str(t).strip().lower() for t in tags if str(t).strip()], db=db)

def strip_markup(text):
    text = text or ''
    text = re.sub(r'<script[\s\S]*?</script>', ' ', text, flags=re.IGNORECASE)
    text = re.sub(r'<style[\s\S]*?</style>', ' ', text, flags=re.IGNORECASE)
    text = re.sub(r'<br\s*/?>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'</(p|div|li|h1|h2|h3|blockquote|pre|tr|table|ul|ol)>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'\[\[(.+?)\]\]', r'\1', text)
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n\s*', '\n', text)
    text = re.sub(r'\n{2,}', '\n', text)
    return text.strip()

def sentence_split(text):
    chunks = re.split(r'(?<=[.!?])\s+|\n+', strip_markup(text))
    return [c.strip() for c in chunks if c.strip()]

def summarize_text(text, max_sentences=3):
    sentences = sentence_split(text)
    if not sentences:
        return "I don't have enough note content to summarize yet."
    return ' '.join(sentences[:max_sentences])

def normalize_json_blob(value, fallback):
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except Exception:
            value = fallback
    if not isinstance(value, type(fallback)):
        return fallback
    return value

def normalize_painter_vector(data):
    doc = normalize_json_blob(data, {})
    blocks = doc.get('blocks') if isinstance(doc, dict) else []
    if not isinstance(blocks, list):
        blocks = []
    meta = doc.get('metadata') if isinstance(doc, dict) and isinstance(doc.get('metadata'), dict) else {}
    return {'version': int(doc.get('version', 1)) if isinstance(doc, dict) else 1, 'blocks': blocks, 'metadata': meta}

def normalize_painter_metadata(data):
    meta = normalize_json_blob(data, {})
    if not isinstance(meta, dict):
        meta = {}
    meta.setdefault('search_text', '')
    meta.setdefault('engine', 'nexus-vector-ink')
    meta.setdefault('updated_with', 'painter')
    return meta

def build_inline_drawing_html(title, vector_data, metadata=None, image_data=''):
    doc = normalize_painter_vector(vector_data)
    meta = normalize_painter_metadata(metadata)
    payload = html.escape(json.dumps(doc, separators=(',', ':')), quote=True)
    meta_payload = html.escape(json.dumps(meta, separators=(',', ':')), quote=True)
    preview = html.escape(image_data or '', quote=True)
    label = html.escape(title or 'Sketch')
    search_text = html.escape(meta.get('search_text', ''), quote=True)
    return (
        f'<div class="note-sketch-block" contenteditable="false" draggable="true" data-sketch="{payload}" '
        f'data-sketch-meta="{meta_payload}" data-sketch-title="{label}" data-sketch-preview="{preview}" '
        f'data-sketch-search="{search_text}" style="width:560px;height:360px;">'
        f'<div class="note-sketch-shell">'
        f'<div class="note-sketch-meta">Sketch {label} {search_text}</div>'
        f'<div class="note-sketch-header">'
        f'<div class="note-sketch-title-wrap"><span class="note-sketch-kicker">Sketch</span><span class="note-sketch-title">{label}</span></div>'
        f'<div class="note-sketch-actions"></div>'
        f'</div>'
        f'<div class="note-sketch-stage"><canvas class="note-sketch-canvas"></canvas></div>'
        f'</div></div><p><br></p>'
    )

def extract_keywords(text, limit=6):
    words = re.findall(r"[A-Za-z][A-Za-z0-9\-']+", strip_markup(text).lower())
    stop = {
        'the','and','for','that','with','this','from','have','your','about','into','they','them','their','note',
        'notes','just','what','when','where','which','there','would','could','should','because','while','will',
        'also','than','then','been','were','being','after','before','under','over','more','some','such','very',
        'only','make','made','like','want','need','into','onto','does','dont','cant','isnt','you','are','was'
    }
    freq = {}
    for word in words:
        if len(word) < 4 or word in stop:
            continue
        freq[word] = freq.get(word, 0) + 1
    ranked = sorted(freq.items(), key=lambda kv: (-kv[1], kv[0]))
    return [word for word, _ in ranked[:limit]]

def suggest_title(text):
    keywords = extract_keywords(text, limit=4)
    if not keywords:
        return "Quick Note"
    return ' '.join(word.title() for word in keywords[:3])

def build_note_snippets(db, prompt, limit=3):
    terms = [t for t in extract_keywords(prompt, limit=5) if t]
    if not terms:
        rows = db.execute("SELECT title, content, folder FROM notes WHERE is_deleted=0 ORDER BY updated_at DESC LIMIT ?", (limit,)).fetchall()
    else:
        like_terms = [f'%{term}%' for term in terms]
        query = " OR ".join(["title LIKE ? OR content LIKE ?"] * len(terms))
        params = []
        for term in like_terms:
            params.extend([term, term])
        params.append(limit)
        rows = db.execute(
            f"SELECT title, content, folder FROM notes WHERE is_deleted=0 AND ({query}) ORDER BY updated_at DESC LIMIT ?",
            tuple(params)
        ).fetchall()
    snippets = []
    for row in rows:
        preview = summarize_text(row['content'], max_sentences=2)
        snippets.append(f"- {row['title']} ({row['folder']}): {preview}")
    return snippets

def stringify_context_value(value, depth=0):
    if value is None:
        return ''
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (int, float, bool)):
        return str(value)
    if depth > 3:
        return ''
    if isinstance(value, list):
        parts = [stringify_context_value(item, depth + 1) for item in value]
        return '\n'.join(part for part in parts if part)
    if isinstance(value, dict):
        lines = []
        preferred_order = ['label', 'title', 'name', 'tab', 'page', 'type', 'id', 'folder', 'content', 'text', 'summary', 'description']
        seen = set()
        for key in preferred_order + list(value.keys()):
            if key in seen or key not in value:
                continue
            seen.add(key)
            text = stringify_context_value(value.get(key), depth + 1)
            if text:
                label = key.replace('_', ' ').title()
                lines.append(f"{label}: {text}")
        return '\n'.join(lines)
    return str(value).strip()

def normalize_ai_context(context):
    if isinstance(context, str):
        text = context.strip()
        return text, text
    if not context:
        return '', ''
    if isinstance(context, dict):
        sections = []
        summary_parts = []
        preferred_sections = [
            ('page', 'Current Page'),
            ('tab', 'Current Tab'),
            ('selection', 'Selected Text'),
            ('note', 'Current Note'),
            ('note_content', 'Note Content'),
            ('editor', 'Editor State'),
            ('mindmap', 'Mindmap'),
            ('painter', 'Painter'),
            ('items', 'Related Items'),
            ('open_notes', 'Open Notes'),
            ('notes', 'Notes'),
            ('metadata', 'Metadata')
        ]
        handled = set()
        for key, label in preferred_sections:
            if key in context:
                handled.add(key)
                text = stringify_context_value(context.get(key))
                if text:
                    sections.append(f"{label}:\n{text}")
                    summary_parts.append(text)
        for key, value in context.items():
            if key in handled:
                continue
            text = stringify_context_value(value)
            if text:
                label = key.replace('_', ' ').title()
                sections.append(f"{label}:\n{text}")
                summary_parts.append(text)
        return '\n\n'.join(sections).strip(), '\n'.join(summary_parts).strip()
    text = stringify_context_value(context)
    return text, text

def build_ai_full_prompt(prompt, context):
    normalized_context, _ = normalize_ai_context(context)
    clean_prompt = (prompt or '').strip() or 'Help with the current Nexus Notes context.'
    if normalized_context:
        return f"Nexus Notes context:\n{normalized_context}\n\nUser request:\n{clean_prompt}"
    return f"User request:\n{clean_prompt}"

def extract_context_source(context):
    if not isinstance(context, dict):
        return normalize_ai_context(context)[1]
    primary_parts = []
    selection = stringify_context_value(context.get('selection'))
    note_content = stringify_context_value(context.get('note_content'))
    mindmap = stringify_context_value(context.get('mindmap'))
    painter = stringify_context_value(context.get('painter'))
    note = context.get('note') if isinstance(context.get('note'), dict) else {}
    note_title = stringify_context_value(note.get('title'))
    note_tags = stringify_context_value(note.get('tags'))
    if selection:
        primary_parts.append(selection)
    if note_content:
        primary_parts.append(note_content)
    elif note_title:
        primary_parts.append(note_title)
        if note_tags:
            primary_parts.append(note_tags)
    if mindmap:
        primary_parts.append(mindmap)
    if painter:
        primary_parts.append(painter)
    return '\n'.join(part for part in primary_parts if part).strip()

def prompt_looks_like_question(text):
    lower = (text or '').strip().lower()
    if not lower:
        return False
    question_starters = (
        'what', 'why', 'how', 'when', 'where', 'who', 'which', 'does', 'do', 'did',
        'is', 'are', 'can', 'could', 'should', 'would', 'will', 'summarize', 'explain'
    )
    return '?' in lower or lower.startswith(question_starters)

def best_matching_sentences(prompt, text, limit=4):
    sentences = [strip_markup(sentence).strip() for sentence in sentence_split(text)]
    sentences = [sentence for sentence in sentences if len(sentence.split()) >= 3]
    if not sentences:
        return []
    terms = extract_keywords(prompt, limit=8)
    ranked = []
    for idx, sentence in enumerate(sentences):
        lower = sentence.lower()
        score = 0
        for term in terms:
            if term in lower:
                score += 3
        if prompt_looks_like_question(prompt):
            score += 1
        if idx == 0:
            score += 1
        ranked.append((score, idx, sentence))
    ranked.sort(key=lambda item: (-item[0], item[1]))
    picked = []
    seen = set()
    for score, _, sentence in ranked:
        if sentence in seen:
            continue
        if terms and score <= 0:
            continue
        seen.add(sentence)
        picked.append(sentence)
        if len(picked) >= limit:
            break
    if not picked:
        return sentences[:limit]
    return picked

def duckai_get_vqd():
    """Fetch the x-vqd-4 token required for Duck.ai chat."""
    hdrs = {
        'User-Agent': DUCKAI_UA,
        'x-vqd-accept': '1',
        'Accept': 'text/html,application/xhtml+xml,*/*',
        'Referer': DUCKAI_WEB_URL,
    }
    resp = requests.get(DUCKAI_STATUS_URL, headers=hdrs, timeout=10)
    resp.raise_for_status()
    vqd = resp.headers.get('x-vqd-4') or resp.headers.get('x-vqd4')
    if not vqd:
        raise RuntimeError('Duck.ai did not return a VQD token')
    return vqd

def duckai_chat_stream(system_prompt, user_prompt):
    """Generator that yields text chunks from Duck.ai SSE stream."""
    vqd = duckai_get_vqd()
    hdrs = {
        'User-Agent': DUCKAI_UA,
        'x-vqd-4': vqd,
        'Content-Type': 'application/json',
        'Accept': 'text/event-stream',
        'Referer': DUCKAI_WEB_URL,
        'Origin': 'https://duck.ai',
    }
    messages = []
    if system_prompt:
        messages.append({'role': 'user', 'content': system_prompt})
        messages.append({'role': 'assistant', 'content': 'Understood.'})
    messages.append({'role': 'user', 'content': user_prompt})
    payload = {'model': DUCKAI_MODEL, 'messages': messages}
    with requests.post(DUCKAI_CHAT_URL, headers=hdrs, json=payload, stream=True, timeout=60) as resp:
        resp.raise_for_status()
        for raw_line in resp.iter_lines():
            if not raw_line:
                continue
            line = raw_line.decode('utf-8', errors='replace')
            if not line.startswith('data: '):
                continue
            data_str = line[6:]
            if data_str.strip() == '[DONE]':
                break
            try:
                chunk = json.loads(data_str)
                token = chunk.get('message', '')
                if token:
                    yield token
            except Exception:
                continue

def duckai_chat_full(system_prompt, user_prompt):
    """Collect full Duck.ai response (non-streaming)."""
    return ''.join(duckai_chat_stream(system_prompt, user_prompt))


def local_ai_response(prompt, context, db, mode='auto'):
    clean_prompt = strip_markup(prompt)
    normalized_context, context_summary = normalize_ai_context(context)
    clean_context = strip_markup(extract_context_source(context) or context_summary)
    lower = clean_prompt.lower()
    source = clean_context or '\n'.join(build_note_snippets(db, clean_prompt, limit=3))
    
    # Determine behavior based on mode
    is_local = mode == 'local'
    is_online = mode == 'online'

    if not source.strip():
        if clean_prompt:
            return f'I can help with "{clean_prompt}", but I need some note or page context first. Open a note, select text, or add a little more detail.'
        return "I can help once there is note content to work with. Open a note or write a little context first."

    if any(word in lower for word in ['summarize', 'summary', 'tl;dr']):
        return "Summary:\n- " + "\n- ".join(sentence_split(source)[:4])

    if any(word in lower for word in ['title', 'rename', 'headline']):
        return f"Suggested title: {suggest_title(source)}"

    if any(word in lower for word in ['tag', 'keywords']):
        keywords = extract_keywords(source, limit=8)
        return "Suggested tags: " + (', '.join(keywords) if keywords else 'general, notes')

    if any(word in lower for word in ['action items', 'todo', 'tasks', 'next steps']):
        sentences = sentence_split(source)[:5]
        items = []
        for sentence in sentences:
            sentence = sentence.rstrip('.')
            if len(sentence.split()) < 3:
                continue
            items.append(f"- {sentence}")
        return "Action items:\n" + ("\n".join(items) if items else "- Review the note and extract concrete follow-ups.")

    if any(word in lower for word in ['rewrite', 'improve', 'clean up', 'fix grammar']):
        summary = summarize_text(source, max_sentences=4)
        return f"Clean rewrite:\n{summary}"

    if any(word in lower for word in ['outline', 'structure']):
        sentences = sentence_split(source)[:4]
        outline = [f"- {sentence[:80].rstrip('.')}" for sentence in sentences]
        return "Outline:\n" + "\n".join(outline)

    if normalized_context and any(phrase in lower for phrase in ['current tab', 'this tab', 'this note', 'current note', 'on this page', 'what is this about']):
        matches = best_matching_sentences(clean_prompt, source, limit=3)
        return "From the current tab:\n- " + "\n- ".join(matches)

    if (prompt_looks_like_question(clean_prompt) or is_online) and not is_local:
        matches = best_matching_sentences(clean_prompt, source, limit=3)
        # In Auto mode, we only search web if local notes don't have a good answer.
        # In Online mode, we prioritize the web search.
        if is_online or not matches or len(matches) < 2:
            try:
                response = requests.get(f'https://api.duckduckgo.com/?q={clean_prompt}&format=json&no_html=1&skip_disambig=1', timeout=8)
                if response.status_code == 200:
                    data = response.json()
                    answer = data.get('Answer') or data.get('AbstractText') or data.get('Definition')
                    if answer and len(answer) > 20:
                        return f"From the web:\n{answer}"
            except Exception:
                pass
        if matches and normalized_context:
            return "Based on the current tab:\n- " + "\n- ".join(matches)
        return "Based on your notes:\n- " + "\n- ".join(matches)

    # Web search for "tell me more about" queries
    if (lower.startswith('tell me more about') or (is_online and len(clean_prompt.split()) < 5)) and not is_local:
        topic = clean_prompt[18:].strip()
        if topic:
            try:
                response = requests.get(f'https://en.wikipedia.org/api/rest_v1/page/summary/{topic.replace(" ", "_")}', timeout=8)
                if response.status_code == 200:
                    data = response.json()
                    extract = data.get('extract', '')
                    if extract:
                        return f"From Wikipedia:\n{extract}"
            except Exception as e:
                pass  # Fall through to normal response

    snippets = build_note_snippets(db, clean_prompt, limit=3)
    if snippets:
        prefix = "Built-in local assistant:"
        if normalized_context:
            prefix = "Built-in local assistant using current Nexus Notes context:"
        return prefix + "\n" + "\n".join(snippets)
    return summarize_text(source, max_sentences=4)


# ── STATIC ──
@app.route('/')
def index():
    return send_file(str(FRONTEND_DIR / 'index.html'))

@app.route('/static/<path:filename>')
def static_files(filename):
    return send_from_directory(str(FRONTEND_DIR / 'static'), filename)


# ── NOTES CRUD ──
@app.route('/api/notes', methods=['GET'])
def list_notes():
    db = get_db()
    folder = request.args.get('folder')
    if folder:
        rows = db.execute("SELECT * FROM notes WHERE is_deleted=0 AND folder=? ORDER BY updated_at DESC",(folder,)).fetchall()
    else:
        rows = db.execute("SELECT * FROM notes WHERE is_deleted=0 ORDER BY updated_at DESC").fetchall()
    return jsonify([note_to_dict(row, db=db) for row in rows])

@app.route('/api/notes', methods=['POST'])
def create_note():
    db = get_db()
    data = request.get_json() or {}
    note = create_note_record(
        db,
        title=data.get('title', 'Untitled'),
        content=data.get('content', ''),
        folder=data.get('folder', 'Notes'),
        tags=data.get('tags', []),
        properties=data.get('properties', {}),
        note_id=data.get('id') or data.get('note_id'),
        created_at=data.get('created_at'),
        updated_at=data.get('updated_at')
    )
    db.commit()
    return jsonify(note), 201

@app.route('/api/notes/<note_id>', methods=['GET'])
def get_note(note_id):
    db = get_db()
    row = db.execute("SELECT * FROM notes WHERE id=? AND is_deleted=0",(note_id,)).fetchone()
    if not row: abort(404)
    tags = [r['tag'] for r in db.execute("SELECT tag FROM tags WHERE note_id=?",(note_id,))]
    return jsonify(note_to_dict(row,tags))

@app.route('/api/notes/<note_id>', methods=['PUT'])
def update_note(note_id):
    db = get_db()
    row = db.execute("SELECT * FROM notes WHERE id=? AND is_deleted=0",(note_id,)).fetchone()
    if not row: abort(404)
    data = request.get_json() or {}
    title = data.get('title',row['title'])
    content = data.get('content',row['content'])
    folder = ensure_folder_exists(data.get('folder', row['folder']), db)
    properties = normalize_properties(data.get('properties', row['properties']))
    tags = data.get('tags',None)
    now = datetime.utcnow().isoformat()
    wc = count_words(content)
    if content != row['content']:
        db.execute("INSERT INTO versions (note_id,title,content,saved_at,word_count) VALUES (?,?,?,?,?)",
                   (note_id,row['title'],row['content'],now,row['word_count']))
        db.execute("DELETE FROM versions WHERE id IN (SELECT id FROM versions WHERE note_id=? ORDER BY saved_at DESC LIMIT -1 OFFSET 20)",(note_id,))
    db.execute(
        "UPDATE notes SET title=?,content=?,properties=?,folder=?,updated_at=?,word_count=? WHERE id=?",
        (title,content,json.dumps(properties),folder,now,wc,note_id)
    )
    if tags is not None:
        db.execute("DELETE FROM tags WHERE note_id=?",(note_id,))
        for tag in tags:
            db.execute("INSERT OR IGNORE INTO tags (note_id,tag) VALUES (?,?)",(note_id,tag.strip()))
    rebuild_note_links(db, note_id, content)
    db.commit()
    row = db.execute("SELECT * FROM notes WHERE id=?",(note_id,)).fetchone()
    current_tags = [r['tag'] for r in db.execute("SELECT tag FROM tags WHERE note_id=?",(note_id,))]
    return jsonify(note_to_dict(row,current_tags))

@app.route('/api/notes/<note_id>', methods=['DELETE'])
def delete_note(note_id):
    db = get_db()
    db.execute("UPDATE notes SET is_deleted=1 WHERE id=?",(note_id,))
    db.commit()
    return jsonify({'deleted':note_id})

@app.route('/api/notes/daily', methods=['POST'])
def get_or_create_daily_note():
    """Daily note route used by the promoted daily workspace."""
    db = get_db()
    data = request.get_json() or {}
    date_key = (data.get('date') or datetime.utcnow().date().isoformat()).strip()
    existing = db.execute(
        "SELECT * FROM notes WHERE is_deleted=0 AND json_extract(properties, '$.daily_date')=? ORDER BY updated_at DESC LIMIT 1",
        (date_key,)
    ).fetchone()
    if existing:
        return jsonify(note_to_dict(existing, db=db))
    title = data.get('title') or f'Daily Note {date_key}'
    content = data.get('content') or (
        f"<h2>{title}</h2><p><strong>Focus</strong></p><p><br></p>"
        f"<p><strong>Notes</strong></p><p><br></p><p><strong>Wins</strong></p><p><br></p>"
    )
    properties = normalize_properties(data.get('properties', {}))
    properties['daily_date'] = date_key
    properties.setdefault('type', 'daily')
    note = create_note_record(db, title=title, content=content, folder='Journal', tags=['daily'], properties=properties)
    db.commit()
    return jsonify(note), 201


# ── SEARCH ──
@app.route('/api/search')
def search_notes():
    db = get_db()
    q = request.args.get('q','').strip()
    if not q: return jsonify([])
    fts_q = ' '.join(f'"{w}"*' for w in q.split() if w)
    try:
        rows = db.execute("""
            SELECT n.id,n.title,n.folder,n.updated_at,n.word_count,
                   snippet(notes_fts,2,'<mark>','</mark>','…',24) AS snippet
            FROM notes_fts JOIN notes n ON n.id=notes_fts.id
            WHERE notes_fts MATCH ? AND n.is_deleted=0 ORDER BY rank LIMIT 20
        """,(fts_q,)).fetchall()
    except:
        like = f'%{q}%'
        rows = db.execute("SELECT id,title,folder,updated_at,word_count,substr(content,1,120) AS snippet FROM notes WHERE (title LIKE ? OR content LIKE ?) AND is_deleted=0 ORDER BY updated_at DESC LIMIT 20",(like,like)).fetchall()
    return jsonify([{'id':r['id'],'title':r['title'],'folder':r['folder'],'updated_at':r['updated_at'],'word_count':r['word_count'],'snippet':r['snippet'] or ''} for r in rows])


# ── BACKLINKS ──
@app.route('/api/notes/<note_id>/backlinks')
def get_backlinks(note_id):
    db = get_db()
    note = db.execute("SELECT title FROM notes WHERE id=?",(note_id,)).fetchone()
    if not note: abort(404)
    incoming = db.execute("""
        SELECT DISTINCT n.id,n.title,n.folder,n.updated_at,substr(n.content,1,200) AS preview
        FROM note_links l
        JOIN notes n ON n.id=l.source_id
        WHERE l.target_id=? AND n.is_deleted=0
        ORDER BY n.updated_at DESC
    """,(note_id,)).fetchall()
    unresolved = db.execute("""
        SELECT DISTINCT n.id,n.title,n.folder,n.updated_at,substr(n.content,1,200) AS preview
        FROM backlinks b
        JOIN notes n ON n.id=b.source_id
        WHERE b.target_title=? AND n.is_deleted=0
        ORDER BY n.updated_at DESC
    """,(note['title'],)).fetchall()
    incoming_map = {row['id']: dict(row) for row in incoming}
    for row in unresolved:
        incoming_map.setdefault(row['id'], dict(row))
    outgoing = db.execute("""
        SELECT DISTINCT n.id,n.title,n.folder,n.updated_at
        FROM note_links l
        JOIN notes n ON n.id=l.target_id
        WHERE l.source_id=? AND n.is_deleted=0
        ORDER BY n.updated_at DESC
    """,(note_id,)).fetchall()
    unresolved_outgoing = [
        {'id': None, 'title': row['target_title'], 'folder': 'Unresolved', 'updated_at': ''}
        for row in db.execute("SELECT target_title FROM note_links WHERE source_id=? AND target_id IS NULL",(note_id,)).fetchall()
    ]
    return jsonify({'incoming':list(incoming_map.values()),'outgoing':[dict(r) for r in outgoing] + unresolved_outgoing})


# ── VERSIONS ──
@app.route('/api/notes/rebuild-links', methods=['POST'])
def rebuild_links_endpoint():
    """Used after bulk imports so all note links resolve against the final imported note set."""
    db = get_db()
    rebuild_all_links(db)
    db.commit()
    return jsonify({'rebuilt': True})

@app.route('/api/notes/<note_id>/versions')
def get_versions(note_id):
    db = get_db()
    rows = db.execute("SELECT * FROM versions WHERE note_id=? ORDER BY saved_at DESC LIMIT 20",(note_id,)).fetchall()
    return jsonify([dict(r) for r in rows])

@app.route('/api/notes/<note_id>/versions/<int:version_id>/restore', methods=['POST'])
def restore_version(note_id, version_id):
    db = get_db()
    ver = db.execute("SELECT * FROM versions WHERE id=? AND note_id=?",(version_id,note_id)).fetchone()
    if not ver: abort(404)
    now = datetime.utcnow().isoformat()
    db.execute("UPDATE notes SET title=?,content=?,updated_at=?,word_count=? WHERE id=?",(ver['title'],ver['content'],now,ver['word_count'],note_id))
    rebuild_note_links(db, note_id, ver['content'])
    db.commit()
    return jsonify({'restored':version_id})


# ── GRAPH ──
@app.route('/api/graph')
def get_graph():
    db = get_db()
    notes = db.execute("SELECT id,title,folder,word_count FROM notes WHERE is_deleted=0").fetchall()
    backlinks = db.execute("SELECT source_id,target_id FROM note_links WHERE target_id IS NOT NULL").fetchall()
    return jsonify({'nodes':[{'id':r['id'],'title':r['title'],'folder':r['folder'],'word_count':r['word_count']} for r in notes],
                    'edges':[{'source':r['source_id'],'target':r['target_id']} for r in backlinks]})


# ── TAGS ──
@app.route('/api/tags')
def list_tags():
    db = get_db()
    rows = db.execute("SELECT tag,COUNT(*) as count FROM tags GROUP BY tag ORDER BY count DESC").fetchall()
    return jsonify([dict(r) for r in rows])

@app.route('/api/tags/<tag>/notes')
def notes_by_tag(tag):
    db = get_db()
    rows = db.execute("SELECT n.id,n.title,n.folder,n.updated_at,n.word_count FROM tags t JOIN notes n ON n.id=t.note_id WHERE t.tag=? AND n.is_deleted=0 ORDER BY n.updated_at DESC",(tag,)).fetchall()
    return jsonify([dict(r) for r in rows])


# ── FOLDERS ──
@app.route('/api/folders')
def list_folders():
    db = get_db()
    sync_folders(db)
    # Persist additive folder sync before reading so empty folders created
    # in previous actions do not disappear from the returned folder list.
    db.commit()
    rows = db.execute("""
        SELECT f.name AS folder, COALESCE(COUNT(n.id), 0) as count
        FROM folders f
        LEFT JOIN notes n ON n.folder=f.name AND n.is_deleted=0
        GROUP BY f.name
        ORDER BY CASE WHEN f.name='Notes' THEN 0 WHEN f.name='Inbox' THEN 1 ELSE 2 END, LOWER(f.name)
    """).fetchall()
    return jsonify([dict(r) for r in rows])

@app.route('/api/folders', methods=['POST'])
def create_folder():
    db = get_db()
    data = request.get_json() or {}
    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({'error': 'Folder name is required'}), 400
    existing = db.execute("SELECT name FROM folders WHERE LOWER(name)=LOWER(?)", (name,)).fetchone()
    if existing:
        # Folder creation in Nexus is effectively idempotent: if a matching
        # folder row already exists, return the canonical folder name instead of
        # hard failing so the UI can surface it consistently.
        return jsonify({'name': existing['name'], 'existing': True}), 200
    created = ensure_folder_exists(name, db)
    db.commit()
    return jsonify({'name': created}), 201

@app.route('/api/folders/<path:folder_name>', methods=['PUT'])
def rename_folder(folder_name):
    db = get_db()
    data = request.get_json() or {}
    new_name = (data.get('name') or '').strip()
    old_name = folder_name.strip()
    if not old_name or not new_name:
        return jsonify({'error': 'Folder name is required'}), 400
    existing = db.execute("SELECT name FROM folders WHERE name=?", (old_name,)).fetchone()
    if not existing:
        return jsonify({'error': 'Folder not found'}), 404
    conflict = db.execute("SELECT name FROM folders WHERE LOWER(name)=LOWER(?) AND name<>?", (new_name, old_name)).fetchone()
    if conflict:
        return jsonify({'error': 'Folder already exists'}), 409
    db.execute("UPDATE folders SET name=? WHERE name=?", (new_name, old_name))
    db.execute("UPDATE notes SET folder=? WHERE folder=?", (new_name, old_name))
    db.commit()
    return jsonify({'renamed': old_name, 'name': new_name})

@app.route('/api/folders/<path:folder_name>', methods=['DELETE'])
def delete_folder(folder_name):
    db = get_db()
    data = request.get_json(silent=True) or {}
    old_name = folder_name.strip()
    if not old_name:
        return jsonify({'error': 'Folder name is required'}), 400
    if old_name == 'Notes':
        return jsonify({'error': 'The default Notes folder cannot be deleted'}), 400
    existing = db.execute("SELECT name FROM folders WHERE name=?", (old_name,)).fetchone()
    if not existing:
        return jsonify({'error': 'Folder not found'}), 404
    target_folder = ensure_folder_exists(data.get('target_folder', 'Notes'), db)
    db.execute("UPDATE notes SET folder=? WHERE folder=?", (target_folder, old_name))
    db.execute("DELETE FROM folders WHERE name=?", (old_name,))
    db.commit()
    return jsonify({'deleted': old_name, 'moved_to': target_folder})


# ── STATS ──
@app.route('/api/stats')
def get_stats():
    db = get_db()
    sync_folders(db)
    total = db.execute("SELECT COUNT(*) FROM notes WHERE is_deleted=0").fetchone()[0]
    words = db.execute("SELECT SUM(word_count) FROM notes WHERE is_deleted=0").fetchone()[0] or 0
    tags = db.execute("SELECT COUNT(DISTINCT tag) FROM tags").fetchone()[0]
    links = db.execute("SELECT COUNT(*) FROM note_links WHERE target_id IS NOT NULL").fetchone()[0]
    folders = db.execute("SELECT COUNT(*) FROM folders").fetchone()[0]
    bookmarks = db.execute("SELECT COUNT(*) FROM bookmarks").fetchone()[0]
    mindmaps = db.execute("SELECT COUNT(*) FROM mindmaps").fetchone()[0]
    open_tasks = 0
    for row in db.execute("SELECT content FROM notes WHERE is_deleted=0").fetchall():
        open_tasks += len([task for task in extract_tasks(row['content']) if not task['done']])
    return jsonify({'total_notes':total,'total_words':words,'total_tags':tags,'total_links':links,'total_folders':folders,'total_bookmarks':bookmarks,'total_mindmaps':mindmaps,'open_tasks':open_tasks})


# ── BOOKMARKS ──
@app.route('/api/bookmarks', methods=['GET'])
def list_bookmarks():
    db = get_db()
    rows = db.execute("SELECT b.id,b.note_id,b.label,b.created_at,n.title,n.folder,n.updated_at,n.word_count FROM bookmarks b JOIN notes n ON n.id=b.note_id WHERE n.is_deleted=0 ORDER BY b.created_at DESC").fetchall()
    return jsonify([dict(r) for r in rows])

@app.route('/api/bookmarks', methods=['POST'])
def add_bookmark():
    db = get_db()
    data = request.get_json() or {}
    note_id = data.get('note_id','')
    label = data.get('label','')
    if not note_id: abort(400)
    now = datetime.utcnow().isoformat()
    try:
        db.execute("INSERT INTO bookmarks (note_id,label,created_at) VALUES (?,?,?)",(note_id,label,now))
    except sqlite3.IntegrityError:
        db.execute("UPDATE bookmarks SET label=? WHERE note_id=?",(label,note_id))
    db.commit()
    row = db.execute("SELECT * FROM bookmarks WHERE note_id=?",(note_id,)).fetchone()
    return jsonify(dict(row)),201

@app.route('/api/bookmarks/note/<note_id>', methods=['DELETE'])
def remove_bookmark_by_note(note_id):
    db = get_db()
    db.execute("DELETE FROM bookmarks WHERE note_id=?",(note_id,))
    db.commit()
    return jsonify({'deleted':note_id})


# ── MINDMAPS ──
@app.route('/api/mindmaps', methods=['GET'])
def list_mindmaps():
    db = get_db()
    rows = db.execute("SELECT id,title,created_at,updated_at FROM mindmaps ORDER BY updated_at DESC").fetchall()
    return jsonify([dict(r) for r in rows])

@app.route('/api/mindmaps', methods=['POST'])
def create_mindmap():
    db = get_db()
    data = request.get_json() or {}
    title = data.get('title','Untitled Map')
    default_data = {'nodes':[{'id':'1','text':'Central Idea','x':400,'y':300,'color':'#c8a96e','shape':'ellipse'}],'edges':[]}
    map_data = json.dumps(data.get('data', default_data))
    now = datetime.utcnow().isoformat()
    mid = generate_id(title)
    db.execute("INSERT INTO mindmaps (id,title,data,created_at,updated_at) VALUES (?,?,?,?,?)",(mid,title,map_data,now,now))
    db.commit()
    row = db.execute("SELECT * FROM mindmaps WHERE id=?",(mid,)).fetchone()
    r = dict(row); r['data'] = json.loads(r['data'])
    return jsonify(r),201

@app.route('/api/mindmaps/<map_id>', methods=['GET'])
def get_mindmap(map_id):
    db = get_db()
    row = db.execute("SELECT * FROM mindmaps WHERE id=?",(map_id,)).fetchone()
    if not row: abort(404)
    r = dict(row); r['data'] = json.loads(r['data'])
    return jsonify(r)

@app.route('/api/mindmaps/<map_id>', methods=['PUT'])
def update_mindmap(map_id):
    db = get_db()
    data = request.get_json() or {}
    now = datetime.utcnow().isoformat()
    if 'title' in data and 'data' in data:
        db.execute("UPDATE mindmaps SET title=?,data=?,updated_at=? WHERE id=?",(data['title'],json.dumps(data['data']),now,map_id))
    elif 'data' in data:
        db.execute("UPDATE mindmaps SET data=?,updated_at=? WHERE id=?",(json.dumps(data['data']),now,map_id))
    elif 'title' in data:
        db.execute("UPDATE mindmaps SET title=?,updated_at=? WHERE id=?",(data['title'],now,map_id))
    db.commit()
    row = db.execute("SELECT * FROM mindmaps WHERE id=?",(map_id,)).fetchone()
    r = dict(row); r['data'] = json.loads(r['data'])
    return jsonify(r)

@app.route('/api/mindmaps/<map_id>', methods=['DELETE'])
def delete_mindmap(map_id):
    db = get_db()
    db.execute("DELETE FROM mindmaps WHERE id=?",(map_id,))
    db.commit()
    return jsonify({'deleted':map_id})


# ── PAINTER ──
@app.route('/api/painter', methods=['GET'])
def list_painter():
    db = get_db()
    rows = db.execute("SELECT id,title,created_at,updated_at FROM painter_saves ORDER BY updated_at DESC").fetchall()
    return jsonify([dict(r) for r in rows])

@app.route('/api/painter', methods=['POST'])
def save_painter():
    db = get_db()
    data = request.get_json() or {}
    title = data.get('title','Untitled Drawing')
    image_data = data.get('image_data','')
    vector_data = json.dumps(normalize_painter_vector(data.get('vector_data', {})))
    metadata = json.dumps(normalize_painter_metadata(data.get('metadata', {})))
    now = datetime.utcnow().isoformat()
    pid = generate_id(title)
    db.execute(
        "INSERT INTO painter_saves (id,title,image_data,vector_data,metadata,created_at,updated_at) VALUES (?,?,?,?,?,?,?)",
        (pid,title,image_data,vector_data,metadata,now,now)
    )
    db.commit()
    return jsonify({'id':pid,'title':title}),201

@app.route('/api/painter/save-as-note', methods=['POST'])
def save_painter_as_note():
    db = get_db()
    data = request.get_json() or {}
    title = (data.get('title') or 'Untitled Drawing').strip() or 'Untitled Drawing'
    image_data = data.get('image_data', '')
    vector_data = data.get('vector_data', {})
    metadata = data.get('metadata', {})
    folder = data.get('folder', 'Notes')
    caption = (data.get('caption') or '').strip()
    has_vector = bool(normalize_painter_vector(vector_data).get('blocks'))
    if not image_data and not has_vector:
        return jsonify({'error': 'image_data or vector_data is required'}), 400
    parts = []
    if has_vector:
        parts.append(build_inline_drawing_html(title, vector_data, metadata, image_data))
    else:
        parts.extend([f'<p><strong>{title}</strong></p>', f'<p><img src="{image_data}" alt="{html.escape(title, quote=True)}"></p>'])
    if caption:
        parts.append(f'<p>{html.escape(caption)}</p>')
    note = create_note_record(db, title=title, content=''.join(parts), folder=folder, tags=['drawing', 'painter'])
    db.commit()
    return jsonify(note), 201

@app.route('/api/painter/<pid>', methods=['GET'])
def get_painter(pid):
    db = get_db()
    row = db.execute("SELECT * FROM painter_saves WHERE id=?",(pid,)).fetchone()
    if not row: abort(404)
    payload = dict(row)
    payload['vector_data'] = normalize_painter_vector(payload.get('vector_data'))
    payload['metadata'] = normalize_painter_metadata(payload.get('metadata'))
    return jsonify(payload)

@app.route('/api/painter/<pid>', methods=['PUT'])
def update_painter(pid):
    db = get_db()
    data = request.get_json() or {}
    now = datetime.utcnow().isoformat()
    row = db.execute("SELECT * FROM painter_saves WHERE id=?", (pid,)).fetchone()
    if not row:
        abort(404)
    title = data.get('title', row['title'])
    image_data = data.get('image_data', row['image_data'])
    vector_data = json.dumps(normalize_painter_vector(data.get('vector_data', row['vector_data'])))
    metadata = json.dumps(normalize_painter_metadata(data.get('metadata', row['metadata'])))
    db.execute(
        "UPDATE painter_saves SET title=?,image_data=?,vector_data=?,metadata=?,updated_at=? WHERE id=?",
        (title,image_data,vector_data,metadata,now,pid)
    )
    db.commit()
    return jsonify({'id':pid,'updated':True})

@app.route('/api/painter/<pid>', methods=['DELETE'])
def delete_painter(pid):
    db = get_db()
    db.execute("DELETE FROM painter_saves WHERE id=?",(pid,))
    db.commit()
    return jsonify({'deleted':pid})


# ── SETTINGS ──
@app.route('/api/settings', methods=['GET'])
def get_settings():
    db = get_db()
    rows = db.execute("SELECT key,value FROM settings").fetchall()
    return jsonify({r['key']:r['value'] for r in rows})

@app.route('/api/settings', methods=['PUT'])
def update_settings():
    db = get_db()
    data = request.get_json() or {}
    for key,value in data.items():
        db.execute("INSERT OR REPLACE INTO settings (key,value) VALUES (?,?)",(key,str(value)))
    db.commit()
    return jsonify({'saved':True})

@app.route('/api/backup')
def export_backup():
    """Structured local backup used by the richer export/import flow."""
    db = get_db()
    notes = [note_to_dict(row, db=db) for row in db.execute("SELECT * FROM notes WHERE is_deleted=0 ORDER BY updated_at DESC").fetchall()]
    folders = [dict(row) for row in db.execute("SELECT * FROM folders ORDER BY name COLLATE NOCASE").fetchall()]
    settings_rows = db.execute("SELECT key,value FROM settings").fetchall()
    bookmarks = [dict(row) for row in db.execute("SELECT * FROM bookmarks ORDER BY created_at DESC").fetchall()]
    mindmaps = [dict(row) for row in db.execute("SELECT * FROM mindmaps ORDER BY updated_at DESC").fetchall()]
    painter_saves = [dict(row) for row in db.execute("SELECT * FROM painter_saves ORDER BY updated_at DESC").fetchall()]
    return jsonify({
        'version': 3,
        'exported_at': datetime.utcnow().isoformat(),
        'notes': notes,
        'folders': folders,
        'settings': {row['key']: row['value'] for row in settings_rows},
        'bookmarks': bookmarks,
        'mindmaps': mindmaps,
        'painter_saves': painter_saves
    })


# ── OLLAMA AI PROXY ──
OPENAI_COMPAT_PROVIDERS = [
    {
        'provider': 'lmstudio',
        'label': 'LM Studio',
        'urls': ['http://127.0.0.1:1234/v1', 'http://localhost:1234/v1']
    },
    {
        'provider': 'gpt4all',
        'label': 'GPT4All',
        'urls': ['http://127.0.0.1:4891/v1', 'http://localhost:4891/v1']
    }
]
OLLAMA_URLS = ['http://localhost:11434','http://127.0.0.1:11434']
DEFAULT_OLLAMA_MODEL = 'llama3.2:1b'
OLLAMA_LOCK = threading.Lock()
OLLAMA_PROCESS = None
OLLAMA_PULL_PROCESS = None
OLLAMA_STATE = {'starting': False, 'pulling': False, 'pull_attempted': False, 'last_error': None}

def fetch_json(url, method='GET', payload=None, headers=None, timeout=4):
    data = None
    request_headers = {'Accept': 'application/json'}
    if payload is not None:
        data = json.dumps(payload).encode('utf-8')
        request_headers['Content-Type'] = 'application/json'
    if headers:
        request_headers.update(headers)
    req = urllib.request.Request(url, data=data, method=method)
    for key, value in request_headers.items():
        req.add_header(key, value)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        charset = None
        try:
            charset = resp.headers.get_content_charset()
        except Exception:
            charset = None
        body = resp.read().decode(charset or 'utf-8', errors='replace')
        return (json.loads(body) if body else {}), resp.status

def parse_openai_models(payload):
    models = []
    for item in (payload or {}).get('data', []):
        model_id = (item or {}).get('id')
        if model_id:
            models.append(model_id)
    return models

def stringify_message_content(content):
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict):
                text = item.get('text') or item.get('content') or item.get('value')
                if text:
                    parts.append(str(text))
            elif item:
                parts.append(str(item))
        return '\n'.join(parts).strip()
    if content is None:
        return ''
    return str(content).strip()

def probe_openai_provider(provider):
    for base in provider['urls']:
        try:
            data, status = fetch_json(f"{base}/models", timeout=2)
            if status != 200:
                continue
            models = parse_openai_models(data)
            return {
                'provider': provider['provider'],
                'provider_label': provider['label'],
                'online': True,
                'ready': bool(models),
                'url': base,
                'models': models,
                'status': 'ready' if models else 'no_models',
                'message': f"{provider['label']} ready" if models else f"{provider['label']} is running, but no model is loaded."
            }
        except Exception:
            continue
    return None

def chat_with_openai_provider(base_url, model, system, prompt):
    payload = {
        'model': model,
        'messages': [
            {'role': 'system', 'content': system},
            {'role': 'user', 'content': prompt}
        ],
        'stream': False
    }
    data, status = fetch_json(f"{base_url}/chat/completions", method='POST', payload=payload, timeout=90)
    if status != 200:
        raise RuntimeError(f"Provider returned status {status}")
    choices = data.get('choices') or []
    if not choices:
        return ''
    message = (choices[0] or {}).get('message') or {}
    return stringify_message_content(message.get('content'))

def ollama_binary():
    return shutil.which('ollama')

def find_ollama():
    for base in OLLAMA_URLS:
        try:
            req = urllib.request.Request(f"{base}/api/tags",method='GET')
            with urllib.request.urlopen(req,timeout=2) as resp:
                if resp.status == 200: return base
        except: continue
    return None

def list_ollama_models(url):
    with urllib.request.urlopen(f"{url}/api/tags", timeout=2) as resp:
        data = json.loads(resp.read())
        return [m['name'] for m in data.get('models',[])]

def with_provider(status, provider, provider_label):
    tagged = dict(status or {})
    tagged['provider'] = provider
    tagged['provider_label'] = provider_label
    return tagged

def _spawn_ollama_pull(binary):
    global OLLAMA_PULL_PROCESS
    with OLLAMA_LOCK:
        if OLLAMA_STATE['pulling']:
            return
        OLLAMA_STATE['pulling'] = True
        OLLAMA_STATE['pull_attempted'] = True
        OLLAMA_STATE['last_error'] = None
    creationflags = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
    try:
        OLLAMA_PULL_PROCESS = subprocess.Popen(
            [binary, 'pull', DEFAULT_OLLAMA_MODEL],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=creationflags
        )
    except Exception as exc:
        with OLLAMA_LOCK:
            OLLAMA_STATE['pulling'] = False
            OLLAMA_STATE['last_error'] = str(exc)
        return

    def _watch_pull():
        global OLLAMA_PULL_PROCESS
        try:
            OLLAMA_PULL_PROCESS.wait()
        finally:
            with OLLAMA_LOCK:
                OLLAMA_STATE['pulling'] = False
            OLLAMA_PULL_PROCESS = None

    threading.Thread(target=_watch_pull, daemon=True).start()

def bootstrap_ollama(wait_for_ready=0, auto_pull=True):
    global OLLAMA_PROCESS
    url = find_ollama()
    binary = ollama_binary()
    if not url and binary:
        with OLLAMA_LOCK:
            should_start = not OLLAMA_STATE['starting']
            if should_start:
                OLLAMA_STATE['starting'] = True
                OLLAMA_STATE['last_error'] = None
        if should_start:
            try:
                creationflags = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
                OLLAMA_PROCESS = subprocess.Popen(
                    [binary, 'serve'],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    creationflags=creationflags
                )
            except Exception as exc:
                with OLLAMA_LOCK:
                    OLLAMA_STATE['starting'] = False
                    OLLAMA_STATE['last_error'] = str(exc)
        deadline = time.time() + max(wait_for_ready, 0)
        while time.time() < deadline and not url:
            time.sleep(0.4)
            url = find_ollama()
        if url:
            with OLLAMA_LOCK:
                OLLAMA_STATE['starting'] = False

    if not url:
        status = 'missing_binary' if not binary else 'starting'
        message = 'OLLAMA is not installed.' if not binary else 'Starting local OLLAMA service...'
        return with_provider({'online': False, 'ready': False, 'url': None, 'models': [], 'status': status, 'message': message}, 'ollama', 'Ollama')

    try:
        models = list_ollama_models(url)
        with OLLAMA_LOCK:
            OLLAMA_STATE['starting'] = False
        if models:
            return with_provider({'online': True, 'ready': True, 'url': url, 'models': models, 'status': 'ready', 'message': 'Ollama ready'}, 'ollama', 'Ollama')
        if auto_pull and binary and not OLLAMA_STATE['pulling'] and not OLLAMA_STATE['pull_attempted']:
            _spawn_ollama_pull(binary)
        return with_provider({
            'online': True,
            'ready': False,
            'url': url,
            'models': [],
            'status': 'pulling' if OLLAMA_STATE['pulling'] else 'no_models',
            'message': f'Preparing local model {DEFAULT_OLLAMA_MODEL}...'
        }, 'ollama', 'Ollama')
    except Exception as exc:
        with OLLAMA_LOCK:
            OLLAMA_STATE['last_error'] = str(exc)
        return with_provider({'online': False, 'ready': False, 'url': url, 'models': [], 'status': 'error', 'message': str(exc)}, 'ollama', 'Ollama')

def detect_external_ai_provider(wait_for_ready_ollama=0, auto_pull_ollama=False):
    fallback_status = None
    for provider in OPENAI_COMPAT_PROVIDERS:
        status = probe_openai_provider(provider)
        if not status:
            continue
        if status.get('ready'):
            return status
        if fallback_status is None:
            fallback_status = status
    ollama_status = bootstrap_ollama(wait_for_ready=wait_for_ready_ollama, auto_pull=auto_pull_ollama)
    if ollama_status.get('ready'):
        return ollama_status
    return fallback_status or ollama_status

@app.route('/api/ai/status')
def ai_status():
    try:
        duckai_get_vqd()
        return jsonify({
            'online': True,
            'ready': True,
            'url': DUCKAI_WEB_URL,
            'models': [DUCKAI_MODEL],
            'provider': 'duckai',
            'provider_label': 'Duck.ai',
            'status': 'ready',
            'message': 'Duck.ai ready'
        })
    except Exception as exc:
        return jsonify({
            'online': False,
            'ready': False,
            'url': DUCKAI_WEB_URL,
            'models': [DUCKAI_MODEL],
            'provider': 'duckai',
            'provider_label': 'Duck.ai',
            'status': 'offline',
            'message': f'Duck.ai unavailable: {exc}'
        })

@app.route('/api/ai/chat', methods=['POST'])
def ai_chat():
    data = request.get_json() or {}
    prompt = data.get('prompt', '')
    context = data.get('context', '')
    mode = 'online'
    system = data.get('system', 'You are a helpful assistant integrated into Nexus Notes. Be concise and helpful.')
    system += " Answer using the official Duck.ai service and the provided Nexus Notes tab context when relevant."
    try:
        full_prompt = build_ai_full_prompt(prompt, context)
        content = (duckai_chat_full(system, full_prompt) or '').strip()
        if not content:
            raise RuntimeError('Duck.ai returned an empty response')
        return jsonify({
            'response': content,
            'model': DUCKAI_MODEL,
            'provider': 'duckai',
            'provider_label': 'Duck.ai',
            'online': True,
            'mode': mode,
            'status': 'ready'
        })
    except Exception as exc:
        return jsonify({
            'response': '',
            'model': DUCKAI_MODEL,
            'provider': 'duckai',
            'provider_label': 'Duck.ai',
            'online': False,
            'mode': mode,
            'status': 'offline',
            'message': f'Duck.ai unavailable: {exc}'
        }), 503


@app.route('/api/ai/stream', methods=['POST'])
def ai_stream():
    """Server-Sent Events streaming endpoint backed by Duck.ai."""
    data = request.get_json() or {}
    prompt = data.get('prompt', '')
    context = data.get('context', '')
    mode = 'online'
    system = data.get('system', 'You are a helpful assistant integrated into Nexus Notes. Be concise and helpful.')
    system += " Answer using the official Duck.ai service and the provided Nexus Notes tab context when relevant."

    full_prompt = build_ai_full_prompt(prompt, context)

    def generate_duckai():
        try:
            yield f"data: {json.dumps({'type':'meta','provider':'Duck.ai','model':DUCKAI_MODEL})}\n\n"
            for token in duckai_chat_stream(system, full_prompt):
                yield f"data: {json.dumps({'type':'token','text':token})}\n\n"
            yield f"data: {json.dumps({'type':'done'})}\n\n"
        except Exception as exc:
            message = f'Duck.ai is unavailable right now: {exc}'
            yield f"data: {json.dumps({'type':'meta','provider':'Duck.ai','model':DUCKAI_MODEL})}\n\n"
            yield f"data: {json.dumps({'type':'token','text':message})}\n\n"
            yield f"data: {json.dumps({'type':'done'})}\n\n"

    return Response(
        stream_with_context(generate_duckai()),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no',
        }
    )

@app.route('/api/duckai/open', methods=['POST'])
def duckai_open():
    opened = launch_browser_app(DUCKAI_WEB_URL)
    if not opened:
        try:
            webbrowser.open(DUCKAI_WEB_URL)
            opened = True
        except Exception:
            opened = False
    return jsonify({'opened': opened, 'url': DUCKAI_WEB_URL})


# ── ENTRYPOINT ──
def run_flask():
    app.run(host='127.0.0.1',port=5050,debug=False,use_reloader=False)

def set_windows_app_id():
    if not sys.platform.startswith('win'):
        return
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(WINDOWS_APP_ID)
    except Exception:
        pass
    # Also set via AppUserModelID property on the taskbar button
    try:
        import ctypes.wintypes
        HWND = ctypes.windll.user32.GetForegroundWindow()
        if HWND:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(WINDOWS_APP_ID)
    except Exception:
        pass

def launch_browser_app(url):
    candidates = [
        shutil.which('msedge'),
        shutil.which('chrome'),
        shutil.which('brave'),
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    ]
    browser = next((path for path in candidates if path and Path(path).exists()), None)
    if not browser:
        return False
    creationflags = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
    try:
        subprocess.Popen(
            [browser, f'--app={url}', '--window-size=1400,900'],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=creationflags
        )
        return True
    except Exception:
        return False

if __name__ == '__main__':
    init_db()
    set_windows_app_id()
    flask_thread = threading.Thread(target=run_flask,daemon=True)
    flask_thread.start()
    time.sleep(0.8)
    try:
        import webview
        window_kwargs = {
            'title': 'Nexus Notes',
            'url': 'http://127.0.0.1:5050',
            'width': 1400,
            'height': 900,
            'min_size': (900, 600),
            'resizable': True
        }
        icon_path = FRONTEND_DIR / 'static' / 'icon.ico'
        if icon_path.exists():
            try:
                import inspect
                sig = inspect.signature(webview.create_window)
                if 'icon' in sig.parameters:
                    window_kwargs['icon'] = str(icon_path)
            except Exception:
                pass
        window = webview.create_window(**window_kwargs)
        set_windows_app_id()  # re-apply after window creation
        webview.start()
    except ImportError:
        if not launch_browser_app('http://127.0.0.1:5050'):
            webbrowser.open('http://127.0.0.1:5050')
        try:
            while True: time.sleep(1)
        except KeyboardInterrupt: pass
