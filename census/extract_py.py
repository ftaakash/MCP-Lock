"""Static extraction of MCP tool definitions from Python source (ast only; nothing is imported)."""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

from census.tooldefs import OPAQUE, ToolDef

TOOL_CTORS = {"Tool"}
DECORATOR_ATTRS = {"tool"}
SKIP_PARAMS = {"self", "cls", "ctx", "context"}


class Index:
    """Package-wide symbol index: constants, enum members, classes, functions."""

    def __init__(self):
        self.consts: dict[str, list[ast.AST]] = {}
        self.classes: dict[str, list[ast.ClassDef]] = {}
        self.funcs: dict[str, list[ast.AST]] = {}

    def add_module(self, tree: ast.Module) -> None:
        for node in tree.body:
            if isinstance(node, ast.Assign):
                for tgt in node.targets:
                    if isinstance(tgt, ast.Name):
                        self.consts.setdefault(tgt.id, []).append(node.value)
            elif (isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name)
                  and node.value):
                self.consts.setdefault(node.target.id, []).append(node.value)
            elif isinstance(node, ast.ClassDef):
                self.classes.setdefault(node.name, []).append(node)
                for b in node.body:
                    if isinstance(b, ast.Assign) and len(b.targets) == 1 and isinstance(
                            b.targets[0], ast.Name):
                        self.consts.setdefault(f"{node.name}.{b.targets[0].id}", []).append(b.value)
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self.funcs.setdefault(node.name, []).append(node)

    @staticmethod
    def _unique(lst):
        if not lst:
            return None
        first = ast.dump(lst[0])
        return lst[0] if all(ast.dump(x) == first for x in lst[1:]) else None

    def const(self, name):
        return self._unique(self.consts.get(name))

    def cls(self, name):
        lst = self.classes.get(name)
        return lst[0] if lst and len(lst) == 1 else None


def _callee_name(func: ast.AST) -> str:
    if isinstance(func, ast.Attribute):
        return func.attr
    if isinstance(func, ast.Name):
        return func.id
    return ""


def _attr_path(node: ast.AST) -> str | None:
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
        return ".".join(reversed(parts))
    return None


def evaluate(node: ast.AST | None, idx: Index, depth: int = 0):
    if node is None:
        return None
    if depth > 8:
        return OPAQUE
    ev = lambda n: evaluate(n, idx, depth + 1)  # noqa: E731
    if isinstance(node, ast.Constant):
        return node.value if isinstance(node.value, (str, int, float, bool)) or node.value is None \
            else OPAQUE
    if isinstance(node, ast.JoinedStr):
        parts = []
        for v in node.values:
            if isinstance(v, ast.Constant):
                parts.append(str(v.value))
            else:
                r = ev(v.value) if isinstance(v, ast.FormattedValue) else OPAQUE
                parts.append(r if isinstance(r, str) and r != OPAQUE else "{" + OPAQUE + "}")
        return "".join(parts)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        a, b = ev(node.left), ev(node.right)
        if isinstance(a, str) and isinstance(b, str) and OPAQUE not in (a, b):
            return a + b
        return OPAQUE
    if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        return [ev(e) for e in node.elts]
    if isinstance(node, ast.Dict):
        out = {}
        for k, v in zip(node.keys, node.values, strict=True):
            kk = ev(k) if k is not None else None
            if isinstance(kk, str) and kk != OPAQUE:
                out[kk] = ev(v)
        return out
    if isinstance(node, ast.Name):
        c = idx.const(node.id)
        return ev(c) if c is not None else OPAQUE
    if isinstance(node, ast.Attribute):
        path = _attr_path(node)
        if path:
            tail2 = ".".join(path.split(".")[-2:])
            c = idx.const(tail2)
            if c is not None:
                return ev(c)
            if path.endswith(".value") and idx.const(".".join(path.split(".")[-3:-1])):
                return ev(idx.const(".".join(path.split(".")[-3:-1])))
        return OPAQUE
    if isinstance(node, ast.Call):
        name = _callee_name(node.func)
        if name == "model_json_schema" and isinstance(node.func, ast.Attribute):
            target = node.func.value
            cname = target.id if isinstance(target, ast.Name) else None
            cd = idx.cls(cname) if cname else None
            return {"$model": model_fields(cd, idx)} if cd else OPAQUE
        if name in ("dict", "json") and node.keywords and not node.args:
            return {k.arg: ev(k.value) for k in node.keywords if k.arg}
        return {"$call": name, "args": [ev(a) for a in node.args],
                "kwargs": {k.arg: ev(k.value) for k in node.keywords if k.arg}}
    return OPAQUE


