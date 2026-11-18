# yap-forever: rules for agents

## Project setup

Recorded in [docs/project-setup.md](docs/project-setup.md): remote and branch rules, verified build, tags, review and decision rules.

## Commits and pull requests

- Commit as the owner's GitHub noreply address (repo-local `user.email`). `tests/test_publishable.py`
  fails on any later commit with a personal address.
- Stacked pull requests: before merging one, retarget the PR above it to `main`; delete branches only
  after the whole stack is merged. Deleting a merged PR's branch closes the PR stacked on it.
- Never put the owner's details in tracked files; keep them in the untracked `.private-denylist`
  (plain text or `re:` patterns), which the same test reads. A detail the owner gives in chat
  (character names, realm, IDs) goes into the denylist before any code uses it.
- No force-push: bring a branch up to date by merging `main` into it. Every PR appends to
  `docs/progress.md`, so open the next PR only after the previous one is merged.

## Planner changes

- A planner fix is done only after a before/after run on real data (the owner's route and a case the
  fix targets, in a scratch copy of the home folder) and a render through the guide and the full
  report. If real data does not change, say so in the PR.
- Every number the skill's reference documents promise (`skills/forever-professions/references/`)
  gets a test.
