"""DEF-VOLSCALE-01 — volatility-scaled sizing + portfolio vol target.

Vol is used for SIZING ONLY, never as an alpha signal. Each instrument targets
equal risk; the whole book is then scaled to a portfolio vol target (capped at
k_max leverage). Per-instrument and per-sleeve gross caps prevent any single
name or asset class from dominating.
"""
from __future__ import annotations

import numpy as np


def estimate_cov(ret_window: np.ndarray, trading_days_year: int):
    """Annualized covariance matrix and per-instrument vol from a returns window.

    Columns with any NaN in the window get vol=NaN (insufficient/again history);
    NaNs are zero-filled in the covariance so finite instruments are unaffected.
    """
    finite_col = np.all(np.isfinite(ret_window), axis=0)
    filled = np.where(np.isfinite(ret_window), ret_window, 0.0)
    cov = np.cov(filled, rowvar=False) * trading_days_year
    cov = np.atleast_2d(cov)
    vol = np.sqrt(np.clip(np.diag(cov), 0, None))
    vol = np.where(finite_col, vol, np.nan)
    return cov, vol


def target_weights(signs: np.ndarray, vol: np.ndarray, cov: np.ndarray,
                   sleeve_ids: np.ndarray, p) -> np.ndarray:
    """Vol-scaled, capped, portfolio-vol-targeted weights (per instrument)."""
    m = len(signs)
    w = np.zeros(m)
    valid = np.isfinite(vol) & (vol > 0) & (signs != 0)
    w[valid] = signs[valid] * (p.target_vol_inst / vol[valid])
    # per-instrument gross cap
    w = np.clip(w, -p.max_inst_weight, p.max_inst_weight)

    # per-sleeve gross cap (each sleeve <= max_sleeve_gross of total gross)
    total_gross = np.abs(w).sum()
    if total_gross > 0:
        for s in np.unique(sleeve_ids):
            mask = sleeve_ids == s
            sleeve_gross = np.abs(w[mask]).sum()
            cap = p.max_sleeve_gross * total_gross
            if sleeve_gross > cap and sleeve_gross > 0:
                w[mask] *= cap / sleeve_gross

    # portfolio vol target
    sig_port = float(np.sqrt(max(w @ cov @ w, 0.0)))
    if sig_port <= 0:
        return np.zeros(m)
    k = min(p.target_vol_port / sig_port, p.k_max)
    return w * k
