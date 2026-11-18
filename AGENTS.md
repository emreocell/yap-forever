# yap-forever: rules for agents

## Project setup

Recorded in [docs/project-setup.md](docs/project-setup.md): remote and branch rules, verified build, tags, review and decision rules.

## Commits and pull requests

- Commit as the owner's GitHub noreply address (repo-local `user.email`). `tests/test_publishable.py`
  fails on any later commit with a personal address.
- Stacked pull requests: before merging one, retarget the PR above it to `main`; delete branches only
  after the whole stack is merged. Deleting a merged PR's branch closes the PR stacked on it.
- Never put the owner's details in tracked files; keep them in the untracked `.private-denylist`
  (plain text or `re:` patterns), which the same test reads.
