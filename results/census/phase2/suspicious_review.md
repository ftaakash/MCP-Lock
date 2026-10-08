# Suspicious-text review, Phase 2 Part T (2026-10-09)

The heuristic flagged 157 versions in 14 packages, i.e. 26 distinct (package, tool, match) hits.
Every hit was read in context. **No malicious tool-poisoning or exfiltration instruction was found**,
so the stop-and-report condition is not met.

| Category | Packages | Verdict |
|---|---|---|
| Security scanners describing what they detect | shrike-mcp, @inkog-io/mcp, mcp-heimdall-scan, @skillsmith/mcp-server, agentic-sdlc-mcp, @orygn/opa-mcp | benign |
| Defensive anti-injection guidance | @aicommander/mcp, proton-mail-mcp | benign |
| Test fixture showing an injection example | @mailsai/mcp-server | benign |
| Key / SSH / crypto parameter docs | mcp-cryptography, unlimited-mcp, codemagicmcp | benign |
| Instructions about what the agent tells the user | @porkbunllc/mcp-server ("do not tell the user it is in their account": the domain is reserved, not delivered), @replen/mcp ("Do NOT tell the user to set tags on the web") | not malicious; **user-communication steering via tool descriptions**, noted for RQ1 alongside edgeone-pages-mcp-fullstack |
