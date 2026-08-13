"""Parse earnings-forecast direction (预增/预减/扭亏) from cninfo announcement PDFs.

cninfo announcement PDFs live at ``http://static.cninfo.com.cn/finalpage/{date}/{announcementId}.PDF``.
This module downloads the PDF, extracts text via ``pdftotext`` (or pymupdf), and
classifies the forecast direction from the body text.

Direction is a *derived field* (LLM/rule extraction), never a substitute for the
original full text.
"""
from __future__ import annotations

import re
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import requests

PDF_BASE = "http://static.cninfo.com.cn/finalpage"


def announcement_pdf_url(detail_url: str, published_at: str) -> str | None:
    """Derive the PDF URL from a cninfo detail URL + publish date."""
    qs = parse_qs(urlparse(detail_url).query)
    aid = (qs.get("announcementId") or qs.get("announcementid") or [""])[0]
    if not aid:
        return None
    date = str(published_at)[:10]
    return f"{PDF_BASE}/{date}/{aid}.PDF"


def extract_pdf_text(pdf_bytes: bytes) -> str:
    """Extract text from PDF bytes using pdftotext (system) or pymupdf."""
    # try pymupdf first (no subprocess)
    try:
        import fitz

        with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
            return "\n".join(page.get_text() for page in doc)
    except Exception:
        pass
    # fall back to pdftotext
    try:
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            f.write(pdf_bytes)
            tmp = Path(f.name)
        out = tmp.with_suffix(".txt")
        subprocess.run(
            ["pdftotext", "-layout", str(tmp), str(out)],
            capture_output=True, check=True,
        )
        text = out.read_text(encoding="utf-8", errors="replace")
        tmp.unlink(missing_ok=True)
        out.unlink(missing_ok=True)
        return text
    except Exception:
        return ""


def classify_forecast_direction(title: str, body_text: str) -> str:
    """Classify an earnings forecast as 预增 / 预减 / 扭亏 / 续盈 / 首亏 / 续亏 / 未知.

    The direction is determined by the title + the "重要内容提示" block only.
    Scanning the full body is unreliable (e.g. a line about "集成电路业务继续亏损"
    inside an otherwise 预减 forecast would misclassify as 续亏).
    """
    # title-level explicit labels (most reliable)
    if "扭亏" in title:
        return "扭亏"
    if "首亏" in title:
        return "首亏"
    if "续亏" in title:
        return "续亏"
    if "续盈" in title:
        return "续盈"
    if "预增" in title:
        return "预增"
    if "预减" in title:
        return "预减"
    if "预盈" in title:
        return "预盈"
    if "预亏" in title:
        return "预亏"

    # 重要内容提示 block (the headline figures live in the first ~800 chars)
    head = body_text[:800]

    # Checkbox form: "√同向上升" / "☑同向下降" / "☑扭亏为盈" — the checkbox
    # label itself is NOT evidence; only a checked marker (√/☑) counts.
    checked = re.search(r"[√☑✓]\s*(同向上升|同向下降|扭亏为盈|亏损|续盈|续亏)", head)
    if checked:
        marker = checked.group(1)
        if marker == "同向上升":
            return "预增"
        if marker == "同向下降":
            return "预减"
        if marker == "扭亏为盈":
            return "扭亏"
        if marker == "亏损":
            return "首亏"
        if marker == "续盈":
            return "续盈"
        if marker == "续亏":
            return "续亏"

    # explicit 扭亏/首亏/续亏 in the prompt block (NOT checkbox labels)
    if "扭亏为盈" in head and "☑扭亏为盈" not in head and "√扭亏为盈" not in head:
        return "扭亏"
    if "预计亏损" in head or "将出现亏损" in head:
        return "首亏"
    if "预计继续亏损" in head:
        return "续亏"

    # 增加/减少 percentage phrases
    incr = len(re.findall(r"(同比增加|同比上升|同比增长|预增)", head))
    decr = len(re.findall(r"(同比减少|同比下降|同比下滑|预减)", head))
    if decr > incr:
        return "预减"
    if incr > decr:
        return "预增"
    return "未知"


def fetch_and_classify(
    *,
    detail_url: str,
    published_at: str,
    title: str,
    timeout: int = 20,
) -> tuple[str, str]:
    """Download + parse a forecast PDF, returning (direction, body_text)."""
    pdf_url = announcement_pdf_url(detail_url, published_at)
    if not pdf_url:
        return "未知", ""
    try:
        resp = requests.get(pdf_url, timeout=timeout)
        resp.raise_for_status()
    except requests.RequestException:
        return "未知", ""
    text = extract_pdf_text(resp.content)
    if not text:
        return "未知", ""
    return classify_forecast_direction(title, text), text
