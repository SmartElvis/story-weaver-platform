"""
Export service: generates EPUB and DOCX files from project chapters.
"""

import io
import os
import re
import uuid
import tempfile
from datetime import datetime

from ebooklib import epub


def _strip_markdown(text: str) -> list[dict]:
    """
    Convert markdown text to a list of paragraph dicts with basic formatting.
    Each dict: {"text": str, "bold": bool, "heading": int|None}
    """
    paragraphs = []
    if not text:
        return paragraphs

    for line in text.split("\n"):
        stripped = line.strip()
        if not stripped:
            paragraphs.append({"text": "", "bold": False, "heading": None})
            continue

        # Headings
        heading_match = re.match(r"^(#{1,3})\s+(.+)$", stripped)
        if heading_match:
            level = len(heading_match.group(1))
            paragraphs.append({
                "text": heading_match.group(2),
                "bold": True,
                "heading": level,
            })
            continue

        # Bold markers (**text** or __text__)
        clean = re.sub(r"\*\*(.+?)\*\*", r"\1", stripped)
        clean = re.sub(r"__(.+?)__", r"\1", clean)
        # Italic markers (*text* or _text_)
        clean = re.sub(r"\*(.+?)\*", r"\1", clean)
        clean = re.sub(r"_(.+?)_", r"\1", clean)

        paragraphs.append({"text": clean, "bold": False, "heading": None})

    return paragraphs


def _plain_text(text: str) -> str:
    """Strip all markdown formatting to get plain text."""
    if not text:
        return ""
    clean = re.sub(r"#{1,6}\s+", "", text)
    clean = re.sub(r"\*\*(.+?)\*\*", r"\1", clean)
    clean = re.sub(r"__(.+?)__", r"\1", clean)
    clean = re.sub(r"\*(.+?)\*", r"\1", clean)
    clean = re.sub(r"_(.+?)_", r"\1", clean)
    return clean


def generate_epub(
    title: str,
    author: str,
    description: str | None,
    chapters: list[dict],
) -> bytes:
    """
    Generate an EPUB file from project data.

    Args:
        title: Book title
        author: Author name
        description: Book description/synopsis
        chapters: List of dicts with keys: chapter_number, title, content

    Returns:
        EPUB file as bytes
    """
    book = epub.EpubBook()

    # Metadata
    book_id = str(uuid.uuid4())
    book.set_identifier(book_id)
    book.set_title(title)
    book.set_language("zh")
    book.add_author(author)
    if description:
        book.add_metadata("DC", "description", description)
    book.add_metadata("DC", "date", datetime.now().strftime("%Y-%m-%d"))

    # Default CSS
    style = """
    body { font-family: "Source Han Serif", "Noto Serif CJK SC", serif; line-height: 1.8; }
    h1 { text-align: center; margin: 2em 0 1em; font-size: 1.5em; }
    h2 { margin: 1.5em 0 0.8em; font-size: 1.3em; }
    h3 { margin: 1.2em 0 0.6em; font-size: 1.1em; }
    p { text-indent: 2em; margin: 0.5em 0; }
    .title-page { text-align: center; margin-top: 30%; }
    .title-page h1 { font-size: 2em; margin-bottom: 0.5em; }
    .title-page .author { font-size: 1.2em; color: #555; }
    """
    css = epub.EpubItem(
        uid="style",
        file_name="style/default.css",
        media_type="text/css",
        content=style.encode("utf-8"),
    )
    book.add_item(css)

    # Title page
    title_page = epub.EpubHtml(
        title="封面",
        file_name="title.xhtml",
        lang="zh",
    )
    title_page.content = f"""
    <html><head><link rel="stylesheet" href="style/default.css"/></head>
    <body>
    <div class="title-page">
        <h1>{title}</h1>
        <p class="author">{author}</p>
    </div>
    </body></html>
    """.encode("utf-8")
    title_page.add_item(css)
    book.add_item(title_page)

    # Chapters
    epub_chapters = []
    for ch in chapters:
        ch_num = ch["chapter_number"]
        ch_title = ch.get("title") or f"第{ch_num}章"
        content = ch.get("content") or ""

        # Convert content to HTML paragraphs
        html_paragraphs = []
        for line in content.split("\n"):
            stripped = line.strip()
            if not stripped:
                continue

            heading_match = re.match(r"^(#{1,3})\s+(.+)$", stripped)
            if heading_match:
                level = len(heading_match.group(1))
                html_paragraphs.append(f"<h{level}>{heading_match.group(2)}</h{level}>")
                continue

            # Clean markdown
            clean = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", stripped)
            clean = re.sub(r"__(.+?)__", r"<strong>\1</strong>", clean)
            clean = re.sub(r"\*(.+?)\*", r"<em>\1</em>", clean)
            clean = re.sub(r"_(.+?)_", r"<em>\1</em>", clean)
            html_paragraphs.append(f"<p>{clean}</p>")

        body_html = "\n".join(html_paragraphs)

        epub_ch = epub.EpubHtml(
            title=ch_title,
            file_name=f"chapter_{ch_num:03d}.xhtml",
            lang="zh",
        )
        epub_ch.content = f"""
        <html><head><link rel="stylesheet" href="style/default.css"/></head>
        <body>
        <h1>{ch_title}</h1>
        {body_html}
        </body></html>
        """.encode("utf-8")
        epub_ch.add_item(css)
        book.add_item(epub_ch)
        epub_chapters.append(epub_ch)

    # Table of contents
    book.toc = [epub.Link(ch.file_name, ch.title, ch.id) for ch in epub_chapters]

    # Spine
    book.spine = ["nav", title_page] + epub_chapters

    # Navigation files
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())

    # Write to bytes via temp file (ebooklib requires a file path)
    tmp_fd, tmp_path = tempfile.mkstemp(suffix=".epub")
    os.close(tmp_fd)
    try:
        epub.write_epub(tmp_path, book, {})
        with open(tmp_path, "rb") as f:
            return f.read()
    finally:
        os.unlink(tmp_path)


