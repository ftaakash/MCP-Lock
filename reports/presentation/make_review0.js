// Builds MCP-Lock-Review0.pptx: the 10-slide Review 0 deck, one slide per rubric item (21CSP401L).
// Numbers come from paper/numbers.tex; references from paper/refs.bib (docs/CITATIONS_VERIFIED.md) plus two
// patents checked on Google Patents on 2026-11-03.
// Run: NODE_PATH=<dir with pptxgenjs> node make_review0.js <path to pptx skill apply_theme.js>
const path = require("path");
const pptxgen = require("pptxgenjs");
const { applyTheme } = require(process.argv[2]);

const THEME = {
  name: "MCP-Lock",
  headFontFace: "Calibri",
  bodyFontFace: "Calibri",
  colors: {
    dk1: "14213D", lt1: "FFFFFF", dk2: "4A5568", lt2: "EEF1F6",
    accent1: "F4A100", accent2: "8D99AE", accent3: "2A9D8F", accent4: "D62839", accent5: "1F3A60", accent6: "F2C14E",
    hlink: "1F6FB2", folHlink: "6B4FA0",
  },
};
const HEX = THEME.colors;
const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE";
pres.title = "MCP-Lock: Review 0";
pres.author = "Aakash G S, Hariharan J, J Jaswanth Raj";
pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };
const C = pres.SchemeColor;

pres.defineSlideMaster({
  title: "DARK",
  background: { color: C.text1 },
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: 0.7, y: 1.0, w: 8.4, h: 1.2, fontSize: 54, bold: true, color: C.background1, valign: "bottom", align: "left", margin: 0 }, text: "" } },
    { placeholder: { options: { name: "body", type: "body", x: 0.7, y: 2.3, w: 8.4, h: 1.0, fontSize: 20, color: C.accent6, valign: "top", align: "left", margin: 0 }, text: "" } },
  ],
});
pres.defineSlideMaster({
  title: "CONTENT",
  background: { color: C.background1 },
  margin: [0.5, 0.6, 0.6, 0.6],
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: 0.6, y: 0.3, w: 10.2, h: 0.8, fontSize: 30, bold: true, color: C.text1, valign: "middle", align: "left", margin: 0 }, text: "" } },
    { text: { text: "21CSP401L Major Project  |  Review 0  |  MCP-Lock  |  SRM IST, Kattankulathur", options: { x: 0.6, y: 7.05, w: 9, h: 0.3, fontSize: 10, color: C.text2, margin: 0 } } },
  ],
  slideNumber: { x: 12.2, y: 7.05, w: 0.5, h: 0.3, fontSize: 10, color: C.text2, align: "right" },
});

function card(s, x, y, w, h, fill, name, line) {
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, rectRadius: 0.1, fill: { color: fill }, line: line || { type: "none" }, objectName: name });
}
function badge(s, x, y, d, fill, label, color, size, name) {
  s.addShape(pres.shapes.OVAL, { x, y, w: d, h: d, fill: { color: fill }, line: { type: "none" }, objectName: name });
  s.addText(label, { x, y, w: d, h: d, align: "center", valign: "middle", fontSize: size, bold: true, color, margin: 0, isTextBox: true });
}
function txt(s, text, o) {
  s.addText(text, Object.assign({ margin: 0, isTextBox: true, fontSize: 14, color: C.text1, valign: "top" }, o));
}
function arrow(s, x, y, w, color, name) {
  s.addShape(pres.shapes.RIGHT_ARROW, { x, y, w, h: 0.34, fill: { color }, line: { type: "none" }, objectName: name });
}
function source(s, text) {
  txt(s, text, { x: 0.6, y: 6.7, w: 12.1, h: 0.3, fontSize: 10, color: C.text2, italic: true });
}
// The rubric criterion each slide answers, top right.
function rubric(s, label) {
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 10.95, y: 0.45, w: 1.75, h: 0.5, rectRadius: 0.25, fill: { color: C.background2 }, line: { color: HEX.accent2, width: 0.75 }, objectName: "Rubric tag" });
  txt(s, label, { x: 10.95, y: 0.45, w: 1.75, h: 0.5, fontSize: 11, bold: true, align: "center", valign: "middle", color: C.accent5 });
}
function lock(s, x, y, scale, name) {
  s.addShape(pres.shapes.BLOCK_ARC, { x: x + 0.25 * scale, y, w: 1.0 * scale, h: 1.0 * scale, angleRange: [180, 0], arcThicknessRatio: 0.24, fill: { color: C.accent1 }, line: { type: "none" }, objectName: name + " shackle" });
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y: y + 0.5 * scale, w: 1.5 * scale, h: 1.15 * scale, rectRadius: 0.12 * scale, fill: { color: C.accent1 }, line: { type: "none" }, objectName: name + " body" });
  s.addShape(pres.shapes.OVAL, { x: x + 0.62 * scale, y: y + 0.85 * scale, w: 0.26 * scale, h: 0.26 * scale, fill: { color: C.text1 }, line: { type: "none" }, objectName: name + " keyhole" });
}
const th = (t, o = {}) => ({ text: t, options: Object.assign({ bold: true, fontSize: 13, color: "FFFFFF", fill: { color: HEX.dk1 }, valign: "middle" }, o) });
const td = (t, o = {}) => ({ text: t, options: Object.assign({ fontSize: 12, color: HEX.dk1, valign: "middle", fill: { color: "FFFFFF" } }, o) });

