// Builds MCP-Lock.pptx. Every number below is copied from paper/numbers.tex (generated from results/).
// Run: NODE_PATH=<dir with pptxgenjs> node make_deck.js <path to pptx skill apply_theme.js>
const path = require("path");
const pptxgen = require("pptxgenjs");
const { applyTheme } = require(process.argv[2]);

const THEME = {
  name: "MCP-Lock",
  headFontFace: "Calibri",
  bodyFontFace: "Calibri",
  colors: {
    dk1: "14213D", lt1: "FFFFFF", dk2: "4A5568", lt2: "EEF1F6",
    accent1: "F4A100", // amber: MCP-Lock (ours)
    accent2: "8D99AE", // grey: baseline / prior work
    accent3: "2A9D8F", // teal: good outcome
    accent4: "D62839", // red: attack / block
    accent5: "1F3A60", // deep navy panels
    accent6: "F2C14E",
    hlink: "1F6FB2", folHlink: "6B4FA0",
  },
};
const HEX = THEME.colors;
const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE"; // 13.33 x 7.5
pres.title = "MCP-Lock";
pres.author = "Aakash G S, Hariharan J, J Jaswanth Raj";
pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };
const C = pres.SchemeColor;
const W = 13.333;

// ---------- layouts ----------
pres.defineSlideMaster({
  title: "DARK",
  background: { color: C.text1 },
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: 0.7, y: 2.2, w: 8.2, h: 1.4, fontSize: 54, bold: true, color: C.background1, valign: "bottom", align: "left", margin: 0 }, text: "" } },
    { placeholder: { options: { name: "body", type: "body", x: 0.7, y: 3.75, w: 8.2, h: 1.2, fontSize: 22, color: C.accent6, valign: "top", align: "left", margin: 0 }, text: "" } },
  ],
});
pres.defineSlideMaster({
  title: "DARK_TOP",
  background: { color: C.text1 },
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: 0.7, y: 0.5, w: 8.6, h: 1.0, fontSize: 44, bold: true, color: C.background1, valign: "middle", align: "left", margin: 0 }, text: "" } },
  ],
});
pres.defineSlideMaster({
  title: "CONTENT",
  background: { color: C.background1 },
  margin: [0.5, 0.6, 0.6, 0.6],
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: 0.6, y: 0.35, w: 12.1, h: 0.85, fontSize: 34, bold: true, color: C.text1, valign: "middle", align: "left", margin: 0 }, text: "" } },
    { text: { text: "MCP-Lock  |  SRM Institute of Science and Technology", options: { x: 0.6, y: 7.0, w: 8, h: 0.3, fontSize: 10, color: C.text2, margin: 0 } } },
  ],
  slideNumber: { x: 12.2, y: 7.0, w: 0.5, h: 0.3, fontSize: 10, color: C.text2, align: "right" },
});

