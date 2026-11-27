"""dependency_inventory.py - the Python packages of a release: one tested set, written down.

    python tools/dependency_inventory.py                 the inventory, from origin_plot_app/requirements.lock
                                                         -> docs/DEPENDENCIES.md and docs/dependencies.json (no network)
    python tools/dependency_inventory.py --check         are the requirements exact pins, and does the lock match them?
                                                         (no network; exit code 1 when not)
    python tools/dependency_inventory.py --lock          make requirements.lock again from requirements.txt:
                                                         the full set with the sha256 of every wheel (NEEDS the network:
                                                         pip resolves, the hashes are read from pypi.org)
    python tools/dependency_inventory.py --audit         look the locked set up in the advisory database
                                                         (pip-audit when it is installed; with --online the advisory data
                                                         of pypi.org otherwise; else it says "not run" and why)
    --audit-python PY   the Python that has pip-audit, when it is kept in its own tools environment
    --online       allow this run to ask pypi.org (licences of packages that are not installed here, the audit fallback)
    --out DIR      write the inventory there instead of docs/

What the lock is: every package (direct and pulled in) at one exact version, with the hashes pip checks before it
installs (pip install --require-hashes --only-binary :all: -r requirements.lock). Versions of packages that are
installed in the environment this runs in are kept as they are there - that is the set the tests ran with; the others
are what pip resolves and are marked "not installed here". Run it on the machine the release is tested on.

It never installs or removes anything. Standard library only (uses the pip that belongs to this Python).
"""
import argparse, datetime, importlib.metadata as md, json, os, platform, re, subprocess, sys, tempfile, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP = os.path.join(ROOT, "origin_plot_app")
REQ = os.path.join(APP, "requirements.txt")
LOCK = os.path.join(APP, "requirements.lock")
PYPI = "https://pypi.org/pypi/{name}/{version}/json"
NO_HASH_HEADER = "# TODO hashes not generated: run tools/dependency_inventory.py --lock on a connected machine"


def canon(name): return re.sub(r"[-_.]+", "-", str(name)).lower()


# ------------------------------------------------------------------------------------------------ reading the files
def parse_requirements(path):
    """[{name, spec, version, marker, hashes, line}] of a requirements file (also a lock: continuation lines joined)."""
    out = []; text = open(path, encoding="utf-8").read().replace("\\\n", " ")
    for raw in text.splitlines():
        line = raw.split(" #")[0].strip() if not raw.lstrip().startswith("#") else ""
        if not line or line.startswith("-"): continue
        hashes = re.findall(r"--hash=sha256:([0-9a-f]{64})", line); line = re.sub(r"--hash=\S+", "", line).strip()
        req, _, marker = line.partition(";")
        m = re.match(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)\s*(\[[^\]]*\])?\s*(.*)$", req)
        if not m: continue
        spec = m.group(3).strip(); v = re.fullmatch(r"==\s*([A-Za-z0-9][A-Za-z0-9.!+_-]*)", spec)
        out.append({"name": m.group(1), "spec": spec, "version": v.group(1) if v and "*" not in v.group(1) else None, "marker": marker.strip(), "hashes": hashes, "line": raw.strip()})
    return out


def check(req_path=REQ, lock_path=LOCK):
    """The problems of the requirement files, as a list of sentences (empty = fine): every direct requirement is an
    exact pin, the lock exists, holds every direct requirement at the same version, pins everything, and either every
    entry has hashes or the file says at its top that it has none."""
    bad = []
    if not os.path.isfile(req_path): return [f"{req_path} is missing"]
    direct = parse_requirements(req_path)
    if not direct: bad.append("requirements.txt lists no package")
    for r in direct:
        if not r["version"]: bad.append(f"requirements.txt: {r['name']} is not pinned to one exact version ('{r['spec'] or 'no version'}')")
    if not os.path.isfile(lock_path): return bad + ["requirements.lock is missing: run tools/dependency_inventory.py --lock"]
    locked = parse_requirements(lock_path); by = {canon(r["name"]): r for r in locked}
    for r in locked:
        if not r["version"]: bad.append(f"requirements.lock: {r['name']} is not pinned to one exact version")
    for r in direct:
        l = by.get(canon(r["name"]))
        if not l: bad.append(f"requirements.lock does not hold {r['name']}")
        elif r["version"] and l["version"] != r["version"]: bad.append(f"requirements.lock holds {r['name']} {l['version']}, requirements.txt wants {r['version']}")
    head = open(lock_path, encoding="utf-8").read(4000)
    with_h = [r for r in locked if r["hashes"]]
    if with_h and len(with_h) != len(locked): bad.append("requirements.lock: some entries have hashes and some have none (" + ", ".join(r["name"] for r in locked if not r["hashes"])[:200] + ")")
    if not with_h and NO_HASH_HEADER not in head: bad.append("requirements.lock has no hashes and does not say so at its top")
    return bad


