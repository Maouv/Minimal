{% include 'edit_base.md' %}

## Edit format: unified diff

Output edits as a unified diff inside a ```diff code block.
Use the EXACT file path from the editable files list in the --- and +++ headers.

```diff
--- a/{{ example_file }}
+++ b/{{ example_file }}
@@ -10,7 +10,7 @@
 context line
-old line
+new line
 context line
```

Rules:
- The path in --- / +++ must exactly match the editable files list (after stripping a/ b/ prefix)
- Include 3 lines of context around each change for unambiguous matching
- One ```diff block per file; multiple @@ hunks are fine in the same block
- Use exact line content — no abbreviation, no ellipsis
