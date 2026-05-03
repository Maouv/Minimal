{% include 'edit_base.md' %}

## Edit format: whole file rewrite

Output the EXACT file path on its own line, then immediately a fenced code block with the full file content.
No blank line between the filename and the opening fence.

{{ example_file }}
```{{ ext }}
<complete file content — every line, no truncation>
```

Rules:
- The filename line must be EXACTLY as shown in the editable files list above
- Output the ENTIRE file content — not just the changed parts
- No blank line between filename and opening ```
- Do not wrap the filename in backticks or other markers
