"""Save documents to disk: markdown + styled HTML + PDF.

Two tools share the same writer:
- ``render_resume`` (legacy name, kept for backwards compatibility) calls
  ``_write_document`` with filename="resume".
- ``save_document`` (new) lets the agent pick any filename — useful for cover
  letters, motivation letters, plain notes alongside the resume in the same dir.

A third tool, ``render_pdf``, converts a single HTML file (or a raw HTML string)
to PDF without going through markdown. Use it when you already have a polished
HTML page and just want a PDF copy.

Output layout (per slug + timestamp):

    data/applications/<YYYYMMDD-HHMMSS>-<slug>/
    ├── <filename>.md      (source markdown, if provided)
    ├── <filename>.html    (styled HTML)
    └── <filename>.pdf     (PDF; only when weasyprint imports cleanly)

WeasyPrint requires system libs (pango, cairo, fontconfig) on macOS via
``brew install pango``. If the import fails the markdown + html still get written
and the tool reports ``pdf_path: null`` with an install hint instead of crashing.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any

import markdown as md_lib

from pyapi.config import ToolConfig, find_data_dir

from .args import string_arg

logger = logging.getLogger("pyapi.tools.render")

RESUME_CSS = """
@page { size: A4; margin: 18mm 16mm; }
body { font-family: -apple-system, "Helvetica Neue", Arial, sans-serif; font-size: 10.5pt; line-height: 1.45; color: #222; max-width: 720px; margin: 0 auto; padding: 24px; }
h1 { font-size: 22pt; margin: 0 0 4px; color: #111; }
h2 { font-size: 13pt; margin: 18px 0 6px; padding-bottom: 3px; border-bottom: 1px solid #ccc; color: #1a1a1a; letter-spacing: 0.5px; text-transform: uppercase; }
h3 { font-size: 11.5pt; margin: 10px 0 2px; color: #222; }
p  { margin: 4px 0; }
ul { margin: 4px 0 8px 18px; padding: 0; }
li { margin: 2px 0; }
a  { color: #1d4ed8; text-decoration: none; }
hr { border: 0; border-top: 1px solid #ddd; margin: 8px 0; }
strong { color: #111; }
code { font-family: ui-monospace, "SF Mono", Menlo, monospace; font-size: 9.8pt; background: #f5f5f5; padding: 1px 3px; border-radius: 3px; }
"""

INVALID_FILENAME_CHARS = re.compile(r"[^a-zA-Z0-9._-]")


def run_render_resume(
    config: ToolConfig,
    arguments: dict[str, Any],
    current_session_id: str | None = None,
) -> str:
    return _save_markdown_doc(arguments, default_filename="resume")


def run_save_document(
    config: ToolConfig,
    arguments: dict[str, Any],
    current_session_id: str | None = None,
) -> str:
    filename = string_arg(arguments, "filename", "").strip()
    if not filename:
        raise ValueError("filename is required (e.g. 'cover_letter' — no extension)")
    return _save_markdown_doc(arguments, default_filename=filename)


def run_render_pdf(
    config: ToolConfig,
    arguments: dict[str, Any],
    current_session_id: str | None = None,
) -> str:
    """Render HTML → PDF. Accepts either ``html_path`` (existing file) or ``html`` (string).

    If ``html_path`` is given the PDF is written next to it as ``<stem>.pdf``.
    If only ``html`` (string) is given, ``slug`` + ``filename`` are required and
    the PDF lands under ``data/applications/<timestamp>-<slug>/<filename>.pdf``.
    """
    html_path_arg = string_arg(arguments, "html_path", "").strip()
    html_arg = string_arg(arguments, "html", "").strip()

    if html_path_arg:
        src = Path(html_path_arg).expanduser()
        if not src.is_file():
            raise ValueError(f"html_path does not exist: {src}")
        pdf_path = src.with_suffix(".pdf")
        ok, error = _write_pdf(src.read_text(), pdf_path)
        return _pdf_result(pdf_path, ok, error)

    if not html_arg:
        raise ValueError("provide either html_path (existing file) or html (string)")

    slug = _slugify(string_arg(arguments, "slug", ""))
    filename = _sanitize_filename(string_arg(arguments, "filename", ""))
    if not slug or not filename:
        raise ValueError("slug and filename are required when passing raw html")
    out_dir = _make_out_dir(slug)
    pdf_path = out_dir / f"{filename}.pdf"
    ok, error = _write_pdf(html_arg, pdf_path)
    return _pdf_result(pdf_path, ok, error)


def _save_markdown_doc(arguments: dict[str, Any], default_filename: str) -> str:
    markdown_text = string_arg(arguments, "markdown", "").strip()
    if not markdown_text:
        raise ValueError("markdown is required")
    slug = _slugify(string_arg(arguments, "slug", default_filename))
    filename = _sanitize_filename(string_arg(arguments, "filename", default_filename))

    out_dir = _make_out_dir(slug)
    md_path = out_dir / f"{filename}.md"
    html_path = out_dir / f"{filename}.html"
    pdf_path = out_dir / f"{filename}.pdf"

    md_path.write_text(markdown_text)
    body_html = md_lib.markdown(markdown_text, extensions=["extra", "sane_lists"])
    html_doc = (
        "<!doctype html>\n"
        f'<html><head><meta charset="utf-8"><title>{filename}</title>'
        f"<style>{RESUME_CSS}</style></head>"
        f"<body>{body_html}</body></html>"
    )
    html_path.write_text(html_doc)
    pdf_ok, pdf_error = _write_pdf(html_doc, pdf_path)

    payload: dict[str, Any] = {
        "ok": True,
        "slug": slug,
        "filename": filename,
        "markdown_path": str(md_path),
        "html_path": str(html_path),
        "pdf_path": str(pdf_path) if pdf_ok else None,
    }
    if not pdf_ok:
        payload["pdf_error"] = pdf_error
        payload["hint"] = "Open html_path in a browser and Cmd+P → 'Save as PDF'."
    return json.dumps(payload, indent=2)


def _make_out_dir(slug: str) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    out_dir = find_data_dir() / "applications" / f"{timestamp}-{slug}"
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir


def _write_pdf(html: str, pdf_path: Path) -> tuple[bool, str | None]:
    try:
        from weasyprint import HTML  # type: ignore
    except Exception as err:
        logger.warning("weasyprint unavailable: %s", err)
        return False, (
            f"weasyprint not available ({err}). "
            "Install: `brew install pango` then `uv pip install weasyprint`."
        )
    try:
        HTML(string=html).write_pdf(str(pdf_path))
    except Exception as err:
        logger.warning("weasyprint render failed: %s", err)
        return False, f"weasyprint render failed: {err}"
    return True, None


def _pdf_result(pdf_path: Path, ok: bool, error: str | None) -> str:
    payload: dict[str, Any] = {
        "ok": ok,
        "pdf_path": str(pdf_path) if ok else None,
    }
    if not ok:
        payload["error"] = error
        payload["hint"] = "Open the HTML in a browser and Cmd+P → 'Save as PDF'."
    return json.dumps(payload, indent=2)


def _slugify(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower()).strip("-")
    return (cleaned or "resume")[:60]


def _sanitize_filename(value: str) -> str:
    cleaned = INVALID_FILENAME_CHARS.sub("_", value.strip()).strip("._-")
    return (cleaned or "document")[:80]
