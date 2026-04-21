# vendored from aider/coders/editblock_coder.py
# commit: f09d70659ae90a0d068c80c288cbb55f2d3c3755
# stripped: EditBlockCoder class, aider imports, base_coder dependency
# kept: all standalone parse/apply functions

import difflib
import math
import re
from difflib import SequenceMatcher
from pathlib import Path

DEFAULT_FENCE = ("`" * 3, "`" * 3)


def prep(content):
    if content and not content.endswith("\n"):
        content += "\n"
    lines = content.splitlines(keepends=True)
    return content, lines


def perfect_or_whitespace(whole_lines, part_lines, replace_lines):
    res = perfect_replace(whole_lines, part_lines, replace_lines)
    if res:
        return res
    res = replace_part_with_missing_leading_whitespace(whole_lines, part_lines, replace_lines)
    if res:
        return res


def perfect_replace(whole_lines, part_lines, replace_lines):
    part_tup = tuple(part_lines)
    part_len = len(part_lines)
    for i in range(len(whole_lines) - part_len + 1):
        whole_tup = tuple(whole_lines[i : i + part_len])
        if whole_tup == part_tup:
            res = whole_lines[:i] + replace_lines + whole_lines[i + part_len :]
            return "".join(res)


def replace_most_similar_chunk(whole, part, replace):
    whole, whole_lines = prep(whole)
    part, part_lines = prep(part)
    replace, replace_lines = prep(replace)
    res = perfect_or_whitespace(whole_lines, part_lines, replace_lines)
    if res:
        return res
    res = try_dotdotdots(whole, part, replace)
    if res:
        return res
    res = replace_closest_edit_distance(whole_lines, part, part_lines, replace_lines)
    if res:
        return res


def try_dotdotdots(whole, part, replace):
    dots_re = re.compile(r"(^\s*\.\.\.\n)", re.MULTILINE | re.DOTALL)
    part_pieces = re.split(dots_re, part)
    replace_pieces = re.split(dots_re, replace)
    if len(part_pieces) != len(replace_pieces):
        return
    if len(part_pieces) == 1:
        return
    for i in range(0, len(part_pieces), 2):
        if part_pieces[i] != replace_pieces[i]:
            if part_pieces[i].strip() != replace_pieces[i].strip():
                return
    part_pieces = [part_pieces[0]]
    replace_pieces = [replace_pieces[0]]
    for i in range(1, len(part_pieces), 2):
        dots = part_pieces[i]
        section = part_pieces[i + 1]
        replace_sec = replace_pieces[i + 1]
        if not section.strip():
            part_pieces.append(dots)
            part_pieces.append(section)
            replace_pieces.append(dots)
            replace_pieces.append(replace_sec)
            continue
        if section not in whole:
            return
        start = part_pieces[-1]
        end = section
        start_index = whole.find(start)
        end_index = whole.find(end)
        if start_index < 0 or end_index < 0:
            return
        if start_index > end_index:
            return
        part_pieces.append(whole[start_index + len(start) : end_index])
        part_pieces.append(end)
        replace_pieces.append(whole[start_index + len(start) : end_index])
        replace_pieces.append(replace_sec)
    part = "".join(part_pieces)
    replace = "".join(replace_pieces)
    if part in whole:
        return whole.replace(part, replace, 1)


def replace_part_with_missing_leading_whitespace(whole_lines, part_lines, replace_lines):
    leading = [len(p) - len(p.lstrip()) for p in part_lines if p.strip()]
    if leading and min(leading) > 0:
        leading = min(leading)
        part_lines = [p[leading:] if len(p) >= leading else p for p in part_lines]
        replace_lines = [p[leading:] if len(p) >= leading else p for p in replace_lines]
    res = match_but_for_leading_whitespace(whole_lines, part_lines)
    if not res:
        return
    leading = res
    replace_lines = [leading + rline if rline.strip() else rline for rline in replace_lines]
    part_lines = [leading + pline for pline in part_lines]
    return perfect_replace(whole_lines, part_lines, replace_lines)


def match_but_for_leading_whitespace(whole_lines, part_lines):
    num = len(part_lines)
    for i in range(len(whole_lines) - num + 1):
        add = set()
        for j in range(num):
            whole_line = whole_lines[i + j]
            part_line = part_lines[j]
            if whole_line == part_line:
                add.add("")
                continue
            if not whole_line.endswith(part_line):
                break
            add.add(whole_line[: len(whole_line) - len(part_line)])
        else:
            if len(add) == 1:
                return add.pop()