// ---------- 1. title and team ----------
pres.addSection({ title: "Introduction" });
let s = pres.addSlide({ masterName: "DARK", sectionTitle: "Introduction" });
s.addText("MCP-Lock", { placeholder: "title" });
s.addText("Provenance and tool-definition pinning to stop AI coding agents from silently running unreviewed tool servers", { placeholder: "body" });
lock(s, 10.4, 0.9, 1.6, "Title lock");
txt(s, "Domain: Cybersecurity · Software supply-chain security · AI agents (Model Context Protocol)", { x: 0.7, y: 3.45, w: 11.5, h: 0.4, fontSize: 15, color: C.accent2 });
s.addTable([
  [th("Team member", { fill: { color: HEX.accent5 } }), th("Register number", { fill: { color: HEX.accent5 } })],
  ...[["Aakash G S", "RA2311042010060"], ["Hariharan J", "RA2311042010059"], ["J Jaswanth Raj", "RA2311042010013"]].map(([n, reg]) => [
    td(n, { fontSize: 15, bold: true, color: "FFFFFF", fill: { color: HEX.dk1 } }),
    td(reg, { fontSize: 15, color: HEX.accent6, fill: { color: HEX.dk1 }, fontFace: "Courier New" }),
  ]),
], { x: 0.7, y: 4.1, w: 6.4, colW: [3.4, 3.0], rowH: 0.42, border: { type: "solid", pt: 0.75, color: HEX.accent5 } });
card(s, 7.6, 4.1, 5.05, 1.68, C.accent5, "Guide card");
txt(s, "Project guide", { x: 7.85, y: 4.25, w: 4.6, h: 0.35, fontSize: 13, bold: true, color: C.accent6 });
txt(s, "Sai Prasanth D", { x: 7.85, y: 4.6, w: 4.6, h: 0.45, fontSize: 18, bold: true, color: C.background1 });
txt(s, "Assistant Professor, Department of Data Science and Business Systems", { x: 7.85, y: 5.05, w: 4.6, h: 0.65, fontSize: 13, color: C.background2 });
txt(s, "Department of Data Science and Business Systems, School of Computing, SRM Institute of Science and Technology, Kattankulathur", { x: 0.7, y: 6.1, w: 11.9, h: 0.35, fontSize: 13, color: C.accent2 });
txt(s, "21CSP401L Major Project  ·  Review 0", { x: 0.7, y: 6.5, w: 11.9, h: 0.35, fontSize: 13, bold: true, color: C.background1 });
s.addNotes("Introduce the team and guide. One line: MCP-Lock records what you reviewed and checks every launch of an agent's tool server against it.");

// ---------- 2. problem statement ----------
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Introduction" });
s.addText("Problem statement and background", { placeholder: "title" });
rubric(s, "Criterion 1");
txt(s, "Background: AI coding agents (Claude Code, Cursor, …) get their tools from MCP servers, which they start straight from npm or PyPI.", { x: 0.6, y: 1.25, w: 12.1, h: 0.4, fontSize: 15, color: C.text2 });
const steps = [
  ["1", "Config says", "npx -y weather-mcp", "No version pinned: “give me the latest”"],
  ["2", "Agent", "starts the server", "Automatically, every session"],
  ["3", "Registry", "serves newest version", "May be hijacked or changed since review"],
  ["4", "Server runs", "+ tools reach the model", "Tool descriptions act as instructions"],
];
steps.forEach((st, i) => {
  const x = 0.6 + i * 3.15;
  card(s, x, 1.8, 2.7, 2.0, C.background2, "Step " + st[0]);
  badge(s, x + 0.2, 1.95, 0.5, C.text1, st[0], C.background1, 16, "Step badge " + st[0]);
  txt(s, st[1], { x: x + 0.85, y: 2.0, w: 1.75, h: 0.4, fontSize: 16, bold: true });
  txt(s, st[2], { x: x + 0.2, y: 2.6, w: 2.35, h: 0.4, fontSize: 14, bold: true, color: i === 0 ? C.accent5 : C.text1, fontFace: i === 0 ? "Courier New" : undefined });
  txt(s, st[3], { x: x + 0.2, y: 3.05, w: 2.35, h: 0.65, fontSize: 13, color: C.text2 });
  if (i < 3) arrow(s, x + 2.74, 2.62, 0.38, C.accent2, "Flow arrow " + i);
});
card(s, 0.6, 4.05, 12.1, 2.5, C.text1, "Problem statement");
txt(s, "PROBLEM STATEMENT", { x: 0.9, y: 4.25, w: 6, h: 0.35, fontSize: 13, bold: true, color: C.accent1, charSpacing: 2 });
txt(s, [
  { text: "Unpinned MCP-server launches let the code and the tool descriptions an agent runs change after a human reviewed them, with no signal to the user. Existing pre-install checks look only at package names, sources and age. " },
  { text: "We need a gate that, before every launch and without executing package code, detects when the version about to run departs from the reviewed one in build provenance, publisher, install scripts or tool definitions, ", options: { bold: true, color: C.accent6 } },
  { text: "and that catches more real attacks than existing checks at a measured false-block cost." },
], { x: 0.9, y: 4.65, w: 11.5, h: 1.8, fontSize: 16, color: C.background1 });
source(s, "MCP = Model Context Protocol, the open standard through which agents call external tools. Rug pull: a server changes a tool after it was approved.");
s.addNotes("Context first: the four-step launch path. Then read the formal problem statement. It names the input (a launch), the constraint (no code execution), the signals, and the success criteria.");

