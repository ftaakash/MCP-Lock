"""Parse MCP server launch lines (command + args) into (ecosystem, package, pinned)."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

NPM_RUNNERS = {"npx", "bunx", "pnpx"}
NPM_DLX = {"pnpm", "yarn", "bun"}  # followed by "dlx" / "x"
PY_RUNNERS = {"uvx"}

# npm flags of npx/pnpm dlx that take a value
NPM_VALUE_FLAGS = {"-p", "--package", "--registry", "--cache", "--userconfig", "-c", "--call"}
UVX_VALUE_FLAGS = {"--from", "--with", "--python", "-p", "--index", "--index-url",
                   "--extra-index-url", "--default-index", "--with-requirements", "--directory",
                   "--env-file", "--refresh-package", "--reinstall-package"}

SEMVER_EXACT = re.compile(r"^v?\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?$")
NPM_NAME = re.compile(r"^(?:@[a-z0-9][\w.-]*/)?[a-z0-9][\w.-]*$", re.I)
PY_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


@dataclass(frozen=True)
class Launch:
    ecosystem: str  # "npm" | "pypi"
    package: str  # normalized name
    spec: str  # raw spec as written
    pinned: bool
    runner: str


def _base(cmd: str) -> str:
    cmd = cmd.strip().strip('"').replace("\\", "/").split("/")[-1].lower()
    return re.sub(r"\.(cmd|exe|bat|ps1)$", "", cmd)


def split_npm_spec(spec: str) -> tuple[str, str | None]:
    """'@a/b@1.2.3' -> ('@a/b', '1.2.3'); 'x' -> ('x', None)."""
    if spec.startswith("@"):
        head, _, rest = spec[1:].partition("@")
        return "@" + head, (rest or None)
    name, _, ver = spec.partition("@")
    return name, (ver or None)


def split_py_spec(spec: str) -> tuple[str, str | None]:
    m = re.match(r"^([A-Za-z0-9._-]+)(?:\[[^\]]*\])?\s*(?:(==|@)\s*([^\s;,]+)|([<>~!=]=?.*))?$", spec)
    if not m:
        return spec, None
    if m.group(2):
        return m.group(1), m.group(3)
    return m.group(1), ("RANGE" if m.group(4) else None)


def pep503(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def parse(command: str, args: list[str] | None) -> Launch | None:
    """Return the package launched, or None if this is not an npm/PyPI runner launch."""
    toks = [str(a) for a in (args or [])]
    cmd_toks = command.split() if " " in command.strip() and not toks else [command]
    if len(cmd_toks) > 1:
        command, toks = cmd_toks[0], cmd_toks[1:] + toks
    base = _base(command)

    # Windows wrappers: cmd /c npx ..., powershell -c npx ...
    if base in {"cmd", "powershell", "pwsh"} and toks:
        while toks and toks[0].lower() in {"/c", "/s", "/k", "-c", "-command", "-noprofile"}:
            toks = toks[1:]
        if not toks:
            return None
        if " " in toks[0] and len(toks) == 1:
            toks = toks[0].split()
        return parse(toks[0], toks[1:])

    if base in NPM_DLX and toks and toks[0] in {"dlx", "x"}:
        base, toks = "npx", toks[1:]
    if base in NPM_RUNNERS:
        return _parse_npm(base, toks)
    if base in PY_RUNNERS:
        return _parse_uvx(base, toks)
    if base == "uv" and toks[:2] == ["tool", "run"]:
        return _parse_uvx("uv tool run", toks[2:])
    if base == "pipx" and toks[:1] == ["run"]:
        return _parse_uvx("pipx run", [t for t in toks[1:] if t != "--spec"])
    return None


def _parse_npm(runner: str, toks: list[str]) -> Launch | None:
    pkg_flag = None
    i = 0
    while i < len(toks):
        t = toks[i]
        if t == "--":
            i += 1
            break
        if t.startswith("--package="):
            pkg_flag = t.split("=", 1)[1]
        elif t in {"-p", "--package"} and i + 1 < len(toks):
            pkg_flag = toks[i + 1]
            i += 1
        elif t in NPM_VALUE_FLAGS and i + 1 < len(toks):
            i += 1
        elif not t.startswith("-"):
            break
        i += 1
    spec = pkg_flag or (toks[i] if i < len(toks) else None)
    if not spec:
        return None
    name, ver = split_npm_spec(spec)
    if not NPM_NAME.match(name):
        return None
    pinned = bool(ver and SEMVER_EXACT.match(ver))
    return Launch("npm", name.lower(), spec, pinned, runner)


def _parse_uvx(runner: str, toks: list[str]) -> Launch | None:
    from_spec = None
    i = 0
    while i < len(toks):
        t = toks[i]
        if t.startswith("--from="):
            from_spec = t.split("=", 1)[1]
        elif t == "--from" and i + 1 < len(toks):
            from_spec = toks[i + 1]
            i += 1
        elif t in UVX_VALUE_FLAGS and i + 1 < len(toks):
            i += 1
        elif not t.startswith("-"):
            break
        i += 1
    spec = from_spec or (toks[i] if i < len(toks) else None)
    if not spec or spec.startswith(("git+", "http", ".", "/")) or "://" in spec:
        return None
    name, ver = split_py_spec(spec)
    if not PY_NAME.match(name):
        return None
    pinned = bool(ver and ver != "RANGE" and ver != "latest")
    return Launch("pypi", pep503(name), spec, pinned, runner)


def _servers(obj) -> dict:
    if not isinstance(obj, dict):
        return {}
    for key in ("mcpServers", "servers", "mcp_servers"):
        if isinstance(obj.get(key), dict):
            return obj[key]
    if isinstance(obj.get("mcp"), dict):
        return _servers(obj["mcp"])
    return {}


def strip_jsonc_comments(text: str) -> str:
    out, i, n, in_str = [], 0, len(text), False
    while i < n:
        c = text[i]
        if in_str:
            out.append(c)
            if c == "\\" and i + 1 < n:
                out.append(text[i + 1])
                i += 1
            elif c == '"':
                in_str = False
        elif c == '"':
            in_str = True
            out.append(c)
        elif text.startswith("//", i):
            j = text.find("\n", i)
            i = n if j == -1 else j
            continue
        elif text.startswith("/*", i):
            j = text.find("*/", i + 2)
            i = n if j == -1 else j + 2
            continue
        else:
            out.append(c)
        i += 1
    return "".join(out)


def parse_config_text(text: str) -> list[Launch]:
    """Parse a full JSON(C) MCP config file. Falls back to regex on invalid JSON."""
    try:
        obj = json.loads(text)
    except json.JSONDecodeError:
        stripped = re.sub(r",(\s*[}\]])", r"\1", strip_jsonc_comments(text))
        try:
            obj = json.loads(stripped)
        except json.JSONDecodeError:
            return parse_fragment(text)
    out = []
    for entry in _servers(obj).values():
        if isinstance(entry, dict) and isinstance(entry.get("command"), str):
            args = entry.get("args") if isinstance(entry.get("args"), list) else []
            launch = parse(entry["command"], args)
            if launch:
                out.append(launch)
    return out


_CMD_RE = re.compile(r'"command"\s*:\s*"([^"]+)"(?P<rest>.{0,800})', re.S)
_ARGS_RE = re.compile(r'"args"\s*:\s*\[(.*?)\]', re.S)
_STR_RE = re.compile(r'"((?:[^"\\]|\\.)*)"')


def parse_fragment(text: str) -> list[Launch]:
    """Best-effort regex parse of a partial config (search snippet)."""
    out = []
    for m in _CMD_RE.finditer(text):
        rest = m.group("rest")
        nxt = rest.find('"command"')
        if nxt != -1:
            rest = rest[:nxt]
        am = _ARGS_RE.search(rest)
        args = _STR_RE.findall(am.group(1)) if am else []
        launch = parse(m.group(1), args)
        if launch:
            out.append(launch)
    return out
