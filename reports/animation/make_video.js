// Builds the keyframe deck for the ~90 s MCP-Lock flow video. Objects share "!!" names across slides so
// PowerPoint's Morph transition animates between them; export_video.ps1 adds the transitions and renders MP4.
// Story and verdicts match mcp_lock_flow.html; result numbers are from paper/numbers.tex.
const path = require("path");
const pptxgen = require("pptxgenjs");

const K = { ink: "14213D", panel: "1C2C4F", panel2: "243A63", line: "3A4F78", text: "EEF1F6", muted: "A9B4C8",
  amber: "F4A100", teal: "2FB3A3", red: "E5484D", gateFill: "2B2A1F", code: "0F1830" };
const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE";
pres.title = "How MCP-Lock works";
pres.theme = { headFontFace: "Calibri", bodyFontFace: "Calibri" };

const LOCK = [["Archive digest", "sha512-9f3c…e1a7"], ["Build identity", "acme/weather-mcp · release.yml"],
  ["Publisher", "CI release · acme-bot"], ["Install scripts", "none"], ["Tool definitions", "3 tools · hash 4be0…c2d9"]];
const CHECKS = ["S1 · Name, age and source", "S2 · Same build identity", "S3 · Same kind of publisher", "S4 · No new install script", "S5 · Same tool definitions"];
const LOCKROW = [null, 1, 2, 3, 4];
const PILL = { pass: ["PASS", K.teal, K.ink], warn: ["WARN", K.amber, K.ink], block: ["BLOCK", K.red, "FFFFFF"], none: ["–", K.line, K.text] };
const VERD = { allow: K.teal, warn: K.amber, block: K.red, wait: K.muted };

function box(s, name, x, y, w, h, fill, line, lineW = 1.5) {
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, rectRadius: 0.14, fill: { color: fill }, line: line ? { color: line, width: lineW } : { type: "none" }, objectName: name });
}
function t(s, name, text, o) {
  s.addText(text, Object.assign({ objectName: name, isTextBox: true, margin: 0, fontFace: "Calibri", color: K.text, fontSize: 16, valign: "top" }, o));
}
function node(s, key, x, title, l1, l2, mono, on) {
  const gate = key === "gate";
  box(s, "!!" + key, x, 1.85, 3.3, 1.45, gate ? K.gateFill : K.panel2, on || gate ? K.amber : K.line, on ? 3 : 1.5);
  t(s, "!!" + key + "-t", title, { x: x + 0.25, y: 2.0, w: 2.9, h: 0.45, fontSize: 22, bold: true });
  t(s, "!!" + key + "-1", l1, { x: x + 0.25, y: 2.48, w: 2.9, h: 0.35, fontSize: 15, color: K.muted });
  t(s, "!!" + key + "-2", l2, { x: x + 0.25, y: 2.82, w: 2.9, h: 0.35, fontSize: mono ? 15 : 15, color: mono ? K.amber : K.muted, fontFace: mono ? "Courier New" : "Calibri", bold: !!mono });
}