// ---------- 3. motivation ----------
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Introduction" });
s.addText("Motivation and justification: why now", { placeholder: "title" });
rubric(s, "Criterion 1");
const why = [
  ["9.8%", "of 2,660 real agent setups launch MCP servers unpinned [1]", C.accent1],
  ["500+", "npm packages hit by the Shai-Hulud worm through stolen maintainer tokens, Sept. 2025 [2]", C.accent4],
  ["36.5%", "of 2,000 sampled MCP packages changed their tools within 90 days (our pilot census)", C.accent5],
  ["Rarely", "do coding assistants check trust signals before installing anything [3]", C.accent3],
];
why.forEach((w, i) => {
  const x = 0.6 + i * 3.075;
  card(s, x, 1.3, 2.85, 2.25, C.background2, "Why stat " + (i + 1));
  txt(s, w[0], { x: x + 0.2, y: 1.45, w: 2.45, h: 0.85, fontSize: 40, bold: true, color: w[2] });
  txt(s, w[1], { x: x + 0.2, y: 2.35, w: 2.5, h: 1.1, fontSize: 13, color: C.text2 });
});
card(s, 0.6, 3.8, 5.9, 2.8, C.background2, "Beneficiaries");
txt(s, "Who benefits", { x: 0.85, y: 3.95, w: 5.4, h: 0.4, fontSize: 18, bold: true });
txt(s, [
  { text: "Developers using AI coding agents: ", options: { bold: true, bullet: true } },
  { text: "their keys, files and tokens stay safe", options: { breakLine: true } },
  { text: "Companies and security teams: ", options: { bold: true, bullet: true } },
  { text: "one auditable lockfile for every approved tool server", options: { breakLine: true } },
  { text: "Open-source maintainers and registries: ", options: { bold: true, bullet: true } },
  { text: "a hijacked release no longer spreads silently" },
], { x: 0.85, y: 4.45, w: 5.45, h: 2.05, fontSize: 14, paraSpaceAfter: 8 });
card(s, 6.8, 3.8, 5.9, 2.8, C.text1, "Scope");
txt(s, "Scope", { x: 7.05, y: 3.95, w: 5.4, h: 0.4, fontSize: 18, bold: true, color: C.accent1 });
txt(s, [
  { text: "In: ", options: { bold: true, color: C.accent3 } },
  { text: "MCP servers launched from npm and PyPI; attackers who squat a name, steal a token, enter the release pipeline, own the package, or own a dependency.", options: { breakLine: true } },
  { text: " ", options: { breakLine: true } },
  { text: "Out: ", options: { bold: true, color: C.accent4 } },
  { text: "compromise of the registry itself, forged Sigstore signatures, attacks on the language model." },
], { x: 7.05, y: 4.4, w: 5.45, h: 2.1, fontSize: 14, color: C.background1 });
source(s, "The 36.5% figure is from our RQ1 census (stratified random sample, tool definitions extracted statically). Numbers in [ ] refer to the References slide.");
s.addNotes("Why now: agents are adopted fast, launches are unpinned, worms already used stolen npm tokens, and tool definitions change often. Then who benefits and what is in and out of scope.");

// ---------- 4. literature survey ----------
pres.addSection({ title: "Background" });
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Background" });
s.addText("Literature survey", { placeholder: "title" });
rubric(s, "Criterion 2");
const lit = [
  ["[4]", "Ladisa et al., 2023\nIEEE S&P", "SoK: taxonomy of attacks on open-source supply chains, incl. account takeover and install scripts", "General package ecosystems; nothing on agents, MCP or tool descriptions"],
  ["[5]", "Hou et al., 2025\narXiv", "Survey of the MCP landscape; defines tool poisoning and rug-pull threats", "Survey only: no defence measured on real packages"],
  ["[6]", "Bhatt et al., 2025\narXiv", "ETDI: OAuth-signed, versioned tool definitions with policy-based access control", "Needs servers and registries to change and sign; not usable with existing unsigned packages"],
  ["[7]", "Bagmar & Saraf, 2026\narXiv", "Pre-install hook for coding agents: 7 checks on name, source and age (pip)", "Never compares with the version you reviewed; misses hijacks of existing packages"],
  ["[1]", "Kapner et al., 2026\narXiv", "Scans 2,660 coding-agent setups; finds 9.8% with unpinned MCP servers", "Measures exposure only; no provenance analysis and no defence"],
  ["[8]", "Kraishan, 2026\narXiv", "Census of drift in MCP-registry fields over 8,900 multi-version servers", "Registry does not version tool definitions, so tool changes go unmeasured; recommends client-side pinning"],
];
const litRows = [[th("Ref", { align: "center" }), th("Author, year, venue"), th("Method / contribution"), th("Limitation (what is left open)")]];
lit.forEach((r, i) => {
  const f = { color: i % 2 ? "F5F7FA" : "FFFFFF" };
  litRows.push([td(r[0], { align: "center", bold: true, fill: f, color: HEX.accent5 }), td(r[1], { bold: true, fill: f }), td(r[2], { fill: f, fontSize: 11.5 }), td(r[3], { fill: f, fontSize: 11.5, color: "A01F2D" })]);
});
s.addTable(litRows, { x: 0.6, y: 1.25, w: 12.1, colW: [0.6, 2.3, 4.7, 4.5], rowH: [0.42, 0.68, 0.68, 0.68, 0.68, 0.68, 0.68], border: { type: "solid", pt: 0.75, color: "D5DAE2" } });
card(s, 0.6, 6.12, 12.1, 0.5, "FDF1D6", "Survey takeaway");
txt(s, [
  { text: "Common thread: ", options: { bold: true, color: C.accent4 } },
  { text: "no work checks, before launch, whether a server's build, publisher, install scripts and tools still match what was reviewed." },
], { x: 0.8, y: 6.15, w: 11.7, h: 0.5, fontSize: 14, valign: "middle" });
source(s, "All six sources verified against their primary pages (docs/CITATIONS_VERIFIED.md). Ladisa et al. appeared at IEEE S&P 2023, DOI 10.1109/SP46215.2023.10179304.");
s.addNotes("Six works across three layers: generic supply chain (Ladisa), MCP threats and defences (Hou, ETDI), and agent supply chains (Bagmar & Saraf, Kapner, Kraishan). The red column is what each leaves open.");

