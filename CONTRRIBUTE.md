# Contributing to TheNag

This doc covers exactly how to get the repo, stay up to date, and push your changes. Follow this order every time.

---

## 1. First-time setup — clone the repo

1. `git clone <paste url>`
2. `cd TheNag`
3. `code .`

This opens the project in VS Code. You only need to do this once per machine.

### Backend setup (Python)

Each backend subsystem (`extraction/`, `classification/`, `actions/`) has its own `requirements.txt` — see Section 1a below for why. From the specific subsystem folder you're working in:
```
python -m venv venv
```
Activate it:
- Windows: `venv\Scripts\activate`
- Mac/Linux: `source venv/bin/activate`

Then install that subsystem's dependencies:
```
pip install -r requirements.txt
```

Run this activation step every time you open a new terminal to work on that subsystem — it doesn't persist automatically. If you're working across more than one subsystem, repeat this per folder rather than assuming one shared environment covers everything.

### Frontend setup (Vite + React)

From the `frontend/` folder:
```
npm install
npm run dev
```
This starts the local dev server — Vite will print the local URL to open in your browser.

---

## 1a. Every module owns its own README and requirements.txt

Each subsystem folder — `backend/extraction/`, `backend/classification/`, `backend/actions/`, and `frontend/` — must have its own `README.md` and, for the Python subsystems, its own `requirements.txt`. This isn't optional documentation, it's how the team stays able to work independently:

- **`requirements.txt` per subsystem** means each person only installs what their own module actually needs (extraction needs Whisper and an OCR library, classification needs an LLM SDK, actions needs a calendar API client — there's no reason for one person's environment to carry another's dependencies), and it means one subsystem's dependency changes never silently break another's setup.
- **`README.md` per subsystem** should cover, at minimum: what the module does, how to run it on its own, what its inputs and outputs look like (the actual data contract, matching what's in `docs/spec.md` and `docs/team-structure.md`), and any environment variables or API keys it needs.

Whoever creates a new subsystem folder is responsible for adding both files at the same time — not after the fact once code already exists. If you add a new dependency to your subsystem, update that subsystem's `requirements.txt` in the same commit, not a later one.

---

## Per-folder README and requirements.txt (required for every subsystem folder)

Every subsystem folder — `backend/extraction/`, `backend/classification/`, `backend/actions/`, `frontend/`, and any subfolder that's its own working unit — must have its own:

- **`README.md`** — a short doc covering: what this subsystem does, how to run it on its own, what its inputs/outputs look like (the data contract it exposes to other subsystems), and any setup steps specific to it beyond the top-level repo setup.
- **`requirements.txt`** — for Python folders, listing only the dependencies that specific subsystem actually needs, not a copy of every package used anywhere in the backend. This keeps each subsystem installable and testable in isolation, and makes it obvious at a glance what a given piece of code actually depends on.

Whoever creates a new subsystem folder is responsible for adding both files before the first real code goes in, not after. If you're extending an existing subsystem, keep its README's inputs/outputs section current — it's the fastest way for a teammate to understand a data contract without reading your code.

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
| Set up backend (Python, per subsystem) | From the subsystem folder (e.g. `backend/extraction/`): `python -m venv venv`, activate it, `pip install -r requirements.txt` |
| Set up frontend (Vite + React) | From `frontend/`: `npm install`, then `npm run dev` |
| Update my local `main` | `git checkout main` then `git pull origin main` |
| Start new work | `git checkout -b your-name/short-description` |
| Save my changes locally | `git add .` then `git commit -m "message"` |
| Push my branch | `git push origin your-branch-name` |
| See what's changed but not committed | `git status` |