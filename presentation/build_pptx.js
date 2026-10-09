// Build IndieQA_Pitch.pptx: a native, editable rebuild of "IndieQA Pitch.html".
// Geometry is carried over from the 1920x1080 HTML grid: 144 px = 1 inch, 1 px = 0.5 pt.
const path = require("path");
const pptxgen = require("pptxgenjs");
const { applyTheme } = require(process.env.PPTX_SKILL + "/scripts/apply_theme.js");

const DECK = "C:/Users/Fidan-HP/Desktop/instruction/IndieQA_Deck";
const OUT = path.join(DECK, "IndieQA_Pitch.pptx");
const IMG = (f) => path.join(DECK, "img", f);

const THEME = {
  name: "IndieQA Swiss",
  headFontFace: "Arial",
  bodyFontFace: "Arial",
  colors: {
    dk1: "0F0F0E", lt1: "F4F3EF", dk2: "6A6964", lt2: "E9E7E0",
    accent1: "D7261E", accent2: "D3D1C8", accent3: "FFF3A6", accent4: "FFFFFF",
    accent5: "A9A79F", accent6: "4A4A47", hlink: "D7261E", folHlink: "6A6964",
  },
};
const MONO = "Consolas";

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE"; // 13.333 x 7.5 in
pres.title = "IndieQA Pitch";
pres.author = "IndieQA team";
pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };
const C = pres.SchemeColor;
const INK = C.text1, PAPER = C.background1, MUTED = C.text2, SOFT = C.background2;
const RED = C.accent1, RULE = C.accent2, FILL = C.accent3, GREY = C.accent5, DRULE = C.accent6;

const M = 0.78, W = 13.333, CW = W - 2 * M, R = W - M;

// ---------- layouts ----------
function railObjects(dark) {
  const line = dark ? PAPER : INK, sub = dark ? GREY : MUTED;
  return [
    { line: { x: M, y: 0.78, w: CW, h: 0, line: { color: line, width: 1.5 } } },
    { placeholder: { options: { name: "rail", type: "body", x: 1.61, y: 0.86, w: 7.2, h: 0.32, margin: 0, fontFace: MONO, fontSize: 11, color: sub, charSpacing: 1, valign: "middle" }, text: "" } },
    { placeholder: { options: { name: "tag", type: "body", x: 7.0, y: 0.86, w: R - 7.0, h: 0.32, margin: 0, fontFace: MONO, fontSize: 11, color: sub, align: "right", valign: "middle" }, text: "" } },
  ];
}
const slideNumber = (dark) => ({ x: M, y: 0.86, w: 0.6, h: 0.32, fontFace: MONO, fontSize: 11, bold: true, color: dark ? PAPER : INK, margin: 0, valign: "middle" });

pres.defineSlideMaster({
  title: "IndieQA Dark", background: { color: INK },
  objects: railObjects(true), slideNumber: slideNumber(true),
});
pres.defineSlideMaster({
  title: "IndieQA Content", background: { color: PAPER },
  objects: [
    ...railObjects(false),
    { placeholder: { options: { name: "title", type: "title", x: M, y: 1.45, w: CW, h: 1.4, margin: 0, fontSize: 44, bold: true, color: INK, align: "left", valign: "top", lineSpacingMultiple: 0.92 }, text: "" } },
  ],
  slideNumber: slideNumber(false),
});
pres.defineSlideMaster({
  title: "IndieQA Content No Title", background: { color: PAPER },
  objects: railObjects(false), slideNumber: slideNumber(false),
});

// ---------- helpers ----------
let sec = "";
function newSlide(layout, section, rail, tag, notes) {
  if (section !== sec) { pres.addSection({ title: section }); sec = section; }
  const s = pres.addSlide({ masterName: layout, sectionTitle: section });
  s.addText(rail.toUpperCase(), { placeholder: "rail" });
  s.addText(tag, { placeholder: "tag" });
  s.addNotes(notes);
  return s;
}
const T = (s, text, o) => s.addText(text, { isTextBox: true, margin: 0, valign: "top", ...o });
const hline = (s, x, y, w, color, width = 0.75, dash) =>
  s.addShape(pres.shapes.LINE, { x, y, w, h: 0, line: { color, width, ...(dash ? { dashType: dash } : {}) } });
