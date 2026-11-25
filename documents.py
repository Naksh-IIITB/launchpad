import csv
import io
import json
import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree

SUFFIXES = {".pdf", ".pptx", ".docx", ".txt", ".md", ".csv", ".ipynb"}


def extract(filename, content):
    suffix = Path(filename).suffix.lower()
    if suffix == ".pdf":
        try:
            from pypdf import PdfReader
        except ImportError as error:
            raise ValueError("Install pypdf using the supplied requirements file.") from error
        pdf = PdfReader(io.BytesIO(content))
        return [(f"page {i}", page.extract_text() or "") for i, page in enumerate(pdf.pages, 1)]
    if suffix in {".pptx", ".docx"}:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            if suffix == ".docx":
                files = ["word/document.xml"]
            else:
                files = sorted((name for name in archive.namelist() if re.fullmatch(r"ppt/slides/slide\d+.xml", name)),
                               key=lambda name: int(re.search(r"(\d+)\.xml$", name)[1]))
            output = []
            for index, name in enumerate(files, 1):
                if archive.getinfo(name).file_size > 12_000_000:
                    raise ValueError("Document XML exceeds 12 MB.")
                root = ElementTree.fromstring(archive.read(name))
                text = " ".join(node.text for node in root.iter() if node.tag.endswith("}t") and node.text)
                output.append((f"slide {index}" if suffix == ".pptx" else "document", text))
            return output
    if suffix not in SUFFIXES:
        raise ValueError("Unsupported file type.")
    text = content.decode("utf-8-sig", errors="replace")
    if suffix == ".ipynb":
        return [(f"cell {i}", "".join(cell.get("source", [])))
                for i, cell in enumerate(json.loads(text).get("cells", []), 1)]
    if suffix == ".csv":
        text = "\n".join(" | ".join(row) for row in csv.reader(io.StringIO(text)))
    return [("text", text)]


def chunks(sections, width=1400):
    for label, text in sections:
        text = text.strip()
        for offset in range(0, len(text), width - 150):
            yield label, text[offset:offset+width]
            if offset + width >= len(text):
                break
