"""
setup.pyw - the installer of Origin Plot Studio (started by Setup.bat).

What it does, in a window that shows each step:
  1. installs the Python packages the app needs (only the missing ones),
  2. copies the program into  %LOCALAPPDATA%\\Programs\\Origin Plot Studio  (your settings there are kept),
  3. puts a shortcut with the app's icon on the Desktop and in the Start menu,
  4. adds "Origin Plot Studio" to Windows' list of installed apps, so it can be removed there.
Nothing needs administrator rights: everything is installed for the current user only.

    pythonw setup.pyw              install (or install again over an older version)
    pythonw setup.pyw --uninstall  remove the shortcuts, the entry in Windows and the program folder
"""
import os, sys, shutil, subprocess, threading, queue, traceback

APP = "Origin Plot Studio"
KEY = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\OriginPlotStudio"
PACKAGES = [("pywin32", "win32com"), ("numpy", "numpy"), ("pandas", "pandas"), ("openpyxl", "openpyxl"), ("matplotlib", "matplotlib"), ("xlrd", "xlrd"), ("python-calamine", "python_calamine"), ("certifi", "certifi"), ("scipy", "scipy"), ("tzdata", "tzdata"), ("PySide6", "PySide6")]
KEEP = ("settings.json", "settings_modern.json", "last_session.json", "last_run_log.txt")                     # yours: never overwritten by an install
SKIP_DIRS = ("__pycache__", "dry_out", ".git")
WIN = os.name == "nt"
HERE = os.path.dirname(os.path.abspath(__file__))
NOWIN = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def install_dir():
    base = os.environ.get("LOCALAPPDATA") or os.path.join(os.path.expanduser("~"), ".local", "share")
    return os.path.join(base, "Programs", APP)

def python_exe(windowed=False):
    """python.exe for installing packages, pythonw.exe for starting the app without a console."""
    d = os.path.dirname(sys.executable); want = "pythonw.exe" if windowed else "python.exe"
    p = os.path.join(d, want)
    return p if os.path.isfile(p) else sys.executable

def version(folder):
    import re
    try:
        m = re.search(r'^VERSION\s*=\s*["\']([^"\']+)["\']', open(os.path.join(folder, "smart_plots.py"), encoding="utf-8").read(), re.M); return m.group(1) if m else ""
    except Exception: return ""

def vkey(v):
    import re
    return tuple(int(x) for x in re.findall(r"\d+", str(v))[:4]) or (0,)

def missing_packages():
    import importlib.util
    out = []
    for pip_name, module in PACKAGES:
        if module == "win32com" and not WIN: continue
        try:
            if importlib.util.find_spec(module) is None: out.append(pip_name)
        except Exception: out.append(pip_name)
    return out

def copy_program(src, dst, say):
    """Copy the program files. Returns the number of files copied. Your settings in the folder are kept."""
    n = 0
    if os.path.abspath(src) == os.path.abspath(dst): return 0
    for base, dirs, files in os.walk(src):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        rel = os.path.relpath(base, src); out = os.path.join(dst, rel) if rel != "." else dst; os.makedirs(out, exist_ok=True)
        for f in files:
            t = os.path.join(out, f)
            if rel == "." and f in KEEP and os.path.exists(t): continue
            if f in ("console_output.txt", "startup_error.txt") or f.endswith(".pyc"): continue
            shutil.copy2(os.path.join(base, f), t); n += 1
            if n % 5 == 0: say(f"Copying the program … {n} files")
    shutil.rmtree(os.path.join(dst, "__pycache__"), ignore_errors=True)
    return n

def ps_quote(s): return "'" + str(s).replace("'", "''") + "'"

def shortcut_script(dst, desktop=True, startmenu=True):
    """The PowerShell lines that make the shortcuts. The Desktop is asked from Windows, so a Desktop kept in OneDrive is found too."""
    target, script, icon = python_exe(True), os.path.join(dst, "start.pyw"), os.path.join(dst, "app.ico")
    L = ["$ErrorActionPreference = 'Stop'", "$w = New-Object -ComObject WScript.Shell", "$places = @()"]
    if desktop: L.append("$places += [Environment]::GetFolderPath('Desktop')")
    if startmenu: L.append("$places += [Environment]::GetFolderPath('Programs')")
    L += ["foreach ($p in $places) {", f"  $s = $w.CreateShortcut((Join-Path $p {ps_quote(APP + '.lnk')}))", f"  $s.TargetPath = {ps_quote(target)}", "  $s.Arguments = " + ps_quote('"' + script + '"'),
          f"  $s.WorkingDirectory = {ps_quote(dst)}", f"  $s.IconLocation = {ps_quote(icon)}", "  $s.Description = 'Turn measurement files into publication-ready plots'", "  $s.Save()", "}"]
    return "\n".join(L)

