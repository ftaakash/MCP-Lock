// Builds MCP-Lock-Review0.pptx: the 10-slide Review 0 deck, one slide per rubric item (21CSP401L), in the
// department's black-and-white template (Times New Roman, SRM logo top right on every slide).
// Numbers come from paper/numbers.tex; references from paper/refs.bib (docs/CITATIONS_VERIFIED.md) plus two
// patents checked on Google Patents on 2026-11-03.
// Run: NODE_PATH=<dir with pptxgenjs> node make_review0.js <path to pptx skill apply_theme.js>
const path = require("path");
const pptxgen = require("pptxgenjs");
const { applyTheme } = require(process.argv[2]);

const THEME = {
  name: "SRM Review",
  headFontFace: "Times New Roman",
  bodyFontFace: "Times New Roman",
  colors: {
    dk1: "000000", lt1: "FFFFFF", dk2: "404040", lt2: "F2F2F2",
    accent1: "000000", accent2: "595959", accent3: "7F7F7F", accent4: "A6A6A6", accent5: "262626", accent6: "D9D9D9",
    hlink: "000000", folHlink: "404040",
  },
};
const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE";
pres.title = "MCP-Lock: Review 0";
pres.author = "Aakash G S, Hariharan J, J Jaswanth Raj";
pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };
const C = pres.SchemeColor;
const LOGO = path.join(__dirname, "srm_logo.png");
const logo = { image: { path: LOGO, x: 10.81, y: 0.68, w: 1.71, h: 0.58 } };
const BLACK = "000000", GREY = "F2F2F2";

pres.defineSlideMaster({
  title: "TITLE",
  background: { color: C.background1 },
  objects: [
    logo,
    { placeholder: { options: { name: "title", type: "title", x: 1.2, y: 1.55, w: 10.9, h: 1.9, fontSize: 32, bold: true, color: C.text1, align: "center", valign: "middle", margin: 0 }, text: "" } },
  ],
});
pres.defineSlideMaster({
  title: "CONTENT",
  background: { color: C.background1 },
  margin: [0.5, 0.6, 0.6, 0.6],
  objects: [
    logo,
    { placeholder: { options: { name: "title", type: "title", x: 0.92, y: 1.0, w: 9.7, h: 0.7, fontSize: 28, bold: true, color: C.text1, align: "left", valign: "middle", margin: 0 }, text: "" } },
  ],
  slideNumber: { x: 12.2, y: 7.0, w: 0.5, h: 0.3, fontSize: 11, color: C.text2, align: "right" },
});

function txt(s, text, o) {
  s.addText(text, Object.assign({ margin: 0, isTextBox: true, fontSize: 16, color: C.text1, valign: "top" }, o));
}
function box(s, x, y, w, h, name, fill) {
  s.addShape(pres.shapes.RECTANGLE, { x, y, w, h, fill: { color: fill || "FFFFFF" }, line: { color: BLACK, width: 1 }, objectName: name });
}
function arrow(s, x, y, w, name) {
  s.addShape(pres.shapes.LINE, { x, y, w, h: 0, line: { color: BLACK, width: 1.5, endArrowType: "triangle" }, objectName: name });
}
function note(s, text) {
  txt(s, text, { x: 0.92, y: 6.75, w: 11.0, h: 0.3, fontSize: 11, italic: true, color: C.text2 });
}
// Bold label + text, one bullet per item.
const items = (rows, extra = {}) => rows.flatMap(([label, body], i) => [
  { text: label + " ", options: Object.assign({ bold: true, bullet: true }, extra) },
  { text: body, options: { breakLine: i < rows.length - 1 } },
]);
const th = (t, o = {}) => ({ text: t, options: Object.assign({ bold: true, fontSize: 14, color: BLACK, fill: { color: GREY }, valign: "middle" }, o) });
const td = (t, o = {}) => ({ text: t, options: Object.assign({ fontSize: 13, color: BLACK, valign: "middle" }, o) });
const border = { type: "solid", pt: 1, color: BLACK };

