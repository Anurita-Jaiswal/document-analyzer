import os
import tempfile
import pytest
from backend.app.services.document_parser.parser import DocumentParserService

def test_txt_parser():
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as f:
        f.write("DocuMind AI Test Document\nLine 1: High performance document intelligence.\nLine 2: Grounded citation verification.")
        f_path = f.name

    try:
        pages = DocumentParserService.extract_document(f_path, "text/plain")
        assert len(pages) >= 1
        assert "DocuMind AI Test Document" in pages[0].text
        assert pages[0].page_number == 1
    finally:
        if os.path.exists(f_path):
            os.remove(f_path)

def test_unsupported_file_format():
    with pytest.raises(ValueError):
        DocumentParserService.extract_document("test.exe", "application/x-msdownload")
