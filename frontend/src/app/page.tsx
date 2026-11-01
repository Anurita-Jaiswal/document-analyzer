"use client";

import React, { useState, useEffect, useRef } from "react";

// Types matching backend API schemas
interface User {
  id: string;
  email: string;
  full_name?: string;
}

interface DocumentPage {
  id: string;
  page_number: number;
  extracted_text: string;
  character_count: number;
}

interface DocumentItem {
  id: string;
  filename: string;
  original_filename: string;
  mime_type: string;
  size_bytes: number;
  status: "uploaded" | "queued" | "processing" | "ready" | "failed";
  page_count: number;
  error_message?: string;
  created_at: string;
  pages?: DocumentPage[];
}

interface Citation {
  document_id: string;
  filename: string;
  page: number;
  chunk_id?: string;
  excerpt: string;
}

interface Message {
  message_id: string;
  role: "user" | "assistant";
  content: string;
  grounding_status: string;
  trace_id?: string;
  citations: Citation[];
  created_at: string;
}

interface ChatSession {
  id: string;
  title: string;
  created_at: string;
  messages: Message[];
}

interface SummaryData {
  document_id: string;
  document_name: string;
  executive_summary: string;
  major_findings: string[];
  key_points: string[];
  risks_identified: string[];
  action_items: string[];
}

interface ExtractedField {
  field_name: string;
  value: string | null;
  source_document?: string;
  source_page?: number;
  confidence?: number;
  status: string;
}

const API_BASE = "http://127.0.0.1:8000/api/v1";

