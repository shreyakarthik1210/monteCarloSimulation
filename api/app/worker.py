import os
import sys
import time
from datetime import datetime, timezone
from typing import Any, Dict

from google.cloud import firestore
from app.services.firestore import get_db, runs_collection

from app.core.simulate import simulate_aggregate_loss
from app.core.simulate import simulate_gross_net



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

    cfg = req.get("config", {}) or {}
    freq_lambda = float(cfg.get("freq_lambda", 0.3))
    sev_mu = float(cfg.get("sev_mu", 10.2))
    sev_sigma = float(cfg.get("sev_sigma", 1.1))
    seed = int(cfg.get("seed", 42))

    reinsurance = cfg.get("reinsurance", {"type": "none"})

    # Mark running
    update_run(db, run_id, {
        "status": "running",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "error": None,
    })

    try:
        results = simulate_gross_net(
        n_sims=n_sims,
        freq_lambda=freq_lambda,
        sev_mu=sev_mu,
        sev_sigma=sev_sigma,
        capital=capital,
        reinsurance=reinsurance,
        seed=seed,
    )
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