// ---------- helpers ----------
function card(s, x, y, w, h, fill, name, opts = {}) {
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, {
    x, y, w, h, rectRadius: 0.12, fill: { color: fill }, line: opts.line || { type: "none" },
    shadow: opts.shadow ? { type: "outer", color: "000000", opacity: 0.12, blur: 6, offset: 2, angle: 90 } : undefined,
    objectName: name,
  });
}
function badge(s, x, y, d, fill, label, color, size, name) {
  s.addShape(pres.shapes.OVAL, { x, y, w: d, h: d, fill: { color: fill }, line: { type: "none" }, objectName: name });
  s.addText(label, { x, y, w: d, h: d, align: "center", valign: "middle", fontSize: size, bold: true, color, margin: 0, isTextBox: true });
}
function txt(s, text, o) {
  s.addText(text, Object.assign({ margin: 0, isTextBox: true, fontSize: 15, color: C.text1, valign: "top" }, o));
}
function arrow(s, x, y, w, color, name) {
  s.addShape(pres.shapes.RIGHT_ARROW, { x, y, w, h: 0.38, fill: { color }, line: { type: "none" }, objectName: name });
}
function source(s, text) {
  txt(s, text, { x: 0.6, y: 6.6, w: 12.1, h: 0.3, fontSize: 10, color: C.text2, italic: true });
}
function lock(s, x, y, scale, name) {
  // shackle + body: the deck's motif
  s.addShape(pres.shapes.BLOCK_ARC, { x: x + 0.25 * scale, y, w: 1.0 * scale, h: 1.0 * scale, angleRange: [180, 0], arcThicknessRatio: 0.24, fill: { color: C.accent1 }, line: { type: "none" }, objectName: name + " shackle" });
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y: y + 0.5 * scale, w: 1.5 * scale, h: 1.15 * scale, rectRadius: 0.12 * scale, fill: { color: C.accent1 }, line: { type: "none" }, objectName: name + " body" });
  s.addShape(pres.shapes.OVAL, { x: x + 0.62 * scale, y: y + 0.85 * scale, w: 0.26 * scale, h: 0.26 * scale, fill: { color: C.text1 }, line: { type: "none" }, objectName: name + " keyhole" });
}
const axis = { catAxisLabelColor: HEX.dk2, valAxisLabelColor: HEX.dk2, catAxisLabelFontFace: "+mn-lt", valAxisLabelFontFace: "+mn-lt", dataLabelFontFace: "+mn-lt", titleFontFace: "+mn-lt", legendFontFace: "+mn-lt", catAxisLabelFontSize: 13, valAxisLabelFontSize: 11, dataLabelFontSize: 14, dataLabelColor: HEX.dk1, valGridLine: { color: "E2E6EC", size: 0.5 }, catGridLine: { style: "none" }, titleColor: HEX.dk1, titleFontSize: 14 };

// ---------- 1. title ----------
pres.addSection({ title: "Introduction" });
let s = pres.addSlide({ masterName: "DARK", sectionTitle: "Introduction" });
s.addText("MCP-Lock", { placeholder: "title" });
s.addText("A lockfile and launch gate that stops AI coding agents from silently running new, unreviewed tool servers", { placeholder: "body" });
lock(s, 9.9, 1.7, 2.0, "Title lock");
txt(s, "Aakash G S  ·  Hariharan J  ·  J Jaswanth Raj", { x: 0.7, y: 5.55, w: 9, h: 0.4, fontSize: 18, bold: true, color: C.background1 });
txt(s, "Department of Data Science and Business Systems, SRM Institute of Science and Technology", { x: 0.7, y: 5.95, w: 10, h: 0.4, fontSize: 14, color: C.accent2 });
s.addNotes("MCP-Lock protects developers who let AI coding agents start Model Context Protocol servers. One sentence: lock what you reviewed, check every launch against it.");

// ---------- 2. problem ----------
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Introduction" });
s.addText("The problem: every launch can run code nobody reviewed", { placeholder: "title" });
const steps = [
  ["1", "Config says", "npx -y weather-mcp", "No version: “give me the latest”"],
  ["2", "AI agent", "starts the server", "Happens automatically, every session"],
  ["3", "npm / PyPI", "serves newest version", "May be hijacked or changed since review"],
  ["4", "Server runs", "+ tools enter the model", "Tool descriptions are read as instructions"],
];
steps.forEach((st, i) => {
  const x = 0.6 + i * 3.15;
  card(s, x, 1.55, 2.7, 2.3, C.background2, "Step " + st[0]);
  badge(s, x + 0.2, 1.75, 0.55, C.text1, st[0], C.background1, 18, "Step badge " + st[0]);
  txt(s, st[1], { x: x + 0.9, y: 1.8, w: 1.7, h: 0.45, fontSize: 17, bold: true });
  txt(s, st[2], { x: x + 0.2, y: 2.45, w: 2.35, h: 0.5, fontSize: 15, bold: true, color: i === 0 ? C.accent5 : C.text1, fontFace: i === 0 ? "Courier New" : undefined });
  txt(s, st[3], { x: x + 0.2, y: 3.0, w: 2.35, h: 0.7, fontSize: 14, color: C.text2 });
  if (i < 3) arrow(s, x + 2.74, 2.52, 0.38, C.accent2, "Flow arrow " + i);
});
const risks = [
  ["New code runs on your machine", "Install scripts and payloads execute with your files, keys and tokens. Hijacked maintainer accounts did exactly this in the 2025 Shai-Hulud worm waves."],
  ["New tool descriptions steer the agent", "A “rug pull” swaps a harmless tool description for a poisoned one. The model obeys it, and no one sees the change."],
];
risks.forEach((r, i) => {
  const x = 0.6 + i * 6.15;
  card(s, x, 4.25, 5.95, 2.1, "FBE9EB", "Risk " + (i + 1));
  badge(s, x + 0.25, 4.5, 0.55, C.accent4, "!", C.background1, 22, "Risk badge " + (i + 1));
  txt(s, r[0], { x: x + 1.0, y: 4.5, w: 4.75, h: 0.5, fontSize: 18, bold: true, color: C.accent4 });
  txt(s, r[1], { x: x + 1.0, y: 5.05, w: 4.75, h: 1.2, fontSize: 14 });
});
s.addNotes("Agents start MCP servers with unpinned commands such as npx -y. Each start may fetch a version whose code and tool descriptions nobody reviewed. Two dangers: code execution and tool poisoning / rug pulls.");

