import difflib
from itertools import groupby
from pathlib import Path
from .search_replace import flexible_search_and_replace, udiff_strategies

def do_replace(content, diff_text):
    """Fungsi jembatan untuk coder.py"""
    edits = find_diffs(diff_text)
    if not edits:
        return None
    
    new_content = content
    for fname, hunk in edits:
        # Kita gunakan content yang sudah terupdate jika ada banyak hunk
        result = apply_hunk(new_content, hunk)
        if result:
            new_content = result
        else:
            return None # Fail fast jika satu hunk gagal
    return new_content

def hunk_to_before_after(hunk, lines=False):
    before = []
    after = []
    for line in hunk:
        if not line: continue
        op = line[0]
        rest = line[1:]
        if op == " ":
            before.append(rest)
            after.append(rest)
        elif op == "-":
            before.append(rest)
        elif op == "+":
            after.append(rest)
    
    if lines: return before, after
    return "".join(before), "".join(after)

def directly_apply_hunk(content, hunk):
    before, after = hunk_to_before_after(hunk)
    if not before: return None
    # Pastikan flexible_search_and_replace ada di search_replace.py
    return flexible_search_and_replace(content, before, after)

def apply_hunk(content, hunk):
    # Logika minimalis apply hunk
    before, after = hunk_to_before_after(hunk)
    if before in content:
        return content.replace(before, after, 1)
    
    # Jika gagal exact, panggil helper logic (seperti original aider)
    return directly_apply_hunk(content, hunk)

def find_diffs(content):
    if not content.endswith("\n"):
        content += "\n"
    
    lines = content.splitlines(keepends=True)
    edits = []
    hunk = []
    fname = None
    
    for line in lines:
        if line.startswith("--- ") or line.startswith("+++ "):
            continue
        if line.startswith("@@"):
            if hunk:
                edits.append((fname, hunk))
                hunk = []
            continue
        if line[0] in " +-":
            hunk.append(line)
            
    if hunk:
        edits.append((fname, hunk))
    return edits

