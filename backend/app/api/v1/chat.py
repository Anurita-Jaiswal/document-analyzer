from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from backend.app.db.session import get_db
from backend.app.models import User, ChatSession, Message, MessageCitation, Document
from backend.app.schemas.chat import (
    ChatSessionCreate,
    ChatSessionOut,
    MessageCreate,
    MessageOut,
    CitationOut
)
from backend.app.api.deps import get_current_user
from backend.app.services.retrieval.retriever import retriever_service
from backend.app.services.generation.generator import generator_service

router = APIRouter()

@router.post("/sessions", response_model=ChatSessionOut, status_code=status.HTTP_201_CREATED)
def create_session(
    session_in: ChatSessionCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    session = ChatSession(
        user_id=current_user.id,
        title=session_in.title or "Research Chat"
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return ChatSessionOut(
        id=session.id,
        title=session.title,
        created_at=session.created_at,
        updated_at=session.updated_at,
        messages=[]
    )

@router.get("/sessions", response_model=List[ChatSessionOut])
def list_sessions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    sessions = db.query(ChatSession).filter(
        ChatSession.user_id == current_user.id
    ).order_by(ChatSession.updated_at.desc()).all()

    results = []
    for s in sessions:
        msgs = db.query(Message).filter(Message.session_id == s.id).order_by(Message.created_at.asc()).all()
        msg_outs = []
        for m in msgs:
            cits = db.query(MessageCitation).filter(MessageCitation.message_id == m.id).all()
            msg_outs.append(MessageOut(
                message_id=m.id,
                role=m.role,
                content=m.content,
                grounding_status=m.grounding_status,
                trace_id=m.trace_id,
                citations=[
                    CitationOut(
                        id=c.id,
                        chunk_id=c.chunk_id,
                        document_id=c.document_id,
                        filename=c.document_name,
                        page=c.page_number,
                        excerpt=c.excerpt
                    ) for c in cits
                ],
                created_at=m.created_at
            ))
        results.append(ChatSessionOut(
            id=s.id,
            title=s.title,
            created_at=s.created_at,
            updated_at=s.updated_at,
            messages=msg_outs
        ))
    return results

@router.get("/sessions/{session_id}", response_model=ChatSessionOut)
def get_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    session = db.query(ChatSession).filter(
        ChatSession.id == session_id,
        ChatSession.user_id == current_user.id
    ).first()

    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found or access denied.")

    msgs = db.query(Message).filter(Message.session_id == session.id).order_by(Message.created_at.asc()).all()
    msg_outs = []
    for m in msgs:
        cits = db.query(MessageCitation).filter(MessageCitation.message_id == m.id).all()
        msg_outs.append(MessageOut(
            message_id=m.id,
            role=m.role,
            content=m.content,
            grounding_status=m.grounding_status,
            trace_id=m.trace_id,
            citations=[
                CitationOut(
                    id=c.id,
                    chunk_id=c.chunk_id,
                    document_id=c.document_id,
                    filename=c.document_name,
                    page=c.page_number,
                    excerpt=c.excerpt
                ) for c in cits
            ],
            created_at=m.created_at
        ))

    return ChatSessionOut(
        id=session.id,
        title=session.title,
        created_at=session.created_at,
        updated_at=session.updated_at,
        messages=msg_outs
    )

@router.delete("/sessions/{session_id}", status_code=status.HTTP_200_OK)
def delete_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    session = db.query(ChatSession).filter(
        ChatSession.id == session_id,
        ChatSession.user_id == current_user.id
    ).first()

    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found or access denied.")

    db.delete(session)
    db.commit()
    return {"message": "Session deleted."}

@router.post("/sessions/{session_id}/messages", response_model=MessageOut)
def post_message(
    session_id: str,
    msg_in: MessageCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    session = db.query(ChatSession).filter(
        ChatSession.id == session_id,
        ChatSession.user_id == current_user.id
    ).first()

    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found or access denied.")

    # 1. Save User question message
    user_msg = Message(
        session_id=session.id,
        role="user",
        content=msg_in.question.strip(),
        grounding_status="user_query"
    )
    db.add(user_msg)
    db.commit()

    # Update session title if default
    if session.title == "New Research Session" or session.title == "Research Chat":
        words = msg_in.question.strip().split()
        session.title = " ".join(words[:6]) + ("..." if len(words) > 6 else "")
        db.commit()

    # 2. Retrieve grounded passages
    retrieved_chunks = retriever_service.retrieve_chunks(
        db=db,
        query=msg_in.question,
        user_id=current_user.id,
        document_ids=msg_in.document_ids
    )

    # 3. Generate grounded answer
    gen_result = generator_service.answer_question(msg_in.question, retrieved_chunks)

    # 4. Save Assistant message
    assistant_msg = Message(
        session_id=session.id,
        role="assistant",
        content=gen_result.answer,
        grounding_status=gen_result.grounding_status,
        trace_id=gen_result.trace_id
    )
    db.add(assistant_msg)
    db.commit()
    db.refresh(assistant_msg)

    # 5. Save Citations
    citation_outs = []
    for cit in gen_result.citations:
        mc = MessageCitation(
            message_id=assistant_msg.id,
            chunk_id=cit.get("chunk_id"),
            document_id=cit["document_id"],
            document_name=cit["filename"],
            page_number=cit["page"],
            excerpt=cit["excerpt"]
        )
        db.add(mc)
        db.commit()
        db.refresh(mc)
        citation_outs.append(CitationOut(
            id=mc.id,
            chunk_id=mc.chunk_id,
            document_id=mc.document_id,
            filename=mc.document_name,
            page=mc.page_number,
            excerpt=mc.excerpt
        ))

    return MessageOut(
        message_id=assistant_msg.id,
        role=assistant_msg.role,
        content=assistant_msg.content,
        grounding_status=assistant_msg.grounding_status,
        trace_id=assistant_msg.trace_id,
        citations=citation_outs,
        created_at=assistant_msg.created_at
    )