def lock_has_hashes(lock_path=LOCK):
    locked = parse_requirements(lock_path)
    return bool(locked) and all(r["hashes"] for r in locked)


def installed_version(name):
    try: return md.version(name)
    except Exception: return None


def installed_licence(name):
    try: m = md.metadata(name)
    except Exception: return ""
    lic = (m.get("License-Expression") or "").strip()
    if lic: return lic
    cls = [c.split("::")[-1].strip() for c in (m.get_all("Classifier") or []) if c.startswith("License ::")]
    if cls: return "; ".join(dict.fromkeys(cls))
    lic = (m.get("License") or "").strip().splitlines()
    return lic[0][:60] if lic else ""


# ------------------------------------------------------------------------------------------------ the network part
def pypi(name, version):
    with urllib.request.urlopen(PYPI.format(name=canon(name), version=version), timeout=60) as r:
        return json.load(r)


def pypi_licence(info):
    lic = (info.get("license_expression") or "").strip()
    if lic: return lic
    cls = [c.split("::")[-1].strip() for c in (info.get("classifiers") or []) if c.startswith("License ::")]
    if cls: return "; ".join(dict.fromkeys(cls))
    lic = (info.get("license") or "").strip().splitlines()
    return lic[0][:60] if lic else ""


def _markers():
    try: from packaging.requirements import Requirement
    except ImportError: from pip._vendor.packaging.requirements import Requirement
    return Requirement


def _on_windows(conditions):
    """Is a package with these conditions (a set of 'all of these markers' groups) installed on Windows at all?"""
    try: from packaging.markers import Marker
    except ImportError: from pip._vendor.packaging.markers import Marker
    return any(all(Marker(m).evaluate(WINDOWS) for m in group) for group in conditions)


WINDOWS = {"sys_platform": "win32", "platform_system": "Windows", "os_name": "nt", "extra": ""}
PLATFORM_WORDS = ("sys_platform", "platform_system", "os_name")


def _resolve(req_path, constraints=None):
    """What pip would install for the requirements, without installing: its own report (names, versions, the hash of
    the file it chose, what each package needs)."""
    with tempfile.TemporaryDirectory() as tmp:
        rep = os.path.join(tmp, "report.json")
        cmd = [sys.executable, "-m", "pip", "install", "--dry-run", "--ignore-installed", "--quiet", "--disable-pip-version-check", "--only-binary", ":all:", "--report", rep, "-r", req_path]
        if constraints: cmd += ["-c", constraints]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0 or not os.path.isfile(rep): raise RuntimeError("pip could not resolve the requirements:\n" + (r.stderr or r.stdout)[-1500:])
        return json.load(open(rep, encoding="utf-8"))


