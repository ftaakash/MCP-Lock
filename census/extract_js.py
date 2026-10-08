"""Static extraction of MCP tool definitions from JS/TS (tree-sitter; nothing is executed).

Patterns:
  * X.tool(name, [description], [shape], ..., handler)          MCP TS SDK (legacy API)
  * X.registerTool(name, {title, description, inputSchema}, h)   MCP TS SDK
  * X.addTool({name, description, parameters | inputSchema})     FastMCP (TS)
  * any object literal {name: <string>, inputSchema: ...}        ListTools handlers / tool consts
Identifiers are resolved through `const/let/var` declarations (file-local first, then unique
across the package). Unresolvable values become OPAQUE; call callees keep only their last
property name with trailing digits stripped, so bundler renames do not alter hashes.
"""

from __future__ import annotations

import re
from pathlib import Path

import tree_sitter_javascript as tsjs
import tree_sitter_typescript as tsts
from tree_sitter import Language, Node, Parser

from census.tooldefs import OPAQUE, ToolDef

JS = Language(tsjs.language())
TS = Language(tsts.language_typescript())
_PARSERS = {"js": Parser(JS), "ts": Parser(TS)}

CALL_PATTERNS = {"tool", "registerTool", "addTool"}
WRAPPERS = {"parenthesized_expression", "as_expression", "satisfies_expression",
            "non_null_expression", "type_assertion"}
ESCAPES = {"n": "\n", "t": "\t", "r": "\r", "b": "\b", "f": "\f", "v": "\v", "0": "\0",
           "'": "'", '"': '"', "\\": "\\", "`": "`", "\n": ""}


def _text(n: Node) -> str:
    return n.text.decode("utf-8", errors="replace")


def _decode_escape(s: str) -> str:
    body = s[1:]
    if body and body[0] in ESCAPES:
        return ESCAPES[body[0]]
    m = re.match(r"u\{([0-9a-fA-F]+)\}|u([0-9a-fA-F]{4})|x([0-9a-fA-F]{2})", body)
    if m:
        code = int(next(g for g in m.groups() if g), 16)
        try:
            return chr(code)
        except ValueError:
            return ""
    return body


def _walk(root: Node):
    stack = [root]
    while stack:
        n = stack.pop()
        yield n
        stack.extend(reversed(n.children))


def _norm_ident(name: str) -> str:
    return re.sub(r"\d+$", "", name)


class FileCtx:
    def __init__(self, rel: str, root: Node):
        self.rel = rel
        self.root = root
        self.decls: dict[str, list[Node]] = {}
        for n in _walk(root):
            if n.type == "variable_declarator":
                name, val = n.child_by_field_name("name"), n.child_by_field_name("value")
                if name is not None and val is not None and name.type == "identifier":
                    self.decls.setdefault(_text(name), []).append(val)