const vline = (s, x, y, h, color) => s.addShape(pres.shapes.LINE, { x, y, w: 0, h, line: { color, width: 0.75 } });
const kicker = (s, text, x, y, w, color = MUTED) =>
  T(s, text.toUpperCase(), { x, y, w, h: 0.28, fontFace: MONO, fontSize: 10, color, charSpacing: 2 });
function footer(s, left, right, dark) {
  hline(s, M, 6.37, CW, dark ? DRULE : RULE);
  T(s, left, { x: M, y: 6.48, w: 6.5, h: 0.3, fontFace: MONO, fontSize: 10, color: dark ? GREY : MUTED });
  T(s, right, { x: R - 5.5, y: 6.48, w: 5.5, h: 0.3, fontFace: MONO, fontSize: 10, color: dark ? GREY : MUTED, align: "right" });
}
const fillTag = (s, text, x, y, w, size = 12) =>
  T(s, text, { x, y, w, h: 0.32, fontFace: MONO, fontSize: size, color: INK, fill: { color: FILL }, margin: 4, valign: "middle", objectName: "Fill in" });

// ---------- 01 title ----------
{
  const s = newSlide("IndieQA Dark", "Opening", "Neurobridge Game Summit 2026 · Baku", "Hackathon pitch",
    "We're IndieQA. Small studios can't afford QA teams, so physics bugs ship. Our bot plays your level on its own, far faster than a human, finds collision bugs and tells you exactly how to reproduce each one.");
  T(s, [{ text: "Indie", options: { color: PAPER } }, { text: "QA", options: { color: RED } }],
    { x: M - 0.08, y: 1.55, w: 10, h: 2.3, fontSize: 150, bold: true, charSpacing: -6, objectName: "Wordmark" });
  T(s, "An autonomous QA bot for indie studios. It plays your level ~240× faster than real time, hunts physics and collision bugs, and hands you every bug with where it happened and the exact buttons to reproduce it.",
    { x: M, y: 4.15, w: 9.4, h: 1.75, fontSize: 22, color: PAPER, lineSpacingMultiple: 1.1, objectName: "One-liner" });
  footer(s, "Team of 4", "github.com/GasimovDev/indieQA_bot", true);
}

// ---------- 02 problem ----------
{
  const s = newSlide("IndieQA Content", "Problem & solution", "Problem", "User value",
    "A human QA tester costs about $25 an hour. Physics bugs like clipping or falling out of the map are easy to miss by hand, and they show up on launch day as negative Steam reviews and refunds. Even when found, nobody knows the exact inputs.");
  s.addText("Collision bugs ship. Players find them on launch day", { placeholder: "title" });
  const items = [
    "Indie studios can't afford a QA team.",
    "Walking through walls, falling out of the map, getting stuck: easy to miss by hand.",
    "They surface as negative Steam reviews and refund requests.",
    "Testers often can't say which inputs caused the bug, so reproducing it is slow.",
  ];
  let y = 3.2;
  items.forEach((t, i) => {
    hline(s, M, y, 7.4, RULE);
    T(s, t, { x: M, y: y + 0.05, w: 7.4, h: 0.68, valign: "middle", fontSize: 16, color: INK, objectName: `Problem ${i + 1}` });
    y += 0.78;
  });
  hline(s, M, y, 7.4, RULE);
  kicker(s, "Human QA tester", 8.9, 4.05, 3.66);
  T(s, [{ text: "$25", options: { fontSize: 100, bold: true, charSpacing: -3 } }, { text: " /h", options: { fontSize: 40, bold: true } }],
    { x: 8.85, y: 4.3, w: 3.9, h: 1.55, color: INK, valign: "bottom", objectName: "Cost stat" });
  T(s, "and still misses physics edge cases", { x: 8.9, y: 6.0, w: 3.66, h: 0.3, fontFace: MONO, fontSize: 11, color: MUTED });
}

