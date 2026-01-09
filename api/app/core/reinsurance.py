import numpy as np
from typing import TypedDict, Literal

class ReinsuranceConfig(TypedDict, total=False):
    type: Literal["none", "xol"]
    retention: float
    limit: float

def apply_xol_per_loss(sev: np.ndarray, retention: float, limit: float) -> np.ndarray:
    """
    Per-loss XoL net severity (insurer portion).
    Insurer pays: min(X, r) + max(0, X - (r + L))
    """
    r = max(float(retention), 0.0)
    L = max(float(limit), 0.0)
    below = np.minimum(sev, r)
    above = np.maximum(sev - (r + L), 0.0)
    return below + above

def apply_reinsurance_to_severities(
    severities: np.ndarray,
    rein: ReinsuranceConfig | None,
) -> np.ndarray:
    if rein is None or rein.get("type", "none") == "none":
        return severities

    if rein.get("type") == "xol":
        return apply_xol_per_loss(
            severities,
            retention=float(rein.get("retention", 0.0)),
            limit=float(rein.get("limit", 0.0)),
        )

    raise ValueError(f"Unsupported reinsurance type: {rein.get('type')}")
