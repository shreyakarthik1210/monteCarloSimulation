from fastapi import APIRouter, HTTPException
import logging
import traceback
from datetime import datetime, timezone
from google.cloud import firestore
from pydantic import BaseModel
from typing import Literal
from app.services.run_jobs import run_job
import os

from app.models.schemas import RunCreateRequest, RunResponse, RunDoc
from app.services.firestore import get_db, runs_collection

router = APIRouter(prefix="/runs", tags=["runs"])

@router.post("", response_model=RunResponse)
def create_run(req: RunCreateRequest):
    logger = logging.getLogger(__name__)
    try:
        db = get_db()
        col = runs_collection(db)

        doc_ref = col.document()  # auto-id
        run_id = doc_ref.id

        payload = {
            "run_id": run_id,
            "status": "queued",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "request": req.model_dump(),
            "results": None,
            "error": None,
        }

        doc_ref.set(payload)
        job_name = os.environ.get("WORKER_JOB_NAME", "risk-lab-worker")
        region = os.environ.get("REGION", "us-central1")
        run_job(job_name=job_name, region=region, run_id=run_id)
        return RunResponse(run_id=run_id, status="queued")
    except Exception as e:
        # Log full traceback to server logs for debugging
        logger.error("Failed to create run: %s", e)
        logger.error(traceback.format_exc())
        # Return a sanitized error to the client
        raise HTTPException(status_code=500, detail=f"Failed to create run: {str(e)}")

@router.get("/{run_id}", response_model=RunDoc)
def get_run(run_id: str):
    logger = logging.getLogger(__name__)
    try:
        db = get_db()
        doc = runs_collection(db).document(run_id).get()
    except Exception as e:
        logger.error("Failed to fetch run from Firestore: %s", e)
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Failed to fetch run: {str(e)}")

    if not doc.exists:
        raise HTTPException(status_code=404, detail="Run not found")

    data = doc.to_dict()

    # Basic shape validation
    try:
        return RunDoc(
            run_id=data["run_id"],
            status=data["status"],
            created_at=data["created_at"],
            request=RunCreateRequest(**data["request"]),
            results=data.get("results"),
            error=data.get("error"),
        )
    except Exception as e:
        logger.error("Invalid run document shape: %s", e)
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Invalid run document: {e}")

class StatusUpdateRequest(BaseModel):
    status: Literal["queued", "running", "done", "failed"]
    error: str | None = None

@router.post("/{run_id}/status")
def update_status(run_id: str, req: StatusUpdateRequest):
    db = get_db()
    doc_ref = runs_collection(db).document(run_id)

    if not doc_ref.get().exists:
        raise HTTPException(status_code=404, detail="Run not found")

    update = {"status": req.status}
    if req.error:
        update["error"] = req.error

    doc_ref.update(update)
    return {"run_id": run_id, "status": req.status}