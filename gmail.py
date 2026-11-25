"""Optional, read-only Gmail connection using a user-provided desktop OAuth client."""
import base64
import hashlib
import json
import os
import re
import secrets
import time
from datetime import date
from pathlib import Path
from urllib.parse import urlencode, parse_qs
from urllib.request import Request, urlopen
from core import DATA

TOKEN_URL = "https://oauth2.googleapis.com/token"
SCOPE = "https://www.googleapis.com/auth/gmail.readonly"
TOKEN_PATH = DATA / "gmail-token.json"
PENDING = {}


def client():
    path = os.environ.get("LAUNCHPAD_GOOGLE_CLIENT")
    if not path:
        raise ValueError("Set LAUNCHPAD_GOOGLE_CLIENT to the path of your Google Desktop OAuth client JSON.")
    oauth = json.loads(Path(path).expanduser().read_text()).get("installed")
    if not oauth:
        raise ValueError("Use Google’s Desktop app OAuth client type.")
    return oauth


def token_request(**data):
    data.update(client_id=client()["client_id"], client_secret=client()["client_secret"])
    return remote(TOKEN_URL, data=data)


def remote(url, data=None, token=None):
    headers = {"Authorization": "Bearer " + token} if token else {}
    req = Request(url, data=urlencode(data).encode() if data else None, headers=headers)
    with urlopen(req, timeout=20) as response:
        return json.load(response)


def save_token(value):
    draft = TOKEN_PATH.with_name("gmail-token-" + secrets.token_hex(6))
    with os.fdopen(os.open(draft, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w") as handle:
        value["expires_at"] = time.time() + int(value.get("expires_in", 3600))
        json.dump(value, handle)
    draft.replace(TOKEN_PATH)


def begin(port):
    config = client()
    state, verifier = secrets.token_urlsafe(32), secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
    redirect = "http://127.0.0.1:" + str(port) + "/gmail-oauth"
    now = time.monotonic()
    for key, item in list(PENDING.items()):
        if item[2] < now:
            PENDING.pop(key, None)
    PENDING[state] = (verifier, redirect, now + 600)
    query = urlencode({"client_id":config["client_id"],"response_type":"code","scope":SCOPE,
                       "redirect_uri":redirect,"state":state,"code_challenge":challenge,
                       "code_challenge_method":"S256","access_type":"offline","prompt":"consent"})
    return {"url":"https://accounts.google.com/o/oauth2/v2/auth?" + query}


def callback(query):
    value = parse_qs(query)
    state = value.get("state", [""])[0]
    pending = PENDING.pop(state, None)
    if not pending or pending[2] < time.monotonic() or not value.get("code"):
        return "Gmail authorization expired, was declined, or did not match the connection request.", 400
    try:
        verifier, redirect, _ = pending
        token = token_request(grant_type="authorization_code", code=value["code"][0],
                              code_verifier=verifier, redirect_uri=redirect)
        if token.get("scope") and SCOPE not in token["scope"].split():
            return "Gmail read access was not granted.", 400
        save_token(token)
    except (OSError, KeyError, ValueError):
        return "Gmail authorization failed. Review your Google OAuth client configuration and retry.", 400
    return "Gmail connected. Return to LAUNCHPAD and refresh the inbox.", 200


def access_token():
    if not TOKEN_PATH.exists():
        raise ValueError("Connect Gmail first.")
    old = json.loads(TOKEN_PATH.read_text())
    if old.get("expires_at", 0) > time.time() + 60:
        return old["access_token"]
    if not old.get("refresh_token"):
        raise ValueError("Reconnect Gmail to renew access.")
    value = token_request(grant_type="refresh_token", refresh_token=old["refresh_token"])
    value.setdefault("refresh_token",old["refresh_token"])
    save_token(value)
    return value["access_token"]


def suggest(subject, snippet):
    text = (subject + " " + snippet).lower()
    rules = [
        (r"\b(offer letter|pleased to offer)\b", "Offer"),
        (r"\b(unfortunately|not moving forward|not selected|unsuccessful)\b", "Rejected"),
        (r"\b(hr interview|people team interview)\b", "HR interview"),
        (r"\b(technical interview|live coding interview)\b", "Technical interview"),
        (r"\b(assessment|coding challenge|online test)\b", "Online assessment"),
        (r"\b(application received|thank you for applying)\b", "Applied"),
    ]
    stage = next((stage for pattern,stage in rules if re.search(pattern,text)), "")
    dates = []
    for value in re.findall(r"\b20\d{2}-\d{2}-\d{2}\b",text):
        try:
            dates.append(date.fromisoformat(value).isoformat())
        except ValueError:
            continue
    return {"stage":stage,"dates":sorted(set(dates))}


def inbox():
    token = access_token()
    root = "https://gmail.googleapis.com/gmail/v1/users/me/messages"
    filters = urlencode({"q":"newer_than:45d {interview assessment internship application recruiter offer}","maxResults":25})
    ids = remote(root + "?" + filters, token=token).get("messages", [])
    output = []
    for item in ids:
        msg_id = item["id"]
        if not re.fullmatch(r"[a-zA-Z0-9_-]+",msg_id):
            continue
        query = urlencode([("format","metadata"),("metadataHeaders","Subject"),("metadataHeaders","From"),("metadataHeaders","Date")])
        msg = remote(root + "/" + msg_id + "?" + query,token=token)
        headers = {header["name"].lower():header["value"] for header in msg["payload"].get("headers",[])}
        subject, snippet = headers.get("subject",""), msg.get("snippet","")
        output.append({"subject":subject,"from":headers.get("from",""),"sent":headers.get("date",""),
                       "snippet":snippet,**suggest(subject,snippet)})
    return output


def disconnect():
    if TOKEN_PATH.exists():
        value = json.loads(TOKEN_PATH.read_text())
        token = value.get("refresh_token") or value.get("access_token")
        if token:
            with urlopen(Request("https://oauth2.googleapis.com/revoke", data=urlencode({"token":token}).encode()), timeout=20):
                pass
        TOKEN_PATH.unlink()
    return {"ok":True}
