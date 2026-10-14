"""Safer-alternative suggestions (gate/suggest.py): offline, registry calls monkeypatched."""

from pathlib import Path

from gate import core, s1, signals, suggest
from gate.findings import Finding


def test_edit_distance_and_similar(monkeypatch):
    assert suggest.edit_distance("reqeusts", "requests") == 1          # transposition
    assert suggest.edit_distance("exprss", "express") == 1
    assert suggest.edit_distance("abc", "xyz", cap=2) == 3                # stops above the cap
    monkeypatch.setattr(s1, "popular", lambda eco: ["express", "expresso", "react", "exprees"])
    got = suggest.similar_popular("npm", "exprss", s1.S1Config.charitable())
    assert got[0] == "express" and "react" not in got


def test_rewrite_keeps_command_shape():
    assert suggest.rewrite("npx -y @a/srv@2.0.0 --port 3", "npm", "@a/srv", "@a/srv@1.0.0") == \
        "npx -y @a/srv@1.0.0 --port 3"
    assert suggest.rewrite('pip install "reqeusts==1.0" flask', "pypi", "reqeusts", "requests") == \
        'pip install "requests" flask'
    assert suggest.rewrite("uvx Some_Pkg", "pypi", "some-pkg", "some-pkg==2.0") == "uvx some-pkg==2.0"
    assert suggest.rewrite("npm install express", "npm", "react", "react@1") is None
    assert suggest.rewrite("npx --package=@a/srv adv", "npm", "@a/srv", "@a/srv@1.0.0") == (
        "npx --package=@a/srv@1.0.0 adv")


def test_passes_rules():
    lock = {("npm", "srv"): {"version": "1.0.0"}}
    assert suggest.passes([Finding("gate", "unlocked", "warn", "x", "")], lock)
    assert suggest.passes([Finding("S1", "new_package", "block", "srv", "")], lock)   # locked: first-use rule
    assert not suggest.passes([Finding("S1", "new_package", "block", "other", "")], lock)
    assert not suggest.passes([Finding("S4", "new_install_script", "block", "srv", "")], lock)
    assert suggest.passes([Finding("gate", "version_drift", "info", "srv", "")], lock)


ENTRY = {"ecosystem": "npm", "name": "srv", "version": "1.0.0", "integrity": "sha512-old", "archive": "x",
         "installScripts": [], "provenance": None,
         "publisher": {"publisher": "alice", "maintainers": ["alice"]},
         "tools": {"hash": "sha256:old", "method": "static", "names": ["read"]}}
RECORDS = {"1.0.0": {"version": "1.0.0", "integrity": "sha512-old", "prerelease": False, "publisher": "alice",
                     "install_scripts": {}},
           "1.1.0": {"version": "1.1.0", "integrity": "sha512-mid", "prerelease": False, "publisher": "alice",
                     "install_scripts": {}},
           "1.2.0": {"version": "1.2.0", "integrity": "sha512-new", "prerelease": False, "publisher": "alice",
                     "install_scripts": {"postinstall": "node x.js"}}}


def _lock_file(tmp_path: Path) -> Path:
    import json
    p = tmp_path / "mcp-lock.json"
    p.write_text(json.dumps({"lockfileVersion": "0.2", "servers": {"srv": ENTRY}}), encoding="utf-8")
    return p


def _offline(monkeypatch):
    from census import versions as V
    monkeypatch.setattr(signals, "resolve",
                        lambda eco, pkg, pinned: RECORDS[pinned] if pinned else RECORDS["1.2.0"])
    monkeypatch.setattr(signals, "_identity", lambda eco, pkg, v: None)
    monkeypatch.setattr(signals, "static_tools", lambda eco, pkg, v: ("sha256:old", ["read"]))
    monkeypatch.setattr(V, "npm_versions", lambda pkg: list(RECORDS.values()))


def test_rug_pull_suggests_last_good_then_locked(monkeypatch, tmp_path):
    _offline(monkeypatch)
    lock = _lock_file(tmp_path)
    enabled = frozenset({"S2", "S3", "S4", "S5"})
    plain = core.evaluate("npx -y srv", tmp_path, lock, enabled=enabled)
    d = core.evaluate("npx -y srv", tmp_path, lock, enabled=enabled, suggest=True)
    assert d.decision == plain.decision == "block" and d.reason == plain.reason   # decision unchanged
    assert [(s.kind, s.command, s.verified) for s in d.suggestions] == [
        ("last_good", "npx -y srv@1.1.0", True), ("locked_version", "npx -y srv@1.0.0", True)]
    assert "suggestions" not in plain.to_dict()                                   # frozen output shape


def test_unverifiable_suggestion_is_dropped(monkeypatch, tmp_path):
    _offline(monkeypatch)
    lock = _lock_file(tmp_path)
    # every pinned version now adds an install script, so neither alternative passes the gate
    bad = {v: dict(r, install_scripts={"postinstall": "x"}) for v, r in RECORDS.items()}
    monkeypatch.setattr(signals, "resolve", lambda eco, pkg, pinned: bad[pinned] if pinned else bad["1.2.0"])
    d = core.evaluate("npx -y srv@1.2.0", tmp_path, lock, enabled=frozenset({"S4"}), suggest=True)
    assert d.decision == "block"
    assert all(s.command is None or s.verified for s in d.suggestions)
    assert not any(s.kind == "last_good" for s in d.suggestions)


