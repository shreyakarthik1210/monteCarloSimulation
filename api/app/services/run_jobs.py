import os
import requests
from google.auth import default
from google.auth.transport.requests import Request


def run_job(job_name: str, region: str, run_id: str) -> None:
    """
    Triggers a Cloud Run Job execution and passes RUN_ID env var to the job container.
    """
    project_id = os.environ["GOOGLE_CLOUD_PROJECT"]

    # Cloud Run Jobs REST endpoint
    url = (
        f"https://{region}-run.googleapis.com/apis/run.googleapis.com/v1/"
        f"namespaces/{project_id}/jobs/{job_name}:run"
    )

    creds, _ = default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
    creds.refresh(Request())
    token = creds.token

    payload = {
        "overrides": {
            "containerOverrides": [
                {
                    "env": [
                        {"name": "RUN_ID", "value": run_id}
                    ]
                }
            ]
        }
    }

    resp = requests.post(
        url,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json=payload,
        timeout=20,
    )

    if resp.status_code >= 300:
        raise RuntimeError(f"Failed to run job: {resp.status_code} {resp.text}")
