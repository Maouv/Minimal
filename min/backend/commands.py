# commands.py — slash command parser + handler
# Parse input user, return Command object yang bisa di-dispatch

from dataclasses import dataclass
from typing import Literal


EditMode = Literal["block", "udiff", "whole"]

EDIT_COMMANDS = {
    "/edit-block": "block",
    "/edit-udiff": "udiff",
    "/edit-whole": "whole",
}

SLASH_COMMANDS = [
    "/add", "/add -r", "/drop",
    "/edit-block", "/edit-udiff", "/edit-whole",
    "/ask",
    "/clear", "/reset",
    "/undo", "/diff", "/commit",
    "/run", "/tokens", "/model",
    "/help",
]


@dataclass
class Command:
    kind: Literal[
        "add", "drop",
        "edit", "ask",
        "clear", "reset",
        "undo", "diff", "commit",
        "run", "tokens", "model",
        "help",
        "prompt",  # bukan slash command — prompt biasa ke AI
    ]
    args: str = ""
    edit_mode: EditMode | None = None
    readonly: bool = False


def parse(raw: str) -> Command:
    """
    Parse raw input dari user.
    Return Command yang siap di-dispatch.
    """
    text = raw.strip()

    if not text.startswith("/"):
        return Command(kind="prompt", args=text)

    # split command dan args
    parts = text.split(" ", 1)
    cmd = parts[0].lower()
    args = parts[1].strip() if len(parts) > 1 else ""

    # edit commands
    if cmd in EDIT_COMMANDS:
        return Command(kind="edit", args=args, edit_mode=EDIT_COMMANDS[cmd])

    # ask — kembali ke mode normal
    if cmd == "/ask":
        return Command(kind="ask")

    # context commands
    if cmd == "/add":
        readonly = False
        if args.startswith("-r "):
            readonly = True
            args = args[3:].strip()
        return Command(kind="add", args=args, readonly=readonly)

    if cmd == "/drop":
        return Command(kind="drop", args=args)

    # session commands
    if cmd == "/clear":
        return Command(kind="clear")

    if cmd == "/reset":
        return Command(kind="reset")

    if cmd == "/undo":
        return Command(kind="undo")

    if cmd == "/diff":
        return Command(kind="diff")

    if cmd == "/commit":
        return Command(kind="commit", args=args)

    if cmd == "/run":
        return Command(kind="run", args=args)

    if cmd == "/tokens":
        return Command(kind="tokens")

    if cmd == "/model":
        return Command(kind="model", args=args)

    if cmd == "/help":
        return Command(kind="help")

    # unknown slash command — treat as prompt
    return Command(kind="prompt", args=text)


HELP_TEXT = """
Commands:
  /add <f1> [f2 ...]   add files to context (editable)
  /add -r <f1> [f2 ...]  add files as read-only
  /drop <file>         remove file from context
  /edit-block [prompt] SEARCH/REPLACE mode (permanent if no prompt)
  /edit-udiff [prompt] unified diff mode (permanent if no prompt)
  /edit-whole [prompt] whole-file mode (permanent if no prompt)
  /ask                 return to ask mode
  /undo                rollback last edit
  /diff                show last diff
  /commit [msg]        git commit changes
  /run <cmd>           run shell command
  /tokens              show session token usage
  /model <alias|id>    switch model
  /clear               clear chat history (keep context)
  /reset               clear chat + context
  /help                show this help
""".strip()

