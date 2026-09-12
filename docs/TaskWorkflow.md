# Task Workflow

This document describes how work is tracked and delivered in the Monkey-Business-project repository.
Every teammate is expected to follow it.

## 1. Where tasks live

- All work items are tracked as **GitHub Issues** in this repository.
- Anyone on the team may create an issue. Before creating one, search existing issues to avoid duplicates.
- An issue must have:
  - a short, action-oriented title (e.g. `Write TeamCharter.md`, `Setup GitHub Actions CI`);
  - a description of what needs to be done and what "done" looks like (acceptance criteria);
  - at least one label;
  - an assignee.

## 2. Labels

| Label           | Meaning                                                                                             |
|-----------------|-----------------------------------------------------------------------------------------------------|
| `setup`         | Repository, tooling, or process configuration (will be archived later)                              |
| `documentation` | Writing or updating project documents (`*.md` files)                                                |
| `feature`       | New functionality of the product                                                                    |
| `bug`           | Something that is broken and must be fixed                                                          |
| `in progress`   | Someone is actively working on the task (see Task states)                                           |
| `accepted`      | Tasks that were reviewed, and merged with main                                                      |
| `blocker`       | Critical bugs that interrupt existing features or issues that must be done before doing other tasks |

Labels may be combined (e.g. `documentation` + `setup`). New labels are added only after a team discussion.

## 3. Task states

A task moves through the following states:

```
Open -> In progress -> Done -> Accepted
```

| State       | How you know                                  | Who moves it                                                     |
|-------------|-----------------------------------------------|------------------------------------------------------------------|
| Open        | Issue exists, no `in progress` label          | Issue author                                                     |
| In progress | Issue has the `in progress` label             | Assignee, when they start work                                   |
| Done        | Issue is closed, no `accepted` label          | Assignee, when done with work and the PR is opened               |
| Accepted    | Issue is closed and has the `accepted` label  | Issue author, when all requirements are met and changes are on `main` |

An issue that turns out to be unnecessary is closed with a comment explaining why.
An issue can be reopened by the reviewer if not all conditions were met or something came up during review (a bug, missing requirement, etc.). It then goes back to **In progress**.

## 4. Working with git

1. **Never commit directly to `main`.** `main` is protected and receives changes only through Pull Requests.
2. Create a branch from the latest `main` for each task:

   ```
   git switch main
   git fetch
   git rebase
   git switch -c <type>/<issue-number>-<short-description>
   ```

   Examples: `docs/7-task-status`, `setup/4-github-actions-ci`, `feature/12-login-form`.

3. Commit small, focused changes. Write a commit message in the imperative mood and reference the issue:

   ```
   Add task workflow description (#7)
   ```

4. Push the branch and open a **Pull Request** into `main`.
   - The PR title matches the task.
   - The PR description references the issue (e.g. `#7`).
   - Request review from the issue creator. If the creator is also the assignee, request any other teammate.
   - Close the issue (state **Done**) and remove the `in progress` label. The issue stays closed unless the reviewer reopens it.

## 5. Review and merge

- Every PR needs **at least one approval**, normally from the issue creator (see step 4 above).
- The **CI workflow** (`.github/workflows/ci.yml`) must pass before merging.
- The reviewer checks that the change does what the issue asks, is readable, and does not break anything.
- Review comments are resolved by the PR author, either by changing the code or by explaining why no change is needed.
- If the review finds that the task is not complete, the reviewer reopens the issue and it returns to **In progress**.
- After approval and green CI, the PR author merges the PR and deletes the branch.
- After the merge, the issue creator verifies that all requirements are met on `main` and adds the `accepted` label. The task is now **Accepted**.

## 6. Communication

- Anything that defines or changes a task is recorded in the issue itself, so that it leaves a footprint and is easy to find later:
  - requirements and acceptance criteria (in the issue description, updated when they change);
  - decisions that affect scope, approach, or deadlines;
  - blockers and their resolution;
  - the reason an issue is closed as unnecessary or reopened.
- Smaller details, questions, and anything not important for the task history may be discussed wherever the team finds convenient (chat, calls, in person). Keeping every message in issues makes the important information hard to find.
- Code-level remarks belong in the Pull Request review.
- If a task is blocked, the assignee writes a comment on the issue explaining what is blocking it and tags the teammate who can help. If the blocking issue is not yet marked, it gets the `blocker` label.
- Task status is reviewed at each team meeting; stale issues are re-assigned or closed.