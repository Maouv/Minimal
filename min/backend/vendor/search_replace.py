# vendored from aider/coders/search_replace.py | commit: f09d70659ae90a0d068c80c288cbb55f2d3c3755
# stripped: aider imports, tqdm, git_cherry_pick funcs, proc/main

# vendored from aider/coders/search_replace.py | commit: f09d70659ae90a0d068c80c288cbb55f2d3c3755
# stripped: aider.dump, aider.utils, tqdm, git_cherry_pick funcs, proc/main

#!/usr/bin/env python

from pathlib import Path

try:
    import git
except ImportError:
    git = None

from diff_match_patch import diff_match_patch



class RelativeIndenter:
    """Rewrites text files to have relative indentation, which involves
    reformatting the leading white space on lines.  This format makes
    it easier to search and apply edits to pairs of code blocks which
    may differ significantly in their overall level of indentation.

    It removes leading white space which is shared with the preceding
    line.

    Original:
    ```
            Foo # indented 8
                Bar # indented 4 more than the previous line
                Baz # same indent as the previous line
                Fob # same indent as the previous line
    ```

    Becomes:
    ```
            Foo # indented 8
        Bar # indented 4 more than the previous line
    Baz # same indent as the previous line
    Fob # same indent as the previous line
    ```

    If the current line is *less* indented then the previous line,
    uses a unicode character to indicate outdenting.

    Original
    ```
            Foo
                Bar
                Baz
            Fob # indented 4 less than the previous line
    ```

    Becomes:
    ```
            Foo
        Bar
    Baz
    ←←←←Fob # indented 4 less than the previous line
    ```

    This is a similar original to the last one, but every line has
    been uniformly outdented:
    ```
    Foo
        Bar
        Baz
    Fob # indented 4 less than the previous line
    ```

    It becomes this result, which is very similar to the previous
    result.  Only the white space on the first line differs.  From the
    word Foo onwards, it is identical to the previous result.
    ```
    Foo
        Bar
    Baz
    ←←←←Fob # indented 4 less than the previous line
    ```

    """

    def __init__(self, texts):
        """
        Based on the texts, choose a unicode character that isn't in any of them.
        """

        chars = set()
        for text in texts:
            chars.update(text)

        ARROW = "←"
        if ARROW not in chars:
            self.marker = ARROW
        else:
            self.marker = self.select_unique_marker(chars)

    def select_unique_marker(self, chars):
        for codepoint in range(0x10FFFF, 0x10000, -1):
            marker = chr(codepoint)
            if marker not in chars:
                return marker

        raise ValueError("Could not find a unique marker")

    def make_relative(self, text):
        """
        Transform text to use relative indents.
        """

        if self.marker in text:
            raise ValueError(f"Text already contains the outdent marker: {self.marker}")

        lines = text.splitlines(keepends=True)

        output = []
        prev_indent = ""
        for line in lines:
            line_without_end = line.rstrip("\n\r")

            len_indent = len(line_without_end) - len(line_without_end.lstrip())
            indent = line[:len_indent]
            change = len_indent - len(prev_indent)
            if change > 0:
                cur_indent = indent[-change:]
            elif change < 0:
                cur_indent = self.marker * -change
            else:
                cur_indent = ""

            out_line = cur_indent + "\n" + line[len_indent:]
            # dump(len_indent, change, out_line)
            # print(out_line)
            output.append(out_line)
            prev_indent = indent

        res = "".join(output)
        return res

    def make_absolute(self, text):
        """
        Transform text from relative back to absolute indents.
        """
        lines = text.splitlines(keepends=True)

        output = []
        prev_indent = ""
        for i in range(0, len(lines), 2):
            dent = lines[i].rstrip("\r\n")
            non_indent = lines[i + 1]

            if dent.startswith(self.marker):
                len_outdent = len(dent)
                cur_indent = prev_indent[:-len_outdent]
            else:
                cur_indent = prev_indent + dent

            if not non_indent.rstrip("\r\n"):
                out_line = non_indent  # don't indent a blank line
            else:
                out_line = cur_indent + non_indent

            output.append(out_line)
            prev_indent = cur_indent

        res = "".join(output)
        if self.marker in res:
            # dump(res)
            raise ValueError("Error transforming text back to absolute indents")

        return res


