import base64
import csv
import io
import re
from datetime import date
from core import db, rows, chat
from documents import extract
import gmail

PORT = 8503
STAGES = ["Interested", "Preparing", "Applied", "Online assessment", "Technical interview",
          "HR interview", "Offer", "Rejected", "Withdrawn"]
FIELDS = ("company", "role", "location", "url", "stipend", "deadline", "followup", "notes", "tags", "priority", "stage")


def initialize():
    with db() as con:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS applications(id INTEGER PRIMARY KEY, company TEXT, role TEXT, location TEXT,
          url TEXT, stipend TEXT, deadline TEXT, followup TEXT, notes TEXT, tags TEXT, priority TEXT, stage TEXT,
          created TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS transitions(id INTEGER PRIMARY KEY, application INTEGER REFERENCES applications ON DELETE CASCADE,
          stage TEXT, created TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS cvs(id INTEGER PRIMARY KEY, name TEXT, text TEXT);
        CREATE TABLE IF NOT EXISTS practice(id INTEGER PRIMARY KEY, application INTEGER REFERENCES applications ON DELETE SET NULL,
          topic TEXT, question TEXT, mistake TEXT, score REAL, minutes REAL, created TEXT DEFAULT CURRENT_TIMESTAMP);
        """)


def save(con, p):
    values = [str(p.get(key, "")).strip() for key in FIELDS]
    if not all(values[:2]):
        raise ValueError("Company and role are required.")
    values[-1] = values[-1] or STAGES[0]
    if values[-1] not in STAGES:
        raise ValueError("Invalid stage.")
    for key in ("deadline", "followup"):
        if p.get(key):
            date.fromisoformat(p[key])
    previous = None
    if p.get("id"):
        app = int(p["id"])
        row = con.execute("SELECT stage FROM applications WHERE id=?", (app,)).fetchone()
        if not row:
            raise ValueError("Application missing.")
        previous = row[0]
        con.execute("UPDATE applications SET " + ",".join(key+"=?" for key in FIELDS) + " WHERE id=?", (*values,app))
    else:
        query = "INSERT INTO applications(" + ",".join(FIELDS) + ") VALUES(" + ",".join("?" for _ in FIELDS) + ")"
        app = con.execute(query, values).lastrowid
    if values[-1] != previous:
        con.execute("INSERT INTO transitions(application,stage) VALUES(?,?)", (app, values[-1]))
    return app


def assist(p):
    with db() as con:
        cv = con.execute("SELECT text FROM cvs WHERE id=?", (int(p.get("cv") or 0),)).fetchone()
        app = con.execute("SELECT company,role,notes FROM applications WHERE id=?", (int(p.get("application") or 0),)).fetchone()
    evidence = "[CV]\n" + (cv[0][:4300] if cv else "") + "\n[Application]\n" + (
        " | ".join(app) if app else "") + "\n[Job description]\n" + p.get("description", "")[:3200]
    for token in chat(p["prompt"], evidence, p.get("model")):
        yield {"token": token}


def handle(action, p, post):
    if not post and action == "gmail-status":
        return {"configured":bool(gmail.os.environ.get("LAUNCHPAD_GOOGLE_CLIENT")),
                "connected":gmail.TOKEN_PATH.exists()}
    if post and action in {"gmail-connect","gmail-inbox","gmail-disconnect"}:
        return {"gmail-connect":lambda:gmail.begin(int(p["port"])), "gmail-inbox":gmail.inbox,
                "gmail-disconnect":gmail.disconnect}[action]()
    if not post:
        with db() as con:
            return {
                "applications": lambda: rows(con, "SELECT * FROM applications ORDER BY id DESC"),
                "history": lambda: rows(con, "SELECT transitions.*,company,role FROM transitions JOIN applications ON application=applications.id ORDER BY transitions.id DESC"),
                "cvs": lambda: rows(con, "SELECT * FROM cvs ORDER BY id DESC"),
                "practice": lambda: rows(con, "SELECT practice.*,company FROM practice LEFT JOIN applications ON application=applications.id ORDER BY practice.id DESC"),
                "stages": lambda: STAGES,
            }[action]()
    if action == "assist":
        return assist(p)
    with db() as con:
        if action == "save":
            return {"id": save(con,p)}
        if action == "import":
            data = list(csv.DictReader(io.StringIO(p["csv"].lstrip("\ufeff"))))
            for item in data:
                save(con,item)
            return {"imported": len(data)}
        if action == "delete":
            con.execute("DELETE FROM applications WHERE id=?", (int(p["id"]),))
        elif action == "cv":
            text = "\n".join(text for _,text in extract(p["name"], base64.b64decode(p["data"], validate=True))).strip()
            if not text:
                raise ValueError("No selectable text found in the CV.")
            con.execute("INSERT INTO cvs(name,text) VALUES(?,?)", (p["name"],text))
        elif action == "delete-cv":
            con.execute("DELETE FROM cvs WHERE id=?", (int(p["id"]),))
        elif action == "match":
            cv = con.execute("SELECT text FROM cvs WHERE id=?", (int(p["cv"]),)).fetchone()
            if not cv:
                raise ValueError("Select a CV.")
            tokenize = lambda value: set(re.findall(r"[a-z][a-z0-9+#.]*", value.lower()))
            requirements = [word.strip() for word in p["skills"].split(",") if word.strip()]
            if not requirements:
                raise ValueError("Enter comma-separated required skills.")
            cv_words = tokenize(cv[0])
            matched = [skill for skill in requirements if tokenize(skill) and tokenize(skill) <= cv_words]
            missing = [skill for skill in requirements if skill not in matched]
            return {"score": round(len(matched)*100/len(requirements)), "matched": matched, "missing": missing}
        elif action == "practice":
            score, minutes = float(p.get("score") or 0), float(p.get("minutes") or 0)
            if not (0 <= score <= 100 and 0 <= minutes <= 1440):
                raise ValueError("Invalid score or duration.")
            con.execute("INSERT INTO practice(application,topic,question,mistake,score,minutes) VALUES(?,?,?,?,?,?)",
                        (int(p["application"]) if p.get("application") else None, p["topic"], p["question"],
                         p.get("mistake",""), score, minutes))
        else:
            raise ValueError("Unknown action.")
    return {"ok": True}
