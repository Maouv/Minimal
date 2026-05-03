{% include 'edit_base.md' %}

## Edit format: SEARCH/REPLACE blocks

To edit a file, output the EXACT file path on its own line, then immediately the SEARCH/REPLACE block.

{{ example_file }}
<<<<<<< SEARCH
<only the lines you want to change — nothing more>
=======
<new content to replace with>
>>>>>>> REPLACE

Rules:
- SEARCH must contain ONLY the lines being changed — not the whole file, not the whole function
- SEARCH must match the file exactly (whitespace, indentation, no ellipsis)
- If changing paragraph 1, SEARCH contains only paragraph 1. If changing line 42, SEARCH contains only line 42.
- Multiple blocks are allowed for multiple separate changes
- Never truncate or abbreviate SEARCH content
- The filename line must be EXACTLY as shown in the editable files list above
- Do not wrap the filename in backticks or any other markers
- Do NOT show file content before the block — go straight to filename then <<<<<<< SEARCH
- Do NOT use XML tags like <file path="..."> or </file> — plain filename only
- To write to an EMPTY file, use an empty SEARCH block:

{{ example_file }}
<<<<<<< SEARCH
=======
<full content to write>
>>>>>>> REPLACE
