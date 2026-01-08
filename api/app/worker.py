import os
import sys
import time
from datetime import datetime, timezone
from typing import Any, Dict

from google.cloud import firestore
from app.services.firestore import get_db, runs_collection


def update_run(db: firestore.Client, run_id: str, patch: Dict[str, Any]) -> None:
    runs_collection(db).document(run_id).update(patch)


def main() -> None:
    # Cloud Run Jobs will pass RUN_ID as an env var
    run_id = os.environ.get("RUN_ID")
    if not run_id:
        print("Missing RUN_ID env var", file=sys.stderr)
        sys.exit(2)

    db = get_db()
    doc_ref = runs_collection(db).document(run_id)
    snap = doc_ref.get()

    if not snap.exists:
        print(f"Run not found: {run_id}", file=sys.stderr)
        sys.exit(3)

    run_doc = snap.to_dict()
    req = run_doc.get("request", {})
    n_sims = int(req.get("n_sims", 50000))
    capital = float(req.get("capital", 1_000_000))

    # Mark running
    update_run(db, run_id, {
        "status": "running",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "error": None,
    })

    try:
        # ---- Stub "simulation" for Day 2 ----
        # Replace this with Monte Carlo Day 3.
        time.sleep(5)

        # Fake results so the pipeline is end-to-end
        results = {
            "gross": {
                "mean_loss": 123456.0,
                "VaR95": 250000.0,
                "VaR99": 400000.0,
                "TVaR95": 300000.0,
                "TVaR99": 500000.0,
                "ruinProb": 0.01 if capital > 500000 else 0.2,
            }
        }

        update_run(db, run_id, {
            "status": "done",
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "results": results,
        })
        print(f"Run {run_id} completed.")
    except Exception as e:
        update_run(db, run_id, {
            "status": "failed",
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "error": str(e),
        })
        raise


if __name__ == "__main__":
    main()
