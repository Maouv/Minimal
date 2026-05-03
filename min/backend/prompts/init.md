Analyze the codebase context and write a MINIMAL.md for this directory.
This file will be loaded at the start of every session to give future AI instances
immediate context without re-exploring the codebase.

The context is provided in sections with reliability order:
1. EXISTING MINIMAL.md — ground truth, do not contradict unless repo map shows it outdated
2. @repo: TAGS — developer annotations, high signal
3. REPO MAP — auto-extracted symbols, structural only, no intent
4. MANIFESTS — ground truth for dependencies and run scripts

What to include:
1. Commands — how to run, build, test. Only if verifiable from manifests or existing docs.
   Include how to run a single test if test files exist.
2. Architecture — data flow and module boundaries that require reading multiple files
   to understand. Skip what is obvious from filenames alone.
3. Gotchas — anything from @repo: tags or existing MINIMAL.md marked critical or tricky.
   This is the highest-value section. If empty, omit the section entirely.
4. Non-obvious dependencies — why a library exists, not just that it does.

What to exclude:
- Generic development practices
- File listings discoverable by ls
- Anything you are not confident about — omit rather than guess
- Content already in a parent or sibling MINIMAL.md (it loads separately)

If EXISTING MINIMAL.md is provided:
- Preserve accurate sections as-is
- Only update where repo map clearly shows divergence
- Do not rewrite sections just to paraphrase them

Format:
- Start with exactly:
  # MINIMAL.md
  This file provides guidance to Minimal when working in this repository.
- Maximum 120 lines. If over, cut lowest-confidence sections first.
- No section header if the section has only one item — inline it.
- No nested bullets deeper than one level.

Output as draft only. Do not reference saving or file writing.
User will run /init --save to persist.
