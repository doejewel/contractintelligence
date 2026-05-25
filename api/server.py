import os
import time
import uuid
import json
import tempfile
from pathlib import Path
from datetime import datetime

from fastapi import FastAPI, UploadFile, File, HTTPException, Header, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

from agent.analyzer import ContractAnalysisAgent
from agent.models import ContractAnalysis

app = FastAPI(
    title="Contract Intelligence Manager",
    description="LLM-powered contract analysis agent for UiPath Maestro BPMN orchestration",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory job store (replace with Redis/DB in production)
jobs: dict[str, dict] = {}


class TextContractRequest(BaseModel):
    contract_text: str
    job_id: str | None = None


class JobStatusResponse(BaseModel):
    job_id: str
    status: str  # pending | processing | complete | failed
    result: dict | None = None
    error: str | None = None
    created_at: str
    completed_at: str | None = None


def get_agent() -> ContractAnalysisAgent:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="ANTHROPIC_API_KEY not configured")
    return ContractAnalysisAgent(api_key=api_key)


def run_analysis_job(job_id: str, contract_text: str = None, pdf_path: str = None):
    """Background task: run analysis and store result."""
    jobs[job_id]["status"] = "processing"
    try:
        agent = ContractAnalysisAgent(api_key=os.getenv("ANTHROPIC_API_KEY"))

        if contract_text:
            analysis = agent.analyze_text(contract_text)
        elif pdf_path:
            analysis = agent.analyze_pdf(pdf_path)
        else:
            raise ValueError("No contract content provided")

        payload = agent.get_uipath_payload(analysis)
        jobs[job_id]["status"] = "complete"
        jobs[job_id]["result"] = payload
        jobs[job_id]["completed_at"] = datetime.utcnow().isoformat()

        # Clean up temp file
        if pdf_path and Path(pdf_path).exists():
            Path(pdf_path).unlink()

    except Exception as e:
        jobs[job_id]["status"] = "failed"
        jobs[job_id]["error"] = str(e)
        jobs[job_id]["completed_at"] = datetime.utcnow().isoformat()


@app.get("/")
def root():
    return {
        "service": "Contract Intelligence Manager",
        "status": "running",
        "version": "1.0.0",
        "endpoints": ["/analyze/text", "/analyze/pdf", "/job/{job_id}", "/health"],
    }


@app.get("/health")
def health():
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}


@app.post("/analyze/text", response_model=JobStatusResponse)
async def analyze_contract_text(
    request: TextContractRequest,
    background_tasks: BackgroundTasks,
):
    """
    Analyze a contract from raw text.
    Called by UiPath API Workflow when contract arrives as text.
    Returns a job_id immediately; poll /job/{job_id} for results.
    """
    job_id = request.job_id or str(uuid.uuid4())
    jobs[job_id] = {
        "status": "pending",
        "result": None,
        "error": None,
        "created_at": datetime.utcnow().isoformat(),
        "completed_at": None,
    }
    background_tasks.add_task(run_analysis_job, job_id, contract_text=request.contract_text)
    return JobStatusResponse(job_id=job_id, **jobs[job_id])


@app.post("/analyze/pdf", response_model=JobStatusResponse)
async def analyze_contract_pdf(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
):
    """
    Analyze a contract from an uploaded PDF.
    Called by UiPath API Workflow when contract arrives as PDF.
    """
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted")

    # Save to temp file
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    content = await file.read()
    tmp.write(content)
    tmp.close()

    job_id = str(uuid.uuid4())
    jobs[job_id] = {
        "status": "pending",
        "result": None,
        "error": None,
        "created_at": datetime.utcnow().isoformat(),
        "completed_at": None,
    }
    background_tasks.add_task(run_analysis_job, job_id, pdf_path=tmp.name)
    return JobStatusResponse(job_id=job_id, **jobs[job_id])


@app.get("/job/{job_id}", response_model=JobStatusResponse)
def get_job_status(job_id: str):
    """
    Poll this endpoint from UiPath to get analysis results.
    UiPath Maestro waits here until status = 'complete' or 'failed'.
    """
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    return JobStatusResponse(job_id=job_id, **jobs[job_id])


@app.get("/jobs")
def list_jobs():
    """List all jobs and their statuses. Useful for monitoring."""
    return {
        "total": len(jobs),
        "jobs": [
            {"job_id": jid, "status": j["status"], "created_at": j["created_at"]}
            for jid, j in jobs.items()
        ],
    }