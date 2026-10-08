import json, re, sys
d = json.load(open(sys.argv[1]))
print("snapshot:", d.get("last_update"), "n =", len(d["rows"]))
names = [r["project"].lower() for r in d["rows"]]
def norm(s): return re.sub(r"[-_.]+", "", s)
def lev1(a, b):
    if a == b or abs(len(a) - len(b)) > 1: return False
    if len(a) == len(b): return sum(x != y for x, y in zip(a, b)) == 1
    if len(a) > len(b): a, b = b, a
    i = 0
    while i < len(a) and a[i] == b[i]: i += 1
    return a[i:] == b[i + 1:]
def transp(a, b):
    if len(a) != len(b) or a == b: return False
    diff = [i for i in range(len(a)) if a[i] != b[i]]
    return len(diff) == 2 and diff[1] == diff[0] + 1 and a[diff[0]] == b[diff[1]] and a[diff[1]] == b[diff[0]]
def hit(p, q): return p != q and (lev1(p, q) or transp(p, q) or norm(p) == norm(q))
probe = names[:1000]
for N in (100, 250, 500, 1000, 2000, 5000, 10000):
    P = names[:N]
    flagged = [(p, next(q for q in P if hit(p, q))) for p in probe if any(hit(p, q) for q in P)]
    print(f"P=top-{N:<5} flagged {len(flagged):>3}/1000  e.g. {flagged[:6]}")
