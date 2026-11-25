"""Emit macOS notifications for deadlines and follow-ups. Invoke periodically with launchd."""
import argparse
import json
import subprocess
from datetime import date, timedelta
from core import DATA, db, rows
from feature import initialize

SCRIPT = """on run argv
display notification (item 1 of argv) with title (item 2 of argv)
end run"""


def reminder_items(applications, today):
    upper = (today + timedelta(days=2)).isoformat()
    lower = today.isoformat()
    return [(f"{app['id']}:{kind}:{app[field]}", f"{app['company']} · {app['role']}",
             f"{kind} on {app[field]}") for app in applications
            for field,kind in (("deadline","Application deadline"),("followup","Follow-up"))
            if lower <= (app[field] or "") <= upper]


def run(dry_run=False):
    initialize()
    file = DATA / "sent-reminders.json"
    today = date.today()
    already = json.loads(file.read_text()) if file.exists() else {}
    already = {key:value for key,value in already.items() if value >= (today-timedelta(days=14)).isoformat()}
    with db() as con:
        apps = rows(con,"SELECT * FROM applications WHERE stage NOT IN ('Offer','Rejected','Withdrawn')")
    for key,title,message in reminder_items(apps, today):
        if key not in already:
            if dry_run:
                print(f"{title}: {message}")
            else:
                subprocess.run(["osascript","-e",SCRIPT,"--",message,title],check=True,timeout=20)
                already[key] = today.isoformat()
    if not dry_run:
        pending = file.with_suffix(".tmp")
        pending.write_text(json.dumps(already))
        pending.replace(file)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run",action="store_true")
    run(parser.parse_args().dry_run)
