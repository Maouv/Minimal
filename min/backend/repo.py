from dataclasses import dataclass, field
from pathlib import Path
import re


@dataclass
class RepoContext:
    root: str
    minimal_mds: list[dict] = field(default_factory=list)
    repo_tags: list[dict] = field(default_factory=list)
    symbols: list[dict] = field(default_factory=list)
    manifests: list[dict] = field(default_factory=list)
    token_estimate: int = 0


TAG_PATTERNS = [
    ({"py", "toml", "sh", "yaml", "yml", "ini", "rb", "rs", "tf"}, r'#\s*@repo:\s*(.+)'),
    ({"ts", "tsx", "js", "jsx", "go", "c", "cpp", "java", "cs", "kt"}, r'//\s*@repo:\s*(.+)'),
    ({"md", "html", "xml", "vue", "svelte"}, r'<!--\s*@repo:\s*(.+?)\s*-->'),
    ({"css", "scss", "less"}, r'/\*\s*@repo:\s*(.+?)\s*\*/'),
]

SYMBOL_RE = re.compile(
    r'^\s*(?:export\s+)?(?:pub\s+)?(?:async\s+)?'
    r'(?:function|class|def|fn|func|const|let|var|type|interface|struct|impl|enum)\s+(\w+)',
    re.MULTILINE
)

SKIP_DIRS = {".git", "__pycache__", "node_modules", ".venv", "venv", "dist", "build", ".next", ".nuxt", "target", ".cargo", ".mypy_cache"}
MANIFEST_FILES = {"package.json", "requirements.txt", "go.mod", "Cargo.toml", "pyproject.toml"}


def _get_tag_patterns(ext: str):
    for exts, pattern in TAG_PATTERNS:
        if ext in exts:
            return re.compile(pattern)
    return None


def _is_under_skip_dir(path: Path, root: Path) -> bool:
    parts = path.relative_to(root).parts[:-1]
    return any(part in SKIP_DIRS for part in parts)


def _count_tokens(text: str) -> int:
    return len(text) // 4


def _process_minimal_md(path: Path, root: Path, ctx: RepoContext):
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
        depth = len(path.relative_to(root).parts) - 1
        ctx.minimal_mds.append({"path": str(path.relative_to(root)), "content": content, "depth": depth})
    except Exception:
        pass


def _process_code_file(path: Path, root: Path, ctx: RepoContext, ext: str):
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
    except Exception:
        return

    rel_path = str(path.relative_to(root))

    pattern = _get_tag_patterns(ext)
    tags = []
    if pattern:
        tags = re.findall(pattern, content)
    if tags:
        ctx.repo_tags.append({"file": rel_path, "tags": tags})

    symbols = re.findall(SYMBOL_RE, content)
    if len(symbols) > 20:
        symbols = symbols[:20]
    if symbols:
        ctx.symbols.append({"file": rel_path, "symbols": symbols, "has_tags": bool(tags), "depth": len(path.relative_to(root).parts)})


def _process_manifest(path: Path, root: Path, ctx: RepoContext):
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            lines = [next(f) for _ in range(200)]
        content = "".join(lines)
        ctx.manifests.append({"file": str(path.relative_to(root)), "content": content})
    except Exception:
        pass


def _trim_to_budget(ctx: RepoContext, budget: int):
    while ctx.token_estimate > budget:
        if ctx.symbols:
            non_tagged = [s for s in ctx.symbols if not s.get("has_tags", False)]
            if non_tagged:
                non_tagged_sorted = sorted(non_tagged, key=lambda x: x.get("depth", 0), reverse=True)
                ctx.symbols = [s for s in ctx.symbols if s in non_tagged_sorted[1:]] + [s for s in ctx.symbols if s.get("has_tags", False)]
                ctx.token_estimate = _count_tokens(_serialize_context(ctx))
                continue

        child_mds = [m for m in ctx.minimal_mds if m["depth"] > 0]
        if child_mds:
            child_sorted = sorted(child_mds, key=lambda x: x["depth"], reverse=True)
            ctx.minimal_mds = [m for m in ctx.minimal_mds if m not in [child_sorted[0]]]
            ctx.token_estimate = _count_tokens(_serialize_context(ctx))
            continue

        break


def _serialize_context(ctx: RepoContext) -> str:
    parts = [ctx.root]
    for md in ctx.minimal_mds:
        parts.append(f"{md['path']}|{md['content']}")
    for tag in ctx.repo_tags:
        parts.append(f"{tag['file']}|{','.join(tag['tags'])}")
    for sym in ctx.symbols:
        parts.append(f"{sym['file']}|{','.join(sym['symbols'])}")
    for mf in ctx.manifests:
        parts.append(f"{mf['file']}|{mf['content']}")
    return "\n".join(parts)


def scan(root: Path, token_budget: int = 6000) -> RepoContext:
    root = Path(root).resolve()
    ctx = RepoContext(root=str(root))

    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if _is_under_skip_dir(path, root):
            continue
        if path.name.startswith(".") and path.name != ".env":
            continue

        ext = path.suffix.lstrip(".")
        name = path.name

        if name == "MINIMAL.md":
            _process_minimal_md(path, root, ctx)
        elif ext in {"py", "toml", "sh", "yaml", "yml", "ini", "rb", "rs", "tf",
                     "ts", "tsx", "js", "jsx", "go", "c", "cpp", "java", "cs", "kt",
                     "md", "html", "xml", "vue", "svelte",
                     "css", "scss", "less"}:
            _process_code_file(path, root, ctx, ext)
        elif name in MANIFEST_FILES:
            _process_manifest(path, root, ctx)

    ctx.token_estimate = _count_tokens(_serialize_context(ctx))
    _trim_to_budget(ctx, token_budget)
    return ctx
