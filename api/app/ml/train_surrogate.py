import os
import json
from dataclasses import dataclass
import numpy as np
import pandas as pd
from joblib import dump
from sklearn.ensemble import GradientBoostingRegressor

from google.cloud import storage

try:
    from google.oauth2 import service_account  # type: ignore
except Exception:  # pragma: no cover - optional dependency in local dev
    service_account = None  # type: ignore

from app.core.simulate import simulate_gross_net

@dataclass
class TrainConfig:
    n_scenarios: int = 400
    n_sims_per_scenario: int = 8000
    seed: int = 123
    bucket: str = ""
    model_prefix: str = "models"

def get_storage_client():
    """Return a `google.cloud.storage.Client`, using service-account env fallbacks.

    Falls back to ADC if no explicit credentials are provided.
    """
    creds = None
    sa_path = (
        os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
        or os.environ.get("RISK_ASSER_SERVICE_ACCOUNT_FILE")
    )
    sa_json = os.environ.get("RISK_ASSER_SERVICE_ACCOUNT_JSON")
    project_id = os.environ.get("GOOGLE_CLOUD_PROJECT") or os.environ.get("RISK_ASSER_PROJECT")

    if sa_json and service_account is not None:
        info = json.loads(sa_json)
        creds = service_account.Credentials.from_service_account_info(info)
    elif sa_path and service_account is not None:
        creds = service_account.Credentials.from_service_account_file(sa_path)

    if creds is not None:
        if project_id:
            return storage.Client(project=project_id, credentials=creds)
        return storage.Client(credentials=creds)

    if project_id:
        return storage.Client(project=project_id)
    return storage.Client()


def upload_to_gcs(bucket_name: str, local_path: str, gcs_path: str) -> None:
    client = get_storage_client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(gcs_path)
    blob.upload_from_filename(local_path)

def main():
    cfg = TrainConfig(
        n_scenarios=int(os.environ.get("N_SCENARIOS", "400")),
        n_sims_per_scenario=int(os.environ.get("N_SIMS_PER_SCENARIO", "8000")),
        seed=int(os.environ.get("SEED", "123")),
        bucket=os.environ["ARTIFACT_BUCKET"],
        model_prefix=os.environ.get("MODEL_PREFIX", "models"),
    )

    rng = np.random.default_rng(cfg.seed)

    rows = []
    # Sample scenarios
    for i in range(cfg.n_scenarios):
        freq_lambda = float(rng.uniform(0.05, 0.6))
        sev_mu = float(rng.uniform(9.5, 10.8))
        sev_sigma = float(rng.uniform(0.6, 1.4))

        # XoL parameters (sometimes none)
        if rng.random() < 0.3:
            rein = {"type": "none"}
            retention = 0.0
            limit = 0.0
        else:
            retention = float(rng.choice([5000, 10000, 20000, 30000, 50000]))
            limit = float(rng.choice([25000, 50000, 100000, 200000]))
            rein = {"type": "xol", "retention": retention, "limit": limit}

        # Capital not needed for VaR, but you can include if you want ruin model later
        capital = 200000.0

        out = simulate_gross_net(
            n_sims=cfg.n_sims_per_scenario,
            freq_lambda=freq_lambda,
            sev_mu=sev_mu,
            sev_sigma=sev_sigma,
            capital=capital,
            reinsurance=rein,
            seed=int(cfg.seed + i),
        )

        rows.append({
            "freq_lambda": freq_lambda,
            "sev_mu": sev_mu,
            "sev_sigma": sev_sigma,
            "retention": retention,
            "limit": limit,
            "gross_VaR99": out["gross"]["metrics"]["VaR99"],
            "net_VaR99": out["net"]["metrics"]["VaR99"],
        })

    df = pd.DataFrame(rows)

    X = df[["freq_lambda", "sev_mu", "sev_sigma", "retention", "limit"]]
    y_gross = df["gross_VaR99"]
    y_net = df["net_VaR99"]

    # Quantile regression-ish: use loss='quantile'
    # Note: GradientBoostingRegressor supports quantile loss.
    gross_model = GradientBoostingRegressor(loss="quantile", alpha=0.99, random_state=cfg.seed)
    net_model = GradientBoostingRegressor(loss="quantile", alpha=0.99, random_state=cfg.seed)

    gross_model.fit(X, y_gross)
    net_model.fit(X, y_net)

    os.makedirs("/tmp/models", exist_ok=True)
    gross_path = "/tmp/models/gross_var99.joblib"
    net_path = "/tmp/models/net_var99.joblib"
    dump(gross_model, gross_path)
    dump(net_model, net_path)

    # Upload artifacts
    upload_to_gcs(cfg.bucket, gross_path, f"{cfg.model_prefix}/gross_var99.joblib")
    upload_to_gcs(cfg.bucket, net_path, f"{cfg.model_prefix}/net_var99.joblib")

    # Also upload a small metadata file
    meta = {
        "features": list(X.columns),
        "target": "VaR99",
        "n_scenarios": cfg.n_scenarios,
        "n_sims_per_scenario": cfg.n_sims_per_scenario,
    }
    meta_path = "/tmp/models/meta.json"
    with open(meta_path, "w") as f:
        json.dump(meta, f, indent=2)
    upload_to_gcs(cfg.bucket, meta_path, f"{cfg.model_prefix}/meta.json")

    print("Training complete and uploaded to GCS.")

if __name__ == "__main__":
    main()