// ---------- 5. gap, market, patents ----------
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Background" });
s.addText("Research gap, market and patent study", { placeholder: "title" });
rubric(s, "Criterion 2");
const Y = "✓", N = "✗", P = "partly";
const head = ["Existing solution", "Before launch, runs no code", "Pins tool definitions", "Build, publisher, script continuity", "No server / registry change"];
const rows = [
  ["Bagmar & Saraf hook [7]", Y, N, N, Y],
  ["MCP-Scan, mcp-pin, mcpseal [9]–[11]", N, Y, P, Y],
  ["Signed definitions: ETDI [6]", "–", Y, "–", N],
  ["npm provenance, Sigstore [12], [13]", Y, N, P, Y],
  ["MCP-Lock (proposed)", Y, Y, Y, Y],
];
const cell = (v, last) => ({ text: v, options: { align: "center", valign: "middle", bold: true, fontSize: v.length > 1 ? 12 : 18, color: v === Y ? HEX.accent3 : v === N ? HEX.accent4 : HEX.dk2, fill: { color: last ? "FDF1D6" : "FFFFFF" } } });
const gt = [head.map((h, i) => th(h, { fontSize: 12, align: i ? "center" : "left" }))];
rows.forEach((r, ri) => {
  const last = ri === rows.length - 1;
  gt.push(r.map((v, ci) => (ci === 0 ? td(v, { bold: last, fontSize: 12.5, fill: { color: last ? "FDF1D6" : "FFFFFF" } }) : cell(v, last))));
});
s.addTable(gt, { x: 0.6, y: 1.2, w: 7.3, colW: [3.1, 1.05, 1.05, 1.05, 1.05], rowH: [0.62, 0.42, 0.42, 0.42, 0.42, 0.42], border: { type: "solid", pt: 0.75, color: "D5DAE2" } });
card(s, 8.15, 1.2, 4.55, 2.85, C.background2, "Patent study");
txt(s, "Patent landscape", { x: 8.35, y: 1.3, w: 4.2, h: 0.35, fontSize: 15, bold: true });
txt(s, [
  { text: "US 12,314,394 B2 (Socket, 2025) [14]: ", options: { bold: true, breakLine: true } },
  { text: "scans a project's dependency files for malware via a cache of scanned packages. No comparison with a reviewed version.", options: { breakLine: true } },
  { text: "US 10,055,576 B2 (Red Hat, 2018) [15]: ", options: { bold: true, breakLine: true } },
  { text: "blocks repository packages whose components are on an insecure list. Known-bad lists only.", options: { breakLine: true } },
  { text: "No patent found that pins agent tool definitions before launch.", options: { italic: true, color: C.accent5 } },
], { x: 8.35, y: 1.7, w: 4.2, h: 2.3, fontSize: 12, paraSpaceAfter: 3 });
const gaps = [
  ["G1", "No measurement of how often MCP tool definitions really change"],
  ["G2", "No check reads tool definitions before launch, without starting the server"],
  ["G3", "No continuity checks on build, publisher and install scripts per server"],
  ["G4", "No evaluation on real attacks with the false-block cost on honest upgrades"],
];
gaps.forEach((g, i) => {
  const x = 0.6 + (i % 2) * 3.7, y = 4.55 + Math.floor(i / 2) * 1.02;
  card(s, x, y, 3.55, 0.95, "FBE9EB", "Gap " + g[0]);
  badge(s, x + 0.15, y + 0.2, 0.55, C.accent4, g[0], C.background1, 13, "Gap badge " + g[0]);
  txt(s, g[1], { x: x + 0.85, y: y + 0.08, w: 2.6, h: 0.8, fontSize: 12.5, valign: "middle" });
});
card(s, 8.15, 4.3, 4.55, 2.22, C.text1, "Proposed edge");
txt(s, "Our edge", { x: 8.35, y: 4.42, w: 4.2, h: 0.35, fontSize: 15, bold: true, color: C.accent1 });
txt(s, "One lockfile pins archive, provenance, publisher, install scripts and tool definitions; the gate checks all five before every launch, needs no ecosystem change, and closes G1–G4.", { x: 8.35, y: 4.82, w: 4.2, h: 1.6, fontSize: 14, color: C.background1 });
source(s, "Market: Socket and npm provenance protect packages, MCP-Scan and the pinning proxies protect tools after start-up. Patent search: Google Patents, 3 Nov. 2026, not exhaustive.");
s.addNotes("Table: no existing solution ticks all four boxes. Patents cover malware scanning and known-bad lists, not pinning a reviewed state. G1 to G4 are the explicit gaps the objectives answer.");

