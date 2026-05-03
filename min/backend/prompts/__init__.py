# prompts/__init__.py — public API, signature identik dengan prompts.py lama
# Semua delegasi ke loader.load_prompt() dengan kwargs yang tepat.

from commands import EditMode
from prompts.loader import load_prompt


def init_system() -> str:
    return load_prompt("init")


def ask_system_prompt(files: dict[str, str]) -> str:
    file_list = "\n".join(f"  - {p}" for p in files) if files else "  (none)"
    return load_prompt("ask", file_list=file_list)


def edit_system_prompt(mode: EditMode, editable_files: dict[str, str]) -> str:
    file_paths = list(editable_files.keys())

    # Build file_section: path + content per file (sama persis dengan prompts.py lama)
    if editable_files:
        file_blocks = []
        for path, content in editable_files.items():
            ext = path.rsplit(".", 1)[-1] if "." in path else ""
            fence_lang = ext if ext else ""
            file_blocks.append(f"{path}\n```{fence_lang}\n{content}\n```")
        file_section = "\n\n".join(file_blocks)
    else:
        file_section = "(no editable files)"

    example_file = file_paths[0] if file_paths else "path/to/file.py"

    if mode == "block":
        return load_prompt("edit_block", file_section=file_section, example_file=example_file)
    elif mode == "udiff":
        return load_prompt("edit_udiff", file_section=file_section, example_file=example_file)
    elif mode == "whole":
        ext = example_file.rsplit(".", 1)[-1] if "." in example_file else "python"
        return load_prompt("edit_whole", file_section=file_section, example_file=example_file, ext=ext)

    # Fallback: base only (mode tidak dikenal)
    return load_prompt("edit_base", file_section=file_section)
