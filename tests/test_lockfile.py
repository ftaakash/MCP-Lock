import json
from pathlib import Path

import jsonschema

from lockfile import identity

FIX = Path(__file__).parent / "fixtures"
SCHEMA = json.loads(Path("lockfile/mcp-lock.schema.json").read_text(encoding="utf-8"))


def test_npm_slsa_v1_identity():
    d = json.loads((FIX / "npm_slsa_statement.json").read_text())
    ident = identity.from_npm_statement(d["predicateType"], d["statement"])
    assert ident["sourceRepository"] == "https://github.com/modelcontextprotocol/servers"
    assert ident["workflowPath"] == ".github/workflows/release.yml"
    assert ident["builder"] == "https://github.com/actions/runner/github-hosted"
    assert len(ident["sourceCommit"]) == 40 and ident["digest"].startswith("sha256:")


def test_pypi_identity_matches_npm_continuity_fields():
    ident = identity.from_pypi_provenance(json.loads((FIX / "pypi_provenance.json").read_text()))
    assert ident["sourceRepository"] == "https://github.com/modelcontextprotocol/servers"
    assert ident["workflowPath"] == ".github/workflows/release.yml"
    assert identity.from_pypi_provenance({"attestation_bundles": []}) is None


def test_digest_ignores_ref_and_commit():
    a = {"sourceRepository": "r", "workflowPath": "w", "builder": "b", "sourceCommit": "1" * 40}
    b = dict(a, sourceCommit="2" * 40, sourceRef="refs/tags/v2")
    assert identity._digest(a) == identity._digest(b)
    assert identity._digest(a) != identity._digest(dict(a, workflowPath="other.yml"))


def test_schema_accepts_minimal_and_rejects_ranges():
    entry = {"ecosystem": "npm", "name": "x", "version": "1.0.0", "integrity": "sha512-abc",
             "tools": {"hash": None, "method": "static"}, "provenance": None}
    jsonschema.validate({"lockfileVersion": "0.1", "servers": {"x": entry}}, SCHEMA)
    bad = dict(entry, integrity="md5-abc")
    try:
        jsonschema.validate({"lockfileVersion": "0.1", "servers": {"x": bad}}, SCHEMA)
        raise AssertionError("md5 integrity must be rejected")
    except jsonschema.ValidationError:
        pass