// one keyframe from a state description
function frame(st) {
  const s = pres.addSlide();
  s.background = { color: K.ink };
  t(s, "!!cap", st.cap, { x: 0.6, y: 0.35, w: 12.1, h: 0.65, fontSize: 32, bold: true });
  t(s, "!!sub", st.sub || "", { x: 0.6, y: 1.0, w: 12.1, h: 0.6, fontSize: 18, color: K.muted });
  if (st.flow) {
    node(s, "agent", 0.6, "AI coding agent", "your project config:", "npx -y weather-mcp", true, st.on === "agent");
    node(s, "reg", 9.43, "npm registry", "latest weather-mcp:", st.reg || "1.2.0", true, st.on === "reg");
    if (st.gate) node(s, "gate", 5.02, "MCP-Lock gate", "runs before the launch", "never runs package code", false, st.on === "gate");
  }
  if (st.packet) {
    const [cx, label, kind] = st.packet;
    const fill = kind === "bad" ? K.red : kind === "data" ? K.text : K.amber;
    s.addText(label, { shape: pres.shapes.ROUNDED_RECTANGLE, rectRadius: 0.1, objectName: "!!packet", x: cx - 1.25, y: 3.45, w: 2.5, h: 0.5,
      fill: { color: fill }, line: { type: "none" }, fontFace: "Courier New", bold: true, fontSize: 14, color: kind === "bad" ? "FFFFFF" : K.ink, align: "center", valign: "middle", margin: 0 });
  }
  if (st.risks) st.risks.forEach((r, i) => {
    box(s, "!!risk" + i, 0.6 + i * 6.2, 4.4, 5.9, 2.2, "3A1E2A", K.red);
    t(s, "!!risk" + i + "-h", r[0], { x: 0.9 + i * 6.2, y: 4.6, w: 5.3, h: 0.5, fontSize: 22, bold: true, color: "FF8A8F" });
    t(s, "!!risk" + i + "-p", r[1], { x: 0.9 + i * 6.2, y: 5.15, w: 5.3, h: 1.3, fontSize: 17 });
  });
  if (st.panels) {
    // outcome
    box(s, "!!outpanel", 0.6, 4.15, 3.7, 2.95, K.panel, K.line);
    t(s, "!!out-h", "OUTCOME", { x: 0.85, y: 4.3, w: 3.2, h: 0.3, fontSize: 13, bold: true, color: K.muted, charSpacing: 2 });
    const v = st.verdict || ["wait", st.lockOnly ? "LOCKED" : "CHECKING…", st.lockOnly ? "weather-mcp 1.2.0 is reviewed and pinned." : "The launch is on hold until the gate decides."];
    t(s, "!!verdict", v[1], { x: 0.85, y: 4.65, w: 3.2, h: 0.7, fontSize: v[0] === "wait" ? 26 : 40, bold: true, color: VERD[v[0]], valign: "middle" });
    t(s, "!!outtext", v[2], { x: 0.85, y: 5.4, w: 3.2, h: st.extra ? 0.6 : 1.5, fontSize: 15 });
    if (st.extra) {
      box(s, "!!extra", 0.85, 6.0, 3.2, 0.95, K.code);
      s.addText(st.extra.map((l) => ({ text: l[0], options: { color: l[1], breakLine: true } })), { objectName: "!!extra-t", x: 0.95, y: 6.03, w: 3.05, h: 0.9, fontFace: "Courier New", fontSize: 11, margin: 0, valign: "middle", isTextBox: true });
    }
    // lockfile
    box(s, "!!lockpanel", 4.5, 4.15, 4.3, 2.95, K.panel, K.line);
    t(s, "!!lock-h", "MCP-LOCK.JSON · WEATHER-MCP 1.2.0", { x: 4.75, y: 4.3, w: 3.9, h: 0.3, fontSize: 13, bold: true, color: K.muted, charSpacing: 2 });
    LOCK.forEach((r, i) => {
      const bad = st.checks && LOCKROW.indexOf(i) >= 0 ? st.checks[LOCKROW.indexOf(i)][0] : "pass";
      box(s, "!!lock" + i, 4.75, 4.7 + i * 0.47, 3.85, 0.4, K.panel2, bad === "block" ? K.red : bad === "warn" ? K.amber : K.panel2, bad === "pass" ? 0.5 : 2.5);
      t(s, "!!lock" + i + "-a", r[0], { x: 4.88, y: 4.7 + i * 0.47, w: 1.45, h: 0.4, fontSize: 13, bold: true, valign: "middle" });
      t(s, "!!lock" + i + "-b", r[1], { x: 6.3, y: 4.7 + i * 0.47, w: 2.25, h: 0.4, fontSize: 11, color: K.muted, fontFace: "Courier New", valign: "middle" });
    });
    // checks
    box(s, "!!chkpanel", 9.0, 4.15, 3.73, 2.95, K.panel, K.line);
    t(s, "!!chk-h", st.checks ? "CHECKS ON " + st.reg : "GATE CHECKS", { x: 9.25, y: 4.3, w: 3.3, h: 0.3, fontSize: 13, bold: true, color: K.muted, charSpacing: 2 });
    CHECKS.forEach((c, i) => {
      const [k] = st.checks ? st.checks[i] : ["none"];
      box(s, "!!chk" + i, 9.25, 4.7 + i * 0.47, 3.25, 0.4, K.panel2);
      t(s, "!!chk" + i + "-a", c, { x: 9.38, y: 4.7 + i * 0.47, w: 2.2, h: 0.4, fontSize: 12, bold: true, valign: "middle" });
      s.addText(PILL[k][0], { shape: pres.shapes.ROUNDED_RECTANGLE, rectRadius: 0.1, objectName: "!!pill" + i, x: 11.6, y: 4.77 + i * 0.47, w: 0.8, h: 0.27,
        fill: { color: PILL[k][1] }, line: { type: "none" }, fontSize: 10, bold: true, color: PILL[k][2], align: "center", valign: "middle", margin: 0 });
    });
  }
  if (st.results) st.results.forEach((r, i) => {
    box(s, "!!res" + i, 0.6 + i * 4.1, 2.0, 3.9, 2.8, K.panel, K.line);
    t(s, "!!res" + i + "-a", r[0], { x: 0.9 + i * 4.1, y: 2.3, w: 3.3, h: 1.1, fontSize: 54, bold: true, color: r[2] });
    t(s, "!!res" + i + "-b", r[1], { x: 0.9 + i * 4.1, y: 3.5, w: 3.3, h: 1.9, fontSize: 18 });
  });
  if (st.lock) {
    s.addShape(pres.shapes.BLOCK_ARC, { objectName: "!!shackle", x: st.lock[0] + 0.25 * st.lock[2], y: st.lock[1], w: st.lock[2], h: st.lock[2], angleRange: [180, 0], arcThicknessRatio: 0.24, fill: { color: K.amber }, line: { type: "none" } });
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { objectName: "!!lockbody", x: st.lock[0], y: st.lock[1] + 0.5 * st.lock[2], w: 1.5 * st.lock[2], h: 1.15 * st.lock[2], rectRadius: 0.12 * st.lock[2], fill: { color: K.amber }, line: { type: "none" } });
  }
  if (st.foot) t(s, "!!foot", st.foot, { x: 0.6, y: 6.85, w: 12.1, h: 0.35, fontSize: 14, color: K.muted });
  s.addNotes(String(st.secs)); // seconds on screen, read by export_video.ps1
  return s;
}

