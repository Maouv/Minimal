# prompts/loader.py — Jinja2-based prompt loader
# load_prompt(name, **kwargs) -> str
# Reads {name}.md from the same directory, renders via Jinja2 StrictUndefined.

from pathlib import Path

import jinja2

_PROMPTS_DIR = Path(__file__).parent

_env = jinja2.Environment(
    loader=jinja2.FileSystemLoader(str(_PROMPTS_DIR)),
    undefined=jinja2.StrictUndefined,
    keep_trailing_newline=True,
)


def load_prompt(name: str, **kwargs) -> str:
    """
    Load and render {name}.md from the prompts/ directory.

    Raises FileNotFoundError if the .md file does not exist.
    Raises jinja2.UndefinedError if a required template variable is missing.
    """
    filename = f"{name}.md"
    prompt_path = _PROMPTS_DIR / filename
    if not prompt_path.exists():
        raise FileNotFoundError(
            f"Prompt file not found: '{filename}' (looked in {_PROMPTS_DIR})"
        )
    template = _env.get_template(filename)
    return template.render(**kwargs)
