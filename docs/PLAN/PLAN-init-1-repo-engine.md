# Plan 1 — repo.py (Scan Engine)

## File
`min/backend/repo.py` new modul, no dependency eksternal.

## Output type

```python
@dataclass
class RepoContext:
    root: str
    minimal_mds: list[dict]   # [{path, content, depth}]
    repo_tags: list[dict]     # [{file, tags: [str]}]
    symbols: list[dict]       # [{file, symbols: [str]}]
    manifests: list[dict]     # [{file, content}]
    token_estimate: int
```

## Public function

```python
def scan(root: Path, token_budget: int = 6000) -> RepoContext
```

## Walk logic

- `root.rglob("*")` — strict, can't get off from root
- Skip dirs: `.git __pycache__ node_modules .venv venv dist build .next .nuxt target .cargo .mypy_cache`
- Skip hidden files except `.env`
-For every file, Detection via extension:
  - Nama `MINIMAL.md` → baca full, `depth = len(path.relative_to(root).parts) - 1`
  - Ekstensi code → scan `@repo:` tags + symbols
  - Nama `package.json requirements.txt go.mod Cargo.toml pyproject.toml` → baca full (max 200 baris)

## Tag extraction

```python
TAG_PATTERNS = [
    ({"py","toml","sh","yaml","yml","ini","rb","rs","tf"},  r'#\s*@repo:\s*(.+)'),
    ({"ts","tsx","js","jsx","go","c","cpp","java","cs","kt"}, r'//\s*@repo:\s*(.+)'),
    ({"md","html","xml","vue","svelte"},                     r'<!--\s*@repo:\s*(.+?)\s*-->'),
    ({"css","scss","less"},                                  r'/\*\s*@repo:\s*(.+?)\s*\*/'),
]
```

## Symbol extraction

Single regex, one pass, every language:

```python
SYMBOL_RE = re.compile(
    r'^\s*(?:export\s+)?(?:pub\s+)?(?:async\s+)?'
    r'(?:function|class|def|fn|func|const|let|var|type|interface|struct|impl|enum)\s+(\w+)',
    re.MULTILINE
)
```

Get max 20 symbols per file, if more take the first 20.

## Token budget enforcement

Rough estimate: 1 token ≈ 4 chars.

Trim order if budget exceeds:
1. Trim symbols from files that don't have `@repo:` tags (starting from the deepest file)
2. Trim the child `MINIMAL.md` with the largest `depth`
3. Never trim: `@repo:` tags, manifest, MINIMAL.md in depth 0


## Test standalone

```bash
cd min/backend
python3 -c "
from pathlib import Path
from repo import scan
ctx = scan(Path('.'))
print('minimal_mds:', len(ctx.minimal_mds))
print('symbols files:', len(ctx.symbols))
print('tags files:', len(ctx.repo_tags))
print('token_estimate:', ctx.token_estimate)
"
```