# The patches are created to change S->R.
# So all the patch offsets are relative to S.
# But O has a lot more content. So all the offsets are very wrong.
#
# But patch_apply() seems to imply that once patch N is located,
# then it adjusts the offset of the next patch.
#
# This is great, because once we sync up after a big gap the nearby
# patches are close to being located right.
# Except when indentation has been changed by GPT.
#
# It would help to use the diff trick to build map_S_offset_to_O_offset().
# Then update all the S offsets in the S->R patches to be O offsets.
# Do we also need to update the R offsets?
#
# What if this gets funky/wrong?
#


def map_patches(texts, patches, debug):
    search_text, replace_text, original_text = texts

    dmp = diff_match_patch()
    dmp.Diff_Timeout = 5

    diff_s_o = dmp.diff_main(search_text, original_text)
    # diff_r_s = dmp.diff_main(replace_text, search_text)

    # dmp.diff_cleanupSemantic(diff_s_o)
    # dmp.diff_cleanupEfficiency(diff_s_o)

    if debug:
        html = dmp.diff_prettyHtml(diff_s_o)
        Path("tmp.html").write_text(html)

    for patch in patches:
        start1 = patch.start1
        start2 = patch.start2

        patch.start1 = dmp.diff_xIndex(diff_s_o, start1)
        patch.start2 = dmp.diff_xIndex(diff_s_o, start2)

        if debug:
            print()
            print(start1, repr(search_text[start1 : start1 + 50]))
            print(patch.start1, repr(original_text[patch.start1 : patch.start1 + 50]))
            print(patch.diffs)
            print()

    return patches


example = """Left
Left
    4 in
    4 in
        8 in
    4 in
Left
"""


def relative_indent(texts):
    ri = RelativeIndenter(texts)
    texts = list(map(ri.make_relative, texts))

    return ri, texts


line_padding = 100


def line_pad(text):
    padding = "\n" * line_padding
    return padding + text + padding


def line_unpad(text):
    if set(text[:line_padding] + text[-line_padding:]) != set("\n"):
        return
    return text[line_padding:-line_padding]


def dmp_apply(texts, remap=True):
    debug = False
    # debug = True

    search_text, replace_text, original_text = texts

    dmp = diff_match_patch()
    dmp.Diff_Timeout = 5
    # dmp.Diff_EditCost = 16

    if remap:
        dmp.Match_Threshold = 0.95
        dmp.Match_Distance = 500
        dmp.Match_MaxBits = 128
        dmp.Patch_Margin = 32
    else:
        dmp.Match_Threshold = 0.5
        dmp.Match_Distance = 100_000
        dmp.Match_MaxBits = 32
        dmp.Patch_Margin = 8

    diff = dmp.diff_main(search_text, replace_text, None)
    dmp.diff_cleanupSemantic(diff)
    dmp.diff_cleanupEfficiency(diff)

    patches = dmp.patch_make(search_text, diff)

    if debug:
        html = dmp.diff_prettyHtml(diff)
        Path("tmp.search_replace_diff.html").write_text(html)

        for d in diff:
            print(d[0], repr(d[1]))

        for patch in patches:
            start1 = patch.start1
            print()
            print(start1, repr(search_text[start1 : start1 + 10]))
            print(start1, repr(replace_text[start1 : start1 + 10]))
            print(patch.diffs)

        # dump(original_text)
        # dump(search_text)

    if remap:
        patches = map_patches(texts, patches, debug)

    patches_text = dmp.patch_toText(patches)

    new_text, success = dmp.patch_apply(patches, original_text)

    all_success = False not in success

    if debug:
        # dump(new_text)
        print(patches_text)

        # print(new_text)

        # print(new_text)

    if not all_success:
        return

    return new_text


def lines_to_chars(lines, mapping):
    new_text = []
    for char in lines:
        new_text.append(mapping[ord(char)])

    new_text = "".join(new_text)
    return new_text