// ---------- 1. title and team ----------
pres.addSection({ title: "Introduction" });
let s = pres.addSlide({ masterName: "TITLE", sectionTitle: "Introduction" });
s.addText("MCP-Lock: Provenance and Tool-Definition Pinning to Stop AI Coding Agents from Silently Running Unreviewed Tool Servers", { placeholder: "title" });
txt(s, "Domain: Cybersecurity · Software Supply-Chain Security · AI Agents (Model Context Protocol)", { x: 1.2, y: 3.5, w: 10.9, h: 0.4, fontSize: 16, italic: true, align: "center" });
txt(s, [
  { text: "Guide: ", options: { bold: true, fontSize: 18 } },
  { text: "Mr. Sai Prasanth D", options: { fontSize: 18, breakLine: true } },
  { text: "Assistant Professor", options: { fontSize: 14, breakLine: true } },
  { text: "Department of Data Science and Business Systems", options: { fontSize: 14 } },
], { x: 1.3, y: 4.3, w: 4.8, h: 1.3, paraSpaceAfter: 6 });
const team = [["Aakash G S", "RA2311042010060"], ["Hariharan J", "RA2311042010059"], ["J Jaswanth Raj", "RA2311042010013"]];
txt(s, team.flatMap(([n, r], i) => [
  { text: `${n} (${r})`, options: { fontSize: 18, breakLine: true } },
  { text: "4th Year, B.Tech, DSBS Department", options: { fontSize: 13, breakLine: i < team.length - 1 } },
]), { x: 7.3, y: 4.3, w: 5.2, h: 2.6, paraSpaceAfter: 6 });
txt(s, "SRM Institute of Science and Technology, Kattankulathur  ·  21CSP401L Major Project  ·  Review 0", { x: 1.2, y: 6.85, w: 10.9, h: 0.35, fontSize: 13, align: "center", color: C.text2 });
s.addNotes("Introduce the team and guide. One line: MCP-Lock records what you reviewed and checks every launch of an agent's tool server against it.");

// ---------- 2. problem statement ----------
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Introduction" });
s.addText("Problem Statement & Background", { placeholder: "title" });
txt(s, "Background", { x: 0.92, y: 1.85, w: 11.5, h: 0.35, fontSize: 18, bold: true });
txt(s, [{ text: "AI coding agents (Claude Code, Cursor, …) get their tools from MCP servers, which they start straight from npm or PyPI with unpinned commands such as npx -y.", options: { bullet: true } }], { x: 0.92, y: 2.25, w: 11.5, h: 0.65, fontSize: 16, align: "justify" });
const steps = [
  ["1. Config says", "npx -y weather-mcp", "No version pinned: “give me the latest”"],
  ["2. Agent", "starts the server", "Automatically, every session"],
  ["3. Registry", "serves newest version", "May be hijacked or changed since review"],
  ["4. Server runs", "+ tools reach the model", "Tool descriptions act as instructions"],
];
steps.forEach((st, i) => {
  const x = 0.92 + i * 2.95;
  box(s, x, 3.0, 2.55, 1.35, "Step " + (i + 1));
  txt(s, st[0], { x: x + 0.12, y: 3.07, w: 2.3, h: 0.35, fontSize: 15, bold: true });
  txt(s, st[1], { x: x + 0.12, y: 3.42, w: 2.3, h: 0.35, fontSize: 13, fontFace: i === 0 ? "Courier New" : undefined, bold: i === 0 });
  txt(s, st[2], { x: x + 0.12, y: 3.77, w: 2.3, h: 0.55, fontSize: 12, italic: true });
  if (i < 3) arrow(s, x + 2.57, 3.67, 0.36, "Flow arrow " + i);
});
txt(s, "Problem Statement", { x: 0.92, y: 4.6, w: 11.5, h: 0.35, fontSize: 18, bold: true });
txt(s, [{ text: "Unpinned MCP-server launches let the code and the tool descriptions an agent runs change after a human reviewed them, with no signal to the user; existing pre-install checks look only at package names, sources and age. Develop a gate that, before every launch and without executing package code, detects when the version about to run departs from the reviewed one in build provenance, publisher, install scripts or tool definitions, and that catches more real attacks than existing checks at a measured false-block cost.", options: { bullet: true } }], { x: 0.92, y: 5.0, w: 11.5, h: 1.65, fontSize: 16, align: "justify" });
note(s, "MCP = Model Context Protocol, the open standard through which agents call external tools. Rug pull: a server changes a tool after it was approved.");
s.addNotes("Context first: the four-step launch path. Then read the formal problem statement. It names the input (a launch), the constraint (no code execution), the signals, and the success criteria.");

