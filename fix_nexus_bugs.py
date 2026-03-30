#!/usr/bin/env python3
"""
Nexus Notes — Phase 1 Bug Fix Script
Fixes 3 bugs:
  Bug 1: Context menu doesn't appear on headings / list items
  Bug 2: Formatting toolbar hidden after any view switch
  Bug 3: AI website sidebar shows blocked-screen immediately for known providers
         instead of wasting a network round-trip trying to load them in an iframe

Run from anywhere:
  python fix_nexus_bugs.py

It patches files in-place and prints a summary.
"""

import sys
import pathlib
import shutil
import datetime

# ── Locate project root ───────────────────────────────────────────────────────
SCRIPT_DIR = pathlib.Path(__file__).parent
NEXUS_DIR  = SCRIPT_DIR

INDEX_HTML  = NEXUS_DIR / "frontend" / "index.html"
ENGINE_JS   = NEXUS_DIR / "frontend" / "static" / "context-menu-engine.js"

for p in (INDEX_HTML, ENGINE_JS):
    if not p.exists():
        sys.exit(f"ERROR: Cannot find {p}\nMake sure this script sits next to the nexus_app/ folder.")

# ── Helpers ───────────────────────────────────────────────────────────────────
def backup(path: pathlib.Path):
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    dest  = path.with_suffix(path.suffix + f".bak_{stamp}")
    shutil.copy2(path, dest)
    print(f"  backed up → {dest.name}")

def patch(path: pathlib.Path, old: str, new: str, description: str) -> bool:
    text = path.read_text(encoding="utf-8")
    if old not in text:
        print(f"  ✗ SKIP  ({description}) — search string not found in {path.name}")
        return False
    count = text.count(old)
    if count > 1:
        print(f"  ✗ SKIP  ({description}) — search string found {count}× (ambiguous), aborting this patch")
        return False
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    print(f"  ✓ FIXED ({description})")
    return True


# ═════════════════════════════════════════════════════════════════════════════
# BUG 1  — Context menu disappears on headings & list items
# ─────────────────────────────────────────────────────────────────────────────
# Root cause:
#   ContextResolver adds 'heading-block' or 'list-block' to context.kinds when
#   the user right-clicks a <h1-3> or <li> inside the editor.  Those kinds are
#   mutually exclusive with 'text-block' (the guard excludes headings/list items)
#   and with 'note-background' (same guard).  Because no provider was registered
#   for heading-block or list-block, collectActions() returned [] and openFromEvent
#   silently bailed out without calling event.preventDefault() — giving the user
#   the native browser menu or nothing.
#
# Fix:
#   Add two lightweight providers at the end of context-menu-engine.js, just
#   before the app-background provider.  They reuse actions already implemented
#   in the engine (formatting, insert helpers).
# ─────────────────────────────────────────────────────────────────────────────
BUG1_OLD = "  registerContextMenu('app-background',{priority:80,"

BUG1_NEW = """\
  registerContextMenu('heading-block',{priority:97,matches:ctx=>ctx.kinds.has('heading-block'),getActions:()=>[
    makeAction('Undo',{icon:'undo',hint:'Ctrl+Z',run:()=>fmt('undo')}),
    makeAction('Redo',{icon:'redo',hint:'Ctrl+Y',run:()=>fmt('redo')}),
    makeAction('Copy',{icon:'copy',hint:'Ctrl+C',run:()=>window.contextActions.copySelection()}),
    makeAction('Paste',{icon:'paste',hint:'Ctrl+V',run:()=>window.contextActions.pasteSelection()}),
    makeAction('Insert Link',{icon:'link2',run:()=>insertLink()}),
    makeAction('Find & Replace',{icon:'search',run:()=>openFindReplace()})
  ]});
  registerContextMenu('list-block',{priority:95,matches:ctx=>ctx.kinds.has('list-block'),getActions:()=>[
    makeAction('Undo',{icon:'undo',hint:'Ctrl+Z',run:()=>fmt('undo')}),
    makeAction('Redo',{icon:'redo',hint:'Ctrl+Y',run:()=>fmt('redo')}),
    makeAction('Cut',{icon:'scissors',hint:'Ctrl+X',run:()=>window.contextActions.cutSelection()}),
    makeAction('Copy',{icon:'copy',hint:'Ctrl+C',run:()=>window.contextActions.copySelection()}),
    makeAction('Paste',{icon:'paste',hint:'Ctrl+V',run:()=>window.contextActions.pasteSelection()}),
    makeAction('Insert Link',{icon:'link2',run:()=>insertLink()}),
    makeAction('Indent',{icon:'edit',run:()=>indentSelection()}),
    makeAction('Outdent',{icon:'edit',run:()=>outdentSelection()}),
    makeAction('Find & Replace',{icon:'search',run:()=>openFindReplace()})
  ]});
  registerContextMenu('app-background',{priority:80,"""