def make_lock(req_path=REQ, lock_path=LOCK, log=print):
    Requirement = _markers()
    direct = parse_requirements(req_path)
    notpinned = [r["name"] for r in direct if not r["version"]]
    if notpinned: raise SystemExit("requirements.txt must pin every package with ==  (not pinned: " + ", ".join(notpinned) + ")")
    log("resolving the full set with pip (nothing is installed) ...")
    rep = _resolve(req_path)
    # Keep what is installed here - the set the tests ran with - for the packages pip would pull in.
    roots = {canon(r["name"]) for r in direct}; pins = []
    for i in rep["install"]:
        n = i["metadata"]["name"]; have = installed_version(n)
        if canon(n) not in roots and have and re.fullmatch(r"[0-9][A-Za-z0-9.!+_-]*", have) and "+" not in have: pins.append(f"{n}=={have}")
    note = ""
    if pins:
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as c: c.write("\n".join(pins) + "\n")
        try: rep = _resolve(req_path, c.name)
        except RuntimeError as e: note = "the versions installed here could not all be kept (pip found a conflict); pip's own choice was used"; log("! " + note + "\n" + str(e)[-400:])
        finally: os.unlink(c.name)
    items = {canon(i["metadata"]["name"]): i for i in rep["install"]}
    # markers: a package that is only needed through something platform-specific gets that condition
    cond = {}                                                             # canonical name -> set of frozenset(marker texts); frozenset() = always
    queue = []
    for r in direct:
        if canon(r["name"]) in items: cond.setdefault(canon(r["name"]), set()).add(frozenset([r["marker"]] if r["marker"] else [])); queue.append(canon(r["name"]))
    gaps = []
    while queue:
        n = queue.pop()
        for text in items[n]["metadata"].get("requires_dist") or []:
            q = Requirement(text); child = canon(q.name)
            here = q.marker.evaluate({"extra": ""}) if q.marker else True
            if not here:
                if q.marker and q.marker.evaluate(WINDOWS) and child not in items and child not in roots and _on_windows(cond[n]): gaps.append(f"{q.name} (needed by {items[n]['metadata']['name']} on Windows: {q.marker})")
                continue
            if child not in items: continue
            edge = str(q.marker) if q.marker and any(w in str(q.marker) for w in PLATFORM_WORDS) and "extra" not in str(q.marker) else ""
            new = {frozenset(set(c) | ({edge} if edge else set())) for c in cond[n]}
            if not new <= cond.setdefault(child, set()): cond[child] |= new; queue.append(child)
    entries = []
    for n, i in sorted(items.items()):
        cs = cond.get(n, {frozenset()})
        marker = "" if frozenset() in cs else " or ".join(sorted("(" + " and ".join(sorted(c)) + ")" if len(c) > 1 or len(cs) > 1 else next(iter(c)) for c in cs))
        entries.append({"name": i["metadata"]["name"], "version": i["metadata"]["version"], "marker": marker, "direct": n in roots,
                        "chosen": ((i.get("download_info") or {}).get("archive_info") or {}).get("hashes", {}).get("sha256", "")})
    for r in direct:                                                       # a direct requirement for another system (pywin32): its pin, as written
        if canon(r["name"]) not in items: entries.append({"name": r["name"], "version": r["version"], "marker": r["marker"], "direct": True, "chosen": "", "elsewhere": True})
    log(f"{len(entries)} packages; reading the hashes of their wheels from pypi.org ...")
    licences = {}
    for e in entries:
        d = pypi(e["name"], e["version"]); files = d.get("urls") or []
        wheels = sorted({f["digests"]["sha256"] for f in files if f.get("packagetype") == "bdist_wheel" and not f.get("yanked")})
        e["hashes"] = wheels or sorted({f["digests"]["sha256"] for f in files if not f.get("yanked")}); e["wheels"] = bool(wheels)
        e["requires_python"] = d["info"].get("requires_python") or ""; licences[canon(e["name"])] = pypi_licence(d["info"])
        if e["chosen"] and e["chosen"] not in e["hashes"]: raise SystemExit(f"{e['name']} {e['version']}: the file pip chose is not among the files pypi.org lists - stopped, nothing written")
        if not e["hashes"]: raise SystemExit(f"{e['name']} {e['version']}: pypi.org lists no file - stopped, nothing written")
        if e.get("elsewhere"):
            for text in d["info"].get("requires_dist") or []:
                q = Requirement(text)
                if (not q.marker or q.marker.evaluate(WINDOWS)) and canon(q.name) not in {canon(x["name"]) for x in entries}: gaps.append(f"{q.name} (needed by {e['name']})")
        e["tested"] = installed_version(e["name"]) == e["version"]
    entries.sort(key=lambda e: canon(e["name"]))
    env = rep.get("environment") or {}
    head = ["# requirements.lock - the COMPLETE set of Python packages of this release, each at one exact version, with the",
            "# sha256 of every wheel pypi.org publishes for that version. Made by tools/dependency_inventory.py --lock from",
            "# requirements.txt - do not edit by hand. Setup installs from this file:",
            "#     python -m pip install --require-hashes --only-binary :all: -r requirements.lock",
            "#",
            f"# made:      {datetime.date.today().isoformat()} with Python {platform.python_version()} on {env.get('sys_platform', sys.platform)} {env.get('platform_machine', platform.machine())}, pip {rep.get('pip_version', '?')}",
            f"# packages:  {len(entries)} ({sum(e['direct'] for e in entries)} direct, {sum(not e['direct'] for e in entries)} pulled in)",
            f"# hashes:    yes, {sum(len(e['hashes']) for e in entries)} (read from https://pypi.org/pypi/<name>/<version>/json through the network of the build machine)",
            "# versions:  those installed in the build environment where a package is installed there (the tested set);",
            "#            'not installed here' marks the ones that were resolved but not installed or run in that environment.",
            "# Python:    3.12 or newer. The set was resolved for the Python above; make the lock again on the release machine",
            "#            (Windows) before a release and compare."]
    if note: head.append("# note:      " + note)
    for g in dict.fromkeys(gaps): head.append("# WARNING:   not in this lock: " + g)
    lines = head + [""]
    for e in entries:
        tag = "direct" if e["direct"] else "pulled in"
        tag += "" if e["tested"] else "; not installed here" + (" (another system)" if e.get("elsewhere") else "")
        if not e["wheels"]: tag += "; NO WHEEL published (source hash listed; pip --only-binary will refuse it)"
        lines.append(f"# {tag}")
        lines.append(f"{e['name']}=={e['version']}" + (f" ; {e['marker']}" if e["marker"] else "") + " \\")
        lines += [f"    --hash=sha256:{h}" + (" \\" if k < len(e["hashes"]) - 1 else "") for k, h in enumerate(e["hashes"])]
    tmp = lock_path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f: f.write("\n".join(lines) + "\n")
    os.replace(tmp, lock_path)
    for g in dict.fromkeys(gaps): log("! not in this lock: " + g)
    log(f"wrote {lock_path}: {len(entries)} packages, {sum(len(e['hashes']) for e in entries)} hashes")
    return entries, licences