// ---------- 6. objectives ----------
pres.addSection({ title: "Plan" });
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Plan" });
s.addText("Objectives (SMART)", { placeholder: "title" });
rubric(s, "Criterion 3");
const obj = [
  ["O1", "Measure the problem", "Census MCP packages on npm and PyPI; extract tool definitions from a stratified sample of 2,000 and report the 90-day change rate with 95% intervals.", "G1", "Done: 15,272 packages; 36.5% changed tools"],
  ["O2", "Build MCP-Lock", "A lockfile and a launch gate with 5 checks (S1–S5) that never runs package code, installable as a coding-agent hook and covered by automated tests.", "G2, G3", "Done: gate + hook, 103 tests"],
  ["O3", "Prove it works", "Pre-registered test on ≥ 490 real attacks: detect more than the baseline (McNemar, α = 0.05); report false blocks on 8,180 honest upgrades; withdraw the claim if S2–S5 add < 2.", "G4", "Done: 39.8% vs 19.6%, +0.42 pp"],
  ["O4", "Stress-test and publish", "Build 12 adaptive attacks, add hardening with measured costs, release code and data, and submit an IEEE paper before the final review.", "G2–G4", "Planned: paper drafted, to submit"],
];
obj.forEach((o, i) => {
  const x = 0.6 + i * 3.075;
  card(s, x, 1.25, 2.85, 5.3, C.background2, "Objective " + o[0]);
  badge(s, x + 0.2, 1.42, 0.7, C.accent1, o[0], C.text1, 17, "Objective badge " + o[0]);
  txt(s, o[1], { x: x + 1.05, y: 1.42, w: 1.7, h: 0.7, fontSize: 16, bold: true, valign: "middle" });
  txt(s, o[2], { x: x + 0.2, y: 2.3, w: 2.48, h: 2.45, fontSize: 15, color: C.text2 });
  txt(s, "Closes " + o[3], { x: x + 0.2, y: 4.8, w: 2.45, h: 0.3, fontSize: 12, bold: true, color: C.accent4 });
  const done = o[4].startsWith("Done");
  card(s, x + 0.15, 5.2, 2.55, 1.15, done ? "D7F0EC" : "FDF1D6", "Status " + o[0]);
  txt(s, o[4], { x: x + 0.28, y: 5.25, w: 2.3, h: 1.05, fontSize: 13, bold: true, valign: "middle", color: done ? "1D6F65" : "8A5A00" });
});
source(s, "S specific task · M a number or test · A sized to a 3-person team · R tied to gap G1–G4 · T each closes at a review milestone (see work plan).");
s.addNotes("Four objectives, each specific, measurable, tied to a gap and to a review milestone. O3 includes a kill rule fixed in advance, so the claim can fail.");

// ---------- 7. SDGs ----------
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Plan" });
s.addText("Alignment with UN Sustainable Development Goals", { placeholder: "title" });
rubric(s, "Criterion 4");
const sdg = [
  ["9", "Industry, Innovation and Infrastructure", "FD6925", [
    ["9.1", "Reliable, resilient infrastructure: the open-source supply chain is digital infrastructure; MCP-Lock keeps one hijacked release from reaching every agent that launches it."],
    ["9.5", "Upgrade technological capability: a new, pre-registered security method with public code."],
  ]],
  ["16", "Peace, Justice and Strong Institutions", "00689D", [
    ["16.a", "Capacity to prevent crime: blocks the cyber-crime pattern behind worms like Shai-Hulud (stolen tokens, install-script payloads)."],
    ["16.6", "Accountable, transparent systems: every verdict is traceable to an auditable lockfile."],
  ]],
  ["17", "Partnerships for the Goals", "19486A", [
    ["17.6", "Knowledge sharing in science and technology: code, data, replay bundles and the OSF pre-registration are open, so others, including developing-country teams, can reuse and verify them."],
  ]],
];
sdg.forEach((g, i) => {
  const x = 0.6 + i * 4.1;
  card(s, x, 1.25, 3.9, 5.25, C.background2, "SDG " + g[0]);
  s.addShape(pres.shapes.RECTANGLE, { x: x + 0.25, y: 1.45, w: 1.1, h: 1.1, fill: { color: g[2] }, line: { type: "none" }, objectName: "SDG tile " + g[0] });
  txt(s, g[0], { x: x + 0.25, y: 1.45, w: 1.1, h: 1.1, fontSize: 40, bold: true, align: "center", valign: "middle", color: C.background1 });
  txt(s, "SDG " + g[0], { x: x + 1.5, y: 1.5, w: 2.25, h: 0.35, fontSize: 13, bold: true, color: C.text2 });
  txt(s, g[1], { x: x + 1.5, y: 1.85, w: 2.25, h: 0.7, fontSize: 15, bold: true });
  g[3].forEach((t, j) => {
    const y = 2.85 + j * 1.85;
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: x + 0.25, y, w: 0.8, h: 0.4, rectRadius: 0.08, fill: { color: g[2] }, line: { type: "none" }, objectName: "SDG target " + t[0] });
    txt(s, t[0], { x: x + 0.25, y, w: 0.8, h: 0.4, fontSize: 13, bold: true, align: "center", valign: "middle", color: C.background1 });
    txt(s, t[1], { x: x + 1.2, y: y - 0.03, w: 2.5, h: 1.7, fontSize: 13.5, color: C.text1 });
  });
});
source(s, "Targets as defined in UN resolution A/RES/70/1, “Transforming our world: the 2030 Agenda for Sustainable Development” [17].");
s.addNotes("Primary SDG is 9: the software supply chain is infrastructure. SDG 16: preventing cyber crime and making decisions auditable. SDG 17: open science, everything public and reusable.");

