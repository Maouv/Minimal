# vendored from aider/coders/wholefile_coder.py | commit: f09d70659ae90a0d068c80c288cbb55f2d3c3755
# stripped: WholeFileCoder class sepenuhnya (terlalu coupled ke base_coder/io)
# replaced: parse_whole_edits() — fungsi standalone yang kita butuhkan

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
                # tutup block
                edits.append((fname, "".join(new_lines)))
                fname = None
                new_lines = []
            else:
                # buka block — ambil filename dari baris sebelumnya
                if i > 0:
                    candidate = lines[i - 1].strip()
                    candidate = candidate.strip("*").rstrip(":").strip("`").lstrip("#").strip()
                    if len(candidate) <= 250 and candidate:
                        # normalize path
                        if candidate not in chat_files and Path(candidate).name in chat_files:
                            candidate = Path(candidate).name
                        fname = candidate
                if not fname:
                    if len(chat_files) == 1:
                        fname = chat_files[0]
                    else:
                        raise ValueError(f"No filename before ``` block in response")
        elif fname is not None:
            new_lines.append(line)

    if fname and new_lines:
        edits.append((fname, "".join(new_lines)))

    return edits