def generate_docx(
    title: str,
    author: str,
    description: str | None,
    chapters: list[dict],
) -> bytes:
    """
    Generate a DOCX file from project data.

    Args:
        title: Book title
        author: Author name
        description: Book description/synopsis
        chapters: List of dicts with keys: chapter_number, title, content

    Returns:
        DOCX file as bytes
    """
    # Lazy import to avoid startup crash if python-docx not installed
    from docx import Document
    from docx.shared import Pt, Cm, RGBColor
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.enum.style import WD_STYLE_TYPE
    doc = Document()

    # Page margins
    sections = doc.sections
    for section in sections:
        section.top_margin = Cm(2.54)
        section.bottom_margin = Cm(2.54)
        section.left_margin = Cm(3.18)
        section.right_margin = Cm(3.18)

    # --- Custom styles ---
    styles = doc.styles

    # Title style
    title_style = styles.add_style("BookTitle", WD_STYLE_TYPE.PARAGRAPH)
    title_style.font.size = Pt(26)
    title_style.font.bold = True
    title_style.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
    title_style.paragraph_format.space_after = Pt(6)

    # Author style
    author_style = styles.add_style("BookAuthor", WD_STYLE_TYPE.PARAGRAPH)
    author_style.font.size = Pt(14)
    author_style.font.color.rgb = RGBColor(0x55, 0x55, 0x55)
    author_style.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
    author_style.paragraph_format.space_after = Pt(36)

    # Chapter heading style
    ch_heading_style = styles.add_style("ChapterHeading", WD_STYLE_TYPE.PARAGRAPH)
    ch_heading_style.font.size = Pt(18)
    ch_heading_style.font.bold = True
    ch_heading_style.paragraph_format.space_before = Pt(36)
    ch_heading_style.paragraph_format.space_after = Pt(18)
    ch_heading_style.paragraph_format.page_break_before = True

    # Body text style (Chinese novel style with indent)
    body_style = styles.add_style("NovelBody", WD_STYLE_TYPE.PARAGRAPH)
    body_style.font.size = Pt(12)
    body_style.paragraph_format.first_line_indent = Cm(0.74)  # ~2 Chinese chars
    body_style.paragraph_format.line_spacing = 1.8
    body_style.paragraph_format.space_after = Pt(4)

    # --- Title Page ---
    # Add some space before title
    for _ in range(6):
        doc.add_paragraph("", style="Normal")

    doc.add_paragraph(title, style="BookTitle")
    doc.add_paragraph(author, style="BookAuthor")

    if description:
        desc_para = doc.add_paragraph(style="Normal")
        desc_para.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
        desc_run = desc_para.add_run(_plain_text(description))
        desc_run.font.size = Pt(11)
        desc_run.font.color.rgb = RGBColor(0x66, 0x66, 0x66)

    # --- Chapters ---
    for ch in chapters:
        ch_num = ch["chapter_number"]
        ch_title = ch.get("title") or f"第{ch_num}章"
        content = ch.get("content") or ""

        # Chapter heading
        doc.add_paragraph(ch_title, style="ChapterHeading")

        # Content paragraphs
        paragraphs = _strip_markdown(content)
        for para_data in paragraphs:
            text = para_data["text"]
            heading = para_data["heading"]

            if heading:
                # Sub-headings within chapters
                p = doc.add_paragraph(style="Normal")
                p.paragraph_format.space_before = Pt(12)
                p.paragraph_format.space_after = Pt(8)
                run = p.add_run(text)
                run.bold = True
                run.font.size = Pt(14 if heading == 2 else 12)
            elif text == "":
                # Empty line (paragraph break)
                doc.add_paragraph("", style="Normal")
            else:
                # Normal body text
                doc.add_paragraph(text, style="NovelBody")

    # Write to bytes
    output = io.BytesIO()
    doc.save(output)
    output.seek(0)
    return output.read()