// ---------- 3. motivation ----------
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Introduction" });
s.addText("Motivation & Justification", { placeholder: "title" });
const why = [
  ["9.8%", "of 2,660 real agent setups launch MCP servers unpinned [1]"],
  ["500+", "npm packages hit by the Shai-Hulud worm through stolen maintainer tokens, Sept. 2025 [2]"],
  ["36.5%", "of 2,000 sampled MCP packages changed their tools within 90 days (our pilot census)"],
  ["Rarely", "do coding assistants check trust signals before installing anything [3]"],
];
why.forEach((w, i) => {
  const x = 0.92 + i * 2.9;
  box(s, x, 1.9, 2.7, 1.75, "Why stat " + (i + 1));
  txt(s, w[0], { x: x + 0.15, y: 1.98, w: 2.4, h: 0.6, fontSize: 30, bold: true, align: "center" });
  txt(s, w[1], { x: x + 0.15, y: 2.6, w: 2.4, h: 1.0, fontSize: 13, align: "center" });
});
txt(s, items([
  ["Why now:", "agents start tool servers unattended, worms already used stolen npm tokens, and tool definitions change often without any metadata signal."],
  ["Target beneficiaries:", "developers using AI coding agents (their keys, files and tokens stay safe); companies and security teams (one auditable lockfile for every approved tool server); open-source maintainers and registries (a hijacked release no longer spreads silently)."],
  ["Scope (in):", "MCP servers launched from npm and PyPI; attackers who squat a name, steal a token, enter the release pipeline, own the package, or own a dependency."],
  ["Scope (out):", "compromise of the registry itself, forged Sigstore signatures, attacks on the language model."],
]), { x: 0.92, y: 3.9, w: 11.5, h: 2.8, fontSize: 15, align: "justify", paraSpaceAfter: 6 });
note(s, "The 36.5% figure is from our RQ1 census (stratified random sample, tool definitions extracted statically). Numbers in [ ] refer to the References slide.");
s.addNotes("Why now: agents are adopted fast, launches are unpinned, worms already used stolen npm tokens, and tool definitions change often. Then who benefits and what is in and out of scope.");

// ---------- 4. literature survey ----------
pres.addSection({ title: "Background" });
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Background" });
s.addText("Literature Survey", { placeholder: "title" });
const lit = [
  ["Ladisa et al. [4]", "2023", "IEEE S&P: SoK taxonomy of attacks on open-source supply chains, incl. account takeover and install scripts", "General package ecosystems; nothing on agents, MCP or tool descriptions"],
  ["Hou et al. [5]", "2025", "Survey of the MCP landscape; defines tool poisoning and rug-pull threats", "Survey only: no defence measured on real packages"],
  ["Bhatt et al. [6]", "2025", "ETDI: OAuth-signed, versioned tool definitions with policy-based access control", "Needs servers and registries to change and sign; not usable with existing unsigned packages"],
  ["Bagmar & Saraf [7]", "2026", "Pre-install hook for coding agents: 7 checks on name, source and age (pip)", "Never compares with the version you reviewed; misses hijacks of existing packages"],
  ["Kapner et al. [1]", "2026", "Scans 2,660 coding-agent setups; finds 9.8% with unpinned MCP servers", "Measures exposure only; no provenance analysis and no defence"],
  ["Kraishan [8]", "2026", "Census of drift in MCP-registry fields over 8,900 multi-version servers", "Registry does not version tool definitions, so tool changes go unmeasured; recommends client-side pinning"],
];
s.addTable([[th("Paper / Authors"), th("Year"), th("Method / Contribution"), th("Limitation")], ...lit.map((r) => r.map((c) => td(c, { fontSize: 12.5 })))], {
  x: 0.92, y: 1.85, w: 11.5, colW: [2.2, 0.75, 4.4, 4.15], rowH: [0.4, 0.6, 0.6, 0.6, 0.6, 0.6, 0.6], border, fontFace: "Times New Roman",
});
txt(s, [{ text: "Common thread: ", options: { bold: true } }, { text: "no work checks, before launch, whether a server's build, publisher, install scripts and tools still match what was reviewed." }], { x: 0.92, y: 6.25, w: 11.5, h: 0.45, fontSize: 14 });
note(s, "All six sources verified against their primary pages (docs/CITATIONS_VERIFIED.md). Ladisa et al., IEEE S&P 2023, DOI 10.1109/SP46215.2023.10179304.");
s.addNotes("Six works across three layers: generic supply chain (Ladisa), MCP threats and defences (Hou, ETDI), and agent supply chains (Bagmar & Saraf, Kapner, Kraishan). The last column is what each leaves open.");

