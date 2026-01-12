import os
from functools import lru_cache
from google.cloud import storage
from joblib import load

def download_from_gcs(bucket_name: str, gcs_path: str, local_path: str) -> None:
    client = storage.Client()
    blob = client.bucket(bucket_name).blob(gcs_path)
    blob.download_to_filename(local_path)

@lru_cache(maxsize=2)
def load_var99_models():
    bucket = os.environ["ARTIFACT_BUCKET"]
    os.makedirs("/tmp/models", exist_ok=True)

    gross_local = "/tmp/models/gross_var99.joblib"
    net_local = "/tmp/models/net_var99.joblib"

    download_from_gcs(bucket, "models/gross_var99.joblib", gross_local)
    download_from_gcs(bucket, "models/net_var99.joblib", net_local)

    return load(gross_local), load(net_local)
