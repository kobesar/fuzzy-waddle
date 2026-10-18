"""Count-based baselines on data/pitches.parquet. These are the numbers a sequence model must beat.

Each level is a Dirichlet-smoothed class distribution backed off to the level above:
  global -> pitcher -> pitcher x count -> pitcher x count x previous pitch
Fitted on the train split, scored on val and test (rows with a real pitch label only).
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
K = 11  # CLASSES + OTHER
ALPHA = 300.0  # default pseudo-count weight on the parent distribution (val log loss: 10 < 30 < 100 < 300)


def counts(df: pd.DataFrame, keys: list) -> dict:
    out: dict = {}
    for key, g in df.groupby(keys, sort=False):
        key = key if isinstance(key, tuple) else (key,)
        out[key] = np.bincount(g["y"].to_numpy(), minlength=K).astype(float)
    return out


def dist(table: dict, key, parent: np.ndarray, alpha: float = ALPHA) -> np.ndarray:
    c = table.get(key)
    if c is None:
        return parent
    return (c + alpha * parent) / (c.sum() + alpha)


def score(P: np.ndarray, y: np.ndarray) -> tuple:
    ll = -np.log(np.clip(P[np.arange(len(y)), y], 1e-12, None)).mean()
    return float((P.argmax(1) == y).mean()), float(ll)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--alpha", type=float, default=ALPHA, help="smoothing pseudo-count")
    ap.add_argument("--data", type=Path, default=ROOT / "data" / "pitches.parquet")
    a = ap.parse_args()
    df = pd.read_parquet(a.data)
    df = df[df.y >= 0].copy()
    df["count"] = df["balls"].astype(str) + "-" + df["strikes"].astype(str)
    tr = df[df.split == "train"]

    g = np.bincount(tr.y, minlength=K).astype(float)
    g_dist = g / g.sum()
    t_p = counts(tr, ["pitcher_id"])
    t_pc = counts(tr, ["pitcher_id", "count"])
    t_pcp = counts(tr, ["pitcher_id", "count", "p1"])

    rows = []
    for split in ("val", "test"):
        ev = df[df.split == split]
        y = ev.y.to_numpy()
        P = {n: np.empty((len(ev), K)) for n in ("global", "pitcher", "pitcher_count", "pitcher_count_prev")}
        for i, (pid, cnt, p1) in enumerate(zip(ev.pitcher_id, ev["count"], ev.p1)):
            P["global"][i] = g_dist
            pp = dist(t_p, (pid,), g_dist, a.alpha)
            P["pitcher"][i] = pp
            pc = dist(t_pc, (pid, cnt), pp, a.alpha)
            P["pitcher_count"][i] = pc
            P["pitcher_count_prev"][i] = dist(t_pcp, (pid, cnt, p1), pc, a.alpha)
        for name, p in P.items():
            acc, ll = score(p, y)
            rows.append({"split": split, "model": name, "n": len(y), "top1_acc": round(acc, 4),
                         "log_loss": round(ll, 4)})
    print(pd.DataFrame(rows).to_string(index=False))
    seen = ev.pitcher_id.isin(tr.pitcher_id).mean()
    print(f"test rows whose pitcher appears in train: {seen:.1%}")


if __name__ == "__main__":
    main()