// ---------- 3. census ----------
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Introduction" });
s.addText("How often does it happen? Our census of MCP packages", { placeholder: "title" });
const stats = [
  [36.5, "36.5%", "of 2,000 sampled MCP packages changed the tools they advertise within 90 days", C.accent1, HEX.accent1],
  [97.0, "97.0%", "of those changes carried no provenance, publisher or install-script signal: invisible to metadata checks", C.accent4, HEX.accent4],
];
stats.forEach((st, i) => {
  const x = 0.6 + i * 4.15;
  card(s, x, 1.5, 3.85, 4.85, C.background2, "Census stat " + (i + 1));
  s.addChart(pres.charts.DOUGHNUT, [{ name: "share", labels: ["yes", "no"], values: [st[0], 100 - st[0]] }], {
    x: x + 0.62, y: 1.7, w: 2.6, h: 2.6, holeSize: 68, chartColors: [st[4], "D5DAE2"], showLegend: false, showValue: false, showPercent: false, showLabel: false, showTitle: false, dataBorder: { pt: 0, color: "FFFFFF" },
  });
  txt(s, st[1], { x: x + 0.62, y: 2.65, w: 2.6, h: 0.7, fontSize: 34, bold: true, align: "center", valign: "middle", color: st[3] });
  txt(s, st[2], { x: x + 0.3, y: 4.5, w: 3.25, h: 1.6, fontSize: 15, align: "left" });
});
card(s, 8.9, 1.5, 3.8, 4.85, C.text1, "Census scope");
txt(s, "15,272", { x: 9.2, y: 1.8, w: 3.2, h: 0.9, fontSize: 48, bold: true, color: C.accent1 });
txt(s, "MCP packages on npm and PyPI in the metadata census", { x: 9.2, y: 2.75, w: 3.2, h: 0.8, fontSize: 15, color: C.background1 });
txt(s, "What this means", { x: 9.2, y: 3.85, w: 3.2, h: 0.4, fontSize: 16, bold: true, color: C.accent6 });
txt(s, "Checking names, ages or signatures is not enough. You have to compare the tool definitions themselves.", { x: 9.2, y: 4.3, w: 3.2, h: 1.6, fontSize: 15, color: C.background1 });
source(s, "Source: RQ1 census, tool definitions statically extracted from package archives (stratified sample of 2,000).");
s.addNotes("RQ1. Over a third of sampled packages changed their tools within 90 days, and almost none of those changes are visible from registry metadata. This is the gap MCP-Lock fills.");