def dmp_lines_apply(texts):
    debug = False
    # debug = True

    for t in texts:
        assert t.endswith("\n"), t

    search_text, replace_text, original_text = texts

    dmp = diff_match_patch()
    dmp.Diff_Timeout = 5
    # dmp.Diff_EditCost = 16

    dmp.Match_Threshold = 0.1
    dmp.Match_Distance = 100_000
    dmp.Match_MaxBits = 32
    dmp.Patch_Margin = 1

    all_text = search_text + replace_text + original_text
    all_lines, _, mapping = dmp.diff_linesToChars(all_text, "")
    assert len(all_lines) == len(all_text.splitlines())

    search_num = len(search_text.splitlines())
    replace_num = len(replace_text.splitlines())
    original_num = len(original_text.splitlines())

    search_lines = all_lines[:search_num]
    replace_lines = all_lines[search_num : search_num + replace_num]
    original_lines = all_lines[search_num + replace_num :]

    assert len(search_lines) == search_num
    assert len(replace_lines) == replace_num
    assert len(original_lines) == original_num

    diff_lines = dmp.diff_main(search_lines, replace_lines, None)
    dmp.diff_cleanupSemantic(diff_lines)
    dmp.diff_cleanupEfficiency(diff_lines)

    patches = dmp.patch_make(search_lines, diff_lines)

    if debug:
        diff = list(diff_lines)
        dmp.diff_charsToLines(diff, mapping)
        # dump(diff)
        html = dmp.diff_prettyHtml(diff)
        Path("tmp.search_replace_diff.html").write_text(html)

        for d in diff:
            print(d[0], repr(d[1]))

    new_lines, success = dmp.patch_apply(patches, original_lines)
    new_text = lines_to_chars(new_lines, mapping)

    all_success = False not in success

    if debug:
        pass
    if not all_success:
        return

    return new_text


def diff_lines(search_text, replace_text):
    dmp = diff_match_patch()
    dmp.Diff_Timeout = 5
    # dmp.Diff_EditCost = 16
    search_lines, replace_lines, mapping = dmp.diff_linesToChars(search_text, replace_text)

    diff_lines = dmp.diff_main(search_lines, replace_lines, None)
    dmp.diff_cleanupSemantic(diff_lines)
    dmp.diff_cleanupEfficiency(diff_lines)

    diff = list(diff_lines)
    dmp.diff_charsToLines(diff, mapping)
    # dump(diff)

    udiff = []
    for d, lines in diff:
        if d < 0:
            d = "-"
        elif d > 0:
            d = "+"
        else:
            d = " "
        for line in lines.splitlines(keepends=True):
            udiff.append(d + line)

    return udiff


def search_and_replace(texts):
    search_text, replace_text, original_text = texts

    num = original_text.count(search_text)
    # if num > 1:
    #    raise SearchTextNotUnique()
    if num == 0:
        return

    new_text = original_text.replace(search_text, replace_text)

    return new_text


def flexible_search_and_replace(texts, strategies):
    """Try a series of search/replace methods, starting from the most
    literal interpretation of search_text. If needed, progress to more
    flexible methods, which can accommodate divergence between
    search_text and original_text and yet still achieve the desired
    edits.
    """

    for strategy, preprocs in strategies:
        for preproc in preprocs:
            res = try_strategy(texts, strategy, preproc)
            if res:
                return res


def reverse_lines(text):
    lines = text.splitlines(keepends=True)
    lines.reverse()
    return "".join(lines)


def try_strategy(texts, strategy, preproc):
    preproc_strip_blank_lines, preproc_relative_indent, preproc_reverse = preproc
    ri = None

    if preproc_strip_blank_lines:
        texts = strip_blank_lines(texts)
    if preproc_relative_indent:
        ri, texts = relative_indent(texts)
    if preproc_reverse:
        texts = list(map(reverse_lines, texts))

    res = strategy(texts)

    if res and preproc_reverse:
        res = reverse_lines(res)

    if res and preproc_relative_indent:
        try:
            res = ri.make_absolute(res)
        except ValueError:
            return

    return res


def strip_blank_lines(texts):
    # strip leading and trailing blank lines
    texts = [text.strip("\n") + "\n" for text in texts]
    return texts


