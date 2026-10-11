import pytest

from gate import semver

# (version, range, expected) checked against node-semver's documented semantics
CASES = [
    ("1.2.3", "1.2.3", True), ("1.2.4", "1.2.3", False),
    ("1.9.9", "^1.2.3", True), ("2.0.0", "^1.2.3", False), ("1.2.2", "^1.2.3", False),
    ("0.2.9", "^0.2.3", True), ("0.3.0", "^0.2.3", False),
    ("0.0.3", "^0.0.3", True), ("0.0.4", "^0.0.3", False),
    ("0.9.0", "^0.x", True), ("1.0.0", "^0.x", False),
    ("1.2.9", "~1.2.3", True), ("1.3.0", "~1.2.3", False), ("1.9.0", "~1", True),
    ("1.2.0", "1.2.x", True), ("1.3.0", "1.2.*", False), ("7.0.0", "*", True), ("7.0.0", "", True),
    ("2.5.0", ">=1.2.3 <3", True), ("3.0.0", ">=1.2.3 <3", False), ("1.2.3", ">= 1.2.3", True),
    ("1.0.0", "<1.0.0 || >=2.0.0", False), ("2.1.0", "<1.0.0 || >=2.0.0", True),
    ("2.3.4", "1.2 - 2.3.4", True), ("2.3.5", "1.2 - 2.3.4", False), ("2.9.0", "1.2.3 - 2", True),
    # pre-releases: excluded unless a comparator names one on the same tuple
    ("2.0.0-beta.1", "^1.0.0", False), ("1.2.3-beta.4", "^1.2.3-beta.2", True),
    ("1.2.4-beta.1", "^1.2.3-beta.2", False), ("1.0.0-rc.1", "*", False),
    ("1.0.0", "latest", True), ("v1.2.3", "1.2.3", True),
]


@pytest.mark.parametrize("v,r,want", CASES)
def test_satisfies(v, r, want):
    assert semver.satisfies(v, r) is want


def test_not_registry_ranges():
    for r in ("github:a/b", "git+https://x/y.git", "file:../x", "https://x/y.tgz", "workspace:*"):
        assert semver.parse_range(r) is None
        assert not semver.satisfies("1.0.0", r)


def test_max_satisfying():
    vs = ["1.0.0", "1.4.2", "1.10.0", "2.0.0", "2.1.0-rc.1"]
    assert semver.max_satisfying(vs, "^1.0.0") == "1.10.0"  # numeric, not lexical, order
    assert semver.max_satisfying(vs, ">=2") == "2.0.0"
    assert semver.max_satisfying(vs, "^3") is None