// ---------- 4. related work gap ----------
pres.addSection({ title: "Our approach" });
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Our approach" });
s.addText("What existing defences miss", { placeholder: "title" });
const Y = "✓", N = "✗", P = "partly";
const head = ["Approach", "Checks before launch, runs no package code", "Pins tool definitions", "Checks provenance, publisher and install scripts", "No change to servers or registries"];
const rows = [
  ["Pre-install hook (Bagmar & Saraf) — our baseline", Y, N, N, Y],
  ["Tool pinning: MCP-Scan, mcp-pin, mcpseal", N, Y, P, Y],
  ["Signed definitions: ETDI, attested admission", "–", Y, "–", N],
  ["MCP-Lock (ours)", Y, Y, Y, Y],
];
const cell = (v, r) => {
  const ours = r === rows.length - 1;
  const color = v === Y ? HEX.accent3 : v === N ? HEX.accent4 : HEX.dk2;
  return { text: v, options: { align: "center", valign: "middle", bold: true, fontSize: v.length > 1 ? 14 : 22, color, fill: { color: ours ? "FDF1D6" : "FFFFFF" } } };
};
const tbl = [head.map((h, i) => ({ text: h, options: { bold: true, fontSize: 14, color: "FFFFFF", fill: { color: HEX.dk1 }, align: i ? "center" : "left", valign: "middle" } }))];
rows.forEach((r, ri) => tbl.push(r.map((v, ci) => ci === 0
  ? { text: v, options: { fontSize: 15, bold: ri === rows.length - 1, color: HEX.dk1, valign: "middle", fill: { color: ri === rows.length - 1 ? "FDF1D6" : "FFFFFF" } } }
  : cell(v, ri))));
s.addTable(tbl, { x: 0.6, y: 1.5, w: 12.1, colW: [4.1, 2.0, 2.0, 2.0, 2.0], rowH: [0.85, 0.75, 0.75, 0.75, 0.75], border: { type: "solid", pt: 0.75, color: "D5DAE2" }, fontFace: "Calibri" });
card(s, 0.6, 5.55, 12.1, 0.9, C.background2, "Gap summary");
txt(s, [
  { text: "The gap: ", options: { bold: true, color: C.accent4 } },
  { text: "Kraishan measured drift in MCP registry fields and recommended client-side pinning of tool definitions. MCP-Lock is that pinning, combined with build-identity checks, and tested on real attacks." },
], { x: 0.85, y: 5.65, w: 11.6, h: 0.7, fontSize: 15, valign: "middle" });
source(s, "“partly”: one pinning proxy also records the package version and registry digest. Based on the Related Work section of our paper.");
s.addNotes("Prior work either checks names and ages before install (the baseline), or pins tool definitions but has to start the server first, or needs servers and registries to sign. MCP-Lock checks before launch, without running code, and needs no ecosystem change.");

// ---------- 5. solution ----------
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Our approach" });
s.addText("MCP-Lock: lock what you reviewed, check every launch", { placeholder: "title" });
card(s, 0.6, 1.5, 5.4, 4.9, C.background2, "Lock step");
badge(s, 0.85, 1.72, 0.6, C.accent1, "1", C.text1, 20, "Lock badge");
txt(s, "mcplock lock", { x: 1.6, y: 1.75, w: 4.2, h: 0.55, fontSize: 22, bold: true, fontFace: "Courier New" });
txt(s, "Once, after you review a server. Writes mcp-lock.json, which records:", { x: 0.9, y: 2.45, w: 4.9, h: 0.7, fontSize: 15, color: C.text2 });
["Archive digest (exact bytes)", "Build identity (who built it, from where)", "Publisher account", "Install-time scripts", "Tool definitions (canonical hash)"].forEach((t, i) => {
  card(s, 0.9, 3.2 + i * 0.6, 4.8, 0.5, C.background1, "Lock field " + (i + 1));
  lock(s, 1.02, 3.28 + i * 0.6, 0.2, "Field lock " + i);
  txt(s, t, { x: 1.5, y: 3.2 + i * 0.6, w: 4.1, h: 0.5, fontSize: 15, valign: "middle" });
});
arrow(s, 6.15, 3.7, 0.7, C.accent1, "Lock to gate arrow");
card(s, 7.0, 1.5, 5.7, 4.9, C.text1, "Gate step");
badge(s, 7.25, 1.72, 0.6, C.accent1, "2", C.text1, 20, "Gate badge");
txt(s, "Gate on every launch", { x: 8.0, y: 1.75, w: 4.5, h: 0.55, fontSize: 22, bold: true, color: C.background1 });
txt(s, "Before the agent starts a server, the gate compares the version it would get with the lock, reading tools from the archive. It never executes package code.", { x: 7.3, y: 2.45, w: 5.2, h: 1.1, fontSize: 15, color: C.background2 });
const outs = [["ALLOW", "matches the lock", C.accent3], ["WARN", "changed tools: shows the diff for review", C.accent1], ["BLOCK", "build, scripts or name look wrong", C.accent4]];
outs.forEach((o, i) => {
  const y = 3.75 + i * 0.75;
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 7.3, y, w: 1.35, h: 0.55, rectRadius: 0.1, fill: { color: o[2] }, line: { type: "none" }, objectName: "Verdict " + o[0] });
  txt(s, o[0], { x: 7.3, y, w: 1.35, h: 0.55, fontSize: 15, bold: true, align: "center", valign: "middle", color: i === 1 ? C.text1 : C.background1 });
  txt(s, o[1], { x: 8.85, y, w: 3.7, h: 0.55, fontSize: 15, valign: "middle", color: C.background1 });
});
txt(s, "On a block it suggests a safe version the agent can retry with.", { x: 7.3, y: 5.95, w: 5.2, h: 0.35, fontSize: 14, italic: true, color: C.accent6 });
s.addNotes("Two parts. The lockfile pins five things per server. The gate runs as a hook (e.g. in Claude Code) before every launch, compares against the lock, and allows, warns with a diff, or blocks and suggests a verified safe version.");

