# IndieQA: 90-second pitch script

Per-slide speaker notes are in the deck (press **N** in the HTML version).

---

**[01 Title]** We're IndieQA, an autonomous QA bot for indie game studios.

**[02 Problem]** A human QA tester costs about $25 an hour, so small studios skip QA. Physics bugs like walking through walls, falling out of the map or getting stuck ship anyway, and players find them on launch day. That means negative Steam reviews and refunds, and nobody knows which inputs caused the bug.

**[03 Pipeline]** IndieQA plays your level by itself. The engine runs headless at a fixed 60 FPS, every frame is recorded, and a detector turns physics anomalies into bug reports with the last 30 button presses.

**[04 Agent]** To be precise, it's a rule-based agent, not ML and not an LLM. One mode hugs walls and edges, and the other spams button combos at them. It needs no training data, runs offline and is deterministic, so every bug is reproducible.

**[05 Proof]** We planted three bugs in a test level. The bot simulated ten minutes of play in about 2.5 seconds and found 22 wall clips, 48 infinite falls and 16 softlocks on its own.

**[07 Demo]** Live, with seed 11, it finds all three bugs in under 15 seconds.

**[09 Limits]** It doesn't test story logic, custom inertia physics will cause false positives, and procedural maps are hard.

**[10 Feasibility]** It costs about four cents an hour versus $25, and Unity and Godot plug-ins are next on the roadmap.

**[12]** Let the bot find the bug before your players do. Thank you.