# ------------------------------------------------------------------------------------------------ the inventory
def inventory(req_path=REQ, lock_path=LOCK, licences=None, online=False, previous=None):
    direct = {canon(r["name"]) for r in parse_requirements(req_path)} if os.path.isfile(req_path) else set()
    source = lock_path if os.path.isfile(lock_path) else req_path
    old = {canon(p["name"]): p for p in (previous or {}).get("packages", [])}
    rows = []
    for r in parse_requirements(source):
        n = canon(r["name"]); have = installed_version(r["name"])
        lic = (licences or {}).get(n) or (installed_licence(r["name"]) if have == r["version"] else "")
        if not lic and old.get(n, {}).get("version") == r["version"]: lic = old[n].get("licence", "")
        if not lic and online and r["version"]:
            try: lic = pypi_licence(pypi(r["name"], r["version"])["info"])
            except Exception: lic = ""
        rows.append({"name": r["name"], "version": r["version"] or r["spec"], "kind": "direct" if n in direct else "transitive", "only_when": r["marker"],
                     "licence": lic or "not recorded (package not installed here; run with --online)", "hashes": len(r["hashes"]),
                     "build_environment": "installed, same version" if have == r["version"] else (f"installed in another version ({have})" if have else "not installed")})
    return {"made": datetime.date.today().isoformat(), "python": platform.python_version(), "platform": f"{sys.platform} {platform.machine()}",
            "source": os.path.relpath(source, ROOT).replace(os.sep, "/"), "hashes": bool(rows) and all(r["hashes"] for r in rows), "packages": rows}


