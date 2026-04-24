#!/usr/bin/env python3
"""
Jalanin dari folder minimal/:
    python3 strip_vendors.py
"""
import re
from pathlib import Path

vendor = Path("min/backend/vendor")

# ── sendchat.py ──────────────────────────────────────────────────────────────
txt = (vendor / "sendchat.py").read_text()
txt = re.sub(r'^from aider.*\n', '', txt, flags=re.MULTILINE)
txt = re.sub(r'^import aider.*\n', '', txt, flags=re.MULTILINE)
header = (
    "# vendored from aider/sendchat.py | commit: f09d70659ae90a0d068c80c288cbb55f2d3c3755\n"
    "# stripped: aider.dump, aider.utils.format_messages\n\n"
    "def _format_messages(messages):\n"
    "    return '\\n'.join(f\"{m['role']}: {m['content']}\" for m in messages)\n\n\n"
)
txt = header + txt.lstrip()
txt = txt.replace("format_messages(messages)", "_format_messages(messages)")
(vendor / "sendchat.py").write_text(txt)
print("✓ sendchat.py")

# ── search_replace.py ─────────────────────────────────────────────────────────
txt = (vendor / "search_replace.py").read_text()
txt = re.sub(r'^from aider.*\n', '', txt, flags=re.MULTILINE)
txt = re.sub(r'^from tqdm.*\n', '', txt, flags=re.MULTILINE)
txt = re.sub(r'^import sys\n', '', txt, flags=re.MULTILINE)
# hapus fungsi git_cherry_pick_* (pakai GitTemporaryDirectory)
txt = re.sub(r'\ndef git_cherry_pick_\w+\(texts\):.*?(?=\ndef )', '', txt, flags=re.DOTALL)
# hapus debug dump() calls
txt = re.sub(r'^\s+dump\(.*\)\n', '', txt, flags=re.MULTILINE)
# fix empty if debug: blocks
txt = re.sub(r'(    if debug:\n)((?:        #.*\n|\n)*)(    if )', r'\1        pass\n\3', txt)
# hapus proc() dan main() — test runner
txt = re.sub(r'\ndef proc\(.*', '', txt, flags=re.DOTALL)
# tambah all_preprocs dan strategy lists di akhir
txt += """
all_preprocs = [
    (False, False, False),
    (True, False, False),
    (False, True, False),
    (True, True, False),
]

editblock_strategies = [
    (search_and_replace, all_preprocs),
    (dmp_lines_apply, all_preprocs),
]

udiff_strategies = [
    (search_and_replace, all_preprocs),
    (dmp_lines_apply, all_preprocs),
]
"""
header = "# vendored from aider/coders/search_replace.py | commit: f09d70659ae90a0d068c80c288cbb55f2d3c3755\n# stripped: aider imports, tqdm, git_cherry_pick funcs, proc/main\n\n"
txt = header + txt.lstrip()
(vendor / "search_replace.py").write_text(txt)
print("✓ search_replace.py")

# ── udiff.py ──────────────────────────────────────────────────────────────────
txt = (vendor / "udiff.py").read_text()
# strip semua aider/relative imports
txt = re.sub(r'^from \.\..dump.*\n', '', txt, flags=re.MULTILINE)
txt = re.sub(r'^from \.base_coder.*\n', '', txt, flags=re.MULTILINE)
txt = re.sub(r'^from \.udiff_prompts.*\n', '', txt, flags=re.MULTILINE)
txt = re.sub(r'^from \.search_replace import[\s\S]*?\)\n', '', txt, flags=re.MULTILINE)
# hapus class UnifiedDiffCoder
txt = re.sub(r'^class UnifiedDiffCoder.*?(?=\ndef )', '', txt, flags=re.DOTALL | re.MULTILINE)
# fix literal newlines di dalam string (other_hunks_applied dll)
lines = txt.splitlines(keepends=True)
out = []
i = 0
while i < len(lines):
    line = lines[i]
    if '= "' in line and not line.rstrip().endswith('"') and not line.rstrip().endswith('"""'):
        # multiline string — join sampai closing quote
        combined = line.rstrip('\n')
        i += 1
        while i < len(lines):
            part = lines[i].rstrip('\n')
            combined += '\\n' + part
            i += 1
            if part.strip() == '"' or part.rstrip().endswith('"'):
                break
        # rebuild sebagai single line dengan escaped newlines
        out.append(combined + '\n')
    else:
        out.append(line)
        i += 1