// ---------- 5. gap, market, patents ----------
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Background" });
s.addText("Research Gap & Market / Patent Study", { placeholder: "title" });
const Y = "✓", N = "✗", P = "partly";
const head = ["Existing solution", "Before launch, runs no code", "Pins tool definitions", "Build, publisher, script continuity", "No server / registry change"];
const rows = [
  ["Bagmar & Saraf hook [7]", Y, N, N, Y],
  ["MCP-Scan, mcp-pin, mcpseal [9]–[11]", N, Y, P, Y],
  ["Signed definitions: ETDI [6]", "–", Y, "–", N],
  ["npm provenance, Sigstore [12], [13]", Y, N, P, Y],
  ["MCP-Lock (proposed)", Y, Y, Y, Y],
];
s.addTable([
  head.map((h, i) => th(h, { fontSize: 12, align: i ? "center" : "left" })),
  ...rows.map((r, ri) => r.map((v, ci) => td(v, ci === 0
    ? { fontSize: 12.5, bold: ri === rows.length - 1 }
    : { align: "center", fontSize: v.length > 1 ? 12 : 16, bold: ri === rows.length - 1 }))),
], { x: 0.92, y: 1.85, w: 7.0, colW: [2.8, 1.05, 1.05, 1.05, 1.05], rowH: [0.62, 0.38, 0.38, 0.38, 0.38, 0.38], border, fontFace: "Times New Roman" });
txt(s, "Patent landscape", { x: 8.2, y: 1.85, w: 4.3, h: 0.35, fontSize: 16, bold: true });
txt(s, [
  { text: "US 12,314,394 B2 (Socket, 2025) [14]: ", options: { bold: true, bullet: true } },
  { text: "scans a project's dependency files for malware via a cache of scanned packages; no comparison with a reviewed version.", options: { breakLine: true } },
  { text: "US 10,055,576 B2 (Red Hat, 2018) [15]: ", options: { bold: true, bullet: true } },
  { text: "blocks repository packages whose components are on an insecure list; known-bad lists only.", options: { breakLine: true } },
  { text: "No patent found that pins agent tool definitions before launch.", options: { bullet: true, italic: true } },
], { x: 8.2, y: 2.25, w: 4.3, h: 2.35, fontSize: 13, paraSpaceAfter: 4 });
txt(s, "Research gaps", { x: 0.92, y: 4.98, w: 7, h: 0.35, fontSize: 16, bold: true });
txt(s, items([
  ["G1:", "no measurement of how often MCP tool definitions really change."],
  ["G2:", "no check reads tool definitions before launch, without starting the server."],
  ["G3:", "no continuity checks on build, publisher and install scripts per server."],
  ["G4:", "no evaluation on real attacks with the false-block cost on honest upgrades."],
]), { x: 0.92, y: 5.35, w: 7.0, h: 1.35, fontSize: 13.5, paraSpaceAfter: 2 });
txt(s, "Market and our edge", { x: 8.2, y: 4.35, w: 4.3, h: 0.35, fontSize: 16, bold: true });
txt(s, [
  { text: "Socket and npm provenance protect packages; MCP-Scan and the pinning proxies protect tools only after start-up.", options: { bullet: true, breakLine: true } },
  { text: "MCP-Lock: one lockfile pins archive, provenance, publisher, install scripts and tool definitions; the gate checks all five before every launch, needs no ecosystem change, and closes G1–G4.", options: { bullet: true } },
], { x: 8.2, y: 4.75, w: 4.3, h: 1.9, fontSize: 13, paraSpaceAfter: 4 });
note(s, "Patent search: Google Patents, 3 Nov. 2026, not exhaustive.");
s.addNotes("Table: no existing solution ticks all four boxes. Patents cover malware scanning and known-bad lists, not pinning a reviewed state. G1 to G4 are the explicit gaps the objectives answer.");

