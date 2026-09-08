# Contributing to TheNag

This doc covers exactly how to get the repo, stay up to date, and push your changes. Follow this order every time.

---

## 1. First-time setup — clone the repo

1. `git clone <paste url>`
2. `cd TheNag`
3. `code .`

This opens the project in VS Code. You only need to do this once per machine.

---

## 2. Before you start working — update to the latest code

Do this every time before you start a new work session, so you're not building on outdated code.

1. `git checkout main`
2. `git pull origin main`

---

## 3. Making changes — always work on a branch, never commit directly to `main`

1. Create a new branch off the latest `main`:
   ```
   git checkout -b your-name/short-description
   ```
   Example: `git checkout -b jaisika/ocr-pipeline`

2. Make your changes in VS Code as normal.

3. Check what changed:
   ```
   git status
   ```

4. Stage your changes:
   ```
   git add .
   ```
   (Or `git add <specific-file>` if you only want to stage certain files.)

5. Commit with a clear message:
   ```
   git commit -m "Add OCR extraction for Hindi and English"
   ```
   Keep messages short and specific — describe what changed, not "fixed stuff" or "updates."

6. Push your branch to GitHub:
   ```
   git push origin your-name/short-description
   ```
   (First push on a new branch may show a suggested command with `-u` — just run what git suggests.)

---

## 4. Opening a Pull Request (PR)

1. Go to the repo on GitHub — it'll usually show a banner suggesting you open a PR for your just-pushed branch. Click it.
2. Set the base branch to `main` and your branch as the compare branch.
3. Write a short description of what the PR does.
4. **Assign the team lead as a reviewer** — on the right sidebar of the PR page, click the gear icon next to "Reviewers" and select the team lead. Every PR needs their approval before merging, in addition to anyone else whose subsystem the change touches (see the team structure doc for who owns what).
5. Once approved, merge the PR into `main` (use "Squash and merge" to keep history clean, unless the team decides otherwise).
6. Delete the branch after merging (GitHub usually offers a button for this).

---

## 5. After your PR is merged

Switch back to `main` and pull the merged changes before starting your next branch:
```
git checkout main
git pull origin main
```

Then start again from Step 3 for your next piece of work.

---

## 6. If you hit a merge conflict

1. `git checkout main`
2. `git pull origin main`
3. `git checkout your-branch-name`
4. `git merge main`
5. Git will mark the conflicting sections in the affected files — open them in VS Code, decide what should stay, remove the conflict markers (`<<<<<<<`, `=======`, `>>>>>>>`), and save.
6. `git add .`
7. `git commit -m "Resolve merge conflict with main"`
8. `git push origin your-branch-name`

If you're not sure how to resolve a conflict, ask in the team channel before force-pushing anything.

---

## Repo setup: blocking direct pushes to `main` (do this once, team lead only)

Direct pushes to `main` should be technically blocked, not just avoided by convention. Set this up once in GitHub:

1. Go to the repo on GitHub → **Settings**
2. In the left sidebar, click **Branches**
3. Click **Add branch protection rule** (or **Add rule**)
4. Under "Branch name pattern," type `main`
5. Check **Require a pull request before merging**
6. Check **Require approvals**, and set the number to **1**
7. (Optional, stricter) Check **Require review from Code Owners** to make sure the team lead is always a required reviewer automatically — this needs a `CODEOWNERS` file listing the lead against `*`. Without this, just manually assign the team lead as reviewer on each PR (see Step 4 above).
8. Click **Create** (or **Save changes**)

Once this is on, GitHub will reject any push directly to `main` from anyone — including the team lead — and require going through a PR with an approval, exactly as described in Sections 3-4 above.

---

## Quick reference

| I want to... | Command |
|---|---|
| Get the repo for the first time | `git clone <url>` |
| Update my local `main` | `git checkout main` then `git pull origin main` |
| Start new work | `git checkout -b your-name/short-description` |
| Save my changes locally | `git add .` then `git commit -m "message"` |
| Push my branch | `git push origin your-branch-name` |
| See what's changed but not committed | `git status` |