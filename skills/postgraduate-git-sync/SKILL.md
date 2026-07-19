---
name: postgraduate-git-sync
description: "Synchronize Postgraduate research artifacts and Skill changes through Git with explicit comments. Use when the user asks to connect GitHub over SSH, commit and push PDFs/HTML/scripts/wiki where permitted, version research progress, or verify local and remote commit state."
---

# Postgraduate Git Sync

Read `../postgraduate-common/references/privacy-publication.md` and `governance.md`.

## Workflow

1. Inspect status and preserve unrelated user changes.
2. Scan staged files for credentials, private paths, and prohibited public data.
3. Run tests and `git diff --check`.
4. Stage only intended artifacts.
5. Commit with a factual message and optional body explaining the research update.
6. Push through the configured SSH remote.
7. Verify local HEAD equals the remote branch.

Use the existing helper when the whole worktree is intentionally in scope:

```bash
scripts/sync_with_comment.sh "Describe the research update" "Optional audit details"
```

Do not publish PDFs, private ideas, source text, or request payloads unless redistribution and privacy are explicitly acceptable.