// ---------- 03 pipeline ----------
{
  const s = newSlide("IndieQA Content", "Problem & solution", "Solution · How it works", "One command, runs locally",
    "Five steps. The agent plays, the engine simulates physics at a fixed 60 FPS without a window, telemetry records every frame, the detector turns anomalies into bug reports with the last 30 inputs, and the dashboard shows it all in the browser.");
  s.addText("From autonomous play to a bug report you can replay", { placeholder: "title" });
  const steps = [
    ["Agent plays", "An autonomous agent plays the level. No human at the controls.", "buttons →"],
    ["Engine simulates", "Fixed 60 FPS physics, headless (no window), far faster than real time.", "frame state →"],
    ["Telemetry", "Every frame: position, velocity, buttons, grounded, collision.", "CSV →"],
    ["Bug detector", "Classifies physics anomalies. One report per bug: type, severity, location, last 30 inputs.", "reports →"],
    ["Dashboard", "Local website: coverage heatmap, red bug markers, filterable log, export.", "localhost"],
  ];
  hline(s, M, 3.25, CW, INK, 1.5);
  const cw = CW / 5;
  steps.forEach(([h, p, a], i) => {
    const x = M + i * cw, w = cw - 0.25;
    if (i > 0) vline(s, x - 0.12, 3.25, 2.85, RULE);
    T(s, String(i + 1).padStart(2, "0"), { x, y: 3.42, w, h: 0.3, fontFace: MONO, fontSize: 11, bold: true, color: RED });
    T(s, h, { x, y: 3.75, w, h: 0.75, fontSize: 21, bold: true, color: INK, lineSpacingMultiple: 0.95, objectName: `Step ${i + 1} title` });
    T(s, p, { x, y: 4.52, w, h: 1.25, fontSize: 14, color: INK, objectName: `Step ${i + 1} text` });
    T(s, a, { x, y: 5.85, w, h: 0.25, fontFace: MONO, fontSize: 10, color: MUTED });
  });
  footer(s, "Python · Pygame · Streamlit", "No cloud · no API keys · no GPU");
}

// ---------- 04 agent ----------
{
  const s = newSlide("IndieQA Content", "Problem & solution", "Where is the AI?", "Said honestly",
    "Judges will ask where the AI is. It's an autonomous rule-based agent, a two-mode state machine, not ML and not an LLM. One mode seeks boundaries, the other spams inputs at walls. That means no training data, offline, and every bug is 100% reproducible.");
  s.addText("An autonomous, rule-based agent built to break geometry", { placeholder: "title" });
  T(s, "State machine · not machine learning · not an LLM",
    { x: M, y: 2.98, w: 5.3, h: 0.36, fontFace: MONO, fontSize: 12, color: PAPER, fill: { color: INK }, margin: 6, valign: "middle", objectName: "Not ML badge" });
  const modes = [
    ["Mode 1", "Boundary_Seeker", INK, "Senses the level with raycasts (wall ahead?) and ground probes (ledge ahead?). Walks to walls, edges and corners and hugs them, because that's where collision bugs live."],
    ["Mode 2", "Input_Spammer", RED, "When touching a wall, fires rapid non-linear button combos (diagonal + jump, direction toggles) to force the physics into broken states."],
  ];
  const mw = (CW - 0.35) / 2;
  modes.forEach(([k, h, col, p], i) => {
    const x = M + i * (mw + 0.35);
    hline(s, x, 3.72, mw, INK, 1.5);
    kicker(s, k, x, 3.85, mw);
    T(s, h, { x, y: 4.12, w: mw, h: 0.45, fontFace: MONO, fontSize: 22, bold: true, color: col });
    T(s, p, { x, y: 4.62, w: mw, h: 1.15, fontSize: 15, color: INK, objectName: `${h} text` });
  });
  const traits = [["Zero training data", "works day one"], ["Fully offline", "runs on a laptop"], ["Deterministic", "same seed = same run"], ["Explainable", "every decision is a rule"], ["Cheap", "~$0.04/h compute"]];
  hline(s, M, 6.1, CW, RULE);
  traits.forEach(([b, sm], i) => {
    const x = M + i * (CW / 5);
    T(s, b, { x, y: 6.22, w: CW / 5 - 0.15, h: 0.3, fontSize: 14, bold: true, color: INK });
    T(s, sm, { x, y: 6.55, w: CW / 5 - 0.15, h: 0.25, fontFace: MONO, fontSize: 10, color: MUTED });
  });
}