// ---------- 6. objectives ----------
pres.addSection({ title: "Plan" });
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Plan" });
s.addText("Objectives / Product Goals", { placeholder: "title" });
const obj = [
  ["O1. Measure the problem", "Census MCP packages on npm and PyPI; extract tool definitions from a stratified sample of 2,000 and report the 90-day change rate with 95% intervals.", "G1", "Done: 15,272 packages; 36.5% changed tools"],
  ["O2. Build MCP-Lock", "A lockfile and a launch gate with 5 checks (S1–S5) that never runs package code, installable as a coding-agent hook and covered by automated tests.", "G2, G3", "Done: gate + hook, 103 tests"],
  ["O3. Prove it works", "Pre-registered test on ≥ 490 real attacks: detect more than the baseline (McNemar, α = 0.05); report false blocks on 8,180 honest upgrades; withdraw the claim if S2–S5 add < 2.", "G4", "Done: 39.8% vs 19.6%, +0.42 pp"],
  ["O4. Stress-test and publish", "Build 12 adaptive attacks, add hardening with measured costs, release code and data, and submit an IEEE paper before the final review.", "G2–G4", "Planned: paper drafted, to submit"],
];
s.addTable([[th("Objective"), th("Specific, measurable target"), th("Gap"), th("Status at Review 0")], ...obj.map((o) => [td(o[0], { bold: true }), td(o[1]), td(o[2], { align: "center" }), td(o[3])])], {
  x: 0.92, y: 1.85, w: 11.5, colW: [2.4, 5.9, 0.8, 2.4], rowH: [0.4, 0.95, 0.95, 0.95, 0.95], border, fontFace: "Times New Roman",
});
note(s, "SMART: S specific task · M a number or test · A sized to a 3-person team · R tied to gap G1–G4 · T each closes at a review milestone (see work plan).");
s.addNotes("Four objectives, each specific, measurable, tied to a gap and to a review milestone. O3 includes a kill rule fixed in advance, so the claim can fail.");

// ---------- 7. SDGs ----------
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Plan" });
s.addText("Alignment with UN Sustainable Development Goals", { placeholder: "title" });
const sdg = [
  ["SDG 9: Industry, Innovation and Infrastructure", "9.1", "Reliable, resilient infrastructure: the open-source supply chain is digital infrastructure; MCP-Lock keeps one hijacked release from reaching every agent that launches it."],
  ["", "9.5", "Upgrade technological capability: a new, pre-registered security method with public code."],
  ["SDG 16: Peace, Justice and Strong Institutions", "16.a", "Capacity to prevent crime: blocks the cyber-crime pattern behind worms like Shai-Hulud (stolen tokens, install-script payloads)."],
  ["", "16.6", "Accountable, transparent systems: every verdict is traceable to an auditable lockfile."],
  ["SDG 17: Partnerships for the Goals", "17.6", "Knowledge sharing in science and technology: code, data, replay bundles and the OSF pre-registration are open, so others, including developing-country teams, can reuse and verify them."],
];
s.addTable([[th("Goal"), th("Target"), th("How MCP-Lock contributes")], ...sdg.map((r) => [td(r[0], { bold: true }), td(r[1], { align: "center", bold: true }), td(r[2])])], {
  x: 0.92, y: 1.85, w: 11.5, colW: [3.1, 0.9, 7.5], rowH: [0.4, 0.75, 0.55, 0.75, 0.55, 0.75], border, fontFace: "Times New Roman",
});
note(s, "Targets as defined in UN resolution A/RES/70/1, “Transforming our world: the 2030 Agenda for Sustainable Development” [17].");
s.addNotes("Primary SDG is 9: the software supply chain is infrastructure. SDG 16: preventing cyber crime and making decisions auditable. SDG 17: open science, everything public and reusable.");

