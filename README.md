# DocuMind AI — AI Document Intelligence & Research Assistant

A production-grade, Retrieval-Augmented Generation (RAG) based document intelligence system with page-level provenance, grounded question answering, document summarization, and structured information extraction.

Designed according to the technical blueprint for the **Software Development Engineer (SDE) Intern** project milestone report.

---

## 🌟 Key Features

1. **Multi-Format Ingestion with Provenance**:
   - Supports **PDF**, **DOCX**, and **TXT** files up to 25MB.
   - Extracts page-level text, preserving document identity, page numbers, and structural headings.
2. **Asynchronous Processing Pipeline**:
   - Explicit lifecycle tracking: `uploaded` → `queued` → `processing` → `ready` / `failed`.
   - Chunking with configurable size and overlap.
   - 768-dimensional vector embeddings with cosine similarity search and keyword-boosted hybrid reranking.
3. **Grounded Question Answering**:
   - Evidence-grounded generation: Answers are strictly constrained by retrieved passages.
   - Interactive **Citation Cards**: Displays source document name, page number, and text excerpt.
   - Direct Jump: Clicking any citation navigates to the cited page in the document viewer.
   - Hallucination Prevention: Returns `insufficient_evidence` when queries cannot be answered by the uploaded documents.
4. **Document Intelligence Suite**:
   - **Executive Summaries**: Section-by-section analysis highlighting key findings, risks, and action items.
   - **Structured Information Extraction**: Automatic extraction of dates, amounts, stakeholders, deliverables, and risks into structured JSON.
   - **Multi-Document Research**: Query and compare multiple documents simultaneously with per-document source attribution.
5. **Security & Isolation**:
   - JWT authentication with secure PBKDF2-HMAC password hashing.
   - Strict multi-tenant isolation (users cannot view, retrieve, or delete other users' documents or chats).
   - Instant **1-Click Demo Login** for reviewers and evaluators.

---

## 🛠️ Technology Stack

| Layer | Technology | Rationale |
|---|---|---|
| **Frontend** | Next.js 14+ (React + TypeScript) | Fast SSR/SPA, component architecture, typed contracts |
| **Styling** | Modern Vanilla CSS | Rich dark/light glassmorphic UI, custom animations, zero CSS runtime overhead |
| **API Backend** | Python 3.14 + FastAPI | High throughput async endpoints, automatic OpenAPI/Swagger docs, Pydantic validation |
| **Database** | SQLite / PostgreSQL via SQLAlchemy | Persistent users, documents, chunks, chats, and citations |
| **Document Parsing**| PyMuPDF (`fitz`), `python-docx`, `pypdf` | Fast, page-aware text and metadata extraction |
| **Embeddings & LLM**| Google Gemini API (`text-embedding-004`, `gemini-1.5-flash`) + Smart Offline Semantic Fallback | Works with Gemini API or 100% offline without API keys |
| **Testing** | Pytest | Unit tests, integration tests, RAG evaluation benchmark, security isolation |

---

## 🚀 Quick Start Guide

### 1. Backend Setup

```bash
# Clone or navigate to the repository
cd documind-ai

# Activate your Python virtual environment (if not already active)
# Install dependencies
pip install -r backend/requirements.txt

# Run database tests to verify all 9 test suites pass
python -m pytest backend/tests -v

# Start the FastAPI server
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
```

The interactive API documentation is accessible at:
- Swagger UI: `http://127.0.0.1:8000/api/v1/docs`
- Health check: `http://127.0.0.1:8000/api/v1/health`

### 2. Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:3000` in your browser.

---

## 🧪 Testing & Evaluation

Run the automated test suite:
```bash
python -m pytest backend/tests -v
```

Test coverage includes:
- `test_parser.py`: PDF, DOCX, and TXT parsing with page provenance.
- `test_chunking.py`: Chunk boundary sizing, overlap continuity, and heading detection.
- `test_api.py`: Full end-to-end document upload, background worker, summary, and chat Q&A.
- `test_security.py`: Cross-user tenant isolation and unauthorized access refusal.
- `test_rag.py`: RAG evaluation benchmark (direct lookup, cross-document comparison, out-of-scope refusal).
