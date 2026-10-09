from gate.command import parse


def test_pip_flags_and_specs():
    (inv,) = parse("pip install --extra-index-url http://packages.internal/simple/ httpclient "
                   "pytest==8.0.0 --trusted-host packages.internal -r req.txt")
    assert inv.ecosystem == "pypi" and inv.specs == ["httpclient", "pytest==8.0.0"]
    assert inv.extra_index_urls == ["http://packages.internal/simple/"]
    assert inv.trusted_hosts == ["packages.internal"] and inv.req_files == ["req.txt"]


def test_python_m_pip_uv_and_equals_form():
    a, b = parse("python -m pip install --index-url=https://evil.example/simple x && "
                 "uv pip install -e .")
    assert a.index_urls == ["https://evil.example/simple"] and a.specs == ["x"]
    assert b.local_targets == ["."]


def test_env_prefix_export_and_make():
    a, b = parse("export PIP_CONFIG_FILE=./pip.conf; pip install -r requirements.txt; make setup")
    assert a.env["PIP_CONFIG_FILE"] == "./pip.conf"
    assert b.kind == "make" and b.make_target == "setup"
    (c,) = parse("PIP_CONFIG_FILE=/tmp/p.conf pip install foo")
    assert c.env == {"PIP_CONFIG_FILE": "/tmp/p.conf"}


def test_npm_variants():
    a, b, c = parse("npm i --registry http://localhost:4873/ requets && pnpm add lodash@4.17.20 "
                    "&& npm ci")
    assert a.index_urls == ["http://localhost:4873/"] and a.specs == ["requets"]
    assert b.specs == ["lodash@4.17.20"]
    assert c.from_manifest


def test_launches():
    (a,) = parse("npx -y @modelcontextprotocol/server-filesystem /tmp")
    assert a.kind == "launch" and a.launch.package == "@modelcontextprotocol/server-filesystem"
    (b,) = parse("uvx mcp-server-git==2026.8.18")
    assert b.ecosystem == "pypi" and b.launch.pinned


def test_non_install_commands_ignored():
    assert parse("ls -la && git status && pip list && npm run build") == []


def test_npm_names_starting_with_http_are_packages():
    (a,) = parse("npm install https-proxy-agent http-errors https://example.com/x.tgz")
    assert a.specs == ["https-proxy-agent", "http-errors"]
    assert a.local_targets == ["https://example.com/x.tgz"]
