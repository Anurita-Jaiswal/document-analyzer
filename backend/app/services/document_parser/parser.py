import os
from typing import List
from pydantic import BaseModel

class ExtractedPage(BaseModel):
    page_number: int
    text: str
    character_count: int

class DocumentParserService:
    @staticmethod
    def parse_pdf(file_path: str) -> List[ExtractedPage]:
        pages: List[ExtractedPage] = []
        try:
            import fitz  # PyMuPDF
            doc = fitz.open(file_path)
            for page_idx in range(len(doc)):
                page = doc[page_idx]
                text = page.get_text("text").strip()
                pages.append(ExtractedPage(
                    page_number=page_idx + 1,
                    text=text,
                    character_count=len(text)
                ))
            doc.close()
        except Exception as e:
            # Fallback to pypdf if fitz encounters an issue
            try:
                from pypdf import PdfReader
                reader = PdfReader(file_path)
                for page_idx, page in enumerate(reader.pages):
                    text = (page.extract_text() or "").strip()
                    pages.append(ExtractedPage(
                        page_number=page_idx + 1,
                        text=text,
                        character_count=len(text)
                    ))
            except Exception as inner_e:
                raise ValueError(f"Failed to parse PDF document: {str(e)} / {str(inner_e)}")
        
        return pages

    @staticmethod
    def parse_docx(file_path: str) -> List[ExtractedPage]:
        try:
            import docx
            doc = docx.Document(file_path)
            full_text = []
            for para in doc.paragraphs:
                if para.text.strip():
                    full_text.append(para.text.strip())
            
            for table in doc.tables:
                for row in table.rows:
                    row_data = [cell.text.strip() for cell in row.cells if cell.text.strip()]
                    if row_data:
                        full_text.append(" | ".join(row_data))

            # Simulate pagination based on paragraph blocks (approx 1800 characters per standard page)
            combined_text = "\n\n".join(full_text)
            if not combined_text:
                return [ExtractedPage(page_number=1, text="", character_count=0)]

            pages = []
            page_size = 1800
            for i in range(0, max(1, len(combined_text)), page_size):
                chunk_page = combined_text[i:i + page_size]
                pages.append(ExtractedPage(
                    page_number=(i // page_size) + 1,
                    text=chunk_page,
                    character_count=len(chunk_page)
                ))
            return pages
        except Exception as e:
            raise ValueError(f"Failed to parse DOCX document: {str(e)}")

    @staticmethod
    def parse_txt(file_path: str) -> List[ExtractedPage]:
        encodings = ["utf-8", "latin-1", "cp1252"]
        content = None
        for enc in encodings:
            try:
                with open(file_path, "r", encoding=enc) as f:
                    content = f.read()
                    break
            except Exception:
                continue
        
        if content is None:
            raise ValueError("Unable to decode TXT file with supported encodings.")

        # TXT pages split by approx 1800 characters or form-feeds
        if "\f" in content:
            raw_pages = content.split("\f")
            pages = [
                ExtractedPage(page_number=idx + 1, text=p.strip(), character_count=len(p.strip()))
                for idx, p in enumerate(raw_pages) if p.strip()
            ]
            return pages or [ExtractedPage(page_number=1, text="", character_count=0)]
        else:
            page_size = 1800
            pages = []
            for i in range(0, max(1, len(content)), page_size):
                chunk_page = content[i:i + page_size]
                pages.append(ExtractedPage(
                    page_number=(i // page_size) + 1,
                    text=chunk_page.strip(),
                    character_count=len(chunk_page.strip())
                ))
            return pages

    @classmethod
    def extract_document(cls, file_path: str, mime_type: str) -> List[ExtractedPage]:
        ext = os.path.splitext(file_path)[1].lower()
        if ext == ".pdf" or "pdf" in mime_type:
            return cls.parse_pdf(file_path)
        elif ext in [".docx", ".doc"] or "word" in mime_type:
            return cls.parse_docx(file_path)
        elif ext in [".txt", ".text"] or "text/plain" in mime_type:
            return cls.parse_txt(file_path)
        else:
            raise ValueError(f"Unsupported file format: {ext}")
