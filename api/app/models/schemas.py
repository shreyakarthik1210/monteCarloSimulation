from pydantic import BaseModel, Field
from typing import Literal, Optional, Dict, Any

class RunCreateRequest(BaseModel):
    n_sims: int = Field(default=50000, ge=1000, le=500000)
    capital: float = Field(default=1_000_000, gt=0)
    # Keep config flexible for now; you’ll firm this up Day 2
    config: Dict[str, Any] = Field(default_factory=dict)

class RunResponse(BaseModel):
    run_id: str
    status: Literal["queued", "running", "done", "failed"]

class RunDoc(BaseModel):
    run_id: str
    status: Literal["queued", "running", "done", "failed"]
    created_at: str
    request: RunCreateRequest
    results: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