def replace_closest_edit_distance(whole_lines, part, part_lines, replace_lines):
    similarity_thresh = 0.8
    max_similarity = 0
    most_similar_chunk_start = -1
    most_similar_chunk_end = -1
    part_length = len(part_lines)
    scale = 0.1
    min_len = math.floor(part_length * (1 - scale))
    max_len = math.ceil(part_length * (1 + scale))
    for length in range(min_len, max_len):
        for i in range(len(whole_lines) - length + 1):
            chunk = "".join(whole_lines[i : i + length])
            similarity = SequenceMatcher(None, chunk, part).ratio()
            if similarity > max_similarity:
                max_similarity = similarity
                most_similar_chunk_start = i
                most_similar_chunk_end = i + length
    if max_similarity < similarity_thresh:
        return
    replace = "".join(replace_lines)
    return (
        "".join(whole_lines[:most_similar_chunk_start])
        + replace
        + "".join(whole_lines[most_similar_chunk_end:])
    )


def strip_quoted_wrapping(res, fname=None, fence=DEFAULT_FENCE):
    if not res:
        return res
    res = res.splitlines(keepends=True)
    if fname and res[0].strip().endswith(Path(fname).name):
        res = res[1:]
    if res[0].startswith(fence[0]) and res[-1].startswith(fence[1]):
        res = res[1:-1]
    res = "".join(res)
    if res and not res.endswith("\n"):
        res += "\n"
    return res


def do_replace(fname, content, before_text, after_text, fence=None):
    before_text = strip_quoted_wrapping(before_text, fname, fence)
    after_text = strip_quoted_wrapping(after_text, fname, fence)
    if not before_text.strip():
        if not Path(fname).exists():
            return after_text
    return replace_most_similar_chunk(content, before_text, after_text)


def strip_filename(filename, fence):
    filename = filename.strip()
    if filename == "...":
        return
    if filename.startswith(fence[0]):
        return
    filename = filename.rstrip(":")
    filename = filename.lstrip("#")
    filename = filename.strip()
    filename = filename.strip("`")
    filename = filename.strip("*")
    filename = filename.replace("\\_", "_")
    return filename


def find_original_update_blocks(content, fence=DEFAULT_FENCE, valid_fnames=None):
    if not content.endswith("\n"):
        content = content + "\n"
    pieces = re.split(r"^(<<<<<<< SEARCH\n)", content, flags=re.MULTILINE)
    if len(pieces) == 1:
        return
    for i, piece in enumerate(pieces):
        if piece != "<<<<<<< SEARCH\n":
            if i > 0:
                prior = pieces[i - 1]
                fname = find_filename(prior.splitlines(keepends=True), fence, valid_fnames)
                yield fname, None, None
            continue
        rest = pieces[i + 1] if i + 1 < len(pieces) else ""
        split_rest = re.split(r"^(=======\n)", rest, maxsplit=1, flags=re.MULTILINE)
        if len(split_rest) < 3:
            raise ValueError("Missing ======= divider")
        original, _, remainder = split_rest
        split_remainder = re.split(
            r"^(>>>>>>> REPLACE\n)", remainder, maxsplit=1, flags=re.MULTILINE
        )
        if len(split_remainder) < 3:
            raise ValueError("Missing >>>>>>> REPLACE marker")
        updated, _, _ = split_remainder
        prior = pieces[i - 1] if i > 0 else ""
        fname = find_filename(prior.splitlines(keepends=True), fence, valid_fnames)
        yield fname, original, updated


def find_filename(lines, fence, valid_fnames):
    lines = lines[::-1]
    for line in lines:
        if line.startswith(fence[0]):
            continue
        fname = strip_filename(line, fence)
        if not fname:
            continue
        if valid_fnames and fname in valid_fnames:
            return fname
        if not valid_fnames:
            return fname
    return None


def find_similar_lines(search_lines, content_lines, threshold=0.6):
    if isinstance(search_lines, str):
        search_lines = search_lines.splitlines()
    if isinstance(content_lines, str):
        content_lines = content_lines.splitlines()
    best_ratio = 0
    best_match = None
    search_len = len(search_lines)
    for i in range(len(content_lines) - search_len + 1):
        chunk = content_lines[i : i + search_len]
        ratio = SequenceMatcher(None, search_lines, chunk).ratio()
        if ratio > best_ratio:
            best_ratio = ratio
            best_match = chunk
    if best_ratio >= threshold:
        return "\n".join(best_match)
    return None
