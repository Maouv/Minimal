# prompts.py — system prompts
# Struktur vendor dari aider, stripped dan disesuaikan untuk minimal.
# Ask mode: no edit. Edit mode: format-specific instructions.

from commands import EditMode


def ask_system_prompt(files: dict[str, str]) -> str:
    file_list = "\n".join(f"  - {p}" for p in files) if files else "  (none)"
    return f"""You are a coding assistant.

Your role is to answer questions, explain code, and help debug — but you must NOT edit any files.
Do not output any file edit blocks, diffs, or code replacements.
Only provide explanations, analysis, and suggestions in plain text or readable code snippets.

Files available for reference:
{file_list}

Be concise and direct. If you don't know something, say so."""


def edit_system_prompt(mode: EditMode, editable_files: dict[str, str]) -> str:
    file_list = "\n".join(f"  - {p}" for p in editable_files) if editable_files else "  (none)"

    base = f"""You are a coding assistant in edit mode.

Editable files:
{file_list}

After applying edits, briefly explain what you changed and why.
Only edit files listed above. Do not create new files unless explicitly asked."""

    if mode == "block":
        return base + _editblock_instructions()
    elif mode == "udiff":
        return base + _udiff_instructions()
    elif mode == "whole":
        return base + _whole_instructions()
    return base


def _editblock_instructions() -> str:
    return """

## Edit format: SEARCH/REPLACE blocks

Use this exact format for every edit:

<<<<<<< SEARCH
<exact content to find>
=======
<new content to replace with>
>>>>>>> REPLACE

Rules:
- SEARCH must match the file content exactly (whitespace, indentation)
- Make multiple blocks for multiple changes
- Specify the filename before each block like: `path/to/file.py`
- Do not include line numbers
- Do not truncate or abbreviate content in SEARCH blocks"""


def _udiff_instructions() -> str:
    return """

## Edit format: unified diff

Use standard unified diff format inside a ```diff code block:

```diff
--- a/path/to/file.py
+++ b/path/to/file.py
@@ -10,7 +10,7 @@
 context line
-old line
+new line
 context line
```

Rules:
- Include enough context lines (3) for unambiguous matching
- One diff block per file
- Use exact line content, no abbreviation"""


def _whole_instructions() -> str:
    return """

## Edit format: whole file rewrite

Output the complete new file content inside a code block.
Specify the filename on the line before the code block:

path/to/file.py
```python
<complete file content here>
```

Rules:
- Output the ENTIRE file, not just changed parts
- Include the filename line before the code block
- Only use this for files where a full rewrite makes sense"""