// ---------- 6. signals ----------
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Our approach" });
s.addText("Five checks, four of them new", { placeholder: "title" });
const sig = [
  ["S1", "Baseline checks", "Name looks like a popular one, does not exist or is under 30 days old; untrusted source; known-vulnerable pin", "BLOCK", false],
  ["S2", "Provenance continuity", "Build provenance disappears, or a different repository, workflow or builder built the new version", "BLOCK", true],
  ["S3", "Publisher", "Published by hand after CI releases, or by someone who is not a maintainer", "WARN", true],
  ["S4", "Install scripts", "A new install-time script appears (PyPI: source-only release after wheels)", "BLOCK", true],
  ["S5", "Tool definitions", "The canonical hash of the tools differs from the lock; the diff is shown", "WARN", true],
];
sig.forEach((g, i) => {
  const x = 0.6 + i * 2.46;
  card(s, x, 1.5, 2.26, 4.9, g[4] ? "FDF1D6" : C.background2, "Signal " + g[0], { shadow: true });
  badge(s, x + 0.73, 1.75, 0.8, g[4] ? C.accent1 : C.accent2, g[0], C.text1, 20, "Signal badge " + g[0]);
  txt(s, g[1], { x: x + 0.15, y: 2.7, w: 1.96, h: 0.75, fontSize: 17, bold: true, align: "center" });
  txt(s, g[2], { x: x + 0.18, y: 3.5, w: 1.9, h: 2.0, fontSize: 14, color: C.text2 });
  const red = g[3] === "BLOCK";
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: x + 0.43, y: 5.7, w: 1.4, h: 0.45, rectRadius: 0.1, fill: { color: red ? C.accent4 : C.accent1 }, line: { type: "none" }, objectName: "Action " + g[0] });
  txt(s, g[3], { x: x + 0.43, y: 5.7, w: 1.4, h: 0.45, fontSize: 14, bold: true, align: "center", valign: "middle", color: red ? C.background1 : C.text1 });
});
source(s, "Amber cards: added by MCP-Lock (compare a launch with its lock entry). Grey: the existing pre-install hook, kept as is.");
s.addNotes("S1 is the baseline hook's check set. S2 to S5 are our additions; each compares the new version against what was locked.");