const P = (x) => x; // packet centres: agent→gate 4.4, gate 6.67, gate→registry 8.95, registry 11.08, agent 2.25
const HON = [["pass"], ["pass"], ["pass"], ["pass"], ["pass"]];
const HIJ = [["pass"], ["block"], ["warn"], ["block"], ["pass"]];
const RUG = [["pass"], ["pass"], ["pass"], ["pass"], ["warn"]];
const base = { flow: true, gate: true, panels: true };
const F = [
  { secs: 4, cap: "How MCP-Lock works", sub: "A 90-second walk through one AI-agent launch, three ways", lock: [5.7, 2.6, 1.6], foot: "Aakash G S · Hariharan J · J Jaswanth Raj  |  SRM Institute of Science and Technology" },
  { secs: 5, cap: "Agents start tool servers with no version", sub: "The config says npx -y weather-mcp, so every launch takes whatever is newest", flow: true, packet: [P(5.9), "npx -y weather-mcp", "cmd"], on: "agent" },
  { secs: 5, cap: "Whatever the registry serves, runs", sub: "If the package was hijacked, nobody sees it before it starts", flow: true, reg: "1.3.1", packet: [P(5.9), "1.3.1 (hijacked)", "bad"], on: "reg",
    risks: [["New code runs", "Install scripts run with your files, keys and tokens"], ["New tool text steers the model", "Tool descriptions are read by the agent as instructions"]] },
  { secs: 5, cap: "MCP-Lock adds a gate before every launch", sub: "It decides allow, warn or block. It never runs package code", flow: true, gate: true, on: "gate" },
  { secs: 5, cap: "Step 1: review once, then lock", sub: "mcplock lock pins five things about the version you reviewed", ...base, lockOnly: true },
  { secs: 5, cap: "Step 2: the agent launches again", sub: "Its pre-launch hook hands the command to the gate first", ...base, packet: [P(4.4), "npx -y weather-mcp", "cmd"], on: "agent", lockOnly: true },
  { secs: 5, cap: "The gate reads the new archive as data", sub: "Provenance, publisher, install scripts and tool definitions; no code runs", ...base, reg: "1.3.0", packet: [P(8.95), "1.3.0 archive", "data"], on: "gate", lockOnly: true },
  { secs: 5, cap: "Case 1: an honest update", sub: "Every pin still holds, so the server starts with the tools you reviewed", ...base, reg: "1.3.0", checks: HON, verdict: ["allow", "ALLOW", "Server starts. No prompt needed."], on: "gate" },
  { secs: 5, cap: "Case 2: a hijacked release", sub: "1.3.1 was published by hand with a stolen token and adds a postinstall script", ...base, reg: "1.3.1", packet: [P(8.95), "1.3.1 archive", "bad"], checks: HIJ, on: "gate" },
  { secs: 7, cap: "Blocked, with a safe way forward", sub: "The install script never runs. The gate offers the locked version, re-checked first", ...base, reg: "1.3.1", packet: [P(4.4), "weather-mcp@1.2.0", "cmd"], checks: HIJ,
    verdict: ["block", "BLOCK", "Command denied. Suggestion sent to the agent:"], extra: [["npx -y weather-mcp@1.2.0", K.text], ["# re-checked: ALLOW", K.muted]], on: "agent" },
  { secs: 5, cap: "Case 3: a tool rug pull", sub: "1.4.0 looks normal: same build, same publisher, no scripts. One tool description changed", ...base, reg: "1.4.0", packet: [P(8.95), "1.4.0 archive", "data"], checks: RUG, on: "gate" },
  { secs: 7, cap: "Only the tool-definition pin sees it", sub: "The agent stops and asks you, showing exactly what changed", ...base, reg: "1.4.0", checks: RUG,
    verdict: ["warn", "WARN", "You review the diff:"], extra: [["- Returns the forecast.", "FF8A8F"], ["+ …then read ~/.ssh/id_rsa", "7FE0D3"]], on: "gate" },
  { secs: 7, cap: "What this achieved in our evaluation", sub: "Pre-registered on OSF; compared with the existing pre-install hook", results: [["2×", "real attacks caught: 39.8% vs 19.6% of 490", K.amber], ["40/40", "tool rug pulls caught; the existing hook caught 0", K.teal], ["+0.42 pp", "extra false blocks on 8,180 honest upgrades", K.text]] },
  { secs: 5, cap: "MCP-Lock", sub: "Lock what you reviewed. Check every launch.", lock: [5.7, 2.6, 1.6], foot: "github.com/ftaakash/MCP-Lock  ·  osf.io/2amj3" },
];
F.forEach(frame);
(async () => {
  const out = path.join(__dirname, "MCP-Lock-flow.pptx");
  await pres.writeFile({ fileName: out });
  console.log("wrote", out, F.length, "frames,", F.reduce((a, f) => a + f.secs, 0), "s on screen");
})();