def audit(lock_path=LOCK, online=False, python=None):
    """{'tool', 'ran', 'outcome', 'findings': [...]} - the real result, or why it was not run. python: the interpreter
    that has pip-audit (a tools environment), when it is not this one."""
    python = python or sys.executable
    try: has_pip_audit = subprocess.run([python, "-m", "pip_audit", "--version"], capture_output=True, text=True).returncode == 0
    except Exception: has_pip_audit = False
    locked = [r for r in parse_requirements(lock_path) if r["version"]]
    if has_pip_audit:
        cmd = [python, "-m", "pip_audit", "-r", lock_path, "--disable-pip", "--format", "json", "--progress-spinner", "off"]
        if lock_has_hashes(lock_path): cmd.append("--require-hashes")
        r = subprocess.run(cmd, capture_output=True, text=True)
        try:
            data = json.loads(r.stdout); deps = data.get("dependencies", data) if isinstance(data, dict) else data
            found = [{"name": d["name"], "version": d.get("version", ""), "id": v.get("id", ""), "fix": ", ".join(v.get("fix_versions") or [])} for d in deps for v in d.get("vulns", [])]
            ver = subprocess.run([python, "-m", "pip_audit", "--version"], capture_output=True, text=True).stdout.strip()
            seen = {canon(d["name"]) for d in deps}; rest = [x for x in locked if canon(x["name"]) not in seen]; left = []      # packages for another system: pip-audit leaves them out
            for x in rest:
                try:
                    if not online: raise OSError("offline")
                    for v in pypi(x["name"], x["version"]).get("vulnerabilities") or []:
                        if not v.get("withdrawn"): found.append({"name": x["name"], "version": x["version"], "id": v.get("id", ""), "fix": ", ".join(v.get("fixed_in") or [])})
                except Exception: left.append(x["name"])
            n = len(deps) + len(rest) - len(left)
            more = (f"; {len(rest) - len(left)} of them (for another system: {', '.join(x['name'] for x in rest if x['name'] not in left)}) looked up in the advisory data of pypi.org" if len(rest) > len(left) else "") + \
                   (f"; NOT checked (for another system, and pypi.org was not asked): {', '.join(left)}" if left else "")
            return {"tool": ver or "pip-audit", "ran": True, "checked": n, "outcome": f"{len(found)} known vulnerabilit{'y' if len(found) == 1 else 'ies'} in {n} packages" + more, "findings": found}
        except Exception:
            return {"tool": "pip-audit", "ran": False, "checked": 0, "outcome": "not run: pip-audit ended with an error: " + (r.stderr or r.stdout).strip()[-300:], "findings": []}
    if not online:
        return {"tool": "", "ran": False, "checked": 0, "outcome": "not run: pip-audit is not installed in this Python (python -m pip install pip-audit in a tools environment), and --online was not given for the pypi.org advisory lookup", "findings": []}
    found = []; n = 0
    try:
        for r in locked:
            d = pypi(r["name"], r["version"]); n += 1
            for v in d.get("vulnerabilities") or []:
                if v.get("withdrawn"): continue
                found.append({"name": r["name"], "version": r["version"], "id": v.get("id", ""), "fix": ", ".join(v.get("fixed_in") or [])})
    except Exception as e:
        return {"tool": "pypi.org advisory data", "ran": False, "checked": n, "outcome": f"not run to the end: pypi.org could not be asked ({type(e).__name__}) after {n} of {len(locked)} packages", "findings": found}
    return {"tool": "pypi.org advisory data (the JSON API; pip-audit is not installed)", "ran": True, "checked": n, "outcome": f"{len(found)} known vulnerabilit{'y' if len(found) == 1 else 'ies'} in {n} packages", "findings": found}


