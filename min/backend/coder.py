# coder.py — edit engine
# Dispatch ke vendor edit strategies. Verify after apply. Rollback on fail.

import difflib
from pathlib import Path
from dataclasses import dataclass
from commands import EditMode


@dataclass
class EditResult:
    file: str
    original: str
    updated: str
    diff: str
    success: bool
    error: str = ""


def apply_edits(response: str, files: dict[str, str], mode: EditMode) -> list[EditResult]:
    """
    Parse AI response dan apply edits ke files.
    Return list EditResult — satu per file yang diedit.
    """
    if mode == "block":
        return _apply_editblock(response, files)
    elif mode == "udiff":
        return _apply_udiff(response, files)
    elif mode == "whole":
        return _apply_whole(response, files)
    return []


def verify(result: EditResult) -> bool:
    """
    Verify edit berhasil diapply ke disk.
    Baca file dari disk, bandingkan dengan result.updated.
    """
    try:
        actual = Path(result.file).read_text(encoding="utf-8", errors="replace")
        return actual == result.updated
    except Exception:
        return False


def write_to_disk(result: EditResult) -> bool:
    """Write updated content ke file. Return False kalau gagal."""
    try:
        Path(result.file).write_text(result.updated, encoding="utf-8")
        return True
    except Exception:
        return False


def rollback(result: EditResult) -> bool:
    """Rollback file ke original content."""
    try:
        Path(result.file).write_text(result.original, encoding="utf-8")
        return True
    except Exception:
        return False


def make_diff(original: str, updated: str, filename: str) -> str:
    """Generate unified diff string."""
    lines_orig = original.splitlines(keepends=True)
    lines_updated = updated.splitlines(keepends=True)
    diff = difflib.unified_diff(
        lines_orig, lines_updated,
        fromfile=f"a/{filename}",
        tofile=f"b/{filename}",
    )
    return "".join(diff)


# --- Strategy implementations ---

def _apply_editblock(response: str, files: dict[str, str]) -> list[EditResult]:
    from vendor.search_replace import find_original_update_blocks, replace_most_similar_chunk

    results = []

    try:
        blocks = list(find_original_update_blocks(response))
    except Exception as e:
        return [EditResult(file="", original="", updated="", diff="", success=False, error=str(e))]

    # group blocks by filename
    by_file: dict[str, list] = {}
    for fname, original, updated in blocks:
        if fname not in by_file:
            by_file[fname] = []
        by_file[fname].append((original, updated))

    for fname, block_list in by_file.items():
        # resolve file path
        matched_path = _match_file(fname, files)
        if not matched_path:
            results.append(EditResult(
                file=fname, original="", updated="", diff="",
                success=False, error=f"File not in context: {fname}"
            ))
            continue

        content = files[matched_path]
        original_content = content

        for search, replace in block_list:
            # fuzzy normalize sebelum match (fix aider bug #3)
            new_content = replace_most_similar_chunk(content, search, replace)
            if new_content is None:
                results.append(EditResult(
                    file=matched_path, original=original_content, updated=content,
                    diff="", success=False,
                    error=f"Could not find match for SEARCH block in {fname}"
                ))
                return results
            content = new_content

        diff = make_diff(original_content, content, fname)
        results.append(EditResult(
            file=matched_path,
            original=original_content,
            updated=content,
            diff=diff,
            success=True,
        ))

    return results


def _apply_udiff(response: str, files: dict[str, str]) -> list[EditResult]:
    from vendor.udiff import do_replace

    results = []

    # extract udiff blocks dari response
    import re
    pattern = r"```(?:diff|udiff)?\n(.*?)```"
    matches = re.findall(pattern, response, re.DOTALL)

    if not matches:
        # Fallback: coba parse raw diff tanpa fence (model kadang skip backticks)
        import re as _re
        if _re.search(r"^---\s|^\+\+\+\s|^@@", response, _re.MULTILINE):
            matches = [response]
        else:
            return [EditResult(file="", original="", updated="", diff="",
                               success=False, error="No diff block found in response")]

    for diff_text in matches:
        # extract filename dari diff header
        fname = _extract_udiff_filename(diff_text)
        if not fname:
            continue

        matched_path = _match_file(fname, files)
        if not matched_path:
            results.append(EditResult(
                file=fname, original="", updated="", diff="",
                success=False, error=f"File not in context: {fname}"
            ))
            continue

        original = files[matched_path]
        try:
            updated = do_replace(original, diff_text)
            if updated is None:
                raise ValueError("patch failed")
            diff = make_diff(original, updated, fname)
            results.append(EditResult(
                file=matched_path, original=original,
                updated=updated, diff=diff, success=True,
            ))
        except Exception as e:
            results.append(EditResult(
                file=matched_path, original=original, updated=original,
                diff="", success=False, error=str(e)
            ))

    return results


def _apply_whole(response: str, files: dict[str, str]) -> list[EditResult]:
    """Whole file rewrite — pakai parse_whole_edits() dari vendor/wholefile.py."""
    from vendor.wholefile import parse_whole_edits
    import re

    chat_files = list(files.keys())
    results = []

    try:
        edits = parse_whole_edits(response, chat_files)
    except ValueError as e:
        return [EditResult(file="", original="", updated="", diff="",
                           success=False, error=str(e))]

    if not edits:
        code_match = re.search(r"```[^\n]*\n(.*?)```", response, re.DOTALL)
        if code_match and len(files) == 1:
            fname = chat_files[0]
            original = files[fname]
            updated = code_match.group(1)
            diff = make_diff(original, updated, fname)
            return [EditResult(file=fname, original=original, updated=updated, diff=diff, success=True)]
        return [EditResult(file="", original="", updated="", diff="",
                           success=False, error="Could not parse whole file response")]

    for fname, updated in edits:
        matched_path = _match_file(fname, files)
        if not matched_path:
            results.append(EditResult(
                file=fname, original="", updated="", diff="",
                success=False, error=f"File not in context: {fname}"
            ))
            continue
        original = files[matched_path]
        diff = make_diff(original, updated, fname)
        results.append(EditResult(
            file=matched_path, original=original,
            updated=updated, diff=diff, success=True,
        ))

    return results

# --- Helpers ---

def _match_file(fname: str, files: dict[str, str]) -> str | None:
    """
    Match filename dari AI response ke path di context.
    Fuzzy: coba exact, lalu suffix match.
    """
    # exact match
    if fname in files:
        return fname

    # suffix match (AI kadang output nama file tanpa full path)
    for path in files:
        if path.endswith(fname) or path.endswith("/" + fname):
            return path

    # basename match
    from pathlib import Path as P
    target = P(fname).name
    for path in files:
        if P(path).name == target:
            return path

    return None


def _extract_udiff_filename(diff_text: str) -> str | None:
    """Extract filename dari udiff header (--- a/file atau +++ b/file)."""
    for line in diff_text.split("\n"):
        if line.startswith("--- ") or line.startswith("+++ "):
            fname = line[4:].strip()
            # strip a/ b/ prefix
            if fname.startswith("a/") or fname.startswith("b/"):
                fname = fname[2:]
            if fname and fname != "/dev/null":
                return fname
    return None