// ---------- 8. methodology and architecture ----------
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Plan" });
s.addText("Proposed Methodology / High-Level Architecture", { placeholder: "title" });
const blocks = [
  ["AI coding agent", "launch request: npx -y / uvx"],
  ["MCP-Lock hook", "intercepts the launch before it runs"],
  ["Resolver", "npm / PyPI: version, archive digest, attestation"],
  ["Static extractor", "tree-sitter reads tools from the archive; no code runs"],
  ["Checks S1–S5", "S1 name/source/age · S2 provenance · S3 publisher · S4 install scripts · S5 tools"],
];
blocks.forEach((b, i) => {
  const x = 0.92 + i * 2.34;
  box(s, x, 1.9, 2.0, 1.45, "Arch " + b[0], i === 1 ? GREY : undefined);
  txt(s, b[0], { x: x + 0.08, y: 1.97, w: 1.84, h: 0.35, fontSize: 14, bold: true, align: "center" });
  txt(s, b[1], { x: x + 0.08, y: 2.35, w: 1.84, h: 0.95, fontSize: 11.5, align: "center" });
  if (i < 4) arrow(s, x + 2.02, 2.62, 0.3, "Arch arrow " + i);
});
box(s, 10.28, 3.6, 2.0, 0.85, "Lockfile store");
txt(s, [{ text: "mcp-lock.json", options: { bold: true, fontFace: "Courier New", breakLine: true } }, { text: "digest · provenance · publisher · scripts · tool hash" }], { x: 10.33, y: 3.63, w: 1.9, h: 0.8, fontSize: 10.5, align: "center", valign: "middle" });
s.addShape(pres.shapes.LINE, { x: 11.28, y: 3.35, w: 0, h: 0.25, line: { color: BLACK, width: 1.5 }, objectName: "Lock link" });
txt(s, "Verdict returned to the agent:", { x: 0.92, y: 3.6, w: 3.2, h: 0.35, fontSize: 14, bold: true });
txt(s, items([
  ["ALLOW:", "matches the lock."],
  ["WARN:", "tools changed; show the diff and ask the user."],
  ["BLOCK:", "build, scripts or name look wrong; suggest the last safe version."],
]), { x: 0.92, y: 3.95, w: 9.0, h: 0.95, fontSize: 13 });
txt(s, "Modules", { x: 0.92, y: 4.95, w: 5, h: 0.35, fontSize: 15, bold: true });
txt(s, items([
  ["census/", "RQ1: frame of MCP packages, version history, static tool extraction"],
  ["lockfile/", "lock format spec and canonical tool-definition hashing"],
  ["gate/", "checks S1–S5, verdicts, safe-version suggestions, agent hook, CLI"],
  ["eval/", "replay of 490 attacks and 8,180 upgrades; adaptive attacks in Docker"],
]), { x: 0.92, y: 5.3, w: 6.6, h: 1.4, fontSize: 12.5 });
txt(s, "Technology Stack", { x: 7.9, y: 4.95, w: 4.5, h: 0.35, fontSize: 15, bold: true });
txt(s, "Python 3.11, tree-sitter (JS/TS), npm & PyPI APIs, Sigstore / SLSA provenance, Docker sandbox, pytest + GitHub Actions, Claude Code hook, OSF pre-registration, LaTeX IEEEtran.", { x: 7.9, y: 5.3, w: 4.5, h: 1.4, fontSize: 13 });
note(s, "Method: lock once after review (mcplock lock), then the gate checks every launch. Evaluation is pre-registered on OSF [16] against the baseline hook [7].");
s.addNotes("Walk the pipeline left to right: the hook intercepts the launch, the resolver fetches metadata and the archive, the extractor reads tool definitions without running code, and the checks compare against the lockfile. Then modules and stack.");