class Resolver:
    def __init__(self, files: list[FileCtx]):
        self.files = files
        self.global_decls: dict[str, list[Node]] = {}
        for f in files:
            for k, v in f.decls.items():
                self.global_decls.setdefault(k, []).extend(v)

    def lookup(self, name: str, ctx: FileCtx) -> Node | None:
        local = ctx.decls.get(name)
        if local and len(local) == 1:
            return local[0]
        glob = self.global_decls.get(name)
        if glob and len(glob) == 1:
            return glob[0]
        if glob:
            texts = {_text(g) for g in glob}
            if len(texts) == 1:
                return glob[0]
        return None

    def ev(self, n: Node | None, ctx: FileCtx, depth: int = 0):
        if n is None:
            return None
        if depth > 12:
            return OPAQUE
        ev = lambda x: self.ev(x, ctx, depth + 1)  # noqa: E731
        t = n.type
        if t in WRAPPERS:
            inner = n.named_children[0] if n.named_children else None
            return ev(inner)
        if t == "string":
            out = []
            for c in n.children:
                if c.type == "string_fragment":
                    out.append(_text(c))
                elif c.type == "escape_sequence":
                    out.append(_decode_escape(_text(c)))
            return "".join(out)
        if t == "template_string":
            out = []
            for c in n.children:
                if c.type == "string_fragment":
                    out.append(_text(c))
                elif c.type == "escape_sequence":
                    out.append(_decode_escape(_text(c)))
                elif c.type == "template_substitution":
                    inner = c.named_children[0] if c.named_children else None
                    r = ev(inner)
                    out.append(r if isinstance(r, str) and r != OPAQUE
                               else str(r) if isinstance(r, (int, float)) and not isinstance(r, bool)
                               else "${" + OPAQUE + "}")
            return "".join(out)
        if t == "number":
            try:
                v = float(_text(n).replace("_", ""))
                return int(v) if v.is_integer() else v
            except ValueError:
                return OPAQUE
        if t in ("true", "false"):
            return t == "true"
        if t in ("null", "undefined"):
            return None
        if t == "unary_expression" and _text(n).startswith("!") and n.named_children:
            inner = n.named_children[0]
            if inner.type == "number":
                return _text(inner) == "0"
        if t == "array":
            return [ev(c) for c in n.named_children if c.type != "comment"]
        if t == "object":
            out = {}
            for c in n.named_children:
                if c.type == "pair":
                    k = self._key(c.child_by_field_name("key"), ctx, depth)
                    if k is not None:
                        out[k] = ev(c.child_by_field_name("value"))
                elif c.type == "shorthand_property_identifier":
                    out[_text(c)] = ev_ident(self, _text(c), ctx, depth)
                elif c.type == "spread_element":
                    spread = ev(c.named_children[0]) if c.named_children else OPAQUE
                    if isinstance(spread, dict):
                        out.update(spread)
                    else:
                        out["$spread"] = OPAQUE
            return out
        if t == "identifier":
            return ev_ident(self, _text(n), ctx, depth)
        if t == "binary_expression":
            op = n.child_by_field_name("operator")
            if op is not None and _text(op) == "+":
                a, b = ev(n.child_by_field_name("left")), ev(n.child_by_field_name("right"))
                if isinstance(a, str) and isinstance(b, str):
                    return a + b
            return OPAQUE
        if t == "member_expression":
            obj, prop = n.child_by_field_name("object"), n.child_by_field_name("property")
            base = ev(obj)
            if isinstance(base, dict) and prop is not None and _text(prop) in base:
                return base[_text(prop)]
            return OPAQUE
        if t == "call_expression":
            return self._call(n, ctx, depth)
        return OPAQUE

    def _key(self, k: Node | None, ctx, depth):
        if k is None:
            return None
        if k.type in ("property_identifier", "identifier"):
            return _text(k)
        if k.type in ("string", "number"):
            v = self.ev(k, ctx, depth + 1)
            return str(v)
        if k.type == "computed_property_name" and k.named_children:
            v = self.ev(k.named_children[0], ctx, depth + 1)
            return v if isinstance(v, str) and v != OPAQUE else None
        return None

    def _call(self, n: Node, ctx, depth):
        """Flatten call chains like z.string().describe("x").optional()."""
        chain = []
        cur = n
        while cur is not None and cur.type == "call_expression":
            fn = cur.child_by_field_name("function")
            args = cur.child_by_field_name("arguments")
            argv = [self.ev(a, ctx, depth + 1) for a in (args.named_children if args else [])
                    if a.type not in ("comment", "arrow_function", "function_expression",
                                      "function")]
            if fn is not None and fn.type == "member_expression":
                prop = fn.child_by_field_name("property")
                chain.append([_norm_ident(_text(prop)) if prop is not None else "", argv])
                cur = fn.child_by_field_name("object")
            else:
                name = _norm_ident(_text(fn)) if fn is not None and fn.type == "identifier" else ""
                chain.append([name, argv])
                cur = None
        chain.reverse()
        return {"$call": chain}


def ev_ident(r: Resolver, name: str, ctx: FileCtx, depth: int):
    if depth > 10:
        return OPAQUE
    node = r.lookup(name, ctx)
    if node is None:
        return OPAQUE
    return r.ev(node, ctx, depth + 1)


def _parse(path: Path):
    kind = "ts" if path.suffix in (".ts", ".mts", ".cts") else "js"
    return _PARSERS[kind].parse(path.read_bytes())