def model_fields(cd: ast.ClassDef, idx: Index, depth: int = 0) -> list:
    fields = []
    for b in cd.body:
        if isinstance(b, ast.AnnAssign) and isinstance(b.target, ast.Name):
            fields.append([b.target.id, ast.unparse(b.annotation),
                           evaluate(b.value, idx) if b.value is not None else None])
    if depth < 3:
        for base in cd.bases:
            if isinstance(base, ast.Name) and base.id not in ("BaseModel", "object"):
                bc = idx.cls(base.id)
                if bc:
                    fields = model_fields(bc, idx, depth + 1) + fields
    return fields


def signature_schema(fn: ast.AST) -> list:
    out = []
    args = fn.args
    pos = args.posonlyargs + args.args
    defaults = [None] * (len(pos) - len(args.defaults)) + list(args.defaults)
    allargs = list(zip(pos, defaults, strict=True)) + list(
        zip(args.kwonlyargs, args.kw_defaults, strict=True))
    for a, d in allargs:
        ann = ast.unparse(a.annotation) if a.annotation is not None else None
        if a.arg in SKIP_PARAMS or (ann and "Context" in ann):
            continue
        out.append([a.arg, ann, ast.unparse(d) if d is not None else None])
    return out


def _kw(call: ast.Call, name: str):
    for k in call.keywords:
        if k.arg == name:
            return k.value
    return None


def extract_module(tree: ast.Module, idx: Index, rel: str) -> list[ToolDef]:
    tools: list[ToolDef] = []
    for node in ast.walk(tree):
        # Tool(name=..., description=..., inputSchema=...)
        if isinstance(node, ast.Call) and _callee_name(node.func) in TOOL_CTORS:
            name = evaluate(_kw(node, "name"), idx)
            if isinstance(name, str) and name != OPAQUE:
                desc = evaluate(_kw(node, "description"), idx)
                schema = evaluate(_kw(node, "inputSchema") or _kw(node, "input_schema"), idx)
                tools.append(ToolDef(name, desc if isinstance(desc, str) else None, schema,
                                     "py_Tool", rel))
        # @x.tool / @x.tool(...) decorated functions (FastMCP style)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for dec in node.decorator_list:
                call = dec if isinstance(dec, ast.Call) else None
                target = dec.func if call else dec
                if not (isinstance(target, ast.Attribute) and target.attr in DECORATOR_ATTRS):
                    continue
                name, desc = node.name, ast.get_docstring(node)
                if call:
                    n = evaluate(_kw(call, "name"), idx)
                    if call.args and not _kw(call, "name"):
                        n = evaluate(call.args[0], idx)
                    if isinstance(n, str) and n != OPAQUE:
                        name = n
                    d = evaluate(_kw(call, "description"), idx)
                    if isinstance(d, str) and d != OPAQUE:
                        desc = d
                tools.append(ToolDef(name, inspect.cleandoc(desc) if desc else None,
                                     signature_schema(node), "py_decorator", rel))
        # x.add_tool(fn, name=..., description=...)
        if isinstance(node, ast.Call) and _callee_name(node.func) == "add_tool" and node.args:
            fn_ref = node.args[0]
            fname = fn_ref.id if isinstance(fn_ref, ast.Name) else None
            n = evaluate(_kw(node, "name"), idx)
            name = n if isinstance(n, str) and n != OPAQUE else fname
            fdefs = idx.funcs.get(fname or "", [])
            fdef = fdefs[0] if len(fdefs) == 1 else None
            d = evaluate(_kw(node, "description"), idx)
            desc = d if isinstance(d, str) and d != OPAQUE else (
                ast.get_docstring(fdef) if fdef else None)
            if name:
                tools.append(ToolDef(name, inspect.cleandoc(desc) if desc else None,
                                     signature_schema(fdef) if fdef else OPAQUE, "py_add_tool",
                                     rel))
    return tools


def extract_dir(root: Path) -> tuple[list[ToolDef], dict]:
    trees, errors = [], 0
    for p in sorted(root.rglob("*.py")):
        try:
            src = p.read_text(encoding="utf-8", errors="replace")
            trees.append((p.relative_to(root).as_posix(), ast.parse(src)))
        except (SyntaxError, ValueError, RecursionError):
            errors += 1
    idx = Index()
    for _, t in trees:
        idx.add_module(t)
    tools = []
    for rel, t in trees:
        try:
            tools.extend(extract_module(t, idx, rel))
        except RecursionError:
            errors += 1
    return tools, {"py_files": len(trees), "parse_errors": errors}