def remove_shortcuts_script():
    return "\n".join(["foreach ($p in @([Environment]::GetFolderPath('Desktop'), [Environment]::GetFolderPath('Programs'))) {", f"  $f = Join-Path $p {ps_quote(APP + '.lnk')}", "  if (Test-Path $f) { Remove-Item $f -Force }", "}"])

def powershell(script):
    r = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script], capture_output=True, text=True, creationflags=NOWIN, timeout=120)
    if r.returncode != 0: raise RuntimeError((r.stderr or r.stdout or "PowerShell failed").strip()[-600:])

def register(dst):
    """The entry in Settings > Apps > Installed apps (for this user)."""
    import winreg
    size = sum(os.path.getsize(os.path.join(b, f)) for b, _, fs in os.walk(dst) for f in fs) // 1024
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, KEY) as k:
        for name, val in (("DisplayName", APP), ("DisplayVersion", version(dst) or "1"), ("Publisher", APP), ("InstallLocation", dst), ("DisplayIcon", os.path.join(dst, "app.ico")),
                          ("UninstallString", f'"{python_exe(True)}" "{os.path.join(dst, "setup.pyw")}" --uninstall')):
            winreg.SetValueEx(k, name, 0, winreg.REG_SZ, val)
        for name, val in (("NoModify", 1), ("NoRepair", 1), ("EstimatedSize", int(size))): winreg.SetValueEx(k, name, 0, winreg.REG_DWORD, val)

def unregister():
    try:
        import winreg; winreg.DeleteKey(winreg.HKEY_CURRENT_USER, KEY)
    except Exception: pass