// ---------- 8. methodology and architecture ----------
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Plan" });
s.addText("Proposed methodology and high-level architecture", { placeholder: "title" });
rubric(s, "Criteria 3 & 5");
const blocks = [
  [0.6, "AI coding agent", "launch request\nnpx -y / uvx", C.background2, C.text1],
  [2.95, "MCP-Lock hook", "intercepts the launch before it runs", C.accent1, C.text1],
  [5.3, "Resolver", "npm / PyPI: version, archive digest, attestation", C.background2, C.text1],
  [7.65, "Static extractor", "tree-sitter reads tools from the archive; no code runs", C.background2, C.text1],
  [10.0, "Checks S1–S5", "S1 name/source/age · S2 provenance · S3 publisher · S4 install scripts · S5 tools", C.text1, C.background1],
];
blocks.forEach((b, i) => {
  card(s, b[0], 1.35, 2.15, 1.55, b[3], "Arch " + b[1], b[3] === C.background2 ? { color: HEX.accent2, width: 0.75 } : undefined);
  txt(s, b[1], { x: b[0] + 0.12, y: 1.45, w: 1.95, h: 0.45, fontSize: 15, bold: true, align: "center", color: b[4] });
  txt(s, b[2], { x: b[0] + 0.12, y: 1.92, w: 1.95, h: 0.9, fontSize: 12, align: "center", color: b[4] });
  if (i < 4) arrow(s, b[0] + 2.17, 1.95, 0.32, C.accent2, "Arch arrow " + i);
});
card(s, 10.0, 3.15, 2.7, 0.95, "FDF1D6", "Lockfile store", { color: HEX.accent1, width: 1 });
txt(s, [{ text: "mcp-lock.json", options: { bold: true, fontFace: "Courier New", breakLine: true } }, { text: "digest · provenance · publisher · scripts · tool hash" }], { x: 10.1, y: 3.2, w: 2.5, h: 0.85, fontSize: 11.5, align: "center", valign: "middle" });
s.addShape(pres.shapes.LINE, { x: 11.35, y: 2.9, w: 0, h: 0.25, line: { color: HEX.accent1, width: 2 }, objectName: "Lock link" });
const verdicts = [["ALLOW", "matches the lock", C.accent3, C.background1], ["WARN", "tools changed: show diff, ask user", C.accent1, C.text1], ["BLOCK", "+ suggest last safe version", C.accent4, C.background1]];
verdicts.forEach((v, i) => {
  const x = 0.6 + i * 3.1;
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y: 3.25, w: 1.1, h: 0.5, rectRadius: 0.08, fill: { color: v[2] }, line: { type: "none" }, objectName: "Verdict " + v[0] });
  txt(s, v[0], { x, y: 3.25, w: 1.1, h: 0.5, fontSize: 13, bold: true, align: "center", valign: "middle", color: v[3] });
  txt(s, v[1], { x: x + 1.2, y: 3.25, w: 1.85, h: 0.5, fontSize: 12, valign: "middle", color: C.text2 });
});
txt(s, "Modules", { x: 0.6, y: 4.2, w: 6, h: 0.35, fontSize: 16, bold: true });
const mods = [
  ["census/", "RQ1: frame of MCP packages, version history, static tool extraction"],
  ["lockfile/", "lock format spec and canonical tool-definition hashing"],
  ["gate/", "checks S1–S5, verdicts, safe-version suggestions, agent hook, CLI"],
  ["eval/", "replay of 490 attacks and 8,180 upgrades; adaptive attacks in Docker"],
];
mods.forEach((m, i) => {
  const y = 4.6 + i * 0.5;
  txt(s, m[0], { x: 0.6, y, w: 1.3, h: 0.42, fontSize: 13, bold: true, fontFace: "Courier New", color: C.accent5, valign: "middle" });
  txt(s, m[1], { x: 1.95, y, w: 5.2, h: 0.42, fontSize: 13, valign: "middle" });
});
card(s, 7.5, 4.2, 5.2, 2.35, C.text1, "Tech stack");
txt(s, "Tech stack", { x: 7.75, y: 4.3, w: 4.7, h: 0.35, fontSize: 16, bold: true, color: C.accent1 });
const stack = ["Python 3.11", "tree-sitter (JS/TS)", "npm & PyPI APIs", "Sigstore / SLSA provenance", "Docker sandbox", "pytest + GitHub Actions", "Claude Code hook", "OSF · LaTeX IEEEtran"];
stack.forEach((t, i) => {
  const x = 7.75 + (i % 2) * 2.45, y = 4.75 + Math.floor(i / 2) * 0.43;
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w: 2.3, h: 0.35, rectRadius: 0.08, fill: { color: C.accent5 }, line: { type: "none" }, objectName: "Stack " + t });
  txt(s, t, { x, y, w: 2.3, h: 0.35, fontSize: 12, align: "center", valign: "middle", color: C.background1 });
});
source(s, "Method: lock once after review (mcplock lock), then the gate checks every launch. Evaluation is pre-registered on OSF [16] against the baseline hook [7].");
s.addNotes("Walk the pipeline left to right: the hook intercepts the launch, the resolver fetches metadata and the archive, the extractor reads tool definitions without running code, and the checks compare against the lockfile. Then modules and stack.");

