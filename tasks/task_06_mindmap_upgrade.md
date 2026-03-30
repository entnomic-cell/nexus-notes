\# Task 06 — MindNode-Level Mindmap System



\## Objective

Upgrade Nexus’s mindmap to have MindNode-level features \*\*directly\*\* without preliminary research.



\---



\## Core Principle

Do not break existing mindmaps.  

Enhancements must be modular and opt-in if possible.



\---



\## Features to Add



\- Auto-layout of nodes

\- Collapsible/expandable branches

\- Focus mode (zoom into branch)

\- Keyboard navigation (arrows, shortcuts)

\- Drag \& drop reorganization

\- Node color/label styling

\- Undo/redo support



\---



\## Technical Guidelines



\- Target mindmap module only.

\- Maintain backward compatibility.

\- Add optional toggles for new behaviors.

\- Patch should show diff before applying.

\- Preserve existing architecture patterns.



\---



\## Success Criteria



\- Mindmap nodes auto-layout correctly.

\- Collapsing/expanding branches works.

\- Focus mode isolates a branch visually.

\- Keyboard navigation fully functional.

\- Drag \& drop reordering works intuitively.

\- Node styling applies correctly.

\- Undo/redo works for all changes.



\---



\## Execution Rules



\- Explain reasoning \*\*before coding\*\*.

\- Show patch diff \*\*before applying\*\*.

\- Implement \*\*modularly\*\*.

\- Stability > flashy features.