// ---------- 05 proof ----------
{
  const s = newSlide("IndieQA Content", "Proof", "Proof · Planted-bug test level", "800 × 600 px · seed 42",
    "We built a test level with three bugs planted on purpose. In a 10-minute run, simulated in about 2.5 seconds, the bot produced 22 wall clips, 48 infinite falls and 16 softlocks across 65 attempts. Same seed twice gave identical data on all 7,200 frames.");
  s.addText("We planted 3 bugs. The bot found them on its own", { placeholder: "title" });
  const hdr = (t) => ({ text: t.toUpperCase(), options: { fontFace: MONO, fontSize: 9, color: MUTED, charSpacing: 1, border: [{ type: "none" }, { type: "none" }, { pt: 1.5, color: INK }, { type: "none" }] } });
  const rowB = { border: [{ type: "none" }, { type: "none" }, { pt: 0.75, color: RULE }, { type: "none" }] };
  const bug = (name, sub) => ({ text: [{ text: name, options: { bold: true, breakLine: !!sub } }, ...(sub ? [{ text: sub, options: { color: MUTED, fontSize: 12 } }] : [])], options: rowB });
  const cell = (t) => ({ text: t, options: rowB });
  const num = (t, col) => ({ text: t, options: { ...rowB, fontFace: MONO, fontSize: 20, bold: true, color: col } });
  s.addTable([
    [hdr("Planted bug"), hdr("Detection signature"), hdr("Hits")],
    [bug("Wall Clip", "2-px seam in the right wall"), cell("> 25 px in one frame while colliding"), num("22", RED)],
    [bug("Infinite Fall", "hole with no bottom, no reset"), cell("> 120 frames falling, touching nothing"), num("48", RED)],
    [bug("Softlock Pit", "150 px deep, jump is 100 px"), cell("buttons held > 300 frames, moved < 5 px"), num("16", RED)],
    [bug("Out of Bounds"), cell("position outside the map"), num("—", MUTED)],
  ], { x: M, y: 3.0, w: 7.0, colW: [2.25, 3.95, 0.8], rowH: [0.32, 0.66, 0.66, 0.66, 0.5], fontSize: 14, color: INK, margin: [4, 6, 4, 0], valign: "middle", objectName: "Planted bug table" });
  s.addImage({ path: IMG("level_map.png"), x: 8.36, y: 3.0, w: 4.2, h: 3.15, altText: "IndieQA test level map with the three planted bugs", objectName: "Level map" });
  s.addShape(pres.shapes.RECTANGLE, { x: 8.36, y: 3.0, w: 4.2, h: 3.15, fill: { type: "none" }, line: { color: INK, width: 0.75 } });
  const stats = [["36,000", "frames = 10 min of play"], ["~2.5 s", "headless → ~240× real time"], ["65", "episodes, unaided"], ["7,200/7,200", "identical frames, same seed"]];
  hline(s, M, 6.33, CW, INK, 1.5);
  stats.forEach(([b, l], i) => {
    const x = M + i * (CW / 4);
    T(s, b, { x, y: 6.4, w: CW / 4 - 0.1, h: 0.55, fontSize: 30, bold: true, color: INK, charSpacing: -1 });
    T(s, l, { x, y: 6.95, w: CW / 4 - 0.1, h: 0.25, fontFace: MONO, fontSize: 10, color: MUTED });
  });
}

// ---------- 06 website ----------
{
  const s = newSlide("IndieQA Content", "Proof", "The website", "Streamlit · localhost in your browser",
    "This is the dashboard, a local website. The top shows how much gameplay we tested and the cost banner. The map shows where the bot went and red markers at every bug. Click a bug to see the exact 30 inputs that cause it, and export the report.");
  s.addText("Every bug, where it happened, and how to replay it", { placeholder: "title" });
  const ph = [
    [M, 4.55, "[SCREENSHOT: dashboard overview]\nheader · time tested · frames · bugs · $25/h vs $0.04/h"],
    [M + 4.85, 3.6, "[SCREENSHOT: map with red bug markers]"],
    [M + 8.7, 3.08, "[SCREENSHOT: bug detail]\nlast 30 inputs"],
  ];
  ph.forEach(([x, w, t], i) => s.addText(t, {
    isTextBox: true, x, y: 3.0, w, h: 2.5, align: "center", valign: "middle", fontFace: MONO, fontSize: 12, color: MUTED,
    fill: { color: SOFT }, line: { color: MUTED, width: 1, dashType: "dash" }, objectName: `Screenshot placeholder ${i + 1}`,
  }));
  const feats = [["Header", "game time tested, frames analysed, bugs found, cost banner"], ["Map", "heatmap of where the bot explored, red marker at every bug"], ["Bug log", "filter by severity / type, reproduction sequence per bug"], ["Export", "bug reports as Markdown"]];
  feats.forEach(([b, p], i) => {
    const x = M + i * (CW / 4);
    T(s, [{ text: b, options: { bold: true, color: INK, breakLine: true } }, { text: p, options: { color: MUTED } }],
      { x, y: 5.75, w: CW / 4 - 0.3, h: 0.95, fontSize: 14 });
  });
}

