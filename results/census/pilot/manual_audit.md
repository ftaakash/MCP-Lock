# Manual audit of pilot extractions (2026-10-08)

Performed by Claude (assistant) on the committed `extractions.jsonl` / `change_events.jsonl`;
to be spot-checked by Aakash. This audit is not a substitute for the Docker `tools/list` validation
(plan §6), which is still pending (Virtual Machine Platform disabled on the host).

## A. Tool-set plausibility: 25 random packages with ≥1 extracted tool (random.seed(20261008))
All 25 tool sets are consistent with the package's purpose (e.g. `abuseipdb-mcp`: check_ip, blacklist,
check_block, recent_reports; `owncloud-mcp`: create_share, list_shares, ...). No set was obviously
taken from bundled third-party code. Likely **partial** extractions: `fhirhydrant@0.17.3`
(1 valid of 7 candidates) and `@infoinlet/mcp-openapi@0.1.1` (1 tool; most tools are generated
from an OpenAPI spec at runtime). These count as G1 successes under the plan's definition
(≥ 1 valid tool), so G1 measures "some tool definitions extractable", not "all".

## B. Change-event validity: 25 random events of 243 (random.seed(7))
25/25 are genuine edits, not extraction artefacts:
- tools added or removed (e.g. `@n24q02m/better-email-mcp` 1.37.0→1.38.0 removed `send`;
  `aus-accounting-mcp` 0.1.9→0.2.0 added 4 tools);
- rewritten descriptions that change agent-facing instructions (e.g. `strava-mcp-unofficial`
  0.4.10→0.4.11 adds "Requires explicit user action ...");
- real schema changes (e.g. `ai-usage-mcp` 0.8.0→0.9.0 `object` → `strictObject`).

Notable for RQ1 (not malicious, no stop): `edgeone-pages-mcp-fullstack` 0.0.35→0.0.36 adds to the
`deploy_folder` description an instruction that the model's response "MUST start with" a fixed
success banner, i.e. output steering introduced by a description update in a patch release.

## C. Suspicious-text queue
The first extraction run flagged 35 versions; all came from one over-broad regex
(`base64 encode.*(key|token)` spanning the joined text of all tools). With the span limited to 40
characters, **0** versions match any injection/exfiltration heuristic. No stop-and-report condition.
