"""update_regression.py OLD_APP_DIR NEW_APP_DIR
The check the in-app updater makes before it installs a version: NEW_APP_DIR (origin_plot_app of the version to be
published) is compared with OLD_APP_DIR (origin_plot_app of the version people have now) - the same input files must
give the same Origin commands, and no program file of the old version may be missing.
Use a private data folder for it:  OPS_PRIVATE_DIR=$(mktemp -d) python3 tools/update_regression.py OLD NEW
Exit code 0 only when the updater's check says ok and nothing is different or missing."""
import os, sys, warnings
warnings.filterwarnings("ignore"); os.environ.setdefault("QT_QPA_PLATFORM", "offscreen"); os.environ["OPS_NO_OPEN"] = "1"
if len(sys.argv) != 3: print(__doc__); sys.exit(2)
orig, trial = os.path.abspath(sys.argv[1]), os.path.abspath(sys.argv[2])
sys.path.insert(0, trial)
import self_update as U
r = U.check(trial, orig, quick=False)
print("ok:", r["ok"], "| same:", r["same"], "of", r["covered"], "| different:", r["different"])
for line in r["lines"]:
    if "same Origin commands" not in line: print("  ", line[:600])
missing = [f for f in U.program_files(orig) if not os.path.isfile(os.path.join(trial, f))]
print("program files of the old version missing from the new one:", missing)
print("new program files:", len([f for f in U.program_files(trial) if not os.path.isfile(os.path.join(orig, f))]))
sys.exit(0 if r["ok"] and not r["different"] and not missing else 1)
