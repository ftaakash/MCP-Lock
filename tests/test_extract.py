import textwrap

from census import extract_js, extract_py
from census.tooldefs import OPAQUE, dedupe, diff, tools_hash


def _js(tmp_path, code, name="index.js"):
    (tmp_path / name).write_text(textwrap.dedent(code), encoding="utf-8")
    tools, _ = extract_js.extract_dir(tmp_path)
    return {t.name: t for t in tools if t.is_valid()}


def _py(tmp_path, code):
    (tmp_path / "server.py").write_text(textwrap.dedent(code), encoding="utf-8")
    tools, _ = extract_py.extract_dir(tmp_path)
    return {t.name: t for t in tools if t.is_valid()}


def test_js_register_tool_and_const_resolution(tmp_path):
    t = _js(tmp_path, """
        const DESC = "Reads " + 'a file';
        const NAME = `read_file`;
        server.registerTool(NAME, { description: DESC,
            inputSchema: { path: z.string().describe("p") } }, async () => {});
    """)
    assert t["read_file"].description == "Reads a file"
    assert t["read_file"].schema["path"]["$call"][-1] == ["describe", ["p"]]


def test_js_legacy_tool_and_addtool(tmp_path):
    t = _js(tmp_path, """
        server.tool("a", "desc a", { x: z.number() }, async () => {});
        server.tool("b", async () => {});
        mcp.addTool({ name: "c", description: "desc c", parameters: z.object({}) });
    """)
    assert t["a"].description == "desc a" and "c" in t
    assert "b" not in t  # no description, no schema -> not a valid extraction


def test_js_object_literal_and_cross_file(tmp_path):
    (tmp_path / "tools.js").write_text(
        'export const SEARCH = { name: "search", description: "find", '
        'inputSchema: { type: "object" } };', encoding="utf-8")
    t = _js(tmp_path, 'const tools = [SEARCH]; const x = { name: someVar, inputSchema: {} };')
    assert set(t) == {"search"}


def test_js_rename_stability(tmp_path):
    a = _js(tmp_path / "x" if (tmp_path / "x").mkdir() is None else tmp_path,
            'server2.registerTool("t", {description: "d", inputSchema: {a: z3.string()}});')
    b_dir = tmp_path / "y"
    b_dir.mkdir()
    b = _js(b_dir, 'server.registerTool("t", {description: "d", inputSchema: {a: z.string()}});')
    assert tools_hash(list(a.values())) == tools_hash(list(b.values()))


def test_py_tool_ctor_enum_and_model(tmp_path):
    t = _py(tmp_path, """
        from enum import Enum
        from pydantic import BaseModel
        class Names(str, Enum):
            STATUS = "git_status"
        class Status(BaseModel):
            repo_path: str
        async def list_tools():
            return [Tool(name=Names.STATUS, description="Shows status",
                         inputSchema=Status.model_json_schema())]
    """)
    assert t["git_status"].schema == {"$model": [["repo_path", "str", None]]}


def test_py_decorator(tmp_path):
    t = _py(tmp_path, '''
        @mcp.tool()
        async def get_weather(city: str, ctx: Context, units: str = "c") -> str:
            """Get the weather."""
        @mcp.tool(name="renamed", description="Explicit")
        def f(x: int): ...
    ''')
    assert t["get_weather"].description == "Get the weather."
    assert t["get_weather"].schema == [["city", "str", None], ["units", "str", "'c'"]]
    assert t["renamed"].description == "Explicit"


def test_diff_and_dedupe():
    old = [{"name": "a", "description": "x", "schema": {}}]
    new = [{"name": "a", "description": "y", "schema": {}},
           {"name": "b", "description": None, "schema": OPAQUE}]
    d = diff(old, new)
    assert d["added"] == ["b"] and d["description_changed"] == ["a"] and d["changed"]
    assert not diff(old, old)["changed"]
    from census.tooldefs import ToolDef
    tools, conflicts = dedupe([ToolDef("a", "1", None, "k"), ToolDef("a", "2", None, "k")])
    assert len(tools) == 1 and conflicts == 1


def test_py_call_form_and_wrapper_decorators(tmp_path):
    t = _py(tmp_path, '''
        def _watch_tool(annotations):
            def deco(fn):
                return mcp.tool(fn, annotations=annotations)
            return deco

        @_watch_tool(RO)
        async def watch_add(wallet: str) -> dict:
            """Add a watch."""

        def candles(market: str, limit: int = 100):
            """Get candles."""

        def setup():
            mcp.tool(candles, annotations=RO)
            mcp.tool(fn_param_not_a_function)
    ''')
    assert t["watch_add"].description == "Add a watch." and t["watch_add"].kind == "py_wrapper_decorator"
    assert t["candles"].kind == "py_tool_call"
    assert t["candles"].schema == [["market", "str", None], ["limit", "int", "100"]]
    assert "_watch_tool" not in t and "deco" not in t


def test_py_dict_literal_tools(tmp_path):
    t = _py(tmp_path, '''
        TOOLS = [
            {"name": "browser_back", "description": "Go back.", "inputSchema": {"type": "object"}},
            {"name": some_var, "inputSchema": {}},
            {"name": "not_a_tool", "value": 1},
        ]
    ''')
    assert set(t) == {"browser_back"} and t["browser_back"].kind == "py_dict_literal"


def test_fisher_matches_known_values():
    from census.rq1 import fisher_two_sided
    # Lady tasting tea: [[3, 1], [1, 3]] -> two-sided p = 0.4857
    assert abs(fisher_two_sided(3, 1, 1, 3) - 0.4857142857) < 1e-6
    assert fisher_two_sided(0, 10, 10, 0) < 1e-4