def extract_files(root: Path, files: list[Path]) -> tuple[list[ToolDef], dict]:
    ctxs = []
    for p in files:
        try:
            tree = _parse(p)
        except Exception:  # noqa: BLE001 - parser failure is recorded, not fatal
            continue
        ctxs.append(FileCtx(p.relative_to(root).as_posix(), tree.root_node))
    r = Resolver(ctxs)
    tools: list[ToolDef] = []
    for ctx in ctxs:
        for n in _walk(ctx.root):
            if n.type == "call_expression":
                tools.extend(_from_call(r, n, ctx))
            elif n.type == "object":
                t = _from_object(r, n, ctx)
                if t:
                    tools.append(t)
    return tools, {"js_files": len(ctxs)}


def _str(v):
    return v if isinstance(v, str) and v != OPAQUE else None


def _from_call(r: Resolver, n: Node, ctx: FileCtx) -> list[ToolDef]:
    fn = n.child_by_field_name("function")
    if fn is None or fn.type != "member_expression":
        return []
    prop = fn.child_by_field_name("property")
    method = _text(prop) if prop is not None else ""
    if method not in CALL_PATTERNS:
        return []
    args_node = n.child_by_field_name("arguments")
    args = [a for a in (args_node.named_children if args_node else []) if a.type != "comment"]
    if not args:
        return []
    if method == "addTool":
        obj = r.ev(args[0], ctx)
        if not isinstance(obj, dict):
            return []
        name = _str(obj.get("name"))
        if not name:
            return []
        schema = obj.get("parameters", obj.get("inputSchema"))
        return [ToolDef(name, _str(obj.get("description")), schema, "addTool", ctx.rel)]
    name = _str(r.ev(args[0], ctx))
    if not name:
        return []
    rest = [a for a in args[1:] if a.type not in ("arrow_function", "function_expression",
                                                  "function")]
    if method == "registerTool":
        cfg = r.ev(rest[0], ctx) if rest else None
        if not isinstance(cfg, dict):
            return [ToolDef(name, None, OPAQUE, "registerTool", ctx.rel)]
        return [ToolDef(name, _str(cfg.get("description")), cfg.get("inputSchema"),
                        "registerTool", ctx.rel, {"title": _str(cfg.get("title"))})]
    # method == "tool": (name, [desc], [shape], [annotations], cb)
    vals = [r.ev(a, ctx) for a in rest]
    desc = vals[0] if vals and isinstance(vals[0], str) else None
    shapes = [v for v in vals[1 if desc is not None else 0:] if isinstance(v, dict)]
    return [ToolDef(name, _str(desc), shapes[0] if shapes else None, "tool", ctx.rel)]


def _from_object(r: Resolver, n: Node, ctx: FileCtx) -> ToolDef | None:
    keys = {}
    for c in n.named_children:
        if c.type == "pair":
            k = c.child_by_field_name("key")
            if k is not None and k.type in ("property_identifier", "string"):
                keys[_text(k).strip("'\"")] = c.child_by_field_name("value")
        elif c.type == "shorthand_property_identifier":
            keys[_text(c)] = c
    if "name" not in keys or "inputSchema" not in keys:
        return None
    nm = keys["name"]
    name = _str(ev_ident(r, _text(nm), ctx, 0) if nm.type == "shorthand_property_identifier"
                else r.ev(nm, ctx))
    if not name:
        return None
    obj = r.ev(n, ctx)
    if not isinstance(obj, dict):
        return None
    return ToolDef(name, _str(obj.get("description")), obj.get("inputSchema"), "object_literal",
                   ctx.rel)


def source_files(root: Path) -> list[Path]:
    js = sorted(p for p in root.rglob("*") if p.suffix in (".js", ".mjs", ".cjs") and p.is_file())
    if js:
        return js
    return sorted(p for p in root.rglob("*") if p.suffix in (".ts", ".mts", ".cts")
                  and p.is_file())


def extract_dir(root: Path) -> tuple[list[ToolDef], dict]:
    return extract_files(root, source_files(root))
