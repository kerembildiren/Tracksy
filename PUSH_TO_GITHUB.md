# Push Harman Games from terminal (no GitHub page)

You can do everything from the terminal in two cases:

---

## Option 1: Use your existing repo (Tracksy) – no browser

Your Render site already uses **https://github.com/kerembildiren/Tracksy.git**.  
Push the new structure (HarmanGames + SportsGuesser + Trackzy updates) to that repo. You never need to open GitHub.

### 1. In terminal (PowerShell), from your project root:

```powershell
cd "c:\Users\4\Desktop\Cursor_Projects"

# Stage HarmanGames, SportsGuesser, root README, and Trackzy changes
git add HarmanGames/
git add SportsGuesser/
git add README.md
git add Trackzy/

# Commit
git commit -m "Add HarmanGames hub, SportsGuesser, update Trackzy for monorepo"

# Push to GitHub
git push origin main
```

If you see “rejected” because the remote has new commits, run `git pull origin main --rebase` once, then `git push origin main` again.

### 2. In Render (one-time)

- Dashboard → your service → **Settings** → **Root Directory** → set to **`HarmanGames`**.
- **Start Command:** `gunicorn --bind 0.0.0.0:$PORT app:app`
- Save. Render will redeploy; hub at `/`, Trackzy at `/trackzy`, SportsGuesser at `/sportsguesser/`.

You only need the Render dashboard for this; no need to open GitHub in Chrome.

---

## Option 2: Create a *new* repo from terminal (GitHub CLI)

To create a **new** GitHub repo from the terminal (without using the GitHub website), install the GitHub CLI, then run a few commands.

### 1. Install GitHub CLI (one-time)

In PowerShell (Run as Administrator if needed):

```powershell
winget install --id GitHub.cli -e
```

Close and reopen the terminal. Check:

```powershell
gh --version
```

### 2. Log in (one-time; may open browser once)

```powershell
gh auth login
```

- Choose **GitHub.com** → **HTTPS** → **Login with a web browser**.  
- Copy the one-time code, press Enter; browser opens, paste the code and authorize.  
After this you don’t need the GitHub page to create repos.

### 3. Create the new repo and push from here

From your project root (e.g. `c:\Users\4\Desktop\Cursor_Projects`):

```powershell
cd "c:\Users\4\Desktop\Cursor_Projects"

# Create a new repo on GitHub and set it as origin (replace YOUR_USERNAME with your GitHub username)
gh repo create harmangaming --public --source=. --remote=origin --push
```

This will **overwrite** your current `origin` (Tracksy). If you want to keep Tracksy as a remote and add the new repo as a second remote:

```powershell
# Add new repo as remote 'origin' (back up current origin first if you need it)
git remote rename origin tracksy
gh repo create harmangaming --public --source=. --remote=origin --push
```

Then in Render: **New Web Service** → connect **harmangaming** repo → Root Directory **`HarmanGames`** → Start Command **`gunicorn --bind 0.0.0.0:$PORT app:app`**.

---

## If you don’t install GitHub CLI and want a new repo on the website

1. Open **https://github.com/new** in Chrome.
2. **Repository name:** e.g. `harmangaming`.
3. **Public**.
4. Do **not** check “Add a README” or “Add .gitignore”.
5. Click **Create repository**.
6. On the empty repo page, copy the **“push an existing repository”** block. It will look like:

   ```
   git remote add origin https://github.com/YOUR_USERNAME/harmangaming.git
   git branch -M main
   git push -u origin main
   ```

7. In PowerShell, from `c:\Users\4\Desktop\Cursor_Projects`:

   - If this folder is already a git repo with `origin` = Tracksy, either remove the old origin or use another remote name:

   ```powershell
   cd "c:\Users\4\Desktop\Cursor_Projects"
   git remote rename origin tracksy
   git remote add origin https://github.com/YOUR_USERNAME/harmangaming.git
   git add HarmanGames/ SportsGuesser/ README.md Trackzy/
   git commit -m "Add HarmanGames hub, SportsGuesser, update Trackzy"
   git push -u origin main
   ```

   Replace `YOUR_USERNAME` with your GitHub username.

After that, in Render connect the new **harmangaming** repo and set Root Directory to **`HarmanGames`**.
