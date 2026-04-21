# vendored from aider/coders/udiff_coder.py | commit: f09d70659ae90a0d068c80c288cbb55f2d3c3755
# stripped: UnifiedDiffCoder class, base_coder, aider imports

import difflib
from itertools import groupby
from pathlib import Path

from .search_replace import flexible_search_and_replace, udiff_strategies


# vendored from aider/coders/udiff_coder.py | commit: f09d70659ae90a0d068c80c288cbb55f2d3c3755
# stripped: UnifiedDiffCoder class, base_coder, aider imports



    before_text, after_text = hunk_to_before_after(hunk)

    # does it want to make a new file?
    if not fname.exists() and not before_text.strip():
        fname.touch()
        content = ""

    if content is None:
        return

    # TODO: handle inserting into new file
    if not before_text.strip():
        # append to existing file, or start a new file
        new_content = content + after_text
        return new_content

    new_content = None

    new_content = apply_hunk(content, hunk)
    if new_content:
        return new_content


def collapse_repeats(s):
    return "".join(k for k, g in groupby(s))


def apply_hunk(content, hunk):
    before_text, after_text = hunk_to_before_after(hunk)

    res = directly_apply_hunk(content, hunk)
    if res:
        return res

    hunk = make_new_lines_explicit(content, hunk)

    # just consider space vs not-space
    ops = "".join([line[0] for line in hunk])\n    ops = ops.replace("-", "x")\n    ops = ops.replace("+", "x")\n    ops = ops.replace("\n", " ")\n\n    cur_op = " "
    section = []
    sections = []

    for i in range(len(ops)):
        op = ops[i]
        if op != cur_op:
            sections.append(section)
            section = []
            cur_op = op
        section.append(hunk[i])

    sections.append(section)
    if cur_op != " ":\n        sections.append([])\n\n    all_done = True\n    for i in range(2, len(sections), 2):\n        preceding_context = sections[i - 2]\n        changes = sections[i - 1]\n        following_context = sections[i]\n\n        res = apply_partial_hunk(content, preceding_context, changes, following_context)\n        if res:\n            content = res\n        else:\n            all_done = False\n            # FAILED!\n            # this_hunk = preceding_context + changes + following_context\n            break\n\n    if all_done:\n        return content\n\n\ndef flexi_just_search_and_replace(texts):\n    strategies = [\n        (search_and_replace, all_preprocs),\n    ]\n\n    return flexible_search_and_replace(texts, strategies)\n\n\ndef make_new_lines_explicit(content, hunk):\n    before, after = hunk_to_before_after(hunk)\n\n    diff = diff_lines(before, content)\n\n    back_diff = []\n    for line in diff:\n        if line[0] == "+":\n            continue\n        # if line[0] == "-":\n        #    line = "+" + line[1:]\n\n        back_diff.append(line)\n\n    new_before = directly_apply_hunk(before, back_diff)\n    if not new_before:\n        return hunk\n\n    if len(new_before.strip()) < 10:\n        return hunk\n\n    before = before.splitlines(keepends=True)\n    new_before = new_before.splitlines(keepends=True)\n    after = after.splitlines(keepends=True)\n\n    if len(new_before) < len(before) * 0.66:\n        return hunk\n\n    new_hunk = difflib.unified_diff(new_before, after, n=max(len(new_before), len(after)))\n    new_hunk = list(new_hunk)[3:]\n\n    return new_hunk\n\n\ndef cleanup_pure_whitespace_lines(lines):\n    res = [\n        line if line.strip() else line[-(len(line) - len(line.rstrip("\r\n")))] for line in lines\n    ]\n    return res\n\n\ndef normalize_hunk(hunk):\n    before, after = hunk_to_before_after(hunk, lines=True)\n\n    before = cleanup_pure_whitespace_lines(before)\n    after = cleanup_pure_whitespace_lines(after)\n\n    diff = difflib.unified_diff(before, after, n=max(len(before), len(after)))\n    diff = list(diff)[3:]\n    return diff\n\n\ndef directly_apply_hunk(content, hunk):\n    before, after = hunk_to_before_after(hunk)\n\n    if not before:\n        return\n\n    before_lines, _ = hunk_to_before_after(hunk, lines=True)\n    before_lines = "".join([line.strip() for line in before_lines])\n\n    # Refuse to do a repeated search and replace on a tiny bit of non-whitespace context\n    if len(before_lines) < 10 and content.count(before) > 1:\n        return\n\n    try:\n        new_content = flexi_just_search_and_replace([before, after, content])\n    except SearchTextNotUnique:\n        new_content = None\n\n    return new_content\n\n\ndef apply_partial_hunk(content, preceding_context, changes, following_context):\n    len_prec = len(preceding_context)\n    len_foll = len(following_context)\n\n    use_all = len_prec + len_foll\n\n    # if there is a - in the hunk, we can go all the way to `use=0`\n    for drop in range(use_all + 1):\n        use = use_all - drop\n\n        for use_prec in range(len_prec, -1, -1):\n            if use_prec > use:\n                continue\n\n            use_foll = use - use_prec\n            if use_foll > len_foll:\n                continue\n\n            if use_prec:\n                this_prec = preceding_context[-use_prec:]\n            else:\n                this_prec = []\n\n            this_foll = following_context[:use_foll]\n\n            res = directly_apply_hunk(content, this_prec + changes + this_foll)\n            if res:\n                return res\n\n\ndef find_diffs(content):\n    # We can always fence with triple-quotes, because all the udiff content\n    # is prefixed with +/-/space.\n\n    if not content.endswith("\n"):\n        content = content + "\n"

    lines = content.splitlines(keepends=True)
    line_num = 0
    edits = []
    while line_num < len(lines):
        while line_num < len(lines):
            line = lines[line_num]
            if line.startswith("```diff"):
                line_num, these_edits = process_fenced_block(lines, line_num + 1)
                edits += these_edits
                break
            line_num += 1

    # For now, just take 1!
    # edits = edits[:1]

    return edits


