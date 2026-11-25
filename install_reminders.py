"""Install or remove a per-user launchd job for LAUNCHPAD reminders."""
import argparse
import os
import plistlib
import subprocess
import sys
from pathlib import Path

LABEL = "io.launchpad.local-reminders"
root = Path(__file__).resolve().parent
job = Path.home() / "Library" / "LaunchAgents" / (LABEL + ".plist")
domain = f"gui/{os.getuid()}"
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("action", choices=["install","uninstall"])
args = parser.parse_args()
invoke = lambda *parts, **kwargs: subprocess.run(["launchctl",*parts], **kwargs)
if args.action == "install":
    job.parent.mkdir(parents=True, exist_ok=True)
    job.write_bytes(plistlib.dumps({
        "Label":LABEL, "ProgramArguments":[sys.executable,str(root/"reminders.py")],
        "WorkingDirectory":str(root), "StartCalendarInterval":[{"Hour":9,"Minute":0},{"Hour":18,"Minute":0}],
        "EnvironmentVariables":{"APP_DATA_DIR":str(Path(os.environ.get("APP_DATA_DIR",root/"data")).expanduser().resolve())},
    }))
    invoke("bootout",domain,str(job),capture_output=True)
    invoke("bootstrap",domain,str(job),check=True)
    print("Notifications scheduled at 09:00 and 18:00 local time.")
else:
    if job.exists():
        invoke("bootout",domain,str(job),capture_output=True)
        job.unlink()
