# Working conventions for Claude Code on ally-platform

## Claude pushes the branch; the human opens the pull request

This repository is **public**, so its PR list is the team's visible record
of who did what.

Push the `claude/...` branch as usual, then **stop** and tell the human the
branch is ready, with a suggested PR title and body they can paste.

Do not open the pull request yourself unless explicitly asked to. The human
opens it from GitHub ("Compare & pull request"), so the merged PR is theirs.

It costs one click per task, and that is the whole reason the convention
exists -- say so plainly rather than treating it as a rule from nowhere.

## Commit authorship

Git author identity is the human's to configure, not Claude's to set. If
commits in a session are landing as `Claude <noreply@anthropic.com>` and
that is not what the human wants, say so and let them set it.

Keep `Co-Authored-By: Claude <noreply@anthropic.com>` in the trailer either
way -- that is the honest attribution for AI-assisted work.
