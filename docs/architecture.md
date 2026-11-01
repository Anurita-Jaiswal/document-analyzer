# DocuMind AI — System Architecture & Technical Specifications

DocuMind AI is an AI-powered document intelligence and research assistant built on an asynchronous, provenance-tracked Retrieval-Augmented Generation (RAG) pipeline.

## 1. System Topology & Data Flow

```
                      +-----------------------------+
                      |   Modern Web Client (UI)    |
                      |  Next.js 14+ / React / CSS  |
                      +--------------+--------------+
                                     |
                          HTTPS / JSON (REST API)
                                     |
                      +--------------v--------------+
                      |        FastAPI Layer        |
                      |  Auth, Validation, Routing  |
                      +-------+--------------+------+
                              |              |
           +------------------v--+        +--v------------------+
           |     PostgreSQL      |        |  Background Worker  |
           |   (SQLite local)    |        |  Parsing & Indexing |
           | Users, Docs, Chunks |        +--+---------------+--+
           | Chats & Citations   |           |               |
           +---------------------+    +------v-----+   +-----v------+
                                      | Storage    |   | Vector     |
                                      | Local/S3   |   | Store      |
                                      +------------+   +------------+
                                             |
                                      +------v------+
                                      |   Gemini    |
                                      | Embed & Gen |
                                      +-------------+
```

## 2. Ingestion & Provenance Pipeline
1. **File Validation**: File extension (.pdf, .docx, .txt), MIME type, and size limits (< 25MB) enforced server-side.
2. **Page Extraction**:
   - PDF: PyMuPDF (`fitz`) with per-page text & bounding metadata (with `pypdf` fallback).
   - DOCX: `python-docx` extracting paragraph & table blocks.
   - TXT: Multi-encoding safe reading (`utf-8`, `latin-1`).
3. **Chunking**: Sentence & paragraph aware sliding window (~800 characters, 150 overlap). Preserves `page_start`, `page_end`, `chunk_index`, and detected headings.
4. **Vector Embedding**: 768-dimensional embeddings generated via Gemini `text-embedding-004` (or deterministic normalized semantic projection when operating in offline/local zero-key mode).

## 3. Grounded Retrieval & Generation
- **User Ownership Isolation**: Retrieval strictly filters chunks by `Document.user_id == current_user.id` and selected `document_ids`. Cross-tenant data leakage is structurally impossible.
- **Hybrid Retrieval**: Combines cosine vector similarity (65% weight) with keyword term frequency boost (35% weight) for high retrieval precision.
- **Strict Grounding Contract**:
  - The model is instructed to answer *only* from supplied evidence.
  - Returns `insufficient_evidence` when no relevant content is found.
  - Links every assertion to a `Citation` card displaying `filename`, `page`, and verbatim text `excerpt`.
  - Clicking on any citation card navigates directly to that page in the document viewer.

## 4. Evaluation & Quality Metrics
- Unit test coverage across chunking, parsers, and security boundaries.
- Cross-user tenant isolation tested and verified.
- End-to-end RAG benchmark testing direct retrieval, multi-document cross-synthesis, and refusal on out-of-domain prompts.
