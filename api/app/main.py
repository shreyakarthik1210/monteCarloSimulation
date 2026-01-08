from fastapi import FastAPI
from app.routes.runs import router as runs_router

app = FastAPI(title="Risk Lab API")

@app.get("/health")
def health():
    return {"ok": True}

app.include_router(runs_router)
