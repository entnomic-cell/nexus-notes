\# Nexus Master Development Spec



\## Phase 1 — Stability Fixes



\### Task 01 — Context Menu Missing

Custom Nexus right-click menu does not appear.



Expected:

\- Appears globally

\- Overrides default menu



Investigate:

\- contextmenu event listeners

\- renderer permissions

\- preload scripts



Success:

Right click opens Nexus menu everywhere.





\### Task 02 — Text Editor Toolbar Missing

Editor formatting UI not rendering.



Investigate:

\- component mounting

\- editor initialization

\- CSS visibility

\- plugin loading



Success:

Toolbar visible and functional.





\### Task 03 — Websites Not Loading

Embedded browser fails to load AI websites.



Investigate:

\- CSP restrictions

\- iframe sandbox

\- user agent blocking

\- CORS limitations



Success:

AI websites load normally.





\---



\## Phase 2 — Customization System



Goal:

Add extensible settings architecture.



Features:

\- icon packs

\- layout presets

\- sidebar customization

\- theme system

\- workspace profiles





\---



\## Phase 3 — Competitive Features



Research Sources:

\- Evernote

\- Obsidian

\- Notion



Add:

\- bidirectional linking

\- databases/views

\- offline vault

\- quick capture

\- graph visualization





\---



\## Phase 4 — MindMap Upgrade

Inspired by MindNode:

\- auto layout

\- focus mode

\- collapsible branches

\- keyboard navigation





\---



\## Phase 5 — Focus Timer

Inspired by Endel:

\- adaptive timer

\- ambient focus mode

\- session tracking