txt = ''.join(out)
# strip old stdlib imports (akan dibuang ke header baru)
txt = re.sub(r'^import difflib\n', '', txt, flags=re.MULTILINE)
txt = re.sub(r'^from itertools.*\n', '', txt, flags=re.MULTILINE)
txt = re.sub(r'^from pathlib.*\n', '', txt, flags=re.MULTILINE)
header = (
    "# vendored from aider/coders/udiff_coder.py | commit: f09d70659ae90a0d068c80c288cbb55f2d3c3755\n"
    "# stripped: UnifiedDiffCoder class, base_coder, aider imports\n\n"
    "import difflib\n"
    "from itertools import groupby\n"
    "from pathlib import Path\n\n"
    "from .search_replace import flexible_search_and_replace, udiff_strategies\n\n\n"
)
txt = header + txt.lstrip()
(vendor / "udiff.py").write_text(txt)
print("✓ udiff.py")

# ── wholefile.py ──────────────────────────────────────────────────────────────
wholefile_clean = '''# vendored from aider/coders/wholefile_coder.py | commit: f09d70659ae90a0d068c80c288cbb55f2d3c3755
# stripped: WholeFileCoder class (terlalu coupled ke base_coder/io)
# replaced: parse_whole_edits() — fungsi standalone

from pathlib import Path

DEFAULT_FENCE = ("`" * 3, "`" * 3)


def parse_whole_edits(content, chat_files, fence=DEFAULT_FENCE):
    """
    Parse AI response untuk whole-file edits.
    Returns list of (fname, new_content) tuples.
    """
    lines = content.splitlines(keepends=True)
    edits = []
    fname = None
    new_lines = []

    for i, line in enumerate(lines):
        if line.startswith(fence[0]) or line.startswith(fence[1]):
            if fname is not None:
                edits.append((fname, "".join(new_lines)))
                fname = None
                new_lines = []
            else:
                if i > 0:
                    candidate = lines[i - 1].strip()
                    candidate = candidate.strip("*").rstrip(":").strip("`").lstrip("#").strip()
                    if len(candidate) <= 250 and candidate:
                        if candidate not in chat_files and Path(candidate).name in chat_files:
                            candidate = Path(candidate).name
                        fname = candidate
                if not fname:
                    if len(chat_files) == 1:
                        fname = chat_files[0]
                    else:
                        raise ValueError("No filename before ``` block in response")
        elif fname is not None:
            new_lines.append(line)

    if fname and new_lines:
        edits.append((fname, "".join(new_lines)))

    return edits
'''
(vendor / "wholefile.py").write_text(wholefile_clean)
print("✓ wholefile.py")

# ── repo.py ───────────────────────────────────────────────────────────────────
repo_clean = '''# vendored from aider/repo.py | commit: f09d70659ae90a0d068c80c288cbb55f2d3c3755
# stripped: GitRepo class (coupled ke aider io/prompts/utils)
# replaced: fungsi git standalone yang dibutuhkan minimal

import os
from pathlib import Path

try:
    import git
    ANY_GIT_ERROR = (
        git.exc.ODBError,
        git.exc.GitError,
        git.exc.InvalidGitRepositoryError,
        git.exc.GitCommandNotFound,
        OSError, IndexError, BufferError, TypeError,
        ValueError, AttributeError, AssertionError, TimeoutError,
    )
except ImportError:
    git = None
    ANY_GIT_ERROR = (OSError, ValueError)


def get_repo(cwd="."):
    if not git:
        return None
    try:
        return git.Repo(cwd, search_parent_directories=True)
    except ANY_GIT_ERROR:
        return None


def git_commit(message, fnames=None, cwd="."):
    """Commit files. Returns (hash, message) or None."""
    repo = get_repo(cwd)
    if not repo:
        return None
    try:
        if fnames:
            for f in fnames:
                repo.git.add(str(f))
        else:
            repo.git.add("-A")
        repo.git.commit("-m", message)
        sha = repo.head.commit.hexsha[:7]
        return sha, message
    except ANY_GIT_ERROR as e:
        raise RuntimeError(f"git commit failed: {e}")


def git_diff(cwd="."):
    """Return diff of last commit vs working tree."""
    repo = get_repo(cwd)
    if not repo:
        return ""
    try:
        return repo.git.diff("HEAD")
    except ANY_GIT_ERROR:
        return ""


def git_undo(cwd="."):
    """Undo last commit (keep changes staged)."""
    repo = get_repo(cwd)
    if not repo:
        raise RuntimeError("Not a git repo")
    try:
        repo.git.reset("--soft", "HEAD~1")
        return True
    except ANY_GIT_ERROR as e:
        raise RuntimeError(f"git undo failed: {e}")


def git_dirty_files(cwd="."):
    """Return list of modified files."""
    repo = get_repo(cwd)
    if not repo:
        return []
    try:
        staged = repo.git.diff("--name-only", "--cached").splitlines()
        unstaged = repo.git.diff("--name-only").splitlines()
        return list(set(staged + unstaged))
    except ANY_GIT_ERROR:
        return []
'''
(vendor / "repo.py").write_text(repo_clean)
print("✓ repo.py")

print("\nDone! Semua vendor files sudah di-strip.")