// ---------- 7. headline result ----------
pres.addSection({ title: "Results" });
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Results" });
s.addText("Result: twice as many real attacks caught", { placeholder: "title" });
s.addChart(pres.charts.BAR, [
  { name: "Baseline hook", labels: ["All 490 real attacks", "368 hijacked packages", "40 synthetic rug pulls"], values: [19.6, 4.6, 0] },
  { name: "MCP-Lock", labels: ["All 490 real attacks", "368 hijacked packages", "40 synthetic rug pulls"], values: [39.8, 31.5, 100] },
], Object.assign({}, axis, {
  x: 0.6, y: 1.45, w: 7.6, h: 5.0, barDir: "col", barGrouping: "clustered", barGapWidthPct: 60, chartColors: [HEX.accent2, HEX.accent1],
  showValue: true, dataLabelPosition: "outEnd", dataLabelFormatCode: '0.0"%"', valAxisMaxVal: 110, valAxisMinVal: 0, valAxisLabelFormatCode: '0"%"', valAxisMajorUnit: 20,
  showLegend: true, legendPos: "t", legendFontSize: 14, legendColor: HEX.dk1, showTitle: true, title: "Share of attacks detected (block or warn)",
}));
const call = [["2×", "detection: 39.8% vs 19.6%", C.accent1], ["99 vs 0", "attacks only MCP-Lock caught vs only the baseline caught (p = 3.2×10⁻³⁰)", C.accent3], ["40 / 40", "tool-definition rug pulls caught; the baseline caught 0", C.accent5]];
call.forEach((c, i) => {
  const y = 1.5 + i * 1.65;
  card(s, 8.6, y, 4.1, 1.45, C.background2, "Result callout " + (i + 1));
  txt(s, c[0], { x: 8.85, y: y + 0.12, w: 3.7, h: 0.65, fontSize: 32, bold: true, color: c[2] });
  txt(s, c[1], { x: 8.85, y: y + 0.75, w: 3.7, h: 0.65, fontSize: 14, color: C.text2 });
});
source(s, "Pre-registered test (H1), exact McNemar with Holm correction. Real attacks: 22 baseline-paper scenarios + 468 malicious npm/PyPI versions (OpenSSF, Datadog).");
s.addNotes("H1 holds. MCP-Lock detects 39.8% of 490 real attacks (95% CI 35.6–44.2) against 19.6% (16.3–23.3) for the baseline. It never misses a case the baseline catches. On hijacked existing packages the gap is largest: 31.5% vs 4.6%.");

// ---------- 8. where the gain comes from ----------
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Results" });
s.addText("Where the extra detections come from", { placeholder: "title" });
s.addChart(pres.charts.BAR, [{ name: "Detections lost", labels: ["S4 install scripts", "S5 tool definitions", "S3 publisher", "S2 provenance"], values: [96, 2, 1, 0] }], Object.assign({}, axis, {
  x: 0.6, y: 1.45, w: 6.6, h: 4.9, barDir: "bar", chartColors: [HEX.accent1], showValue: true, dataLabelPosition: "outEnd", valAxisMaxVal: 110, valAxisMinVal: 0, valAxisMajorUnit: 20,
  showLegend: false, showTitle: true, title: "Of the 99 added detections, how many are lost when one check is removed", catAxisOrientation: "maxMin", catAxisLabelFontSize: 14,
}));
card(s, 7.6, 1.5, 5.1, 2.2, C.text1, "Insight S4");
txt(s, "Install-script diffs do most of the work", { x: 7.85, y: 1.7, w: 4.6, h: 0.5, fontSize: 18, bold: true, color: C.accent1 });
txt(s, "Hijacked packages usually add an install script. A lock that remembers “this server had none” turns that into a block.", { x: 7.85, y: 2.25, w: 4.6, h: 1.3, fontSize: 15, color: C.background1 });
card(s, 7.6, 3.95, 5.1, 2.4, C.background2, "Insight windows");
txt(s, "Not just one worm campaign", { x: 7.85, y: 4.15, w: 4.6, h: 0.5, fontSize: 18, bold: true });
txt(s, [
  { text: "Outside both Shai-Hulud waves, MCP-Lock still detects " },
  { text: "32.0%", options: { bold: true, color: C.accent1 } },
  { text: " of malicious versions vs " },
  { text: "21.2%", options: { bold: true, color: C.accent2 } },
  { text: " for the baseline (p = 1.5×10⁻¹¹, exploratory)." },
], { x: 7.85, y: 4.7, w: 4.6, h: 1.5, fontSize: 15 });
source(s, "Ablation on the pre-registered corpus. S5 is the only check that sees rug pulls in tool descriptions (R-S: 40/40).");
s.addNotes("Removing S4 loses 96 of the 99 added detections, S5 loses 2, S3 loses 1, S2 loses 0. Provenance is sound but rarely applies because most packages have none. The gain survives outside the two worm windows.");