// ---------- 07 demo ----------
{
  const s = newSlide("IndieQA Content", "Proof", "Live demo", "Backup: screenshots in this deck",
    "Live: seed 11 in real time. Watch it clip through the wall at 1.4 seconds, fall forever at 3.4, and get stuck in the pit at 12.4. Then headless: ten minutes of play in about three seconds. Then the dashboard. If the demo fails, this screenshot is the backup.");
  s.addText("All three bugs in under 15 seconds", { placeholder: "title" });
  const cmd = (t, y) => T(s, t, { x: M, y, w: 6.3, h: 0.38, fontFace: MONO, fontSize: 13, color: PAPER, fill: { color: INK }, margin: 6, valign: "middle" });
  const step = (rich, y) => { hline(s, M, y, 6.3, RULE); T(s, rich, { x: M, y: y + 0.1, w: 6.3, h: 0.32, fontSize: 14, color: INK }); };
  step([{ text: "1 · Watch it play", options: { bold: true } }, { text: "  (real time, 60 FPS)" }], 2.95);
  cmd("python main.py --seed 11", 3.38);
  [["1.4 s", "Wall Clip"], ["3.4 s", "Infinite Fall"], ["12.4 s", "Softlock"]].forEach(([t, l], i) => {
    const x = M + i * 1.75;
    T(s, t, { x, y: 3.85, w: 1.7, h: 0.5, fontSize: 28, bold: true, color: RED });
    T(s, l, { x, y: 4.35, w: 1.7, h: 0.25, fontFace: MONO, fontSize: 11, color: INK });
  });
  step([{ text: "2 · 10 minutes of testing in ~3 seconds", options: { bold: true } }], 4.78);
  cmd("python main.py --headless --frames 36000 --analyze", 5.2);
  step([{ text: "3 · Open the website", options: { bold: true } }, { text: ": map, bug list, one bug's steps" }], 5.72);
  cmd("streamlit run dashboard/app.py", 6.14);
  s.addImage({ path: IMG("game_seed11_all3.png"), x: 7.56, y: 2.95, w: 5.0, h: 3.75, altText: "Game window at frame 744, seed 11: player stuck in the Softlock Pit, HUD shows all three glitches found", objectName: "Game screenshot" });
  s.addShape(pres.shapes.RECTANGLE, { x: 7.56, y: 2.95, w: 5.0, h: 3.75, fill: { type: "none" }, line: { color: INK, width: 0.75 } });
  T(s, "Game window, seed 11, frame 744 (12.4 s): stuck in the Softlock Pit, HUD shows all 3 glitches found",
    { x: 7.56, y: 6.76, w: 5.0, h: 0.4, fontFace: MONO, fontSize: 10, color: MUTED });
}

// ---------- 08 user value ----------
{
  const s = newSlide("IndieQA Content", "Value & limits", "User value", "Steam launch risk",
    "The value is launch risk. You find collision bugs before players do, you can re-run the bot on every build because it's so fast, and every bug comes with location and inputs, so a developer reproduces it immediately instead of guessing.");
  s.addText("Find the bug before it hits your reviews", { placeholder: "title" });
  const cols = [
    ["Before launch", "Collision bugs are caught on your machine, not in Steam reviews and refund requests.", INK],
    ["Every build", "10 minutes of play in ~2.5 s means you can re-test the level after every change.", INK],
    ["Fix fast", "Each bug ships with location + last 30 inputs. Same seed, same bug, 100% reproducible.", RED],
  ];
  const w = (CW - 0.6) / 3;
  cols.forEach(([k, p, col], i) => {
    const x = M + i * (w + 0.3);
    hline(s, x, 3.3, w, col, 1.5);
    kicker(s, k, x, 3.45, w, col === RED ? RED : MUTED);
    T(s, p, { x, y: 3.8, w, h: 1.6, fontSize: 19, bold: true, color: INK, lineSpacingMultiple: 1.05 });
  });
  footer(s, "Every bug report: type · severity · location · last 30 inputs", "Seed 42 · 10 min of play · 86 glitch events");
}

