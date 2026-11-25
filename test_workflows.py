import base64
import importlib
import io
import os
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
os.environ["APP_DATA_DIR"] = tempfile.mkdtemp(prefix="pis-test-")
import atexit
import shutil
atexit.register(shutil.rmtree, os.environ["APP_DATA_DIR"])
feature = importlib.import_module("feature")
from core import db


def put(action, **data):
    return feature.handle(action, data, True)


def get(action):
    return feature.handle(action, {}, False)


def encoded(value):
    return base64.b64encode(value).decode()


class Workflows(unittest.TestCase):
    def setUp(self):
        feature.initialize()

    @unittest.skipUnless(feature.PORT == 8501, "CORTEX")
    def test_document_search_review_and_restart(self):
        data = {"name":"test-course.md","subject":"Test signals","data":encoded(b"Fourier analysis transforms a signal.")}
        imported = put("import", **data)
        self.assertTrue(put("import", **data)["duplicate"])
        self.assertEqual(put("search", query="Fourier", subject="Test signals")[0]["doc"],imported["id"])
        self.assertEqual(put("original", id=imported["id"])["data"],data["data"])
        put("card", question="Define Fourier transform",answer="An integral transform")
        card = get("cards")[0]
        put("review",id=card["id"],remembered=True)
        feature.initialize()
        self.assertEqual(get("cards")[0]["interval_days"],2)
        put("edge",source="Fourier",target="LTI",relation="analyzes")
        self.assertEqual(get("graph")[0]["target"],"LTI")
        put("delete-doc",id=imported["id"])
        self.assertFalse(put("search",query="Fourier"))

    @unittest.skipUnless(feature.PORT == 8502, "CODE ATLAS")
    def test_zip_index_analysis_search_and_secret_exclusion(self):
        raw = io.BytesIO()
        source = "import math\n\ndef scale(value):\n    if value > 0:\n        return math.sqrt(value)\n"
        with zipfile.ZipFile(raw,"w") as archive:
            archive.writestr("fixture/app.py",source)
            archive.writestr("../outside.py","raise RuntimeError")
            archive.writestr("fixture/credentials.py","password=123")
            archive.writestr("fixture/node_modules/hidden.js","const hidden=1")
        repo=put("zip",name="test-fixture.zip",data=encoded(raw.getvalue()))["id"]
        data=put("overview",repo=repo)
        self.assertEqual(data["languages"],{"Python":1})
        self.assertEqual(data["symbols"][0]["complexity"],2)
        self.assertTrue(any(edge["to"]=="math.sqrt" for edge in data["edges"]))
        self.assertEqual(put("search",repo=repo,query="scale")[0]["start"],1)
        self.assertEqual(put("source",repo=repo,path="fixture/app.py")["code"],source)
        feature.initialize()
        self.assertEqual(get("repos")[0]["id"],repo)

    @unittest.skipUnless(feature.PORT == 8503, "LAUNCHPAD")
    def test_tracking_csv_cv_practice_and_restart(self):
        app=put("save",company="Test Co",role="Intern",deadline="2027-01-01")["id"]
        put("save",id=app,company="Test Co",role="Intern",stage="Applied")
        self.assertEqual([item["stage"] for item in get("history")],["Applied","Interested"])
        with self.assertRaises(ValueError):
            put("import",csv="company,role\nFixture,Intern\nMissing role,\n")
        self.assertEqual(len(get("applications")),1)
        put("cv",name="test.txt",data=encoded(b"Skills: Python, SQL."))
        self.assertEqual(put("match",cv=get("cvs")[0]["id"],skills="Python,Rust")["score"],50)
        put("practice",application=app,topic="SQL",question="Write a join",score=85,minutes=20)
        feature.initialize()
        self.assertEqual(get("practice")[0]["score"],85)
        put("delete",id=app)
        self.assertIsNone(get("practice")[0]["application"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