def test_typosquat_and_unlocked(monkeypatch, tmp_path):
    monkeypatch.setattr(s1, "popular", lambda eco: ["express", "react"])
    monkeypatch.setattr(s1, "registry_info", lambda eco, name, now=None, age_days=30:
                        {"exists": True, "first_release": None})
    monkeypatch.setattr(s1, "osv_fixable", lambda eco, name, version: [])
    cfg = s1.S1Config.charitable(exempt_popular=0)
    d = core.evaluate("npm install exrpess", tmp_path, None, cfg, frozenset({"S1"}), suggest=True)
    assert d.decision == "block"
    assert d.suggestions[0].kind == "typosquat" and d.suggestions[0].command == "npm install express"


def test_one_replacement_per_spec_and_combined(monkeypatch, tmp_path):
    monkeypatch.setattr(s1, "popular", lambda eco: ["requests", "flask"])
    monkeypatch.setattr(s1, "registry_info", lambda eco, name, now=None, age_days=30:
                        {"exists": name in ("requests", "flask"), "first_release": None})
    fixes = {("flask", "0.1"): [{"id": "GHSA-x", "lowest_fix": "2.3.2"}]}
    monkeypatch.setattr(s1, "osv_fixable", lambda eco, name, version: fixes.get((name, version), []))
    cfg = s1.S1Config.charitable(exempt_popular=0)
    d = core.evaluate("pip install reqeusts flask==0.1", tmp_path, None, cfg, frozenset({"S1"}), suggest=True)
    cmds = [x.command for x in d.suggestions if x.command]
    assert cmds == ["pip install requests flask==2.3.2"]              # both fixes, one command, no duplicate
    assert d.suggestions[0].kind == "combined"


def test_fixed_version_steps_past_newer_advisories(monkeypatch):
    adv = {"0.21.0": [{"id": "A", "lowest_fix": "0.21.2"}, {"id": "B", "lowest_fix": "0.33.0"}],
           "0.33.0": [{"id": "C", "lowest_fix": "0.34.0"}]}
    monkeypatch.setattr(s1, "osv_fixable", lambda eco, name, v: adv.get(v, []))
    assert suggest.fixed_version("npm", "axios", "0.21.0") == "0.34.0"
    assert suggest.fixed_version("npm", "axios", "0.34.0") is None           # nothing to fix
    loop = {"1": [{"id": "X", "lowest_fix": "2"}], "2": [{"id": "Y", "lowest_fix": "3"}],
            "3": [{"id": "Z", "lowest_fix": "4"}], "4": [{"id": "W", "lowest_fix": "5"}]}
    monkeypatch.setattr(s1, "osv_fixable", lambda eco, name, v: loop.get(v, []))
    assert suggest.fixed_version("npm", "p", "1") is None                    # gives up after 4 hops


def test_locked_package_flagged_by_s1_only_rolls_back(monkeypatch, tmp_path):
    from datetime import UTC, datetime, timedelta
    _offline(monkeypatch)
    now = datetime(2026, 10, 1, tzinfo=UTC)
    monkeypatch.setattr(s1, "registry_info", lambda eco, name, now=None, age_days=30:
                        {"exists": True, "first_release": now - timedelta(days=3)})
    monkeypatch.setattr(s1, "osv_fixable", lambda eco, name, version: [])
    monkeypatch.setattr(s1, "popular", lambda eco: ["react"])
    cfg = s1.S1Config.charitable(now=now)
    d = core.evaluate("npx -y srv", tmp_path, _lock_file(tmp_path), cfg, frozenset({"S1"}), suggest=True)
    assert [f.check for f in d.findings if f.severity == "block"] == ["new_package"]
    assert d.suggestions[0].kind in ("last_good", "locked_version")
    assert d.suggestions[0].command in ("npx -y srv@1.1.0", "npx -y srv@1.0.0")


def test_project_file_packages_get_verified_edit_advice(monkeypatch, tmp_path):
    (tmp_path / "requirements.txt").write_text("reqeusts\nflask==0.1\n", encoding="utf-8")
    monkeypatch.setattr(s1, "popular", lambda eco: ["requests", "flask"])
    monkeypatch.setattr(s1, "registry_info", lambda eco, name, now=None, age_days=30:
                        {"exists": True, "first_release": None})
    fixes = {("flask", "0.1"): [{"id": "GHSA-x", "lowest_fix": "2.3.2"}]}
    monkeypatch.setattr(s1, "osv_fixable", lambda eco, name, version: fixes.get((name, version), []))
    cfg = s1.S1Config.charitable(exempt_popular=0)
    d = core.evaluate("pip install -r requirements.txt", tmp_path, None, cfg, frozenset({"S1"}), suggest=True)
    edits = {x.kind: x.because for x in d.suggestions if x.verified and x.command is None}
    assert "change 'reqeusts' to 'requests'" in edits["typosquat"]
    assert "change 'flask' to 'flask==2.3.2'" in edits["fixed_version"]
