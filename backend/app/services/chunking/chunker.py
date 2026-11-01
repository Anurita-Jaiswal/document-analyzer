import re
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from backend.app.core.config import settings
from backend.app.services.document_parser.parser import ExtractedPage

class ChunkItem(BaseModel):
    chunk_index: int
    page_start: int
    page_end: int
    text: str
    document_id: Optional[str] = None
    section_title: Optional[str] = None
    metadata: Dict[str, Any] = {}

class TextChunkerService:
    def __init__(self, chunk_size: int = None, chunk_overlap: int = None):
        self.chunk_size = chunk_size or settings.CHUNK_SIZE
        self.chunk_overlap = chunk_overlap or settings.CHUNK_OVERLAP

    def _detect_heading(self, text: str) -> Optional[str]:
        # Detect markdown or capitalized headings
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        for line in lines[:3]:
            if line.startswith("#") or line.isupper() and len(line) < 60:
                return line.lstrip("#").strip()
            if re.match(r"^(?:Section|\d+\.|\d+\.\d+)\s+", line, re.IGNORECASE):
                return line.strip()
        return None

    def chunk_pages(self, pages: List[ExtractedPage], document_id: str) -> List[ChunkItem]:
        chunks: List[ChunkItem] = []
        chunk_idx = 0

        current_text = ""
        current_page_start = None
        current_page_end = None
        current_heading = None

        for page in pages:
            page_text = page.text.strip()
            if not page_text:
                continue

            page_heading = self._detect_heading(page_text)
            if page_heading and not current_heading:
                current_heading = page_heading

            # If page alone is smaller than chunk_size, we can accumulate
            paragraphs = re.split(r"\n\s*\n", page_text)

            for para in paragraphs:
                cleaned_para = para.strip()
                if not cleaned_para:
                    continue

                if current_page_start is None:
                    current_page_start = page.page_number
                current_page_end = page.page_number

                # Check potential heading in paragraph
                para_heading = self._detect_heading(cleaned_para)
                if para_heading:
                    current_heading = para_heading

                if len(current_text) + len(cleaned_para) + 2 > self.chunk_size:
                    if current_text:
                        chunks.append(ChunkItem(
                            chunk_index=chunk_idx,
                            page_start=current_page_start,
                            page_end=current_page_end,
                            text=current_text.strip(),
                            document_id=document_id,
                            section_title=current_heading,
                            metadata={"document_id": document_id}
                        ))
                        chunk_idx += 1

                        # Keep overlap from the end of current_text
                        overlap_start = max(0, len(current_text) - self.chunk_overlap)
                        overlap_text = current_text[overlap_start:].strip()
                        current_text = (overlap_text + "\n\n" + cleaned_para) if overlap_text else cleaned_para
                        current_page_start = current_page_end
                    else:
                        # Paragraph itself is longer than chunk_size, split by sentences or hard limit
                        sub_chunks = self._split_long_paragraph(cleaned_para, self.chunk_size, self.chunk_overlap)
                        for sub_idx, sub in enumerate(sub_chunks):
                            chunks.append(ChunkItem(
                                chunk_index=chunk_idx,
                                page_start=page.page_number,
                                page_end=page.page_number,
                                text=sub.strip(),
                                document_id=document_id,
                                section_title=current_heading,
                                metadata={"document_id": document_id, "sub_chunk": sub_idx}
                            ))
                            chunk_idx += 1
                        current_text = ""
                        current_page_start = None
                else:
                    if current_text:
                        current_text += "\n\n" + cleaned_para
                    else:
                        current_text = cleaned_para

        # Flush remaining text
        if current_text.strip():
            chunks.append(ChunkItem(
                chunk_index=chunk_idx,
                page_start=current_page_start or (pages[-1].page_number if pages else 1),
                page_end=current_page_end or (pages[-1].page_number if pages else 1),
                text=current_text.strip(),
                document_id=document_id,
                section_title=current_heading,
                metadata={"document_id": document_id}
            ))

        return chunks

    def _split_long_paragraph(self, text: str, max_size: int, overlap: int) -> List[str]:
        words = text.split()
        parts = []
        cur_words = []
        cur_len = 0

        for word in words:
            cur_words.append(word)
            cur_len += len(word) + 1
            if cur_len >= max_size:
                parts.append(" ".join(cur_words))
                # Retain overlap in words
                overlap_words = int(len(cur_words) * (overlap / max_size))
                cur_words = cur_words[-overlap_words:] if overlap_words > 0 else []
                cur_len = sum(len(w) + 1 for w in cur_words)

        if cur_words:
            parts.append(" ".join(cur_words))

        return parts or [text]
