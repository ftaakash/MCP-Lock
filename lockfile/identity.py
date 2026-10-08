"""Build-identity extraction from npm SLSA provenance and PyPI PEP 740 provenance.

The *continuity identity* is (sourceRepository, workflowPath, builder). It is stable across
honest releases of a package; ref and commit change every release and are recorded but not
compared. Signatures are not verified here (recorded identity only); verification against
Sigstore is the gate's job (Phase 3).
"""

from __future__ import annotations

import base64
import hashlib
import json

from census import http


def _digest(identity: dict) -> str:
    key = [identity.get("sourceRepository"), identity.get("workflowPath"), identity.get("builder")]
    return "sha256:" + hashlib.sha256(json.dumps(key).encode()).hexdigest()


def from_npm_statement(predicate_type: str, statement: dict) -> dict:
    pred = statement.get("predicate", {})
    if predicate_type.endswith("/v1"):
        wf = pred.get("buildDefinition", {}).get("externalParameters", {}).get("workflow", {})
        deps = pred.get("buildDefinition", {}).get("resolvedDependencies") or [{}]
        ident = {"predicateType": predicate_type,
                 "sourceRepository": wf.get("repository"),
                 "workflowPath": wf.get("path"),
                 "sourceRef": wf.get("ref"),
                 "sourceCommit": (deps[0].get("digest") or {}).get("gitCommit"),
                 "builder": pred.get("runDetails", {}).get("builder", {}).get("id")}
    else:  # SLSA v0.2
        inv = pred.get("invocation", {}).get("configSource", {})
        ident = {"predicateType": predicate_type,
                 "sourceRepository": (inv.get("uri") or "").removeprefix("git+").split("@")[0],
                 "workflowPath": inv.get("entryPoint"),
                 "sourceRef": (inv.get("uri") or "").split("@")[-1] or None,
                 "sourceCommit": (inv.get("digest") or {}).get("sha1"),
                 "builder": pred.get("builder", {}).get("id")}
    ident["digest"] = _digest(ident)
    return ident


def from_pypi_provenance(doc: dict) -> dict | None:
    bundles = doc.get("attestation_bundles") or []
    if not bundles:
        return None
    pub = bundles[0].get("publisher", {})
    kind = pub.get("kind")
    repo = pub.get("repository")
    wf = pub.get("workflow")
    if kind == "GitHub":
        repo_url = f"https://github.com/{repo}" if repo else None
        wf_path = f".github/workflows/{wf}" if wf and "/" not in wf else wf
    elif kind == "GitLab":
        repo_url = f"https://gitlab.com/{repo}" if repo else None
        wf_path = wf
    else:
        repo_url, wf_path = repo, wf
    ident = {"predicateType": "https://docs.pypi.org/attestations/publish/v1",
             "sourceRepository": repo_url, "workflowPath": wf_path, "sourceRef": None,
             "sourceCommit": None, "builder": f"pypi-trusted-publisher:{kind}",
             "environment": pub.get("environment")}
    ident["digest"] = _digest(ident)
    return ident


def npm_identity(attestation_url: str | None) -> dict | None:
    if not attestation_url:
        return None
    doc = http.get_json(attestation_url)
    for att in doc.get("attestations", []):
        if "slsa.dev/provenance" in att.get("predicateType", ""):
            payload = att["bundle"]["dsseEnvelope"]["payload"]
            return from_npm_statement(att["predicateType"], json.loads(base64.b64decode(payload)))
    return None


def pypi_identity(pkg: str, version: str, filename: str) -> dict | None:
    try:
        doc = http.get_json(f"https://pypi.org/integrity/{pkg}/{version}/{filename}/provenance",
                            headers={"Accept": "application/vnd.pypi.integrity.v1+json"})
    except http.HttpError as e:
        if e.status == 404:
            return None
        raise
    return from_pypi_provenance(doc)
