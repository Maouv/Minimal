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
    "/add", "/drop", "/ls",
    "/edit-block", "/edit-udiff", "/edit-whole",
    "/clear", "/reset",
    "/undo", "/diff", "/commit",
    "/run", "/tokens", "/model",
    "/help",
]


@dataclass
class Command:
    kind: Literal[
        "add", "drop", "ls",
        "edit",
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

    # context commands
    if cmd == "/add":
        readonly = False
        if args.startswith("-r "):
            readonly = True
            args = args[3:].strip()
        return Command(kind="add", args=args, readonly=readonly)

    if cmd == "/drop":
        return Command(kind="drop", args=args)

    if cmd == "/ls":
        return Command(kind="ls")

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
  /add <file>          add file to context (editable)
  /add -r <file>       add file as read-only
  /drop <file>         remove file from context
  /ls                  list context files + token count
  /edit-block <prompt> edit with SEARCH/REPLACE blocks
  /edit-udiff <prompt> edit with unified diff
  /edit-whole <prompt> rewrite entire file
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