def markdown(inv, aud=None):
    L = ["# Dependencies of Origin Plot Studio", "",
         "Generated by `python tools/dependency_inventory.py` - do not edit by hand; run the tool again instead.", "",
         f"- Source: `{inv['source']}` ({len(inv['packages'])} packages: {sum(p['kind'] == 'direct' for p in inv['packages'])} direct, {sum(p['kind'] == 'transitive' for p in inv['packages'])} transitive)",
         f"- Hashes in the lock: {'yes, for every package' if inv['hashes'] else 'NO - run tools/dependency_inventory.py --lock on a connected machine'}",
         f"- Inventory made: {inv['made']} with Python {inv['python']} on {inv['platform']} (the build environment)",
         "- \"Build environment\" says whether that exact version was installed where the tests ran. \"not installed\" means: pinned and",
         "  hashed, but not run there - it must be checked on Windows before a release.", "",
         "| Package | Version | Kind | Only when | Licence (as declared by the package) | Build environment |", "| --- | --- | --- | --- | --- | --- |"]
    for p in inv["packages"]:
        L.append(f"| {p['name']} | {p['version']} | {p['kind']} | {('`' + p['only_when'] + '`') if p['only_when'] else ''} | {p['licence'].replace('|', '/')} | {p['build_environment']} |")
    L += ["", "## Vulnerability check", ""]
    if aud is None: L.append("Not part of this run. `python tools/dependency_inventory.py --audit` runs it.")
    else:
        L.append(f"- Run on {inv['made']}: {aud['outcome']}" + (f" (tool: {aud['tool']})" if aud.get("tool") else ""))
        for f in aud["findings"]: L.append(f"  - {f['name']} {f['version']}: {f['id']}" + (f" (fixed in {f['fix']})" if f["fix"] else ""))
        L.append("- A result of this kind says what the advisory database knew on that day about these exact versions. It is not a statement that the packages are free of faults.")
    L += ["", "## Changing a version", "",
          "1. Edit the pin in `origin_plot_app/requirements.txt` (always `==`).",
          "2. `python tools/dependency_inventory.py --lock` on a connected machine, then `--audit`.",
          "3. Run the tests with exactly that set installed; review the diff of `requirements.lock`.",
          "4. Commit `requirements.txt`, `requirements.lock`, `docs/DEPENDENCIES.md` and `docs/dependencies.json` together.", ""]
    return "\n".join(L)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Dependency inventory, lock file and vulnerability check of Origin Plot Studio")
    ap.add_argument("--lock", action="store_true"); ap.add_argument("--audit", action="store_true"); ap.add_argument("--check", action="store_true")
    ap.add_argument("--online", action="store_true"); ap.add_argument("--out", default=os.path.join(ROOT, "docs"))
    ap.add_argument("--requirements", default=REQ); ap.add_argument("--lockfile", default=LOCK); ap.add_argument("--audit-python", default=None)
    a = ap.parse_args(argv)
    if a.check:
        bad = check(a.requirements, a.lockfile)
        for b in bad: print("PROBLEM  " + b)
        print("requirements: " + ("consistent, every package pinned" + (", lock with hashes" if not bad and lock_has_hashes(a.lockfile) else ", lock WITHOUT hashes") if not bad else f"{len(bad)} problem(s)"))
        return 1 if bad else 0
    licences = None
    if a.lock: _entries, licences = make_lock(a.requirements, a.lockfile)
    os.makedirs(a.out, exist_ok=True); jpath = os.path.join(a.out, "dependencies.json"); mpath = os.path.join(a.out, "DEPENDENCIES.md")
    try: previous = json.load(open(jpath, encoding="utf-8"))
    except Exception: previous = None
    inv = inventory(a.requirements, a.lockfile, licences=licences, online=a.online or a.lock, previous=previous)
    aud = audit(a.lockfile, online=a.online or a.lock, python=a.audit_python) if a.audit else None
    same_set = bool(previous) and previous.get("source") == inv["source"] and [(p["name"], p["version"]) for p in previous.get("packages", [])] == [(p["name"], p["version"]) for p in inv["packages"]]
    if aud is not None and not aud["ran"]:
        print("vulnerability check " + aud["outcome"])
        if same_set and (previous.get("audit") or {}).get("ran"): aud = None                                          # a check that could not run does not wipe the record of one that did
    if aud is None and same_set and previous.get("audit"):
        aud = previous["audit"]; inv_made_for_audit = previous.get("audit_made", previous.get("made"))                # the last check of this same set stays on record
    else: inv_made_for_audit = inv["made"]
    if aud is not None: inv["audit"] = aud; inv["audit_made"] = inv_made_for_audit
    with open(jpath, "w", encoding="utf-8", newline="\n") as f: json.dump(inv, f, indent=1); f.write("\n")
    text = markdown(inv, aud)
    if aud is not None and inv_made_for_audit != inv["made"]: text = text.replace(f"- Run on {inv['made']}:", f"- Run on {inv_made_for_audit}:")
    with open(mpath, "w", encoding="utf-8", newline="\n") as f: f.write(text)
    print(f"{len(inv['packages'])} packages ({sum(p['kind'] == 'direct' for p in inv['packages'])} direct); hashes: {'yes' if inv['hashes'] else 'NO'}")
    if aud is not None: print("vulnerability check: " + aud["outcome"])
    print("wrote " + mpath + " and " + jpath)
    return 0 if aud is None or not aud["findings"] else 2


if __name__ == "__main__":
    sys.exit(main())
