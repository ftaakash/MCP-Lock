import copy

import pytest

from census import http
from eval import replay

T = "2026-09-01T12:00:00Z"
PROV = {"sourceRepository": "https://github.com/a/b", "workflowPath": ".github/workflows/rel.yml",
        "builder": "gha", "digest": "sha256:aaa"}


def _v(version, **kw):
    v = {"version": version, "published": "2026-08-01T00:00:00Z", "prerelease": False,
         "archive_url": f"https://registry.npmjs.org/zqx-toy-server/-/zqx-toy-server-{version}.tgz",
         "integrity": f"sha512-{version}", "shasum": None, "has_attestation": True,
         "attestation_url": f"https://registry.npmjs.org/-/npm/v1/attestations/zqx-toy-server@{version}",
         "publisher": "GitHub Actions", "maintainers": ["alice"], "install_scripts": {}}
    v.update(kw)
    return v


def _bundle(**kw):
    b = {"case_id": "toy", "corpus": "toy", "ecosystem": "npm", "package": "zqx-toy-server", "t": T,
         "command": "npx -y zqx-toy-server",
         "versions": [_v("1.0.0"), _v("1.0.1", published="2026-08-30T00:00:00Z")],
         "lock": {"ecosystem": "npm", "name": "zqx-toy-server", "version": "1.0.0",
                  "integrity": "sha512-1.0.0", "archive": "x", "installScripts": [],
                  "provenance": PROV,
                  "publisher": {"publisher": "GitHub Actions", "maintainers": ["alice"]},
                  "tools": {"hash": "sha256:old", "method": "static", "names": ["read"]}},
         "registry_info": {"zqx-toy-server": {"exists": True, "first_release": "2025-01-01T00:00:00Z"}},
         "identities": {"1.0.1": PROV},
         "tools": {"1.0.1": {"hash": "sha256:old", "names": ["read"]}},
         "evaluable": {"S2": True, "S3": True, "S4": True, "S5": True}}
    b.update(kw)
    return b


def test_honest_update_is_allowed_by_everyone():
    res = replay.run(_bundle())
    assert {s: r["decision"] for s, r in res.items()} == {s: "allow" for s in res}
    assert not any(r["detected"] for r in res.values())


def test_rug_pull_detected_by_gate_not_baseline():
    b = _bundle()
    b["versions"][1].update(publisher="mallory", install_scripts={"postinstall": "node x"},
                            attestation_url=None, has_attestation=False)
    b["identities"] = {"1.0.1": None}
    b["tools"] = {"1.0.1": {"hash": "sha256:new", "names": ["read", "exfil"]}}
    res = replay.run(b)
    assert not res["S1-C"]["detected"] and not res["S1-L"]["detected"]
    assert res["G"]["decision"] == "block" and res["G"]["detected"]
    checks = {f["check"] for f in res["G"]["findings"]}
    assert {"provenance_lost", "ci_to_human", "new_install_script", "tool_drift"} <= checks
    # ablation without S2 and S4 still warns via S3/S5
    assert res["G-S2"]["detected"]


def test_not_evaluable_signals_are_disabled():
    b = _bundle(evaluable={"S2": False, "S3": False, "S4": True, "S5": False})
    b["versions"][1].update(publisher=None, attestation_url=None)
    b["identities"] = {}
    b["tools"] = {}
    res = replay.run(b)  # would raise OfflineViolation if S2/S5 looked anything up
    assert res["G"]["enabled"] == ["S1", "S4"]
    assert res["G"]["decision"] == "allow"


def test_unlocked_warning_is_not_a_detection():
    res = replay.run(_bundle(lock=None))
    assert res["G"]["decision"] == "warn"
    assert not res["G"]["detected"]


def test_s1_uses_the_as_of_time():
    b = _bundle(command="npm install zqx-toy-server",
                registry_info={"zqx-toy-server": {"exists": True, "first_release": "2026-08-25T00:00:00Z"}})
    res = replay.run(b)
    assert res["S1-C"]["detected"] and res["S1-L"]["detected"]  # 7 days old at t
    assert any(f["check"] == "new_package" for f in res["S1-C"]["findings"])


def test_no_network_during_replay():
    b = _bundle()
    del b["identities"]["1.0.1"]
    with pytest.raises(replay.OfflineViolation):
        replay.run(b)
    assert http.get_json is not None and "no_net" not in http.get_json.__name__  # restored


def test_integrity_mismatch_counts():
    b = _bundle(versions=[_v("1.0.0", integrity="sha512-tampered")])
    res = replay.run(copy.deepcopy(b))
    assert res["G"]["decision"] == "block" and res["G"]["detected"]
    assert not res["S1-C"]["detected"]
