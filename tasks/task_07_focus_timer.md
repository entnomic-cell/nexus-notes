\# Task 07 — Endel-Style Adaptive Focus Timer



\## Objective

Add a built-in adaptive focus timer to Nexus \*\*directly\*\* without preliminary research.



\---



\## Core Principle

Timer must be modular, opt-in, and not interfere with other systems.



\---



\## Features to Add



\- Adjustable focus session length

\- Ambient focus modes (sound + visual cues optional)

\- Session tracking \& history

\- Pause/resume functionality

\- Notifications at session end

\- Optional integration with daily notes



\---



\## Technical Guidelines



\- Target timer module only.

\- Preserve existing workflows if timer is disabled.

\- Add optional toggles for new behaviors.

\- Patch should show diff before applying.

\- Maintain architecture patterns.



\---



\## Success Criteria



\- Users can start, pause, resume, and end sessions.

\- Focus mode behaves correctly (visuals, sounds optional).

\- Sessions are tracked and history persists.

\- Notifications appear on session end.

\- Daily note integration works if enabled.



\---



\## Execution Rules



\- Explain reasoning \*\*before coding\*\*.

\- Show patch diff \*\*before applying\*\*.

\- Implement \*\*modularly\*\*.

\- Stability > new features.