// ---------- 09 failure modes ----------
{
  const s = newSlide("IndieQA Content", "Value & limits", "Quality testing", "Where IndieQA fails",
    "We know where we fail. One, no narrative or quest logic. Two, custom inertia physics will cause false positives because our thresholds assume a standard platformer. Three, procedural maps with no static geometry. We validate ourselves against the engine's ground truth: wall clip is 22 of 22.");
  s.addText("Three failure modes we state up front", { placeholder: "title" });
  const fm = [
    ["Cannot evaluate narrative or quest-sequencing logic.", "It tests physics, not story."],
    ["High false-positive rate on non-standard physics with custom inertia curves.", "Thresholds like 25 px/frame assume standard platformer physics."],
    ["Struggles with procedurally generated maps with no static geometry reference.", ""],
  ];
  let y = 2.95;
  fm.forEach(([h, p], i) => {
    hline(s, M, y, 7.0, RULE);
    T(s, String(i + 1), { x: M, y: y + 0.12, w: 0.6, h: 0.7, fontSize: 40, bold: true, color: RED, objectName: `Failure mode ${i + 1} number` });
    T(s, p ? [{ text: h, options: { bold: true, fontSize: 18, breakLine: true } }, { text: p, options: { fontSize: 13, color: MUTED } }] : h,
      { x: M + 0.75, y: y + 0.15, w: 6.25, h: 0.95, fontSize: 18, bold: !p, color: INK, objectName: `Failure mode ${i + 1}` });
    y += 1.15;
  });
  hline(s, M, y, 7.0, RULE);
  const px = 8.55, pw = R - px;
  s.addShape(pres.shapes.RECTANGLE, { x: px, y: 2.95, w: pw, h: 3.85, fill: { color: SOFT }, line: { type: "none" }, objectName: "Validation panel" });
  kicker(s, "How we validate ourselves", px + 0.28, 3.12, pw - 0.56);
  T(s, "A planted-bug level + an automatic check of detector output vs the engine's ground truth.",
    { x: px + 0.28, y: 3.45, w: pw - 0.56, h: 0.95, fontSize: 15, bold: true, color: INK });
  T(s, "found / missed / false alarms, per bug type", { x: px + 0.28, y: 4.4, w: pw - 0.56, h: 0.3, fontFace: MONO, fontSize: 10, color: MUTED });
  const hb = { border: [{ type: "none" }, { type: "none" }, { pt: 1.5, color: INK }, { type: "none" }] };
  const rb = { border: [{ type: "none" }, { type: "none" }, { pt: 0.75, color: RULE }, { type: "none" }] };
  s.addTable([
    [{ text: "BUG", options: { ...hb, fontFace: MONO, fontSize: 9, color: MUTED } }, { text: "DETECTED", options: { ...hb, fontFace: MONO, fontSize: 9, color: MUTED } }],
    [{ text: "Wall Clip", options: rb }, { text: "22/22", options: { ...rb, fontFace: MONO, bold: true, fontSize: 18, color: RED } }],
    [{ text: "Infinite Fall", options: rb }, { text: "[detector results]", options: { ...rb, fontFace: MONO, fontSize: 11, fill: { color: FILL } } }],
    [{ text: "Softlock", options: rb }, { text: "[detector results]", options: { ...rb, fontFace: MONO, fontSize: 11, fill: { color: FILL } } }],
  ], { x: px + 0.28, y: 4.85, w: pw - 0.56, colW: [1.5, pw - 0.56 - 1.5], rowH: [0.3, 0.48, 0.48, 0.48], fontSize: 14, color: INK, margin: [3, 4, 3, 0], valign: "middle", objectName: "Detector results table" });
}

