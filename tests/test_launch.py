from census.launch import parse, parse_config_text, parse_fragment


def test_npx_unpinned():
    lt = parse("npx", ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"])
    assert (lt.ecosystem, lt.package, lt.pinned) == ("npm", "@modelcontextprotocol/server-filesystem", False)


def test_npx_pinned_and_latest():
    assert parse("npx", ["-y", "@a/b@1.2.3"]).pinned
    assert not parse("npx", ["-y", "@a/b@latest"]).pinned
    assert not parse("npx", ["-y", "foo@^1.0.0"]).pinned
    assert parse("npx", ["foo@2.0.0-beta.1"]).pinned


def test_npx_package_flag_and_windows_wrapper():
    assert parse("npx", ["-y", "-p", "pkg-x", "bin-x"]).package == "pkg-x"
    lt = parse("cmd", ["/c", "npx", "-y", "mcp-server-x"])
    assert lt.package == "mcp-server-x"
    assert parse("npx.cmd", ["-y", "z"]).package == "z"
    assert parse("C:\\Program Files\\nodejs\\npx.cmd", ["-y", "z"]).package == "z"


def test_single_string_command():
    assert parse("npx -y foo-mcp", None).package == "foo-mcp"


def test_dlx():
    assert parse("pnpm", ["dlx", "foo"]).package == "foo"


def test_uvx():
    lt = parse("uvx", ["mcp-server-git", "--repository", "."])
    assert (lt.ecosystem, lt.package, lt.pinned) == ("pypi", "mcp-server-git", False)
    assert parse("uvx", ["mcp-server-git==0.6.2"]).pinned
    assert parse("uvx", ["mcp-server-git@0.6.2"]).pinned
    assert not parse("uvx", ["mcp-server-git@latest"]).pinned
    assert parse("uvx", ["--from", "Foo_Bar==1.0", "foo"]).package == "foo-bar"
    assert parse("uvx", ["--python", "3.11", "x-mcp"]).package == "x-mcp"
    assert parse("uvx", ["--from", "git+https://github.com/a/b", "b"]) is None


def test_not_runner():
    assert parse("node", ["dist/index.js"]) is None
    assert parse("docker", ["run", "-i", "img"]) is None


def test_config_and_fragment():
    text = '{"mcpServers": {"a": {"command": "npx", "args": ["-y", "a-mcp"]}, // c\n' \
           '"b": {"command": "uvx", "args": ["b-mcp"]},}}'
    assert {lt.package for lt in parse_config_text(text)} == {"a-mcp", "b-mcp"}
    frag = '"command": "npx",\n      "args": ["-y", "@x/y"]\n    },\n    "z": {"command": "uvx"'
    assert [lt.package for lt in parse_fragment(frag)] == ["@x/y"]