# ═════════════════════════════════════════════════════════════════════════════
# BUG 2  — Formatting toolbar stays hidden after any view switch
# ─────────────────────────────────────────────────────────────────────────────
# Root cause:
#   switchView() sets fmtBar.style.display='none' (inline style) when leaving
#   normal view.  When returning to normal it only adds the CSS class .visible,
#   but an inline style always beats a class rule.  So the toolbar never
#   reappears after the user visits Table / Kanban / Calendar / Gallery / Inbox.
#
# Fix:
#   Clear the inline style before adding the class so CSS takes over properly.
# ─────────────────────────────────────────────────────────────────────────────
BUG2_OLD = (
    "  if(fmtBar && v!=='normal') fmtBar.style.display='none';\n"
    "  if(fmtBar && v==='normal' && settings.toolbar) fmtBar.classList.add('visible');"
)

BUG2_NEW = (
    "  if(fmtBar && v!=='normal'){ fmtBar.style.display='none'; fmtBar.classList.remove('visible'); }\n"
    "  if(fmtBar && v==='normal' && settings.toolbar){ fmtBar.style.display=''; fmtBar.classList.add('visible'); }"
)

# ═════════════════════════════════════════════════════════════════════════════
# BUG 3  — AI sidebar tries (and fails) to iframe ChatGPT / Claude / Gemini
# ─────────────────────────────────────────────────────────────────────────────
# Root cause:
#   ChatGPT, Claude.ai, Gemini and Perplexity all respond with
#   "X-Frame-Options: DENY" or "Content-Security-Policy: frame-ancestors 'none'".
#   Browsers enforce these headers unconditionally — no client code can bypass
#   them.  The app sets the iframe src, the browser refuses to render it, the
#   onload probe detects about:blank and eventually shows the blocked screen —
#   but only after a multi-second wait and a failed network round-trip.
#
# Fix:
#   Maintain a compile-time set of known-blocked providers and skip straight to
#   the blocked-screen UI for them without touching the iframe.
#   Duck.ai is the only listed provider that allows embedding and continues to
#   load normally.  If a provider is force-reloaded (force=true) we still try,
#   so the user can always retry manually.
# ─────────────────────────────────────────────────────────────────────────────
BUG3_OLD = """\
function duckEnsureSiteLoaded(force=false){
  const provider=AI_WEBSITE_PROVIDERS[aiMode]||AI_WEBSITE_PROVIDERS.duck;
  const frame=document.getElementById('duck-site-frame');
  if(!frame)return;
  clearTimeout(duckEmbedProbeTimer);
  if(force)blockedEmbedProviders.delete(aiMode);
  duckHideBlocked();
  if(force || frame.dataset.provider!==aiMode || !frame.src || frame.src==='about:blank'){"""

BUG3_NEW = """\
// Providers known to send X-Frame-Options:DENY — skip the iframe attempt entirely.
const KNOWN_IFRAME_BLOCKED=new Set(['chatgpt','claude','gemini','perplexity']);

function duckEnsureSiteLoaded(force=false){
  const provider=AI_WEBSITE_PROVIDERS[aiMode]||AI_WEBSITE_PROVIDERS.duck;
  const frame=document.getElementById('duck-site-frame');
  if(!frame)return;
  clearTimeout(duckEmbedProbeTimer);
  if(force)blockedEmbedProviders.delete(aiMode);
  duckHideBlocked();
  // Fast-path: skip the iframe for providers that always block embedding.
  // User can still force a retry via the reload button.
  if(!force && KNOWN_IFRAME_BLOCKED.has(aiMode)){
    duckMarkProviderBlocked(provider);
    return;
  }
  if(force || frame.dataset.provider!==aiMode || !frame.src || frame.src==='about:blank'){"""

# ═════════════════════════════════════════════════════════════════════════════
# Run all patches
# ─────────────────────────────────────────────────────────────────────────────
print("\n── Nexus Notes Phase 1 Bug Fixer ──\n")

print("Backing up files…")
backup(INDEX_HTML)
backup(ENGINE_JS)

print("\nApplying patches…")
results = [
    patch(ENGINE_JS,   BUG1_OLD, BUG1_NEW, "Bug 1 — heading/list context menu providers"),
    patch(INDEX_HTML,  BUG2_OLD, BUG2_NEW, "Bug 2 — toolbar inline-style override"),
    patch(INDEX_HTML,  BUG3_OLD, BUG3_NEW, "Bug 3 — skip iframe for known-blocked AI sites"),
]

ok  = sum(results)
bad = len(results) - ok
print(f"\nDone — {ok}/{len(results)} patches applied" + (f", {bad} skipped (see above)" if bad else " ✓"))
