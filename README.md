# Nexus Notes — Build & Run Guide

## Quick Start (Dev)

```bash
# 1. Install dependencies
pip install flask flask-cors pyinstaller requests openai

# 2. Run in dev mode
python backend/app.py

# 3. Open browser to http://127.0.0.1:5050
```

App auto-opens in your browser on launch.
Data is saved to: `~/NexusNotes/nexus.db` (SQLite)

---

## Build .exe (Windows)

```bash
# From the nexus/ project root:
pip install flask flask-cors pyinstaller

pyinstaller nexus.spec
```

Output: `dist/NexusNotes.exe`

Double-click to run. No Python needed. No installer needed.
On first launch it opens your browser to http://127.0.0.1:5050 automatically.

---

## Build on macOS

```bash
pyinstaller nexus.spec
# Output: dist/NexusNotes (Unix binary)
```

## Build on Linux

```bash
pyinstaller nexus.spec
# Output: dist/NexusNotes
```

---

## Project Structure

```
nexus/
├── backend/
│   └── app.py          ← Flask API + SQLite
├── frontend/
│   └── index.html      ← Full UI (single file, no framework)
├── data/               ← Created at runtime (gitignore this)
│   └── nexus.db        ← SQLite database
├── nexus.spec          ← PyInstaller build spec
└── README.md
```

---

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /api/notes | List all notes |
| POST | /api/notes | Create note |
| GET | /api/notes/:id | Get note |
| PUT | /api/notes/:id | Update note (auto-saves version) |
| DELETE | /api/notes/:id | Soft delete |
| GET | /api/search?q= | Full-text search (FTS5) |
| GET | /api/notes/:id/backlinks | Incoming + outgoing [[links]] |
| GET | /api/notes/:id/versions | Version history (last 20) |
| POST | /api/notes/:id/versions/:vid/restore | Restore version |
| GET | /api/graph | All nodes + edges for graph view |
| GET | /api/tags | All tags with counts |
| GET | /api/tags/:tag/notes | Notes with tag |
| GET | /api/folders | Folder list with counts |
| GET | /api/stats | Workspace stats |

---

## AI Feature

The AI bar calls the Anthropic API directly from the browser.
To enable it, either:
1. Add a proxy route in app.py that forwards to Anthropic with your API key
2. Or add your API key to the fetch call in index.html (local dev only)

---

## Data

All notes stored in SQLite at `~/NexusNotes/nexus.db`.
Backup: just copy that file.
The database uses WAL mode for performance and FTS5 for full-text search.

Backlinks are auto-parsed from `[[Note Title]]` syntax on every save.
Version history keeps the last 20 versions per note.
