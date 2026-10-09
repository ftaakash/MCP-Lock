"""Parse a shell command into the package installs and MCP launches it would perform."""

from __future__ import annotations

import re
import shlex
from dataclasses import dataclass, field

from census import launch

SEPARATORS = {"&&", "||", ";", "|", "&"}
ENV_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)=(.*)$")


@dataclass
class Invocation:
    ecosystem: str  # "pypi" | "npm" | "make"
    kind: str  # "install" | "launch" | "make"
    specs: list[str] = field(default_factory=list)  # requirement / package specs as written
    index_urls: list[str] = field(default_factory=list)  # -i / --index-url / --registry
    extra_index_urls: list[str] = field(default_factory=list)
    trusted_hosts: list[str] = field(default_factory=list)
    find_links: list[str] = field(default_factory=list)
    req_files: list[str] = field(default_factory=list)
    constraint_files: list[str] = field(default_factory=list)
    local_targets: list[str] = field(default_factory=list)  # ".", "-e .", paths
    from_manifest: bool = False  # bare `npm install` / `npm ci`
    env: dict[str, str] = field(default_factory=dict)
    raw: str = ""
    make_target: str | None = None
    launch: launch.Launch | None = None


def _segments(cmd: str) -> list[list[str]]:
    try:
        lex = shlex.shlex(cmd, posix=True, punctuation_chars=";&|")
        lex.whitespace_split = True
        toks = list(lex)
    except ValueError:
        toks = cmd.split()
    segs, cur = [], []
    for t in toks:
        if t in SEPARATORS:
            if cur:
                segs.append(cur)
            cur = []
        else:
            cur.append(t)
    if cur:
        segs.append(cur)
    return segs


def _base(t: str) -> str:
    return re.sub(r"\.(exe|cmd|bat)$", "", t.replace("\\", "/").split("/")[-1].lower())


PIP_VALUE = {"-i": "index_urls", "--index-url": "index_urls", "--extra-index-url": "extra_index_urls",
             "--trusted-host": "trusted_hosts", "-f": "find_links", "--find-links": "find_links",
             "-r": "req_files", "--requirement": "req_files", "-c": "constraint_files",
             "--constraint": "constraint_files"}
PIP_SKIP_VALUE = {"-t", "--target", "--prefix", "--root", "--python", "-p", "--platform",
                  "--python-version", "--implementation", "--abi", "--src", "--cache-dir",
                  "--log", "--progress-bar", "--report", "--config-settings", "-C", "--global-option",
                  "--no-binary", "--only-binary", "--upgrade-strategy", "--exclude-newer"}


def _pip(args: list[str], env: dict, raw: str) -> Invocation:
    inv = Invocation("pypi", "install", env=dict(env), raw=raw)
    i = 0
    while i < len(args):
        a = args[i]
        key, val = (a.split("=", 1) + [None])[:2] if a.startswith("--") and "=" in a else (a, None)
        if key in PIP_VALUE:
            if val is None and i + 1 < len(args):
                val = args[i + 1]
                i += 1
            if val is not None:
                getattr(inv, PIP_VALUE[key]).append(val)
        elif key in ("-e", "--editable"):
            if val is None and i + 1 < len(args):
                val = args[i + 1]
                i += 1
            inv.local_targets.append(val or ".")
        elif key in PIP_SKIP_VALUE:
            if val is None:
                i += 1
        elif a.startswith("-"):
            pass
        elif a.startswith((".", "/")) or a.endswith((".whl", ".tar.gz", ".zip")) or "://" in a:
            inv.local_targets.append(a)
        else:
            inv.specs.append(a)
        i += 1
    return inv


NPM_INSTALL = {"install", "i", "add", "ci", "isntall", "in"}


def _npm(args: list[str], env: dict, raw: str) -> Invocation:
    inv = Invocation("npm", "install", env=dict(env), raw=raw)
    i = 0
    while i < len(args):
        a = args[i]
        if a.startswith("--registry"):
            val = a.split("=", 1)[1] if "=" in a else (args[i + 1] if i + 1 < len(args) else None)
            if "=" not in a:
                i += 1
            if val:
                inv.index_urls.append(val)
        elif a.startswith("-"):
            pass
        elif a.startswith((".", "/", "file:", "git+", "http://", "https://", "git://")):
            inv.local_targets.append(a)
        else:
            inv.specs.append(a)
        i += 1
    inv.from_manifest = not inv.specs and not inv.local_targets
    return inv


def parse(cmd: str) -> list[Invocation]:
    out: list[Invocation] = []
    env: dict[str, str] = {}
    for seg in _segments(cmd):
        local_env = dict(env)
        while seg and ENV_RE.match(seg[0]):
            k, v = ENV_RE.match(seg[0]).groups()
            local_env[k] = v
            seg = seg[1:]
        if not seg:
            env = local_env  # bare assignment persists in the shell
            continue
        head = _base(seg[0])
        if head == "export":
            for t in seg[1:]:
                m = ENV_RE.match(t)
                if m:
                    env[m.group(1)] = m.group(2)
            continue
        if head == "env":
            rest = seg[1:]
            while rest and ENV_RE.match(rest[0]):
                k, v = ENV_RE.match(rest[0]).groups()
                local_env[k] = v
                rest = rest[1:]
            seg = rest
            if not seg:
                continue
            head = _base(seg[0])
        if head == "sudo" and len(seg) > 1:
            seg = seg[1:]
            head = _base(seg[0])
        raw = " ".join(seg)
        args = seg[1:]
        # pip / pip3 / python -m pip / uv pip
        if re.fullmatch(r"pip\d*(\.\d+)?", head) and args[:1] == ["install"]:
            out.append(_pip(args[1:], local_env, raw))
        elif re.fullmatch(r"python\d*(\.\d+)?|py", head) and args[:3] == ["-m", "pip", "install"]:
            out.append(_pip(args[3:], local_env, raw))
        elif re.fullmatch(r"python\d*(\.\d+)?|py", head) and args[:2] == ["-m", "pip"] and \
                len(args) > 2 and args[2] == "install":
            out.append(_pip(args[3:], local_env, raw))
        elif head == "uv" and args[:2] == ["pip", "install"]:
            out.append(_pip(args[2:], local_env, raw))
        elif head == "uv" and args[:1] == ["add"]:
            out.append(_pip(args[1:], local_env, raw))
        elif head in ("npm", "pnpm", "yarn", "bun") and args[:1] and args[0] in NPM_INSTALL:
            out.append(_npm(args[1:], local_env, raw))
        elif head == "yarn" and not args:
            out.append(_npm([], local_env, raw))
        elif head == "make":
            tgt = next((a for a in args if not a.startswith("-") and "=" not in a), None)
            mk_env = dict(local_env)
            for a in args:
                m = ENV_RE.match(a)
                if m:
                    mk_env[m.group(1)] = m.group(2)
            out.append(Invocation("make", "make", env=mk_env, raw=raw, make_target=tgt))
        else:
            lt = launch.parse(seg[0], args)
            if lt is not None:
                out.append(Invocation(lt.ecosystem, "launch", specs=[lt.spec], env=local_env,
                                      raw=raw, launch=lt))
    return out
