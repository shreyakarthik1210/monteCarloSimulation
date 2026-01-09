import numpy as np
from typing import Dict, Any


def simulate_aggregate_loss(
    n_sims: int,
    freq_lambda: float,
    sev_mu: float,
    sev_sigma: float,
    capital: float,
    seed: int | None = None,
) -> Dict[str, Any]:
    """
    Monte Carlo aggregate loss simulation with:
    - Frequency: Poisson(freq_lambda)
    - Severity: Lognormal(mu, sigma)
    """

    rng = np.random.default_rng(seed)

    # 1) Simulate frequency
    N = rng.poisson(lam=freq_lambda, size=n_sims)

    # 2) Simulate severities (flattened)
    total_claims = N.sum()
    severities = rng.lognormal(mean=sev_mu, sigma=sev_sigma, size=total_claims)

    # 3) Aggregate losses
    S = np.zeros(n_sims)
    idx = 0
    for i, n in enumerate(N):
        if n > 0:
            S[i] = severities[idx : idx + n].sum()
            idx += n

    # 4) Risk metrics
    mean_loss = float(S.mean())
    var_95 = float(np.quantile(S, 0.95))
    var_99 = float(np.quantile(S, 0.99))

    tvar_95 = float(S[S >= var_95].mean())
    tvar_99 = float(S[S >= var_99].mean())

    ruin_prob = float((S > capital).mean())

    # 5) Histogram for plotting
    hist, bin_edges = np.histogram(S, bins=50)

    return {
        "metrics": {
            "mean": mean_loss,
            "VaR95": var_95,
            "VaR99": var_99,
            "TVaR95": tvar_95,
            "TVaR99": tvar_99,
            "ruinProb": ruin_prob,
        },
        "histogram": {
            "counts": hist.tolist(),
            "bins": bin_edges.tolist(),
        },
    }
import numpy as np
from typing import Dict, Any
from app.core.reinsurance import apply_reinsurance_to_severities, ReinsuranceConfig

def _metrics_and_hist(S: np.ndarray, capital: float, bins: int = 60) -> Dict[str, Any]:
    mean_loss = float(S.mean())
    var_95 = float(np.quantile(S, 0.95))
    var_99 = float(np.quantile(S, 0.99))
    tvar_95 = float(S[S >= var_95].mean())
    tvar_99 = float(S[S >= var_99].mean())
    ruin_prob = float((S > capital).mean())

    hist, edges = np.histogram(S, bins=bins)
    return {
        "metrics": {
            "mean": mean_loss,
            "VaR95": var_95,
            "VaR99": var_99,
            "TVaR95": tvar_95,
            "TVaR99": tvar_99,
            "ruinProb": ruin_prob,
        },
        "histogram": {"counts": hist.tolist(), "bins": edges.tolist()},
    }

def simulate_gross_net(
    n_sims: int,
    freq_lambda: float,
    sev_mu: float,
    sev_sigma: float,
    capital: float,
    reinsurance: ReinsuranceConfig | None = None,
    seed: int | None = None,
) -> Dict[str, Any]:
    rng = np.random.default_rng(seed)

    # 1) Frequency
    N = rng.poisson(lam=freq_lambda, size=n_sims)
    total_claims = int(N.sum())

    # 2) Severities (gross per claim)
    gross_sev = rng.lognormal(mean=sev_mu, sigma=sev_sigma, size=total_claims)

    # 3) Apply XoL to each claim to get insurer-paid net severities
    net_sev = apply_reinsurance_to_severities(gross_sev, reinsurance)

    # 4) Aggregate both using the same claim counts
    S_gross = np.zeros(n_sims)
    S_net = np.zeros(n_sims)

    idx = 0
    for i, n in enumerate(N):
        if n > 0:
            sl = slice(idx, idx + n)
            S_gross[i] = gross_sev[sl].sum()
            S_net[i] = net_sev[sl].sum()
            idx += n

    return {
        "gross": _metrics_and_hist(S_gross, capital),
        "net": _metrics_and_hist(S_net, capital),
        "reinsurance": reinsurance or {"type": "none"},
    }