# ---------------------------------------------------------------------------------------------- the window
def window(uninstall=False):
    import tkinter as tk
    from tkinter import ttk, messagebox
    BG, INK, SOFT, ACC, LINE, OK = "#FFFFFF", "#172B4D", "#526277", "#2563EB", "#D8E1EC", "#15803D"
    root = tk.Tk(); root.title(("Remove " if uninstall else "Install ") + APP); root.configure(bg=BG); root.resizable(False, False)
    try: root.iconbitmap(os.path.join(HERE, "app.ico"))
    except Exception: pass
    W = 560                                              # the height follows the content, so nothing is cut off at any text size
    try: root.minsize(W, 0); root.geometry(f"+{(root.winfo_screenwidth() - W) // 2}+{max(20, (root.winfo_screenheight() - 520) // 3)}")
    except Exception: pass
    st = ttk.Style()
    try: st.theme_use("clam")
    except Exception: pass
    F = "Segoe UI"
    st.configure(".", background=BG, foreground=INK, font=(F, 10)); st.configure("TFrame", background=BG); st.configure("TLabel", background=BG)
    st.configure("TCheckbutton", background=BG, indicatorbackground="#FFFFFF", indicatorforeground=ACC, upperbordercolor="#CBD5E1", lowerbordercolor="#CBD5E1", focuscolor=BG); st.map("TCheckbutton", background=[("active", BG)])
    st.configure("Link.TButton", background=BG, foreground=SOFT, bordercolor=BG, lightcolor=BG, darkcolor=BG, padding=(4, 7), font=(F, 9)); st.map("Link.TButton", background=[("active", BG)], foreground=[("active", "#B91C1C")])
    st.configure("Horizontal.TProgressbar", background=ACC, troughcolor=LINE, bordercolor=LINE, lightcolor=ACC, darkcolor=ACC, thickness=8)
    st.configure("Go.TButton", background=ACC, foreground="white", font=(F, 10, "bold"), padding=(18, 7), bordercolor=ACC, lightcolor=ACC, darkcolor=ACC); st.map("Go.TButton", background=[("disabled", "#BFD0F5"), ("active", "#1D4FD0")])
    st.configure("TButton", padding=(14, 7), background="#FFFFFF", bordercolor="#CBD5E1"); st.map("TButton", background=[("active", "#F8FAFC")])
    f = ttk.Frame(root, padding=24); f.pack(fill="both", expand=True)
    ttk.Frame(f, width=W - 48, height=1).pack()                 # keeps the width of the window
    ttk.Label(f, text="ORIGIN PLOT STUDIO", foreground=ACC, font=(F, 8, "bold")).pack(anchor="w")
    dst = install_dir(); src_v = version(HERE); old_v = version(dst) if os.path.isdir(dst) else ""
    # What this Setup is about to do depends on what is already on the computer.
    if uninstall: mode = "remove"
    elif not old_v: mode = "install"
    elif vkey(src_v) > vkey(old_v): mode = "update"
    elif vkey(src_v) == vkey(old_v): mode = "repair"
    else: mode = "older"
    title_ = {"remove": "Remove " + APP, "install": "Install " + APP, "update": "Update " + APP, "repair": APP + " is already installed", "older": "A newer version is already installed"}[mode]
    text_ = {"remove": "This removes the app, its shortcuts and its entry in Windows.\nYour results and saved sessions in your own folders are not touched.",
             "install": f"Version {src_v}. It is installed for you only; no administrator rights are needed.",
             "update": f"Version {old_v} is installed on this computer.\nUpdate it to version {src_v}? Your settings, AI link and sessions are kept.",
             "repair": f"Version {old_v} is installed, the same as this Setup.\nYou can install it again over itself (this repairs missing or damaged files), or close this window.",
             "older": f"Version {old_v} is installed, which is newer than this Setup (version {src_v}).\nClose this window to keep it. Installing would put the older version back."}[mode]
    verb = {"remove": "Remove", "install": "Install", "update": "Update", "repair": "Install again", "older": f"Install the older version {src_v}"}[mode]
    doing = {"remove": "Removing", "install": "Installing", "update": "Updating", "repair": "Installing", "older": "Installing"}[mode]
    root.title(title_)
    head = tk.StringVar(value=title_); ttk.Label(f, textvariable=head, font=(F, 16, "bold"), wraplength=W - 48, justify="left").pack(anchor="w", pady=(2, 2))
    sub = tk.StringVar(value=text_)
    ttk.Label(f, textvariable=sub, foreground=SOFT, wraplength=W - 48, justify="left").pack(anchor="w", pady=(0, 14))
    names = (["Remove the shortcuts", "Remove the entry in Windows", "Remove the program"] if uninstall else
             ["Check Python", "Install the packages the app needs", "Replace the program with the new version" if mode == "update" else "Copy the program", "Create the shortcuts", "Add the app to Windows' list of apps"])
    marks = []
    for n_ in names:
        r = ttk.Frame(f); r.pack(fill="x", pady=2); m = ttk.Label(r, text="○", foreground="#94A3B8", width=2, font=(F, 11)); m.pack(side="left"); l = ttk.Label(r, text=n_, foreground=SOFT); l.pack(side="left"); marks.append((m, l))
    bar = ttk.Progressbar(f, mode="determinate", maximum=100); bar.pack(fill="x", pady=(16, 6))
    line = tk.StringVar(value="Ready."); ttk.Label(f, textvariable=line, foreground=SOFT, wraplength=W - 48, justify="left").pack(anchor="w")
    desk = tk.BooleanVar(value=True); launch = tk.BooleanVar(value=True)
    opt = ttk.Frame(f); opt.pack(fill="x", pady=(14, 0))
    desk_box = ttk.Checkbutton(opt, text="Put a shortcut on the Desktop", variable=desk)
    if not uninstall: desk_box.pack(anchor="w")
    launch_box = ttk.Checkbutton(opt, text=f"Start {APP} now", variable=launch)
    bottom = ttk.Frame(f); bottom.pack(fill="x", pady=(16, 0))
    q = queue.Queue(); state = {"running": False, "done": False, "failed": False}
    def say(text): q.put(("line", text))
    def step(i, how): q.put(("step", i, how))                  # how: "now", "ok", "skip", "bad"
    def work_install():
        try:
            step(0, "now"); say(f"Python {sys.version.split()[0]}")
            if sys.version_info < (3, 9): raise RuntimeError(f"Python {sys.version.split()[0]} is too old: version 3.9 or newer is needed. Install it from python.org and run Setup again.")
            step(0, "ok"); q.put(("bar", 8)); step(1, "now"); miss = missing_packages()
            if not miss: say("Every package is already installed.")
            for i, p in enumerate(miss, 1):
                say(f"Installing {p} ({i} of {len(miss)}) … this can take a minute")
                r = subprocess.run([python_exe(), "-m", "pip", "install", "--quiet", "--disable-pip-version-check", "--no-warn-script-location", p], capture_output=True, text=True, creationflags=NOWIN)
                if r.returncode != 0 and p not in ("python-calamine", "xlrd", "certifi"): raise RuntimeError(f"The package {p} could not be installed. Is the computer online?\n{(r.stderr or r.stdout).strip()[-400:]}")
                q.put(("bar", 8 + 52 * i / len(miss)))
            step(1, "ok"); q.put(("bar", 60)); step(2, "now"); n = copy_program(HERE, dst, say); say(f"{n} files copied to {dst}" if n else f"The program is already in {dst}"); step(2, "ok"); q.put(("bar", 82))
            step(3, "now")
            if WIN: powershell(shortcut_script(dst, desktop=desk.get(), startmenu=True)); say("Shortcut on the Desktop and in the Start menu." if desk.get() else "Shortcut in the Start menu."); step(3, "ok")
            else: say("Shortcuts are made on Windows only."); step(3, "skip")
            q.put(("bar", 92)); step(4, "now")
            if WIN: register(dst); step(4, "ok")
            else: step(4, "skip")
            q.put(("bar", 100)); q.put(("done", (f"{APP} is updated to version {version(dst)}." if mode == "update" else f"{APP} {version(dst)} is installed."), "Start it from the shortcut on your Desktop or from the Start menu." if desk.get() else "Start it from the Start menu."))
        except Exception as e: q.put(("fail", str(e) or traceback.format_exc()[-500:]))
    def work_uninstall():
        try:
            step(0, "now")
            if WIN: powershell(remove_shortcuts_script())
            step(0, "ok"); q.put(("bar", 30)); step(1, "now"); unregister(); step(1, "ok"); q.put(("bar", 55)); step(2, "now")
            if os.path.isdir(dst) and os.path.abspath(dst) != os.path.abspath(HERE): shutil.rmtree(dst, ignore_errors=True)
            elif WIN and os.path.isdir(dst):                  # this file is inside the folder: Windows removes it a moment after this window has closed
                subprocess.Popen(f'cmd /c ping -n 3 127.0.0.1 >nul & rmdir /s /q "{dst}"', shell=True, creationflags=NOWIN, cwd=os.path.expanduser("~"))
            step(2, "ok"); q.put(("bar", 100)); q.put(("done", f"{APP} is removed.", "Your results and sessions in your own folders are still there."))
        except Exception as e: q.put(("fail", str(e)))
    def pump():
        try:
            while True:
                m = q.get_nowait()
                if m[0] == "line": line.set(m[1])
                elif m[0] == "bar": bar.configure(value=m[1])
                elif m[0] == "step":
                    mk, lb = marks[m[1]]; how = m[2]
                    mk.configure(text={"now": "●", "ok": "✓", "skip": "–", "bad": "✕"}[how], foreground={"now": ACC, "ok": OK, "skip": "#94A3B8", "bad": "#B91C1C"}[how]); lb.configure(foreground=INK if how in ("now", "ok") else SOFT)
                elif m[0] == "done":
                    state.update(running=False, done=True); head.set(m[1]); sub.set(m[2]); line.set(""); go.configure(text="Finish", state="normal"); cancel.pack_forget()
                    try: remove.pack_forget()
                    except Exception: pass
                    if not uninstall: desk_box.pack_forget(); launch_box.pack(anchor="w")
                elif m[0] == "fail":
                    state.update(running=False, failed=True); head.set({"remove": "The removal did not finish", "update": "The update did not finish"}.get(mode, "The install did not finish")); line.set(m[1]); go.configure(text="Try again", state="normal")
                    for mk, lb in marks:
                        if mk.cget("text") == "●": mk.configure(text="✕", foreground="#B91C1C")
        except queue.Empty: pass
        root.after(80, pump)
    def start():
        if state["done"]:
            if not uninstall and launch.get():
                try: subprocess.Popen([python_exe(True), os.path.join(dst, "start.pyw")], cwd=dst, creationflags=NOWIN)
                except Exception as e: messagebox.showinfo(APP, f"I could not start the app ({e}). Use the shortcut.")
            root.destroy(); return
        if state["running"]: return
        state.update(running=True, failed=False); go.configure(state="disabled", text=doing + "\u2026"); head.set(doing + " " + APP + " \u2026"); bar.configure(value=2)
        try: remove.pack_forget()
        except Exception: pass
        threading.Thread(target=work_uninstall if uninstall else work_install, daemon=True).start()
    def close():
        if state["running"] and not messagebox.askyesno(APP, "The install is still running. Close anyway?"): return
        root.destroy()
    go = ttk.Button(bottom, text=verb, style="TButton" if mode == "older" else "Go.TButton", command=start); go.pack(side="right")
    cancel = ttk.Button(bottom, text="Close" if mode in ("repair", "older") else "Cancel", command=close); cancel.pack(side="right", padx=8)
    def to_remove():
        """From the update screen to removing the app instead."""
        root.destroy(); window(uninstall=True).mainloop()
    remove = ttk.Button(bottom, text="Remove the app instead\u2026", style="Link.TButton", cursor="hand2", command=to_remove)
    if mode in ("update", "repair", "older"): remove.pack(side="left")
    root.protocol("WM_DELETE_WINDOW", close); root.bind("<Return>", lambda e: start()); pump()
    if "--auto" in sys.argv: root.after(300, start)            # for tests: press Install by itself
    return root


if __name__ == "__main__":
    window(uninstall="--uninstall" in sys.argv).mainloop()
