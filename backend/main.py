import os
import io
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional
import uvicorn

from database import db
from ai_engine import analyze_document, chat_with_ai, generate_case_brief, extract_case_map

app = FastAPI(title="BROadvocacy AI")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

STATIC_DIR = Path(__file__).parent.parent / "static"
UPLOADS_DIR = Path(__file__).parent.parent / "uploads"
UPLOADS_DIR.mkdir(exist_ok=True)


# ── Models ─────────────────────────────────────────────────────────────────────────

class CaseCreate(BaseModel):
    name: str
    client_name: str
    charges: str
    jurisdiction: str
    notes: Optional[str] = ""

class CaseUpdate(BaseModel):
    name: str
    client_name: str
    charges: str
    jurisdiction: str
    notes: Optional[str] = ""
    status: Optional[str] = "active"

class ChatMessage(BaseModel):
    message: str

class TaskCreate(BaseModel):
    case_id: int
    title: str
    description: Optional[str] = ""
    type: Optional[str] = "other"
    due_date: Optional[str] = None

class TaskUpdate(BaseModel):
    completed: Optional[bool] = None
    title: Optional[str] = None


# ── Cases ────────────────────────────────────────────────────────────────────────────

@app.get("/api/cases")
def list_cases():
    return db.list_cases()

@app.post("/api/cases", status_code=201)
def create_case(case: CaseCreate):
    case_id = db.create_case(case.dict())
    return {**db.get_case(case_id)}

@app.get("/api/cases/{case_id}")
def get_case(case_id: int):
    case = db.get_case(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    return case

@app.put("/api/cases/{case_id}")
def update_case(case_id: int, data: CaseUpdate):
    if not db.get_case(case_id):
        raise HTTPException(status_code=404, detail="Case not found")
    db.update_case(case_id, data.dict())
    return db.get_case(case_id)

@app.get("/api/cases/{case_id}/map")
def get_case_map(case_id: int):
    cached = db.get_case_map(case_id)
    if cached:
        return cached
    return {"data": None, "created_at": None}

@app.post("/api/cases/{case_id}/map")
def build_case_map(case_id: int):
    context = db.get_case_context(case_id)
    if not context:
        raise HTTPException(status_code=404, detail="Case not found")
    result = extract_case_map(context)
    db.save_case_map(case_id, result)
    return {"data": result, "created_at": "now"}

@app.get("/api/cases/{case_id}/brief")
def get_brief(case_id: int):
    context = db.get_case_context(case_id)
    if not context:
        raise HTTPException(status_code=404, detail="Case not found")
    brief = generate_case_brief(context)
    return {"brief": brief}


# ── Documents ───────────────────────────────────────────────────────────────────────

@app.get("/api/cases/{case_id}/documents")
def list_documents(case_id: int):
    return db.list_documents(case_id)

@app.post("/api/cases/{case_id}/documents", status_code=201)
async def upload_document(case_id: int, file: UploadFile = File(...)):
    if not db.get_case(case_id):
        raise HTTPException(status_code=404, detail="Case not found")

    content_bytes = await file.read()
    text = _extract_text(content_bytes, file.filename)

    doc_id = db.add_document(case_id, file.filename, text)
    context = db.get_case_context(case_id)
    analysis = analyze_document(text, file.filename, context)
    db.update_document_analysis(doc_id, analysis)

    return {
        "id": doc_id,
        "filename": file.filename,
        "analysis": analysis,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

@app.get("/api/documents/{doc_id}")
def get_document(doc_id: int):
    doc = db.get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


# ── Chat ──────────────────────────────────────────────────────────────────────────────

@app.get("/api/cases/{case_id}/chat")
def get_chat(case_id: int):
    return db.get_chat_history(case_id)

@app.post("/api/cases/{case_id}/chat")
def send_chat(case_id: int, msg: ChatMessage):
    context = db.get_case_context(case_id)
    if not context:
        raise HTTPException(status_code=404, detail="Case not found")
    history = db.get_chat_history(case_id)
    response = chat_with_ai(msg.message, context, history)
    db.add_chat_message(case_id, "user", msg.message)
    db.add_chat_message(case_id, "assistant", response)
    return {"response": response}

@app.delete("/api/cases/{case_id}/chat")
def clear_chat(case_id: int):
    db.clear_chat(case_id)
    return {"success": True}


# ── Tasks ─────────────────────────────────────────────────────────────────────────────

@app.get("/api/cases/{case_id}/tasks")
def list_tasks(case_id: int):
    return db.list_tasks(case_id)

@app.post("/api/tasks", status_code=201)
def create_task(task: TaskCreate):
    task_id = db.create_task(task.dict())
    return {"id": task_id, **task.dict()}

@app.patch("/api/tasks/{task_id}")
def update_task(task_id: int, updates: TaskUpdate):
    db.update_task(task_id, updates.dict(exclude_none=True))
    return {"success": True}

@app.delete("/api/tasks/{task_id}")
def delete_task(task_id: int):
    db.delete_task(task_id)
    return {"success": True}


# ── Frontend ──────────────────────────────────────────────────────────────────────

@app.get("/")
def serve_index():
    index = STATIC_DIR / "index.html"
    if index.exists():
        return FileResponse(index)
    return HTMLResponse("<h1>BROadvocacy AI — frontend not found</h1>")


# ── Helpers ────────────────────────────────────────────────────────────────────────

def _extract_text(content: bytes, filename: str) -> str:
    name = (filename or "").lower()
    if name.endswith(".pdf"):
        try:
            import pdfplumber
            with pdfplumber.open(io.BytesIO(content)) as pdf:
                pages = [p.extract_text() or "" for p in pdf.pages]
                return "\n\n".join(pages)
        except Exception as e:
            return f"[PDF extraction failed: {e}]"
    return content.decode("utf-8", errors="ignore")


if __name__ == "__main__":
    db.init()
    print("\n╔══════════════════════════════════════╗")
    print("║        BROadvocacy AI — Ready        ║")
    print("║   Open http://localhost:8000         ║")
    print("╚══════════════════════════════════════╝\n")
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=False)