// ---------- 9. cost ----------
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Results" });
s.addText("The cost: almost no extra false blocks", { placeholder: "title" });
s.addChart(pres.charts.BAR, [{ name: "False blocks", labels: ["Baseline hook", "MCP-Lock", "MCP-Lock, locked servers exempt from 30-day age rule"], values: [32.9, 33.4, 0.73] }], Object.assign({}, axis, {
  x: 0.6, y: 1.45, w: 7.4, h: 4.9, barDir: "col", chartColors: [HEX.accent2, HEX.accent1, HEX.accent3], showValue: true, dataLabelPosition: "outEnd", dataLabelFormatCode: '0.0#"%"',
  valAxisMaxVal: 40, valAxisMinVal: 0, valAxisMajorUnit: 10, valAxisLabelFormatCode: '0"%"', showLegend: false, showTitle: true, title: "Honest upgrades wrongly blocked (8,180 benign upgrades)", catAxisLabelFontSize: 12,
}));
const costs = [["+0.42 pp", "extra false blocks over the baseline: small but statistically significant (H2)", C.accent1], ["0.73%", "false blocks once locked servers skip the baseline’s age rule, which causes almost all of them", C.accent3], ["16.5%", "of honest upgrades get a warning to review, mostly changed tool definitions", C.accent5]];
costs.forEach((c, i) => {
  const y = 1.5 + i * 1.65;
  card(s, 8.4, y, 4.3, 1.45, C.background2, "Cost callout " + (i + 1));
  txt(s, c[0], { x: 8.65, y: y + 0.12, w: 3.9, h: 0.6, fontSize: 30, bold: true, color: c[2] });
  txt(s, c[1], { x: 8.65, y: y + 0.72, w: 3.9, h: 0.7, fontSize: 14, color: C.text2 });
});
source(s, "Age-rule exemption is an exploratory sensitivity analysis, not part of the pre-registered test.");
s.addNotes("H2 holds in the unfavourable direction: 33.4% vs 32.9% false blocks. Those blocks come from the baseline's rule that blocks packages younger than 30 days. Exempting servers that are already locked drops false blocks to 0.73%.");

// ---------- 10. adaptive attacker ----------
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Results" });
s.addText("Adaptive attacks, and how we close the gaps", { placeholder: "title" });
s.addChart(pres.charts.BAR, [
  { name: "Blocked", labels: ["Frozen gate", "With D1–D5"], values: [1, 10] },
  { name: "Warned", labels: ["Frozen gate", "With D1–D5"], values: [4, 1] },
  { name: "Allowed", labels: ["Frozen gate", "With D1–D5"], values: [7, 1] },
], Object.assign({}, axis, {
  x: 0.6, y: 1.45, w: 5.6, h: 4.9, barDir: "col", barGrouping: "stacked", barGapWidthPct: 55, chartColors: [HEX.accent3, HEX.accent1, HEX.accent4],
  showValue: true, dataLabelPosition: "ctr", dataLabelColor: "FFFFFF", valAxisMaxVal: 12, valAxisMinVal: 0, valAxisMajorUnit: 2,
  showLegend: true, legendPos: "t", legendFontSize: 14, legendColor: HEX.dk1, showTitle: true, title: "12 adaptive attacks we built against MCP-Lock",
}));
s.addChart(pres.charts.BAR, [{ name: "Cost", labels: ["D1 lock dependency tree", "D2 runtime tool proxy", "D3 lock every PyPI file", "D4 require provenance", "D5 normalise commands"], values: [1.03, 16.1, 0, 37.3, 0] }], Object.assign({}, axis, {
  x: 6.5, y: 1.45, w: 6.2, h: 4.9, barDir: "bar", chartColors: [HEX.accent5], showValue: true, dataLabelPosition: "outEnd", dataLabelFormatCode: '0.0#"%"', valAxisMaxVal: 45, valAxisMinVal: 0, valAxisMajorUnit: 10, valAxisLabelFormatCode: '0"%"',
  showLegend: false, showTitle: true, title: "Cost: extra honest upgrades blocked (upper estimate)", catAxisOrientation: "maxMin", catAxisLabelFontSize: 13,
}));
source(s, "Still open: a payload shipped through the genuine release workflow (allowed) and a new, unlike name (warned). Hardening is exploratory, not pre-registered.");
s.addNotes("We attacked our own gate with 12 cases (runtime-built tools, tools fetched from a URL, poisoned dependencies, stolen tokens...). The frozen gate stops 5 (1 block, 4 warn). Five optional switches block 10. D3 and D5 are free; D1 costs about 1%; D2 and D4 are expensive and suit high-security setups.");

