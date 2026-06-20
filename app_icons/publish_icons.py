"""Publish app-icon PNGs to a GitHub Pages repo root (gh-pages branch).

Usage: python _tmp_publish_icons.py <variant: prod|staging>
  prod    -> app_icons/prod/*    -> repo wordle-league
  staging -> app_icons/staging/* -> repo wordle-league-staging
Reads GITHUB_TOKEN/GITHUB_USERNAME from .env. Read-only on the working tree.
"""
import sys, os, base64, requests

variant = sys.argv[1] if len(sys.argv) > 1 else "staging"
REPO = {"prod": "wordle-league", "staging": "wordle-league-staging"}[variant]
FOLDER = {"prod": "prod", "staging": "staging_env"}[variant]  # 'staging' dir is .gitignored
BRANCH = "gh-pages"
FILES = ["apple-touch-icon.png", "icon-192.png", "icon-512.png", "favicon-32.png"]

# Load creds from .env
creds = {}
with open(".env", encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if "=" in line and not line.startswith("#"):
            k, _, v = line.partition("=")
            creds[k.strip()] = v.strip().strip('"').strip("'")
USER = creds["GITHUB_USERNAME"]
TOKEN = creds["GITHUB_TOKEN"]
H = {"Authorization": f"token {TOKEN}", "Accept": "application/vnd.github.v3+json"}

print(f"Publishing {variant} icons -> {USER}/{REPO}@{BRANCH} (root)")
for fname in FILES:
    local = f"app_icons/{FOLDER}/{fname}"
    with open(local, "rb") as fh:
        content_b64 = base64.b64encode(fh.read()).decode()
    api = f"https://api.github.com/repos/{USER}/{REPO}/contents/{fname}"
    # get existing sha (if present)
    r = requests.get(api + f"?ref={BRANCH}", headers=H, timeout=15)
    sha = r.json().get("sha") if r.status_code == 200 else None
    body = {"message": f"Add app icon {fname}", "content": content_b64, "branch": BRANCH}
    if sha:
        body["sha"] = sha
    pr = requests.put(api, headers=H, json=body, timeout=20)
    if pr.status_code in (200, 201):
        print(f"  OK {fname}  (commit {pr.json().get('commit',{}).get('sha','')[:7]})")
    else:
        print(f"  FAIL {fname}: {pr.status_code} {pr.text[:200]}")
print("done")