// ---------- 9. work plan ----------
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Plan" });
s.addText("Work plan and review timeline", { placeholder: "title" });
rubric(s, "Criterion 5");
const phases = ["Up to Review 0", "Review 0 → Review 1", "Review 1 → Review 2", "Review 2 → Final"];
const gx = 4.6, gw = 8.1, colw = gw / 4, gy = 1.25;
phases.forEach((p, i) => {
  s.addShape(pres.shapes.RECTANGLE, { x: gx + i * colw, y: gy, w: colw, h: 0.45, fill: { color: i === 0 ? HEX.accent5 : HEX.dk1 }, line: { color: "FFFFFF", width: 1 }, objectName: "Phase " + i });
  txt(s, p, { x: gx + i * colw, y: gy, w: colw, h: 0.45, fontSize: 12, bold: true, align: "center", valign: "middle", color: C.background1 });
});
const tasks = [
  ["Problem study and literature survey", 0, 1, true],
  ["RQ1 census of MCP packages (O1)", 0, 1, true],
  ["Lockfile + gate S1–S5, 103 tests (O2)", 0, 1, true],
  ["OSF pre-registration, RQ2 evaluation (O3)", 0, 1, true],
  ["Adaptive attacks, hardening D1–D5 (O4)", 0, 1, true],
  ["IEEE paper draft and internal review", 0, 1.6, true],
  ["Guide review; expand methods & deviations", 1, 2, false],
  ["Live demo: agent hook + flow animation", 1, 2, false],
  ["Refresh related work, verify refs, pick venue", 1.5, 3, false],
  ["Submit IEEE paper + arXiv preprint", 2, 3, false],
  ["Project report, final demo and viva", 3, 4, false],
];
const rh = 0.4;
tasks.forEach((t, i) => {
  const y = gy + 0.55 + i * rh;
  if (i % 2 === 0) s.addShape(pres.shapes.RECTANGLE, { x: 0.6, y, w: 12.1, h: rh, fill: { color: "F5F7FA" }, line: { type: "none" }, objectName: "Row band " + i });
  txt(s, t[0], { x: 0.7, y, w: 3.85, h: rh, fontSize: 12.5, valign: "middle" });
  const bx = gx + t[1] * colw + 0.08, bw = (t[2] - t[1]) * colw - 0.16;
  const split = t[2] > 1 && t[1] < 1; // finished part before Review 0, rest after
  if (split) {
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: bx, y: y + 0.08, w: bw, h: rh - 0.16, rectRadius: 0.06, fill: { color: HEX.accent1 }, line: { type: "none" }, objectName: "Bar rest " + i });
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: bx, y: y + 0.08, w: colw - 0.16, h: rh - 0.16, rectRadius: 0.06, fill: { color: HEX.accent3 }, line: { type: "none" }, objectName: "Bar done " + i });
  } else {
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: bx, y: y + 0.08, w: bw, h: rh - 0.16, rectRadius: 0.06, fill: { color: t[3] ? HEX.accent3 : HEX.accent1 }, line: { type: "none" }, objectName: "Bar " + i });
  }
});
const my = gy + 0.55 + tasks.length * rh + 0.08;
["Review 0", "Review 1", "Review 2", "Final"].forEach((m, i) => {
  const x = gx + (i + 1) * colw;
  s.addShape(pres.shapes.LINE, { x, y: gy + 0.45, w: 0, h: my - gy - 0.45, line: { color: HEX.accent4, width: 1, dashType: "dash" }, objectName: "Milestone line " + m });
  s.addShape(pres.shapes.DIAMOND, { x: x - 0.14, y: my, w: 0.28, h: 0.28, fill: { color: HEX.accent4 }, line: { type: "none" }, objectName: "Milestone " + m });
  txt(s, m, { x: x - 0.8, y: my + 0.3, w: 1.6, h: 0.3, fontSize: 12, bold: true, align: "center", color: C.accent4 });
});
s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 0.7, y: gy + 0.11, w: 0.45, h: 0.22, rectRadius: 0.05, fill: { color: HEX.accent3 }, line: { type: "none" }, objectName: "Legend done" });
txt(s, "done (8 Oct – 3 Nov 2026)", { x: 1.25, y: gy + 0.06, w: 1.85, h: 0.32, fontSize: 11.5, valign: "middle" });
s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 3.15, y: gy + 0.11, w: 0.45, h: 0.22, rectRadius: 0.05, fill: { color: HEX.accent1 }, line: { type: "none" }, objectName: "Legend planned" });
txt(s, "planned", { x: 3.7, y: gy + 0.06, w: 0.85, h: 0.32, fontSize: 11.5, valign: "middle" });
source(s, "Done dates from the project's git history. Review dates follow the department calendar.");
s.addNotes("Most of the research is already done: census, gate, pre-registered evaluation, hardening and a paper draft. The remaining phases are guide review, the demo, submission and the final report.");