def read_text(fname):
    text = Path(fname).read_text()
    return text



all_preprocs = [
    (False, False, False),
    (True, False, False),
    (False, True, False),
    (True, True, False),
]


# strategy lists — git_cherry_pick removed (not vendored)
editblock_strategies = [
    (search_and_replace, all_preprocs),
    (dmp_lines_apply, all_preprocs),
]

udiff_strategies = [
    (search_and_replace, all_preprocs),
    (dmp_lines_apply, all_preprocs),
]

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


# ── find_original_update_blocks ──────────────────────────────────────────────
# Parse LLM response untuk SEARCH/REPLACE blocks format aider edit-block.
# Format:
#   path/to/file.py
#   <<<<<<< SEARCH
#   <original code>
#   =======
#   <replacement code>
#   >>>>>>> REPLACE

def find_original_update_blocks(content: str):
    """
    Parse content dan yield (filename, original, updated) tuples.
    Raises ValueError jika format tidak valid.
    """
    lines = content.splitlines(keepends=True)
    i = 0
    current_file = None

    while i < len(lines):
        line = lines[i]

        # Detect filename — baris sebelum <<<<<<< SEARCH
        # Bisa dalam code fence (```python) atau plain
        stripped = line.strip()

        # Cek apakah ini fence ``` — skip fence markers tapi ambil language/filename
        if stripped.startswith("```"):
            inner = stripped[3:].strip()
            # Kalau ada nama file setelah ```, set sebagai current_file
            if inner and not inner.lower() in ("python", "js", "ts", "tsx", "go", "rust", "c", "cpp", "java", ""):
                current_file = inner
            i += 1
            continue

        # Detect SEARCH marker
        if stripped == "<<<<<<< SEARCH" or stripped == "<<<<<<<SEARCH":
            if current_file is None:
                # Coba ambil filename dari baris sebelumnya
                for back in range(i - 1, max(i - 5, -1), -1):
                    candidate = lines[back].strip()
                    if candidate and not candidate.startswith("#") and not candidate.startswith("```"):
                        current_file = candidate
                        break

            if current_file is None:
                raise ValueError(f"No filename found before SEARCH block at line {i+1}")

            # Collect SEARCH block
            i += 1
            search_lines = []
            while i < len(lines):
                l = lines[i]
                if l.strip() in ("=======", "=======\n"):
                    break
                search_lines.append(l)
                i += 1
            else:
                raise ValueError("No ======= found after SEARCH block")

            i += 1  # skip =======

            # Collect REPLACE block
            replace_lines = []
            while i < len(lines):
                l = lines[i]
                if l.strip().startswith(">>>>>>> REPLACE") or l.strip().startswith(">>>>>>>REPLACE"):
                    break
                replace_lines.append(l)
                i += 1
            else:
                raise ValueError("No >>>>>>> REPLACE found")

            i += 1  # skip >>>>>>>

            yield (
                current_file,
                "".join(search_lines),
                "".join(replace_lines),
            )
            continue

        # Baris yang bisa jadi filename: tidak kosong, tidak comment, tidak code
        if stripped and not stripped.startswith("#") and not stripped.startswith("//"):
            # Hanya set jika terlihat seperti path (ada . atau /)
            if "." in stripped or "/" in stripped:
                current_file = stripped

        i += 1


# ── replace_most_similar_chunk ───────────────────────────────────────────────
# Cari search_text di content, replace dengan replace_text.
# Pakai flexible_search_and_replace dari aider untuk fuzzy match.

def replace_most_similar_chunk(content: str, search: str, replace: str) -> str | None:
    """
    Coba replace search dengan replace di content.
    Return new content kalau berhasil, None kalau tidak ketemu.
    """
    if not search.strip():
        # Empty search = append
        return content + replace

    # Exact match dulu
    if search in content:
        return content.replace(search, replace, 1)

    # Pakai flexible_search_and_replace (dari vendor)
    result = flexible_search_and_replace(
        [content, search, replace],
        strategies=editblock_strategies,
    )
    return result if result != content or replace == search else result if search not in content else None
