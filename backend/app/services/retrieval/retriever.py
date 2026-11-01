import json
import re
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from backend.app.models import Chunk, Document
from backend.app.services.embeddings.embedder import embedding_service
from backend.app.core.config import settings

class RetrievedChunk(BaseModel := type("RetrievedChunk", (), {})):
    def __init__(self, chunk_id: str, document_id: str, document_name: str, page: int, text: str, score: float, section_title: Optional[str] = None):
        self.chunk_id = chunk_id
        self.document_id = document_id
        self.document_name = document_name
        self.page = page
        self.text = text
        self.score = score
        self.section_title = section_title

    def to_dict(self) -> Dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "document_id": self.document_id,
            "document_name": self.document_name,
            "page": self.page,
            "text": self.text,
            "score": round(self.score, 4),
            "section_title": self.section_title
        }

class DocumentRetrieverService:
    @staticmethod
    def retrieve_chunks(
        db: Session,
        query: str,
        user_id: str,
        document_ids: List[str],
        top_k: int = None
    ) -> List[RetrievedChunk]:
        k = top_k or settings.TOP_K_RETRIEVAL
        if not document_ids:
            return []

        # 1. Enforce user ownership: only query documents belonging to this user
        valid_docs = db.query(Document).filter(
            Document.id.in_(document_ids),
            Document.user_id == user_id,
            Document.status == "ready"
        ).all()

        if not valid_docs:
            return []

        doc_map = {doc.id: doc.original_filename for doc in valid_docs}
        verified_doc_ids = list(doc_map.keys())

        # 2. Fetch all chunks belonging to verified documents
        chunks = db.query(Chunk).filter(Chunk.document_id.in_(verified_doc_ids)).all()
        if not chunks:
            return []

        # 3. Compute query vector
        query_vector = embedding_service.get_embedding(query)

        # 4. Score chunks using Cosine Vector Similarity + Keyword Boost
        query_terms = set(re.findall(r"\b\w{3,}\b", query.lower()))
        scored_candidates = []

        for chunk in chunks:
            chunk_vector = None
            if chunk.embedding_json:
                try:
                    chunk_vector = json.loads(chunk.embedding_json)
                except Exception:
                    pass

            if not chunk_vector:
                chunk_vector = embedding_service.get_embedding(chunk.text)

            # Cosine similarity
            vec_sim = embedding_service.cosine_similarity(query_vector, chunk_vector)

            # Keyword lexical overlap boost (BM25-style term bonus)
            chunk_lower = chunk.text.lower()
            keyword_matches = sum(1 for term in query_terms if term in chunk_lower)
            term_boost = (keyword_matches / max(1, len(query_terms))) * 0.35

            total_score = (vec_sim * 0.65) + term_boost

            doc_name = doc_map.get(chunk.document_id, "Unknown Document")
            scored_candidates.append(
                RetrievedChunk(
                    chunk_id=chunk.id,
                    document_id=chunk.document_id,
                    document_name=doc_name,
                    page=chunk.page_start,
                    text=chunk.text,
                    score=total_score,
                    section_title=chunk.section_title
                )
            )

        # Sort by relevance score descending
        scored_candidates.sort(key=lambda x: x.score, reverse=True)
        return scored_candidates[:k]

retriever_service = DocumentRetrieverService()