// ---------- 10. references ----------
pres.addSection({ title: "References" });
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "References" });
s.addText("References", { placeholder: "title" });
rubric(s, "Criteria 2 & 5");
const refs = [
  "B. Kapner, C. Soceanu, A. Petrunin, and H. Gartner, “Scanning the harness: Configuration exposures in AI coding-agent supply chains,” arXiv:2609.07360v3, 2026.",
  "CISA, “Widespread supply chain compromise impacting npm ecosystem,” Alert, Sept. 23, 2025.",
  "P. Shan, “Do AI coding assistants check before they install? A pre-registered demand-side audit of trust signals in the research software supply chain,” arXiv:2609.07754, 2026.",
  "P. Ladisa, H. Plate, M. Martinez, and O. Barais, “SoK: Taxonomy of attacks on open-source software supply chains,” in Proc. IEEE Symp. Security and Privacy (SP), 2023, pp. 1509–1526, doi: 10.1109/SP46215.2023.10179304.",
  "X. Hou, Y. Zhao, S. Wang, and H. Wang, “Model Context Protocol (MCP): Landscape, security threats, and future research directions,” arXiv:2503.23278, 2025.",
  "M. Bhatt, V. S. Narajala, and I. Habler, “ETDI: Mitigating tool squatting and rug pull attacks in Model Context Protocol (MCP) by using OAuth-enhanced tool definitions and policy-based access control,” arXiv:2506.01333, 2025.",
  "A. Bagmar and P. Saraf, “Setup complete, now you are compromised: Weaponizing setup instructions against AI coding agents,” arXiv:2607.15143, 2026.",
  "O. Kraishan, “Same name, different server: A security census of silent drift in the Model Context Protocol ecosystem,” arXiv:2609.14119, 2026.",
  "L. Beurer-Kellner and M. Fischer, “Introducing MCP-Scan: Protecting MCP with Invariant,” Invariant Labs blog, Apr. 2025.",
  "GautamTalksDev, “mcp-pin: Pin what your agent approved; block it when it changes,” GitHub, 2026. [Online]. Available: github.com/GautamTalksDev/mcp-pin",
  "confuseddude, “mcpseal: Pins the hash of every approved MCP tool definition,” GitHub, 2026. [Online]. Available: github.com/confuseddude/mcpseal",
  "npm, “Generating provenance statements,” npm Docs, 2026. [Online]. Available: docs.npmjs.com/generating-provenance-statements",
  "Z. Newman, J. S. Meyers, and S. Torres-Arias, “Sigstore: Software signing for everybody,” in Proc. ACM CCS, 2022, pp. 2353–2367, doi: 10.1145/3548606.3560596.",
  "F. H. Aboukhadijeh and M. C. Lysenko, “Detecting suspected malware in open-source dependencies,” U.S. Patent 12,314,394 B2, May 27, 2025.",
  "S. B. Milner and J. R. Bowes, “Detection of malicious software packages,” U.S. Patent 10,055,576 B2, Aug. 21, 2018.",
  "A. G S, “MCP-Lock: Does provenance and tool-definition pinning catch MCP-server supply-chain attacks that name/source checks miss, and at what false-block cost?” OSF Registries, Oct. 2026, doi: 10.17605/OSF.IO/2AMJ3.",
  "United Nations General Assembly, “Transforming our world: The 2030 Agenda for Sustainable Development,” Resolution A/RES/70/1, Oct. 2015.",
];
const half = Math.ceil(refs.length / 2);
[refs.slice(0, half), refs.slice(half)].forEach((col, ci) => {
  txt(s, col.map((r, i) => ({ text: `[${ci * half + i + 1}]  ${r}`, options: { breakLine: i < col.length - 1 } })), { x: 0.6 + ci * 6.15, y: 1.25, w: 5.95, h: 5.35, fontSize: 11.5, paraSpaceAfter: 5, color: C.text1 });
});
source(s, "Code and data: github.com/ftaakash/MCP-Lock · All entries checked against their primary source (docs/CITATIONS_VERIFIED.md); patents checked on Google Patents.");
s.addNotes("IEEE-style references in order of first citation in this deck: papers, tools, patents, our pre-registration and the UN SDG resolution.");

(async () => {
  const out = path.join(__dirname, "MCP-Lock-Review0.pptx");
  await pres.writeFile({ fileName: out });
  await applyTheme(out, THEME);
  console.log("wrote", out);
})();