// ---------- 11. rigour ----------
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Results" });
s.addText("Built to be trusted, and to be practical", { placeholder: "title" });
const trust = [
  ["OSF", "Pre-registered", "Hypotheses, data and a kill rule fixed on OSF before any scored run (DOI 10.17605/OSF.IO/2AMJ3)"],
  ["p", "Sound statistics", "Exact McNemar tests with Holm correction; Wilson 95% intervals on every rate"],
  ["11/11", "Checked live", "Attack servers run in hardened Docker: runtime verdicts match the analysis in 11 of 11"],
  ["→", "Safe suggestions", "A verified safe version is offered for 114/116 hijacked cases and 40/40 rug pulls; none was unsafe"],
  ["78.6%", "Beats simple fixes", "Exact pinning stops 78.6% of hijacks but freezes all 8,180 honest upgrades"],
  ["103", "Open and tested", "Open-source code, replay bundles and 103 automated tests on GitHub"],
];
trust.forEach((t, i) => {
  const x = 0.6 + (i % 3) * 4.1, y = 1.5 + Math.floor(i / 3) * 2.5;
  card(s, x, y, 3.9, 2.3, C.background2, "Trust " + (i + 1));
  badge(s, x + 0.25, y + 0.25, 0.95, C.text1, t[0], C.accent1, t[0].length > 3 ? 14 : 20, "Trust badge " + (i + 1));
  txt(s, t[1], { x: x + 1.35, y: y + 0.3, w: 2.4, h: 0.85, fontSize: 18, bold: true, valign: "middle" });
  txt(s, t[2], { x: x + 0.25, y: y + 1.3, w: 3.45, h: 0.95, fontSize: 14, color: C.text2 });
});
s.addNotes("The evaluation was registered before results existed, so the main claims cannot be tuned after the fact. We also compared against simpler alternatives: exact version pinning and npm --ignore-scripts.");

// ---------- 12. close ----------
pres.addSection({ title: "Conclusion" });
s = pres.addSlide({ masterName: "DARK_TOP", sectionTitle: "Conclusion" });
s.addText("Takeaways", { placeholder: "title" });
const take = [
  ["Real problem", "36.5% of MCP packages change their tools within 90 days, and 97.0% of those changes are invisible to metadata checks"],
  ["Clear improvement", "2× the real attacks caught (39.8% vs 19.6%), every rug pull caught, at +0.42 pp false blocks"],
  ["Honest limits", "Adaptive attacks pass the frozen gate 7 of 12 times; five switches close all but two, each with a measured cost"],
];
take.forEach((t, i) => {
  const y = 1.95 + i * 1.25;
  badge(s, 0.7, y, 0.75, C.accent1, String(i + 1), C.text1, 22, "Takeaway badge " + (i + 1));
  txt(s, t[0], { x: 1.7, y: y - 0.02, w: 7.6, h: 0.45, fontSize: 20, bold: true, color: C.accent1 });
  txt(s, t[1], { x: 1.7, y: y + 0.42, w: 7.6, h: 0.75, fontSize: 15, color: C.background1 });
});
lock(s, 10.2, 1.9, 1.6, "Closing lock");
txt(s, "Thank you. Questions?", { x: 0.7, y: 5.85, w: 8, h: 0.55, fontSize: 26, bold: true, color: C.background1 });
txt(s, "Code: github.com/ftaakash/MCP-Lock   ·   Pre-registration: osf.io/2amj3", { x: 0.7, y: 6.45, w: 11, h: 0.4, fontSize: 14, color: C.accent2 });
s.addNotes("Close with the three takeaways and point to the public code and pre-registration.");

(async () => {
  const out = path.join(__dirname, "MCP-Lock.pptx");
  await pres.writeFile({ fileName: out });
  await applyTheme(out, THEME);
  console.log("wrote", out);
})();
