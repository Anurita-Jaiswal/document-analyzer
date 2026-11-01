import pytest
from backend.app.services.chunking.chunker import TextChunkerService
from backend.app.services.document_parser.parser import ExtractedPage

def test_chunking_with_overlap():
    chunker = TextChunkerService(chunk_size=300, chunk_overlap=50)
    
    pages = [
        ExtractedPage(page_number=1, text="Page 1 introduction. This is a comprehensive study of document intelligence and retrieval augmented generation workflows for modern research.", character_count=138),
        ExtractedPage(page_number=2, text="Page 2 methodology. The system parses documents, generates overlapping text chunks, computes dense vector representations, and queries an indexed vector database.", character_count=168)
    ]
    
    chunks = chunker.chunk_pages(pages, document_id="doc_test_123")
    
    assert len(chunks) > 0
    for chunk in chunks:
        assert chunk.document_id == "doc_test_123" or chunk.metadata.get("document_id") == "doc_test_123"
        assert chunk.page_start in [1, 2]
        assert chunk.page_end in [1, 2]
        assert len(chunk.text) > 0

def test_heading_detection():
    chunker = TextChunkerService(chunk_size=500, chunk_overlap=50)
    pages = [
        ExtractedPage(page_number=1, text="# 1. EXECUTIVE SUMMARY\nThis report presents DocuMind AI architecture and evaluation criteria.", character_count=92)
    ]
    chunks = chunker.chunk_pages(pages, document_id="doc_heading_test")
    assert len(chunks) == 1
    assert "EXECUTIVE SUMMARY" in (chunks[0].section_title or "")