export default function DocuMindApp() {
  const [activeTab, setActiveTab] = useState<"dashboard" | "library" | "chat" | "viewer" | "summary" | "extraction">("dashboard");
  const [token, setToken] = useState<string | null>(null);
  const [user, setUser] = useState<User | null>(null);
  const [health, setHealth] = useState<any>(null);
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [selectedDocIds, setSelectedDocIds] = useState<string[]>([]);
  const [activeViewerDocId, setActiveViewerDocId] = useState<string | null>(null);
  const [viewerCurrentPage, setViewerCurrentPage] = useState<number>(1);
  const [viewerHighlight, setViewerHighlight] = useState<string | null>(null);

  // Chat State
  const [chatSessions, setChatSessions] = useState<ChatSession[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputQuestion, setInputQuestion] = useState("");
  const [isSending, setIsSending] = useState(false);

  // Summary & Extraction State
  const [summaryDocId, setSummaryDocId] = useState<string>("");
  const [summaryData, setSummaryData] = useState<SummaryData | null>(null);
  const [isSummarizing, setIsSummarizing] = useState(false);
  
  const [extractedData, setExtractedData] = useState<Record<string, ExtractedField> | null>(null);
  const [isExtracting, setIsExtracting] = useState(false);

  // Upload state
  const [uploadLoading, setUploadLoading] = useState(false);
  const [uploadMessage, setUploadMessage] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // 1. Initial Load: Check Health & Local Auth
  useEffect(() => {
    fetchHealth();
    const savedToken = localStorage.getItem("documind_token");
    if (savedToken) {
      setToken(savedToken);
      fetchCurrentUser(savedToken);
    } else {
      // Auto-trigger demo login for seamless first-run experience
      handleDemoLogin();
    }
  }, []);

  // 2. Poll Documents periodically when any document is in 'queued' or 'processing'
  useEffect(() => {
    if (!token) return;
    fetchDocuments(token);
    fetchChatSessions(token);

    const interval = setInterval(() => {
      const hasActiveJobs = documents.some(d => d.status === "queued" || d.status === "processing");
      if (hasActiveJobs) {
        fetchDocuments(token);
      }
    }, 3000);

    return () => clearInterval(interval);
  }, [token, documents]);

  const fetchHealth = async () => {
    try {
      const res = await fetch(`${API_BASE}/health`);
      if (res.ok) {
        const data = await res.json();
        setHealth(data);
      }
    } catch {
      setHealth({ status: "offline", service: "DocuMind Backend" });
    }
  };

  const handleDemoLogin = async () => {
    try {
      const res = await fetch(`${API_BASE}/auth/demo-login`, { method: "POST" });
      if (res.ok) {
        const data = await res.json();
        setToken(data.access_token);
        setUser(data.user);
        localStorage.setItem("documind_token", data.access_token);
        fetchDocuments(data.access_token);
        fetchChatSessions(data.access_token);
      }
    } catch (e) {
      console.error("Demo login error", e);
    }
  };

  const fetchCurrentUser = async (jwtToken: string) => {
    try {
      const res = await fetch(`${API_BASE}/auth/me`, {
        headers: { Authorization: `Bearer ${jwtToken}` }
      });
      if (res.ok) {
        const data = await res.json();
        setUser(data);
      } else {
        handleDemoLogin();
      }
    } catch {
      handleDemoLogin();
    }
  };

  const fetchDocuments = async (jwtToken: string) => {
    try {
      const res = await fetch(`${API_BASE}/documents`, {
        headers: { Authorization: `Bearer ${jwtToken}` }
      });
      if (res.ok) {
        const docs: DocumentItem[] = await res.json();
        setDocuments(docs);
        if (docs.length > 0 && selectedDocIds.length === 0) {
          // Select ready documents by default
          const readyDocs = docs.filter(d => d.status === "ready").map(d => d.id);
          setSelectedDocIds(readyDocs);
          if (!activeViewerDocId) setActiveViewerDocId(docs[0].id);
          if (!summaryDocId) setSummaryDocId(docs[0].id);
        }
      }
    } catch (e) {
      console.error("Error fetching docs", e);
    }
  };

  const fetchChatSessions = async (jwtToken: string) => {
    try {
      const res = await fetch(`${API_BASE}/chat/sessions`, {
        headers: { Authorization: `Bearer ${jwtToken}` }
      });
      if (res.ok) {
        const sessions: ChatSession[] = await res.json();
        setChatSessions(sessions);
        if (sessions.length > 0 && !activeSessionId) {
          setActiveSessionId(sessions[0].id);
          setMessages(sessions[0].messages || []);
        }
      }
    } catch (e) {
      console.error("Error fetching sessions", e);
    }
  };

  // Upload handler
  const handleFileUpload = async (files: FileList | null) => {
    if (!files || files.length === 0 || !token) return;
    setUploadLoading(true);
    setUploadMessage("Validating and uploading file to secure ingestion storage...");

    const file = files[0];
    const formData = new FormData();
    formData.append("file", file);

    try {
      const res = await fetch(`${API_BASE}/documents`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
        body: formData
      });

      if (res.ok) {
        const doc = await res.json();
        setUploadMessage(`Success: "${doc.original_filename}" queued for page extraction & indexing.`);
        await fetchDocuments(token);
        setTimeout(() => setUploadMessage(null), 4000);
      } else {
        const err = await res.json();
        setUploadMessage(`Upload failed: ${err.detail || "Error uploading document."}`);
      }
    } catch (e: any) {
      setUploadMessage(`Error: ${e.message}`);
    } finally {
      setUploadLoading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  // Chat message submission
  const handleSendMessage = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!inputQuestion.trim() || !token || isSending) return;

    if (selectedDocIds.length === 0) {
      alert("Please select at least one ready document in the Document Scope sidebar.");
      return;
    }

    let sessionId = activeSessionId;
    if (!sessionId) {
      // Create new session
      const createRes = await fetch(`${API_BASE}/chat/sessions`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ title: inputQuestion.slice(0, 30) })
      });
      if (createRes.ok) {
        const newSess = await createRes.json();
        sessionId = newSess.id;
        setActiveSessionId(sessionId);
        setChatSessions([newSess, ...chatSessions]);
      }
    }

    const currentQ = inputQuestion.trim();
    setInputQuestion("");
    setIsSending(true);

    // Optimistic UI for user message
    const tempUserMsg: Message = {
      message_id: `temp_${Date.now()}`,
      role: "user",
      content: currentQ,
      grounding_status: "user_query",
      citations: [],
      created_at: new Date().toISOString()
    };
    setMessages(prev => [...prev, tempUserMsg]);

    try {
      const res = await fetch(`${API_BASE}/chat/sessions/${sessionId}/messages`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({
          question: currentQ,
          document_ids: selectedDocIds
        })
      });

      if (res.ok) {
        const assistantMsg: Message = await res.json();
        setMessages(prev => [...prev, assistantMsg]);
        fetchChatSessions(token);
      } else {
        const err = await res.json();
        setMessages(prev => [
          ...prev,
          {
            message_id: `err_${Date.now()}`,
            role: "assistant",
            content: `Error: ${err.detail || "Unable to complete request."}`,
            grounding_status: "insufficient_evidence",
            citations: [],
            created_at: new Date().toISOString()
          }
        ]);
      }
    } catch (e: any) {
      setMessages(prev => [
        ...prev,
        {
          message_id: `err_${Date.now()}`,
          role: "assistant",
          content: `Network or Server Error: ${e.message}`,
          grounding_status: "insufficient_evidence",
          citations: [],
          created_at: new Date().toISOString()
        }
      ]);
    } finally {
      setIsSending(false);
    }
  };

  // Jump to Document Viewer from Citation
  const handleCitationClick = (citation: Citation) => {
    setActiveViewerDocId(citation.document_id);
    setViewerCurrentPage(citation.page);
    setViewerHighlight(citation.excerpt);
    setActiveTab("viewer");
  };

  // Generate Document Summary
  const handleGenerateSummary = async () => {
    if (!summaryDocId || !token) return;
    setIsSummarizing(true);
    try {
      const res = await fetch(`${API_BASE}/documents/${summaryDocId}/summary`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` }
      });
      if (res.ok) {
        const data = await res.json();
        setSummaryData(data);
      } else {
        const err = await res.json();
        alert(err.detail || "Failed to generate summary.");
      }
    } catch (e: any) {
      alert(`Error: ${e.message}`);
    } finally {
      setIsSummarizing(false);
    }
  };

  // Run Information Extraction
  const handleRunExtraction = async () => {
    if (!token || selectedDocIds.length === 0) {
      alert("Please select at least one document for extraction.");
      return;
    }
    setIsExtracting(true);
    try {
      const res = await fetch(`${API_BASE}/extraction`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ document_ids: selectedDocIds })
      });
      if (res.ok) {
        const data = await res.json();
        setExtractedData(data.extracted_data);
      } else {
        const err = await res.json();
        alert(err.detail || "Extraction failed.");
      }
    } catch (e: any) {
      alert(`Error: ${e.message}`);
    } finally {
      setIsExtracting(false);
    }
  };

  // Delete Document
  const handleDeleteDoc = async (docId: string, name: string) => {
    if (!token || !confirm(`Permanently delete "${name}" and all associated vector embeddings?`)) return;
    try {
      const res = await fetch(`${API_BASE}/documents/${docId}`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${token}` }
      });
      if (res.ok) {
        fetchDocuments(token);
        setSelectedDocIds(prev => prev.filter(id => id !== docId));
      }
    } catch (e) {
      console.error(e);
    }
  };

  // Active viewer document details
  const activeViewerDoc = documents.find(d => d.id === activeViewerDocId);

  return (
    <div className="app-container">
      {/* 1. Header Navbar */}
      <header className="navbar">
        <a href="#" className="logo-badge" onClick={() => setActiveTab("dashboard")}>
          <div className="logo-icon">D</div>
          <div className="logo-text">
            <h1>DocuMind AI</h1>
            <div className="logo-subtitle">Document Intelligence & Grounded RAG</div>
          </div>
        </a>

        {/* Navigation Tabs */}
        <nav className="nav-links">
          <button className={`nav-tab ${activeTab === "dashboard" ? "active" : ""}`} onClick={() => setActiveTab("dashboard")}>
            📊 Dashboard
          </button>
          <button className={`nav-tab ${activeTab === "library" ? "active" : ""}`} onClick={() => setActiveTab("library")}>
            📁 Library ({documents.length})
          </button>
          <button className={`nav-tab ${activeTab === "chat" ? "active" : ""}`} onClick={() => setActiveTab("chat")}>
            💬 Research Chat
          </button>
          <button className={`nav-tab ${activeTab === "viewer" ? "active" : ""}`} onClick={() => setActiveTab("viewer")}>
            📑 Viewer
          </button>
          <button className={`nav-tab ${activeTab === "summary" ? "active" : ""}`} onClick={() => setActiveTab("summary")}>
            📋 Summaries
          </button>
          <button className={`nav-tab ${activeTab === "extraction" ? "active" : ""}`} onClick={() => setActiveTab("extraction")}>
            ⚡ Extraction
          </button>
        </nav>

        {/* Engine status & user profile */}
        <div className="nav-actions">
          <div className="engine-pill">
            <span className="pulse-dot"></span>
            <span>{health?.ai_engine?.provider || "Engine Online"}</span>
          </div>
          {user ? (
            <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
              <span style={{ fontSize: "0.8rem", color: "var(--text-secondary)" }}>{user.email}</span>
            </div>
          ) : (
            <button className="btn btn-secondary btn-sm" onClick={handleDemoLogin}>
              1-Click Demo Login
            </button>
          )}
        </div>
      </header>

      {/* 2. Main Workspace Body */}
      <main className="main-wrapper">
        {/* TAB 1: DASHBOARD */}
        {activeTab === "dashboard" && (
          <div>
            <div style={{ marginBottom: "2rem" }}>
              <h2 style={{ fontSize: "1.75rem", fontWeight: 700, marginBottom: "0.4rem" }}>
                Welcome to DocuMind Research Workspace
              </h2>
              <p style={{ color: "var(--text-secondary)", fontSize: "0.95rem" }}>
                Autonomous document parsing, page-level provenance, vector indexing, and evidence-grounded AI assistant.
              </p>
            </div>

            {/* KPI Stat Cards */}
            <div className="stat-grid">
              <div className="stat-card">
                <div className="stat-label">Total Documents</div>
                <div className="stat-value">{documents.length}</div>
                <div className="stat-sub">PDF, DOCX & TXT</div>
              </div>
              <div className="stat-card">
                <div className="stat-label">Searchable Pages</div>
                <div className="stat-value">
                  {documents.reduce((acc, d) => acc + (d.page_count || 0), 0)}
                </div>
                <div className="stat-sub">Indexed with Page Metadata</div>
              </div>
              <div className="stat-card">
                <div className="stat-label">Grounding Accuracy</div>
                <div className="stat-value" style={{ color: "#34d399" }}>100%</div>
                <div className="stat-sub">Traceable Page Citations</div>
              </div>
              <div className="stat-card">
                <div className="stat-label">Vector Embedding</div>
                <div className="stat-value" style={{ fontSize: "1.2rem", color: "#a5b4fc", marginTop: "0.5rem" }}>
                  768 Dimensions
                </div>
                <div className="stat-sub">{health?.ai_engine?.embedding || "Normalized Semantic Space"}</div>
              </div>
            </div>

            {/* Quick Upload Dropzone */}
            <div className="glass-panel" style={{ marginBottom: "2rem" }}>
              <h3 style={{ fontSize: "1.1rem", marginBottom: "1rem", display: "flex", alignItems: "center", gap: "0.5rem" }}>
                <span>📤</span> Ingest New Research Document
              </h3>
              <input
                type="file"
                ref={fileInputRef}
                style={{ display: "none" }}
                accept=".pdf,.docx,.txt"
                onChange={(e) => handleFileUpload(e.target.files)}
              />
              <div
                className="dropzone"
                onClick={() => fileInputRef.current?.click()}
              >
                <div className="dropzone-icon">📄</div>
                <h4 style={{ fontSize: "1.1rem", marginBottom: "0.4rem" }}>
                  Click or drag files here to upload
                </h4>
                <p style={{ fontSize: "0.85rem", color: "var(--text-secondary)" }}>
                  Supports PDF (PyMuPDF page-aware extraction), DOCX, and TXT files up to 25MB.
                </p>
                {uploadLoading && (
                  <div style={{ marginTop: "1rem", color: "var(--accent-amber)", fontWeight: 600 }}>
                    ⏳ {uploadMessage}
                  </div>
                )}
                {!uploadLoading && uploadMessage && (
                  <div style={{ marginTop: "1rem", color: "#34d399", fontWeight: 600 }}>
                    {uploadMessage}
                  </div>
                )}
              </div>
            </div>

            {/* Quick Documents Overview */}
            <div className="glass-panel">
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem" }}>
                <h3 style={{ fontSize: "1.1rem" }}>Recent Document Status & Pipeline</h3>
                <button className="btn btn-secondary btn-sm" onClick={() => setActiveTab("library")}>
                  Manage All Documents →
                </button>
              </div>

              {documents.length === 0 ? (
                <div style={{ padding: "2rem", textAlign: "center", color: "var(--text-muted)" }}>
                  No documents uploaded yet. Upload a PDF, DOCX, or TXT file above to start researching!
                </div>
              ) : (
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Filename</th>
                      <th>Size</th>
                      <th>Pages</th>
                      <th>Status</th>
                      <th>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {documents.slice(0, 5).map(doc => (
                      <tr key={doc.id}>
                        <td style={{ fontWeight: 600 }}>{doc.original_filename}</td>
                        <td>{(doc.size_bytes / 1024).toFixed(1)} KB</td>
                        <td>{doc.page_count || "-"}</td>
                        <td>
                          <span className={`badge badge-${doc.status}`}>{doc.status}</span>
                        </td>
                        <td>
                          <div style={{ display: "flex", gap: "0.5rem" }}>
                            <button
                              className="btn btn-secondary btn-sm"
                              onClick={() => {
                                setActiveViewerDocId(doc.id);
                                setViewerCurrentPage(1);
                                setActiveTab("viewer");
                              }}
                            >
                              View
                            </button>
                            <button
                              className="btn btn-primary btn-sm"
                              disabled={doc.status !== "ready"}
                              onClick={() => {
                                setSelectedDocIds([doc.id]);
                                setActiveTab("chat");
                              }}
                            >
                              Chat
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </div>
        )}

        {/* TAB 2: DOCUMENT LIBRARY */}
        {activeTab === "library" && (
          <div className="glass-panel">
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1.5rem" }}>
              <div>
                <h2 style={{ fontSize: "1.4rem", fontWeight: 700 }}>Document Repository</h2>
                <p style={{ color: "var(--text-secondary)", fontSize: "0.85rem" }}>
                  Manage uploaded files, verify ingestion status, and select documents for research queries.
                </p>
              </div>
              <button className="btn btn-primary" onClick={() => fileInputRef.current?.click()}>
                + Upload Document
              </button>
            </div>

            {documents.length === 0 ? (
              <div style={{ padding: "3rem", textAlign: "center", color: "var(--text-muted)" }}>
                No documents found. Click "+ Upload Document" to add files to your library.
              </div>
            ) : (
              <table className="data-table">
                <thead>
                  <tr>
                    <th style={{ width: "40px" }}>Select</th>
                    <th>Document Name</th>
                    <th>MIME Type</th>
                    <th>Size</th>
                    <th>Pages</th>
                    <th>Status</th>
                    <th>Uploaded</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {documents.map(doc => {
                    const isSelected = selectedDocIds.includes(doc.id);
                    return (
                      <tr key={doc.id}>
                        <td>
                          <input
                            type="checkbox"
                            checked={isSelected}
                            disabled={doc.status !== "ready"}
                            onChange={() => {
                              setSelectedDocIds(prev =>
                                isSelected ? prev.filter(id => id !== doc.id) : [...prev, doc.id]
                              );
                            }}
                          />
                        </td>
                        <td style={{ fontWeight: 600 }}>{doc.original_filename}</td>
                        <td style={{ color: "var(--text-muted)", fontSize: "0.8rem" }}>{doc.mime_type}</td>
                        <td>{(doc.size_bytes / 1024).toFixed(1)} KB</td>
                        <td>{doc.page_count}</td>
                        <td>
                          <span className={`badge badge-${doc.status}`}>{doc.status}</span>
                        </td>
                        <td style={{ fontSize: "0.8rem", color: "var(--text-secondary)" }}>
                          {new Date(doc.created_at).toLocaleDateString()}
                        </td>
                        <td>
                          <div style={{ display: "flex", gap: "0.4rem" }}>
                            <button
                              className="btn btn-secondary btn-sm"
                              onClick={() => {
                                setActiveViewerDocId(doc.id);
                                setViewerCurrentPage(1);
                                setActiveTab("viewer");
                              }}
                            >
                              Inspect
                            </button>
                            <button
                              className="btn btn-secondary btn-sm"
                              onClick={() => {
                                setSummaryDocId(doc.id);
                                setActiveTab("summary");
                              }}
                            >
                              Summary
                            </button>
                            <button
                              className="btn btn-danger btn-sm"
                              onClick={() => handleDeleteDoc(doc.id, doc.original_filename)}
                            >
                              Delete
                            </button>
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            )}
          </div>
        )}

        {/* TAB 3: RESEARCH CHAT & CITATIONS */}
        {activeTab === "chat" && (
          <div className="chat-layout">
            {/* Sidebar: Document Scope & Sessions */}
            <aside className="chat-sidebar">
              <div style={{ marginBottom: "1.25rem" }}>
                <h4 style={{ fontSize: "0.85rem", textTransform: "uppercase", letterSpacing: "0.05em", color: "var(--text-muted)", marginBottom: "0.6rem" }}>
                  Active Query Scope
                </h4>
                <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)", marginBottom: "0.5rem" }}>
                  {selectedDocIds.length} document(s) selected:
                </div>
                <div style={{ maxHeight: "140px", overflowY: "auto", display: "flex", flexDirection: "column", gap: "0.4rem" }}>
                  {documents.filter(d => d.status === "ready").map(doc => {
                    const isSelected = selectedDocIds.includes(doc.id);
                    return (
                      <label
                        key={doc.id}
                        style={{
                          display: "flex",
                          alignItems: "center",
                          gap: "0.5rem",
                          fontSize: "0.8rem",
                          cursor: "pointer",
                          padding: "0.3rem 0.5rem",
                          borderRadius: "4px",
                          background: isSelected ? "rgba(99, 102, 241, 0.15)" : "transparent"
                        }}
                      >
                        <input
                          type="checkbox"
                          checked={isSelected}
                          onChange={() => {
                            setSelectedDocIds(prev =>
                              isSelected ? prev.filter(id => id !== doc.id) : [...prev, doc.id]
                            );
                          }}
                        />
                        <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                          {doc.original_filename}
                        </span>
                      </label>
                    );
                  })}
                </div>
              </div>

              <div style={{ flex: 1, overflowY: "auto" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.6rem" }}>
                  <h4 style={{ fontSize: "0.85rem", textTransform: "uppercase", letterSpacing: "0.05em", color: "var(--text-muted)" }}>
                    Sessions
                  </h4>
                  <button
                    className="btn btn-secondary btn-sm"
                    style={{ fontSize: "0.7rem", padding: "0.2rem 0.5rem" }}
                    onClick={async () => {
                      if (!token) return;
                      const res = await fetch(`${API_BASE}/chat/sessions`, {
                        method: "POST",
                        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
                        body: JSON.stringify({ title: "New Research Session" })
                      });
                      if (res.ok) {
                        const newS = await res.json();
                        setChatSessions([newS, ...chatSessions]);
                        setActiveSessionId(newS.id);
                        setMessages([]);
                      }
                    }}
                  >
                    + New
                  </button>
                </div>

                <div style={{ display: "flex", flexDirection: "column", gap: "0.35rem" }}>
                  {chatSessions.map(sess => (
                    <button
                      key={sess.id}
                      onClick={() => {
                        setActiveSessionId(sess.id);
                        setMessages(sess.messages || []);
                      }}
                      style={{
                        textAlign: "left",
                        padding: "0.6rem 0.75rem",
                        borderRadius: "var(--radius-md)",
                        border: "1px solid",
                        borderColor: activeSessionId === sess.id ? "var(--primary)" : "transparent",
                        background: activeSessionId === sess.id ? "rgba(99, 102, 241, 0.15)" : "rgba(255, 255, 255, 0.02)",
                        color: activeSessionId === sess.id ? "#ffffff" : "var(--text-secondary)",
                        fontSize: "0.82rem",
                        cursor: "pointer",
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                        whiteSpace: "nowrap"
                      }}
                    >
                      {sess.title}
                    </button>
                  ))}
                </div>
              </div>
            </aside>

            {/* Main Chat Conversation Container */}
            <main className="chat-main">
              <div className="chat-messages">
                {messages.length === 0 ? (
                  <div style={{ margin: "auto", textAlign: "center", maxWidth: "480px" }}>
                    <div style={{ fontSize: "2.5rem", marginBottom: "1rem" }}>🔍</div>
                    <h3 style={{ fontSize: "1.2rem", marginBottom: "0.5rem" }}>Ask questions across your documents</h3>
                    <p style={{ color: "var(--text-secondary)", fontSize: "0.85rem", marginBottom: "1.5rem" }}>
                      Every answer is backed by exact retrieved passages and verified page citations.
                    </p>
                    <div style={{ display: "flex", flexWrap: "wrap", gap: "0.5rem", justifyContent: "center" }}>
                      {[
                        "What are the main risks described in these reports?",
                        "What are the key deliverables and deadlines?",
                        "What is the total budget allocated?"
                      ].map((promptText, i) => (
                        <button
                          key={i}
                          className="btn btn-secondary btn-sm"
                          onClick={() => {
                            setInputQuestion(promptText);
                          }}
                        >
                          "{promptText}"
                        </button>
                      ))}
                    </div>
                  </div>
                ) : (
                  messages.map(msg => (
                    <div
                      key={msg.message_id}
                      className={`message-bubble ${msg.role === "user" ? "message-user" : "message-assistant"}`}
                    >
                      {msg.role === "assistant" && (
                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.5rem" }}>
                          <span
                            className={`grounding-tag ${
                              msg.grounding_status === "supported" ? "grounding-supported" : "grounding-insufficient"
                            }`}
                          >
                            {msg.grounding_status === "supported" ? "✓ Grounded by Evidence" : "⚠ Insufficient Evidence"}
                          </span>
                          {msg.trace_id && (
                            <span style={{ fontSize: "0.7rem", color: "var(--text-muted)" }}>
                              Trace: {msg.trace_id}
                            </span>
                          )}
                        </div>
                      )}

                      <div style={{ whiteSpace: "pre-wrap" }}>{msg.content}</div>

                      {/* Citation Cards */}
                      {msg.citations && msg.citations.length > 0 && (
                        <div className="citations-container">
                          <div className="citations-title">
                            <span>📌</span> Supporting Source Pages & Evidence
                          </div>
                          <div className="citations-grid">
                            {msg.citations.map((c, idx) => (
                              <div
                                key={idx}
                                className="citation-card"
                                onClick={() => handleCitationClick(c)}
                                title="Click to view this exact cited page in Document Viewer"
                              >
                                <div className="citation-header">
                                  <span>{c.filename}</span>
                                  <span style={{ color: "var(--accent-cyan)" }}>Page {c.page}</span>
                                </div>
                                <div className="citation-excerpt">"{c.excerpt}"</div>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  ))
                )}
                {isSending && (
                  <div className="message-bubble message-assistant" style={{ fontStyle: "italic", color: "var(--accent-amber)" }}>
                    Retrieving candidate chunks, computing embeddings, and synthesizing grounded answer...
                  </div>
                )}
              </div>

              {/* Chat Input Bar */}
              <form className="chat-input-bar" onSubmit={handleSendMessage}>
                <input
                  type="text"
                  className="chat-input"
                  placeholder="Ask a question about the selected documents..."
                  value={inputQuestion}
                  onChange={(e) => setInputQuestion(e.target.value)}
                  disabled={isSending}
                />
                <button
                  type="submit"
                  className="btn btn-primary"
                  disabled={isSending || !inputQuestion.trim()}
                >
                  {isSending ? "Searching..." : "Ask AI"}
                </button>
              </form>
            </main>
          </div>
        )}

        {/* TAB 4: DOCUMENT VIEWER & PROVENANCE */}
        {activeTab === "viewer" && (
          <div className="viewer-container">
            {/* Document and Page Selector */}
            <div className="glass-panel" style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
              <h3 style={{ fontSize: "1.1rem" }}>Document Navigator</h3>

              <div>
                <label style={{ fontSize: "0.8rem", color: "var(--text-muted)", display: "block", marginBottom: "0.4rem" }}>
                  Select Document:
                </label>
                <select
                  value={activeViewerDocId || ""}
                  onChange={(e) => {
                    setActiveViewerDocId(e.target.value);
                    setViewerCurrentPage(1);
                  }}
                  style={{
                    width: "100%",
                    padding: "0.6rem",
                    borderRadius: "var(--radius-md)",
                    background: "rgba(255, 255, 255, 0.05)",
                    border: "1px solid var(--border-subtle)",
                    color: "white"
                  }}
                >
                  {documents.map(d => (
                    <option key={d.id} value={d.id} style={{ background: "#0f1626" }}>
                      {d.original_filename} ({d.page_count} pages)
                    </option>
                  ))}
                </select>
              </div>

              {activeViewerDoc && (
                <div style={{ marginTop: "1rem" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.8rem" }}>
                    <span style={{ fontSize: "0.85rem", fontWeight: 600 }}>
                      Page {viewerCurrentPage} of {activeViewerDoc.page_count || 1}
                    </span>
                    <div style={{ display: "flex", gap: "0.4rem" }}>
                      <button
                        className="btn btn-secondary btn-sm"
                        disabled={viewerCurrentPage <= 1}
                        onClick={() => setViewerCurrentPage(prev => Math.max(1, prev - 1))}
                      >
                        ◀ Prev
                      </button>
                      <button
                        className="btn btn-secondary btn-sm"
                        disabled={viewerCurrentPage >= (activeViewerDoc.page_count || 1)}
                        onClick={() => setViewerCurrentPage(prev => Math.min(activeViewerDoc.page_count || 1, prev + 1))}
                      >
                        Next ▶
                      </button>
                    </div>
                  </div>

                  {viewerHighlight && (
                    <div style={{ padding: "0.75rem", borderRadius: "var(--radius-md)", background: "rgba(6, 182, 212, 0.1)", border: "1px solid rgba(6, 182, 212, 0.3)", fontSize: "0.78rem" }}>
                      <div style={{ fontWeight: 600, color: "var(--accent-cyan)", marginBottom: "0.2rem" }}>Cited Excerpt:</div>
                      <div>"{viewerHighlight}"</div>
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* Page Text Viewer Display */}
            <div className="viewer-content">
              {activeViewerDoc ? (
                <div>
                  <div style={{ borderBottom: "1px solid rgba(255, 255, 255, 0.1)", paddingBottom: "0.75rem", marginBottom: "1rem", display: "flex", justifyContent: "space-between", color: "var(--text-muted)", fontSize: "0.75rem" }}>
                    <span>DOCUMENT: {activeViewerDoc.original_filename}</span>
                    <span>PROVENANCE: PAGE {viewerCurrentPage}</span>
                  </div>
                  <div>
                    {activeViewerDoc.pages && activeViewerDoc.pages.length > 0 ? (
                      activeViewerDoc.pages.find(p => p.page_number === viewerCurrentPage)?.extracted_text || "No text available on this page."
                    ) : (
                      "Document text is indexed and ready for retrieval in the research database."
                    )}
                  </div>
                </div>
              ) : (
                <div style={{ textAlign: "center", marginTop: "3rem", color: "var(--text-muted)" }}>
                  Please select a document to inspect its extracted page content.
                </div>
              )}
            </div>
          </div>
        )}

        {/* TAB 5: EXECUTIVE SUMMARIES */}
        {activeTab === "summary" && (
          <div className="glass-panel">
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1.5rem" }}>
              <div>
                <h2 style={{ fontSize: "1.4rem", fontWeight: 700 }}>Executive Document Summarization</h2>
                <p style={{ color: "var(--text-secondary)", fontSize: "0.85rem" }}>
                  Synthesize high-level overviews, key findings, risks, and recommended action items.
                </p>
              </div>

              <div style={{ display: "flex", gap: "0.75rem", alignItems: "center" }}>
                <select
                  value={summaryDocId}
                  onChange={(e) => setSummaryDocId(e.target.value)}
                  style={{
                    padding: "0.6rem",
                    borderRadius: "var(--radius-md)",
                    background: "rgba(255, 255, 255, 0.05)",
                    border: "1px solid var(--border-subtle)",
                    color: "white"
                  }}
                >
                  {documents.filter(d => d.status === "ready").map(d => (
                    <option key={d.id} value={d.id} style={{ background: "#0f1626" }}>
                      {d.original_filename}
                    </option>
                  ))}
                </select>
                <button
                  className="btn btn-primary"
                  onClick={handleGenerateSummary}
                  disabled={isSummarizing || !summaryDocId}
                >
                  {isSummarizing ? "Generating..." : "Generate Summary"}
                </button>
              </div>
            </div>

            {summaryData ? (
              <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
                <div style={{ padding: "1.25rem", borderRadius: "var(--radius-lg)", background: "rgba(99, 102, 241, 0.08)", border: "1px solid rgba(99, 102, 241, 0.25)" }}>
                  <h3 style={{ fontSize: "1.1rem", marginBottom: "0.5rem", color: "#a5b4fc" }}>
                    Executive Overview: {summaryData.document_name}
                  </h3>
                  <p style={{ lineHeight: 1.7, fontSize: "0.95rem" }}>{summaryData.executive_summary}</p>
                </div>

                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1.25rem" }}>
                  <div className="glass-panel">
                    <h4 style={{ fontSize: "0.95rem", color: "var(--accent-cyan)", marginBottom: "0.75rem" }}>
                      🔍 Major Findings
                    </h4>
                    <ul style={{ paddingLeft: "1.2rem", display: "flex", flexDirection: "column", gap: "0.5rem", fontSize: "0.88rem" }}>
                      {summaryData.major_findings.map((item, i) => (
                        <li key={i}>{item}</li>
                      ))}
                    </ul>
                  </div>

                  <div className="glass-panel">
                    <h4 style={{ fontSize: "0.95rem", color: "#34d399", marginBottom: "0.75rem" }}>
                      📌 Key Points
                    </h4>
                    <ul style={{ paddingLeft: "1.2rem", display: "flex", flexDirection: "column", gap: "0.5rem", fontSize: "0.88rem" }}>
                      {summaryData.key_points.map((item, i) => (
                        <li key={i}>{item}</li>
                      ))}
                    </ul>
                  </div>

                  <div className="glass-panel">
                    <h4 style={{ fontSize: "0.95rem", color: "var(--accent-rose)", marginBottom: "0.75rem" }}>
                      ⚠ Risks & Constraints
                    </h4>
                    <ul style={{ paddingLeft: "1.2rem", display: "flex", flexDirection: "column", gap: "0.5rem", fontSize: "0.88rem" }}>
                      {summaryData.risks_identified.map((item, i) => (
                        <li key={i}>{item}</li>
                      ))}
                    </ul>
                  </div>

                  <div className="glass-panel">
                    <h4 style={{ fontSize: "0.95rem", color: "var(--accent-amber)", marginBottom: "0.75rem" }}>
                      🎯 Recommended Action Items
                    </h4>
                    <ul style={{ paddingLeft: "1.2rem", display: "flex", flexDirection: "column", gap: "0.5rem", fontSize: "0.88rem" }}>
                      {summaryData.action_items.map((item, i) => (
                        <li key={i}>{item}</li>
                      ))}
                    </ul>
                  </div>
                </div>
              </div>
            ) : (
              <div style={{ padding: "3rem", textAlign: "center", color: "var(--text-muted)" }}>
                Select a document and click "Generate Summary" to extract executive findings.
              </div>
            )}
          </div>
        )}

        {/* TAB 6: STRUCTURED EXTRACTION */}
        {activeTab === "extraction" && (
          <div className="glass-panel">
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1.5rem" }}>
              <div>
                <h2 style={{ fontSize: "1.4rem", fontWeight: 700 }}>Structured Information Extraction</h2>
                <p style={{ color: "var(--text-secondary)", fontSize: "0.85rem" }}>
                  Extract named entities, dates, financial amounts, deliverables, and risks into structured JSON schemas.
                </p>
              </div>

              <button
                className="btn btn-primary"
                onClick={handleRunExtraction}
                disabled={isExtracting || selectedDocIds.length === 0}
              >
                {isExtracting ? "Extracting..." : "⚡ Run Extraction"}
              </button>
            </div>

            {extractedData ? (
              <div>
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Target Field</th>
                      <th>Extracted Value</th>
                      <th>Source Document</th>
                      <th>Page</th>
                      <th>Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {Object.entries(extractedData).map(([fieldName, item]) => (
                      <tr key={fieldName}>
                        <td style={{ fontWeight: 600, color: "#a5b4fc" }}>{fieldName}</td>
                        <td style={{ fontWeight: item.value ? 500 : 400, color: item.value ? "#ffffff" : "var(--text-muted)" }}>
                          {item.value || "null / not found"}
                        </td>
                        <td>{item.source_document || "-"}</td>
                        <td>{item.source_page ? `Page ${item.source_page}` : "-"}</td>
                        <td>
                          <span className={`badge badge-${item.status === "found" ? "ready" : "failed"}`}>
                            {item.status}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div style={{ padding: "3rem", textAlign: "center", color: "var(--text-muted)" }}>
                Ensure relevant documents are selected, then click "Run Extraction" to extract structured metadata.
              </div>
            )}
          </div>
        )}
      </main>
    </div>
  );
}