def process_fenced_block(lines, start_line_num):
    for line_num in range(start_line_num, len(lines)):
        line = lines[line_num]
        if line.startswith("```"):
            break

    block = lines[start_line_num:line_num]
    block.append("@@ @@")

    if block[0].startswith("--- ") and block[1].startswith("+++ "):
        # Extract the file path, considering that it might contain spaces
        a_fname = block[0][4:].strip()
        b_fname = block[1][4:].strip()

        # Check if standard git diff prefixes are present (or /dev/null) and strip them
        if (a_fname.startswith("a/") or a_fname == "/dev/null") and b_fname.startswith("b/"):\n            fname = b_fname[2:]\n        else:\n            # Otherwise, assume the path is as intended\n            fname = b_fname\n\n        block = block[2:]\n    else:\n        fname = None\n\n    edits = []\n\n    keeper = False\n    hunk = []\n    op = " "
    for line in block:
        hunk.append(line)
        if len(line) < 2:
            continue

        if line.startswith("+++ ") and hunk[-2].startswith("--- "):
            if hunk[-3] == "\n":\n                hunk = hunk[:-3]\n            else:\n                hunk = hunk[:-2]\n\n            edits.append((fname, hunk))\n            hunk = []\n            keeper = False\n\n            fname = line[4:].strip()\n            continue\n\n        op = line[0]\n        if op in "-+":\n            keeper = True\n            continue\n        if op != "@":\n            continue\n        if not keeper:\n            hunk = []\n            continue\n\n        hunk = hunk[:-1]\n        edits.append((fname, hunk))\n        hunk = []\n        keeper = False\n\n    return line_num + 1, edits\n\n\ndef hunk_to_before_after(hunk, lines=False):\n    before = []\n    after = []\n    op = " "
    for line in hunk:
        if len(line) < 2:
            op = " "
            line = line
        else:
            op = line[0]
            line = line[1:]

        if op == " ":\n            before.append(line)\n            after.append(line)\n        elif op == "-":\n            before.append(line)\n        elif op == "+":\n            after.append(line)\n\n    if lines:\n        return before, after\n\n    before = "".join(before)\n    after = "".join(after)\n\n    return before, after
