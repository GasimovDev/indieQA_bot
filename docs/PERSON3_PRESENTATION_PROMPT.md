# Person 3 — Presentation Prompt

> **How to use:** copy everything inside the box below into your AI tool (ChatGPT / Claude / Gamma / etc.) to draft the deck.
> Then fill the `[SCREENSHOT]` placeholders and re-check the numbers marked ⏳ with the team before 19:30.
> **Deadline:** PDF or PPT, **≤ 30 MB**, submitted **before 20:00**.

---

```text
You are helping me build a hackathon pitch deck. Write the slide-by-slide content (title, 3–5 short bullets,
speaker notes ~40 words, and a visual suggestion per slide). Keep text minimal, judges skim. Max 12 slides.
Tone: confident, concrete, honest. Never invent numbers; use only the facts below.

=== EVENT ===
Neurobridge Game Summit 2026 Hackathon, Baku. Team of 4. Product: IndieQA.
Judging weights we must hit explicitly:
- User Value (25 pts): Steam launch risk reduction — preventing negative reviews from launch-day collision bugs.
- Quality Testing (20 pts): must explicitly state the 3 Failure Modes of IndieQA (listed below).
- Feasibility (15 pts): unit economics, zero training data, integration path into Unity and Godot.
Deliverable: PDF/PPT under 30 MB.

=== ONE-LINER ===
IndieQA is an autonomous QA bot for indie game studios: it plays your level thousands of times faster than
a human, hunts physics and collision bugs, and hands you a dashboard with every bug, where it happened on
the map, and the exact button sequence to reproduce it.

=== PROBLEM ===
- Indie studios can't afford QA teams; a human QA tester costs ~$25/hour.
- Physics/collision bugs (walking through walls, falling out of the map, getting stuck) are easy to miss
  by hand and show up on launch day as negative Steam reviews and refund requests.
- Reproducing such bugs is slow: testers often can't say exactly which inputs caused them.

=== SOLUTION: HOW IT WORKS (5 steps, use as a pipeline diagram) ===
1. Autonomous agent plays the level (no human).
2. Game engine simulates physics at a fixed 60 FPS; runs headless (no window) far faster than real time.
3. Telemetry records every frame: position, velocity, buttons pressed, grounded, collision.
4. Bug detector classifies physics anomalies from the telemetry and writes a report per bug
   (type, severity, location, last 30 inputs = reproduction steps).
5. Web dashboard (our website, runs locally in the browser): coverage heatmap of where the bot went,
   red markers where bugs happened, filterable bug log, export, and the cost comparison banner.

=== THE AGENT ("where is the AI") — describe accurately ===
It is an autonomous, rule-based agent (a state machine), NOT machine learning and NOT an LLM. Two modes:
- Boundary_Seeker: senses the level with raycasts (wall ahead?) and ground probes (ledge ahead?), walks to
  walls, edges and corners and hugs them — where collision bugs live.
- Input_Spammer: when touching a wall, fires rapid non-linear button combos (diagonal + jump, direction
  toggles) to force the physics into broken states.
Selling points of this design: zero training data, runs fully offline, deterministic (same seed = identical
run, so every bug is 100% reproducible), explainable, cheap.

=== DETECTION RULES (physics signatures) ===
- Wall Clip: moved > 25 px in a single frame while colliding with geometry.
- Infinite Fall: > 120 consecutive frames falling without touching anything.
- Softlock: buttons held > 300 frames while the player moved < 5 px.
- Out of Bounds: position outside the map.

=== PROOF: OUR TEST LEVEL WITH 3 PLANTED BUGS ===
We built an 800x600 test level with 3 intentional bugs to prove the bot finds them on its own:
- Wall Clip: a 2-pixel seam in the right wall; jumping into it at speed teleports the player through the wall.
- Infinite Fall: a hole in the floor with no bottom and no reset.
- Softlock Pit: a pit 150 px deep while the player can only jump 100 px — stuck forever.

=== VERIFIED NUMBERS (measured by the team, safe to quote) ===
- 10 minutes of gameplay (36,000 frames) simulated in ~2.5 seconds headless → ~240x faster than real time.
- In that 10-minute run (seed 42) the bot, unaided, produced: 22 Wall Clips, 48 Infinite Falls,
  16 Softlocks across 65 attempts (episodes).
- Live demo (seed 11, real-time 60 FPS): Wall Clip at 1.4 s, Infinite Fall at 3.4 s, Softlock at 12.4 s —
  all three bugs found in under 15 seconds.
- Determinism: two runs with the same seed produced identical data on all 7,200/7,200 frames.
- Telemetry overhead: ~1 microsecond per frame on average (no frame drops at 60 FPS).
- Detector accuracy, checked automatically against the engine's ground truth over 4 runs (40 minutes of
  gameplay): 318 of 318 real bugs detected (100%): Wall Clip 81/81, Infinite Fall 163/163, Softlock 74/74,
  with 0 false alarms. Caveat to say honestly: this is on our own test level with planted bugs.

=== COST (unit economics) ===
- Human QA: ~$25/hour. IndieQA: ~$0.04/hour of local compute (team estimate; runs on any laptop).
- Plus: one IndieQA hour covers far more than one hour of gameplay because headless mode runs ~240x real time.
- No cloud, no API keys, no GPU, no training data.

=== FEASIBILITY / ROADMAP (be clear what is built vs planned) ===
Built today: Python + Pygame engine, autonomous agent, telemetry, detector, reporter, Streamlit web dashboard;
whole system runs locally with one command.
Planned (roadmap, NOT built yet — label it as such): plug-in integration into Unity (C#) and Godot (GDScript)
by streaming the same telemetry format over a WebSocket, so the same detector and dashboard work on real games.

=== QUALITY TESTING SLIDE: THE 3 FAILURE MODES (must be stated explicitly, word for word in meaning) ===
1. Cannot evaluate narrative or quest-sequencing logic (it tests physics, not story).
2. High false-positive rate on non-standard physics engines with custom inertia curves (thresholds like
   25 px/frame assume standard platformer physics).
3. Struggles with procedurally generated maps that have no static geometry reference.
Also mention how we validate ourselves: a planted-bug test level + an automatic check comparing detector
output against the engine's ground truth (found / missed / false alarms per bug type).

=== THE WEBSITE (must appear in the deck + demo) ===
The dashboard is a local website (Streamlit, opens in the browser at localhost) showing:
- Header: game time tested, frames analysed, bugs found, "Human QA $25/h vs IndieQA $0.04/h" banner.
- Map: heatmap of where the bot explored + red markers at every bug location.
- Bug log: filterable by severity/type; each bug has its reproduction sequence (last 30 inputs).
- Export of bug reports (Markdown).
[SCREENSHOT: dashboard overview]  [SCREENSHOT: map with red bug markers]  [SCREENSHOT: bug detail]

=== LIVE DEMO PLAN (put on a slide + speaker notes) ===
1. `python main.py --seed 11` — game window: the bot clips through the wall (1.4 s), falls forever (3.4 s),
   gets stuck in the pit (12.4 s). On-screen counter shows bugs as they happen.
2. `python main.py --headless --frames 36000 --analyze` — 10 minutes of testing in ~3 seconds.
3. `streamlit run dashboard/app.py` — open the website, show map, bug list, one bug's reproduction steps.
Backup: screenshots/video in the deck in case the live demo fails.
[SCREENSHOT: game window mid-glitch]

=== SUGGESTED SLIDE ORDER ===
1 Title + one-liner · 2 Problem (Steam launch-day reviews) · 3 Solution pipeline · 4 The agent (where the
"AI" is, honestly) · 5 Planted-bug proof + numbers · 6 The website (screenshots) · 7 Live demo ·
8 User value (Steam launch risk) · 9 Quality testing: 3 failure modes + how we validate · 10 Feasibility:
$0.04/h, zero training data, Unity/Godot roadmap · 11 Team (4 people: engine/agent, detection, website,
pitch) · 12 Ask / next steps.

Output: slide-by-slide content as described, then a 90-second spoken pitch script.
```

---

### Checklist for Person 3
- [ ] Screenshots from Person 4 (website) and Person 1 (game window: `python main.py --seed 11`)
- [x] Detector results filled in: 318/318 found, 0 false alarms (4 seeds, `--verify`)
- [ ] Unity/Godot integration is shown as **roadmap**, not as built
- [ ] Export PDF, check size **< 30 MB**, submit **before 20:00**
