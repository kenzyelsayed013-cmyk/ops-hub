"""Keeps the uploaded data (and the settings) alive without a database.

A PRIVATE GitHub repo holds one cumulative file per (platform, city, kind) and the small settings files.
After a restart wipes the app's disk, the app reads them back, so the latest data stays until new data is uploaded.

Secrets (Streamlit Cloud -> Settings -> Secrets):
    GITHUB_TOKEN = "github_pat_..."      # fine-grained token, Contents: Read and write, on the data repo only
    DATA_REPO    = "your-user/ops-data"  # a private repo, can be empty
    DATA_BRANCH  = "main"                # optional
"""
import base64
import pickle
import zlib
from pathlib import Path
from urllib.parse import quote, unquote

import pandas as pd
import requests
import streamlit as st

API = "https://api.github.com"
ROOT = Path(__file__).resolve().parent.parent
CONFIG_FILES = ("rules.json", "city_alias.json", "cities.json")
_http = requests.request          # swapped in tests


def cfg():
    try:
        tok, repo, br = st.secrets.get("GITHUB_TOKEN"), st.secrets.get("DATA_REPO"), st.secrets.get("DATA_BRANCH") or "main"
    except Exception:
        return None
    return (tok, repo, br) if tok and repo else None


def enabled():
    return cfg() is not None


def _call(method, path, raw=False, **kw):
    tok, _, _ = cfg()
    h = {"Authorization": f"Bearer {tok}", "X-GitHub-Api-Version": "2022-11-28",
         "Accept": "application/vnd.github.raw+json" if raw else "application/vnd.github+json"}
    return _http(method, API + path, headers=h, timeout=40, **kw)


def _dumps(df):
    return zlib.compress(pickle.dumps(df, protocol=4), 6)


def _loads(b):
    return pickle.loads(zlib.decompress(b))


def _get(path):
    """(sha, raw bytes) of a file in the data repo, or (None, None) if it does not exist."""
    _, repo, br = cfg()
    r = _call("GET", f"/repos/{repo}/contents/{quote(path)}?ref={br}")
    if r.status_code == 404:
        return None, None
    r.raise_for_status()
    sha = r.json()["sha"]
    return sha, _call("GET", f"/repos/{repo}/contents/{quote(path)}?ref={br}", raw=True).content


def _put(path, content, msg, sha=None):
    _, repo, br = cfg()
    body = {"message": msg, "content": base64.b64encode(content).decode(), "branch": br}
    if sha:
        body["sha"] = sha
    r = _call("PUT", f"/repos/{repo}/contents/{quote(path)}", json=body)
    if r.status_code not in (200, 201):
        raise RuntimeError(f"GitHub said {r.status_code}")


def push(kind, df, platform, city):
    """Add this upload to the cumulative file of (platform, city, kind). Days that are re-uploaded replace the old ones."""
    path = f"data/{quote(platform, safe='')}__{kind}__{quote(city, safe='')}.bin"
    sha, raw = _get(path)
    merged = df
    if raw is not None:
        old = _loads(raw)
        merged = pd.concat([old[~old["date"].isin(set(df["date"]))], df], ignore_index=True)
    merged = merged.sort_values("date", kind="stable").reset_index(drop=True)
    _put(path, _dumps(merged), f"data {platform}/{city}/{kind}", sha)


def push_text(name, text):
    """Settings files (rules.json, city_alias.json, cities.json). Never raises."""
    if not enabled():
        return
    try:
        path = f"config/{name}"
        sha, _ = _get(path)
        _put(path, text.encode("utf-8"), f"settings {name}", sha)
    except Exception:
        pass


def restore(db):
    """Put everything back after a restart. Returns the number of data files restored."""
    _, repo, br = cfg()
    n = 0
    r = _call("GET", f"/repos/{repo}/contents/config?ref={br}")
    if r.status_code == 200:
        for f in r.json():
            if f["name"] in CONFIG_FILES and not (ROOT / f["name"]).exists():
                _, raw = _get(f"config/{f['name']}")
                (ROOT / f["name"]).write_bytes(raw)
    r = _call("GET", f"/repos/{repo}/contents/data?ref={br}")
    if r.status_code != 200:
        return 0
    for f in r.json():
        if not f["name"].endswith(".bin"):
            continue
        platform, kind, city = [unquote(x) for x in f["name"][:-4].split("__")]
        _, raw = _get(f"data/{f['name']}")
        db.save(kind, _loads(raw), platform, city, "restored from backup")
        n += 1
    return n


def count():
    """How many data files are in the backup (for the admin page)."""
    _, repo, br = cfg()
    r = _call("GET", f"/repos/{repo}/contents/data?ref={br}")
    return len(r.json()) if r.status_code == 200 else 0
