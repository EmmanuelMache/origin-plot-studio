"""Projects, under Start here: a name you give a set of data files (CSV, Excel, TSV ...), saved so you can come back to it,
open several together, or start fresh with a different one. A project holds file paths only - the files themselves stay
wherever they are; nothing is copied or moved. Opening a project reads its files like 'Add data files' always has, and
tags each graph with the project's name, so Your graphs (and Find a graph) can tell which project a graph came from.
Stored in your own settings (not the app, not shared), under the key 'projects'."""
import os
import re
import time

import workspace_qt as WQ


def _load():
    return dict(WQ.load_cfg().get("projects") or {})


def _save(projects):
    WQ.save_cfg({"projects": projects})


def list_projects():
    """[(slug, {name, files, created, modified})], the most recently changed first."""
    return sorted(_load().items(), key=lambda kv: kv[1].get("modified", 0), reverse=True)


def get(slug):
    return _load().get(slug)


def create(name, files=None):
    """A new, empty (or file-filled) project. Returns its slug."""
    projects = _load()
    slug = _slug(name, projects)
    now = time.time()
    projects[slug] = {"name": (name or "").strip() or "Untitled project", "files": list(dict.fromkeys(files or [])), "created": now, "modified": now}
    _save(projects)
    return slug


def rename(slug, new_name):
    projects = _load()
    if slug not in projects or not (new_name or "").strip(): return False
    projects[slug]["name"] = new_name.strip(); projects[slug]["modified"] = time.time()
    _save(projects)
    return True


def add_files(slug, files):
    """Files added to a project you already have; they are not added twice."""
    projects = _load()
    if slug not in projects: return False
    have = set(projects[slug]["files"])
    projects[slug]["files"] += [f for f in files if f not in have]
    projects[slug]["modified"] = time.time()
    _save(projects)
    return True


def remove_file(slug, path):
    """Takes a file out of a project (the file itself is not touched)."""
    projects = _load()
    if slug not in projects: return False
    before = len(projects[slug]["files"])
    projects[slug]["files"] = [f for f in projects[slug]["files"] if f != path]
    if len(projects[slug]["files"]) == before: return False
    projects[slug]["modified"] = time.time()
    _save(projects)
    return True


def delete(slug):
    projects = _load()
    if slug not in projects: return False
    del projects[slug]
    _save(projects)
    return True


def missing_files(slug):
    """Files of this project that are no longer where they were (moved or deleted) - Refresh checks for these."""
    p = get(slug)
    return [f for f in (p or {}).get("files", []) if not os.path.isfile(f)]


def _slug(name, existing):
    base = re.sub(r"[^a-z0-9]+", "-", (name or "").strip().lower()).strip("-") or "project"
    s = base; i = 2
    while s in existing:
        s = f"{base}-{i}"; i += 1
    return s
