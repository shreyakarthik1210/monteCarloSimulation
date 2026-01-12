import os
import json
from typing import Any
from typing import Optional
from google.cloud.firestore import Client

try:
    from google.cloud import firestore  # type: ignore
except Exception:  # pragma: no cover - optional dependency in local dev
    firestore = None  # type: ignore

try:
    from google.oauth2 import service_account  # type: ignore
except Exception:  # pragma: no cover - optional dependency in local dev
    service_account = None  # type: ignore


class _LocalDocumentSnapshot:
    def __init__(self, data: Any):
        self._data = data
        self.exists = data is not None

    def to_dict(self):
        return self._data


class _LocalDocumentRef:
    def __init__(self, collection: "_LocalCollection", doc_id: str):
        self.collection = collection
        self.id = doc_id

    def set(self, payload: dict):
        self.collection._store[self.id] = payload

    def get(self):
        data = self.collection._store.get(self.id)
        return _LocalDocumentSnapshot(data)


class _LocalCollection:
    def __init__(self, name: str, root_store: dict):
        self.name = name
        # store is a dict: doc_id -> payload
        self._store = root_store.setdefault(name, {})

    def document(self, doc_id: str | None = None) -> _LocalDocumentRef:
        import uuid

        if doc_id is None:
            doc_id = uuid.uuid4().hex
        return _LocalDocumentRef(self, doc_id)


class _LocalClient:
    def __init__(self):
        # root: collection_name -> {doc_id: payload}
        self._root: dict = {}

    def collection(self, name: str) -> _LocalCollection:
        return _LocalCollection(name, self._root)


def get_db() -> Any:
    """Return a Firestore client or a lightweight local in-memory client.

    To force local in-memory mode set the env var `RISK_ASSER_LOCAL=1`.
    """
    # Prefer the standard Google env var, but allow a project-specific fallback.
    project_id = os.environ.get("GOOGLE_CLOUD_PROJECT") or os.environ.get("RISK_ASSER_PROJECT")

    # If the user explicitly asked for local mode, return the local client.
    if os.environ.get("RISK_ASSER_LOCAL", "").lower() in ("1", "true", "yes"):
        return _LocalClient()

    if firestore is None:
        raise RuntimeError("google-cloud-firestore is not available in this environment")

    try:
        # First, check for explicit service account credentials provided via
        # environment (either a file path or raw JSON). This allows local
        # development without relying on ADC being configured globally.
        creds = None

        # Path from standard var or project-specific fallback
        sa_path = (
            os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
            or os.environ.get("RISK_ASSER_SERVICE_ACCOUNT_FILE")
        )

        sa_json = os.environ.get("RISK_ASSER_SERVICE_ACCOUNT_JSON")

        if sa_json and service_account is not None:
            info = json.loads(sa_json)
            creds = service_account.Credentials.from_service_account_info(info)
        elif sa_path and service_account is not None:
            creds = service_account.Credentials.from_service_account_file(sa_path)

        if creds is not None:
            if project_id:
                return firestore.Client(project=project_id, credentials=creds)
            return firestore.Client(credentials=creds)

        # Otherwise rely on ADC / environment to provide credentials/project
        if project_id:
            return firestore.Client(project=project_id)
        return firestore.Client()
    except Exception as e:
        # If init failed and local mode wasn't requested, surface a clear error.
        raise RuntimeError(f"Failed to initialize Firestore client: {e}")


def runs_collection(db: Any):
    return db.collection("runs")

def update_run_status(db: Client, run_id: str, status: str, results: Optional[dict] = None, error: Optional[str] = None):
    """Update the status, results, and error fields of a run document."""
    update = {"status": status}

    if error:
        update["error"] = error

    runs_collection(db).document(run_id).update(update)