// ---------- 9. work plan ----------
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Plan" });
s.addText("Work Plan & Review Timeline", { placeholder: "title" });
const phases = ["Up to Review 0", "Review 0 → Review 1", "Review 1 → Review 2", "Review 2 → Final"];
const gx = 5.0, gw = 7.5, colw = gw / 4, gy = 1.85;
phases.forEach((p, i) => {
  box(s, gx + i * colw, gy, colw, 0.42, "Phase " + i, GREY);
  txt(s, p, { x: gx + i * colw, y: gy, w: colw, h: 0.42, fontSize: 12.5, bold: true, align: "center", valign: "middle" });
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
const rh = 0.37;
const bar = (x, y, w, done, name) => s.addShape(pres.shapes.RECTANGLE, { x, y, w, h: rh - 0.14, fill: { color: done ? BLACK : "FFFFFF" }, line: { color: BLACK, width: 1 }, objectName: name });
tasks.forEach((t, i) => {
  const y = gy + 0.5 + i * rh;
  txt(s, t[0], { x: 0.92, y, w: 4.0, h: rh, fontSize: 13, valign: "middle" });
  const bx = gx + t[1] * colw + 0.06, bw = (t[2] - t[1]) * colw - 0.12;
  if (t[2] > 1 && t[1] < 1) { // finished up to Review 0, rest after
    bar(bx, y + 0.07, bw, false, "Bar rest " + i);
    bar(bx, y + 0.07, colw - 0.12, true, "Bar done " + i);
  } else {
    bar(bx, y + 0.07, bw, t[3], "Bar " + i);
  }
});
const my = gy + 0.5 + tasks.length * rh + 0.05;
["Review 0", "Review 1", "Review 2", "Final"].forEach((m, i) => {
  const x = gx + (i + 1) * colw;
  s.addShape(pres.shapes.LINE, { x, y: gy + 0.42, w: 0, h: my - gy - 0.42, line: { color: BLACK, width: 0.75, dashType: "dash" }, objectName: "Milestone line " + m });
  s.addShape(pres.shapes.DIAMOND, { x: x - 0.12, y: my, w: 0.24, h: 0.24, fill: { color: BLACK }, line: { type: "none" }, objectName: "Milestone " + m });
  txt(s, m, { x: x - 0.8, y: my + 0.26, w: 1.6, h: 0.3, fontSize: 12, bold: true, align: "center" });
});
bar(0.92, gy + 0.1, 0.4, true, "Legend done");
txt(s, "done (8 Oct – 3 Nov 2026)", { x: 1.42, y: gy + 0.05, w: 2.2, h: 0.32, fontSize: 12, valign: "middle" });
bar(3.7, gy + 0.1, 0.4, false, "Legend planned");
txt(s, "planned", { x: 4.2, y: gy + 0.05, w: 0.75, h: 0.32, fontSize: 12, valign: "middle" });
note(s, "Done dates from the project's git history. Review dates follow the department calendar.");
s.addNotes("Most of the research is already done: census, gate, pre-registered evaluation, hardening and a paper draft. The remaining phases are guide review, the demo, submission and the final report.");

// ---------- 10. references ----------
pres.addSection({ title: "References" });
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "References" });
s.addText("References", { placeholder: "title" });
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
  txt(s, col.map((r, i) => ({ text: `[${ci * half + i + 1}]  ${r}`, options: { breakLine: i < col.length - 1 } })), { x: 0.92 + ci * 5.85, y: 1.85, w: 5.6, h: 4.85, fontSize: 11.5, paraSpaceAfter: 4 });
});
note(s, "Code and data: github.com/ftaakash/MCP-Lock. All entries checked against their primary source; patents checked on Google Patents.");
s.addNotes("IEEE-style references in order of first citation in this deck: papers, tools, patents, our pre-registration and the UN SDG resolution.");

(async () => {
  const out = path.join(__dirname, "MCP-Lock-Review0.pptx");
  await pres.writeFile({ fileName: out });
  await applyTheme(out, THEME);
  console.log("wrote", out);
})();
