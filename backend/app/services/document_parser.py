import logging
import os
import re
import tempfile
from typing import Optional

logger = logging.getLogger(__name__)


async def parse_document(filename: str, content_bytes: bytes) -> list[dict]:
    """Parse a document into text chunks for embedding."""
    parser = DocumentParserService()
    chapters = parser.parse_file(content_bytes, filename)

    chunks = []
    for ch in chapters:
        text_chunks = parser.chunk_text(ch["content"])
        for text in text_chunks:
            chunks.append({
                "content": text,
                "chapter_source": ch.get("title"),
                "tokens": text,  # Used for BM25 full-text search
            })
    return chunks


class DocumentParserService:
    """Parse uploaded documents (epub, txt, pdf) into structured chapter chunks."""

    def parse_file(self, content: bytes, filename: str) -> list[dict]:
        """Dispatch parsing by file extension.

        Returns list of dicts: [{"title": str, "content": str}, ...]
        """
        ext = os.path.splitext(filename)[1].lower()

        if ext == ".epub":
            return self._parse_epub(content)
        elif ext == ".txt":
            return self._parse_txt(content)
        elif ext == ".pdf":
            return self._parse_pdf(content)
        else:
            raise ValueError(f"Unsupported file type: {ext}")

    def chunk_text(
        self, text: str, chunk_size: int = 500, overlap: int = 50
    ) -> list[str]:
        """Split text into chunks with overlap. Hard split for segments > chunk_size."""
        if not text or not text.strip():
            return []

        chunks = []
        start = 0
        text_len = len(text)

        while start < text_len:
            end = start + chunk_size
            chunk = text[start:end]
            if chunk.strip():
                chunks.append(chunk)
            start = end - overlap

        return chunks

    # ─── Private Methods ───────────────────────────────────────────────

    def _parse_epub(self, content: bytes) -> list[dict]:
        """Parse EPUB file using ebooklib + BeautifulSoup.

        ebooklib doesn't accept BytesIO, so we write to a temp file.
        """
        import ebooklib
        from ebooklib import epub
        from bs4 import BeautifulSoup

        chapters = []

        # Write to temp file since ebooklib requires a file path
        with tempfile.NamedTemporaryFile(suffix=".epub", delete=False) as tmp:
            tmp.write(content)
            tmp_path = tmp.name

        try:
            book = epub.read_epub(tmp_path)
            chapter_num = 0

            for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
                soup = BeautifulSoup(item.get_content(), "html.parser")
                text = soup.get_text(separator="\n", strip=True)

                if not text or len(text.strip()) < 50:
                    continue

                chapter_num += 1
                # Try to extract title from headings
                title = None
                heading = soup.find(["h1", "h2", "h3"])
                if heading:
                    title = heading.get_text(strip=True)

                chapters.append(
                    {
                        "title": title or f"Chapter {chapter_num}",
                        "content": text,
                    }
                )
        finally:
            os.unlink(tmp_path)

        logger.info("Parsed EPUB: %d chapters extracted", len(chapters))
        return chapters

    def _parse_txt(self, content: bytes) -> list[dict]:
        """Parse plain text file as a single chapter."""
        text = content.decode("utf-8", errors="replace")
        chapters = [{"title": "Full Text", "content": text}]
        logger.info("Parsed TXT: %d characters", len(text))
        return chapters

    def _parse_pdf(self, content: bytes) -> list[dict]:
        """Parse PDF using PyPDF2, splitting by chapter markers."""
        import io

        from PyPDF2 import PdfReader

        reader = PdfReader(io.BytesIO(content))
        full_text = ""
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                full_text += page_text + "\n"

        if not full_text.strip():
            return []

        # Split by chapter markers: 第X章, Chapter X, or numbered patterns like "1."
        chapter_pattern = re.compile(
            r"(?=(?:^|\n)\s*(?:\u7b2c[\u4e00-\u9fa5\d]+\u7ae0|Chapter\s+\d+|\d+\.)\s*)"
        )
        parts = chapter_pattern.split(full_text)

        chapters = []
        for i, part in enumerate(parts):
            part = part.strip()
            if not part or len(part) < 50:
                continue

            # Extract title from first line
            lines = part.split("\n", 1)
            title = lines[0].strip() if lines else f"Section {i + 1}"
            chapter_content = lines[1].strip() if len(lines) > 1 else part

            chapters.append({"title": title, "content": chapter_content})

        # If no chapters were split, treat as single document
        if not chapters:
            chapters = [{"title": "Full Document", "content": full_text}]

        logger.info("Parsed PDF: %d chapters extracted", len(chapters))
        return chapters