// ---------- 10 feasibility ----------
{
  const s = newSlide("IndieQA Content No Title", "Feasibility & team", "Feasibility", "Unit economics · integration",
    "Unit economics: $25 an hour for a human, about four cents an hour of local compute for us, and that hour covers far more gameplay. No training data, no cloud. Built today in Python. Unity and Godot plug-ins are roadmap: stream the same telemetry over WebSocket.");
  const half = CW / 2;
  hline(s, M, 1.55, CW, INK, 1.5);
  kicker(s, "Human QA", M, 1.72, half);
  kicker(s, "IndieQA · local compute", M + half, 1.72, half, RED);
  const big = (t, col, x) => T(s, [{ text: t, options: { fontSize: 96, bold: true, charSpacing: -3 } }, { text: " /h", options: { fontSize: 36, bold: true } }],
    { x: x - 0.05, y: 1.95, w: half, h: 1.5, color: col, valign: "bottom", objectName: "Cost stat" });
  big("$25", INK, M); big("$0.04", RED, M + half);
  T(s, "Team estimate. And one IndieQA hour covers far more than one hour of play: headless runs ~240× real time.",
    { x: M, y: 3.6, w: CW, h: 0.3, fontFace: MONO, fontSize: 11, color: MUTED });
  const cols = [
    ["Needs nothing", "No training data · no cloud · no API keys · no GPU. ~1 µs telemetry overhead per frame.", null],
    ["Built today", "Python + Pygame engine, agent, telemetry, detector, reporter, Streamlit dashboard. One command.", null],
    ["Unity & Godot", "Plug-ins in C# and GDScript stream the same telemetry format over WebSocket. Same detector, same dashboard. Not built yet.", "dash"],
  ];
  const w = (CW - 0.6) / 3;
  cols.forEach(([k, p, dash], i) => {
    const x = M + i * (w + 0.3);
    hline(s, x, 4.6, w, INK, 1.5, dash);
    kicker(s, k, x, 4.75, 1.9);
    if (dash) T(s, "ROADMAP", { x: x + 1.75, y: 4.7, w: 1.05, h: 0.3, fontFace: MONO, fontSize: 10, bold: true, color: INK, align: "center", valign: "middle", charSpacing: 2, line: { color: INK, width: 1 }, objectName: "Roadmap tag" });
    T(s, p, { x, y: 5.15, w, h: 1.4, fontSize: 15, color: INK, italic: false });
  });
}

// ---------- 11 team ----------
{
  const s = newSlide("IndieQA Content", "Feasibility & team", "Team", "4 people",
    "Four people, each owning one stage of the pipeline: engine and agent, detection, the website, and the pitch.");
  s.addText("Four people, one pipeline", { placeholder: "title" });
  const team = [["P1", "Engine & agent", "Physics engine, planted glitches, telemetry, autonomous agent."], ["P2", "Detection", "Bug detector and per-bug reporter."], ["P3", "Pitch", "Story, deck and demo."], ["P4", "Website", "Streamlit dashboard: map, bug log, export."]];
  const w = (CW - 0.9) / 4;
  team.forEach(([n, h, p], i) => {
    const x = M + i * (w + 0.3);
    hline(s, x, 2.85, w, INK, 1.5);
    T(s, n, { x, y: 3.0, w, h: 0.3, fontFace: MONO, fontSize: 11, bold: true, color: RED });
    T(s, h, { x, y: 3.3, w, h: 0.45, fontSize: 22, bold: true, color: INK });
    T(s, p, { x, y: 3.8, w, h: 0.75, fontSize: 14, color: INK });
    fillTag(s, "[Name]", x, 4.65, 1.0);
  });
  footer(s, "agent → engine → telemetry → detector → reporter → dashboard", "Python · Pygame · Streamlit");
}

// ---------- 12 next steps ----------
{
  const s = newSlide("IndieQA Dark", "Close", "Next steps", "IndieQA",
    "Next: Unity and Godot plug-ins, per-game thresholds to address our second failure mode, and testing on real indie levels. IndieQA lets the bot find the bug before your players do. Thank you.");
  T(s, [{ text: "Let the bot find the bug ", options: { color: PAPER } }, { text: "before", options: { color: RED } }, { text: " your players do.", options: { color: PAPER } }],
    { x: M, y: 1.5, w: 10.5, h: 2.3, fontSize: 60, bold: true, lineSpacingMultiple: 0.92, objectName: "Closing line" });
  const nx = [["Next · 1", "Unity (C#) and Godot (GDScript) telemetry plug-ins over WebSocket."], ["Next · 2", "Per-game detector thresholds, to cut false positives on custom physics."], ["Next · 3", "Run it on real indie levels."]];
  const w = (CW - 0.6) / 3;
  nx.forEach(([k, p], i) => {
    const x = M + i * (w + 0.3);
    hline(s, x, 4.35, w, DRULE);
    kicker(s, k, x, 4.5, w, GREY);
    T(s, p, { x, y: 4.85, w, h: 1.0, fontSize: 16, color: PAPER });
  });
  footer(s, "github.com/GasimovDev/indieQA_bot", "Thank you", true);
}

(async () => {
  await pres.writeFile({ fileName: OUT });
  await applyTheme(OUT, THEME);
  console.log("wrote", OUT);
})();
