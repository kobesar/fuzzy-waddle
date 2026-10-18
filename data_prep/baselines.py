"""Count-based baselines on data/pitches.parquet. These are the numbers a sequence model must beat.

  global             league pitch mix (train)
  pitcher            pitcher's pitch mix pooled over all train seasons (global for unseen pitchers)
  prior_mix          pitcher's mix in the previous season (global if < 200 pitches or no data)
  prior_mix_count    prior_mix reweighted by the league count effect P(y|count)/P(y)
  in_game_count      prior_mix updated with the pitcher's pitches so far this game
                     (Dirichlet posterior, BETA pseudo-pitches on the prior), then count-reweighted

Scored on val and test rows with a real pitch label.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
K = 11  # CLASSES + OTHER
MIN_PRIOR = 200
EPS = 1e-12


def score(P: np.ndarray, y: np.ndarray) -> tuple:
    ll = -np.log(np.clip(P[np.arange(len(y)), y], EPS, None)).mean()
    return float((P.argmax(1) == y).mean()), float(ll)


def season_mix(df: pd.DataFrame) -> pd.DataFrame:
    """Pitch mix per (pitcher, season) with >= MIN_PRIOR labelled pitches."""
    lab = df[df.y >= 0]
    cnt = lab.groupby(["pitcher_id", "season", "y"]).size().unstack(fill_value=0)
    cnt = cnt.reindex(columns=range(K), fill_value=0)
    cnt = cnt[cnt.sum(axis=1) >= MIN_PRIOR]
    return cnt.div(cnt.sum(axis=1), axis=0)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", type=Path, default=ROOT / "data" / "pitches.parquet")
    ap.add_argument("--pitcher-id", type=int, default=None, help="also report this pitcher on 2026 subsets")
    ap.add_argument("--beta", type=float, default=None, help="in-game prior weight; default: best on val")
    a = ap.parse_args()
    df = pd.read_parquet(a.data, columns=["game_pk", "pitcher_id", "game_pitch_number", "season",
                                          "split", "y", "balls", "strikes", "game_type"])
    df = df.sort_values(["game_pk", "pitcher_id", "game_pitch_number"], kind="stable").reset_index(drop=True)
    df["count"] = df.balls * 3 + df.strikes  # 0..11 (strikes capped at 2 -> max 11)

    tr = df[(df.split == "train") & (df.y >= 0)]
    g = np.bincount(tr.y, minlength=K).astype(float)
    g /= g.sum()
    pooled = tr.groupby(["pitcher_id", "y"]).size().unstack(fill_value=0).reindex(columns=range(K), fill_value=0)
    pooled = pooled.div(pooled.sum(axis=1), axis=0)
    cc = tr.groupby(["count", "y"]).size().unstack(fill_value=0).reindex(columns=range(K), fill_value=0)
    count_factor = (cc.div(cc.sum(axis=1), axis=0) / g).reindex(range(12)).fillna(1.0).to_numpy()

    mix = season_mix(df)
    mix_idx = mix.index
    ev = df[df.split.isin(["val", "test", "test_2026"])].copy()

    # prior-season mix per row
    key = pd.MultiIndex.from_arrays([ev.pitcher_id, ev.season - 1])
    pos = mix_idx.get_indexer(key)
    M = np.tile(g, (len(ev), 1))
    ok = pos >= 0
    M[ok] = 0.97 * mix.to_numpy()[pos[ok]] + 0.03 * g  # light smoothing so unseen classes keep mass

    # pitcher pooled mix
    ppos = pooled.index.get_indexer(ev.pitcher_id)
    Pp = np.tile(g, (len(ev), 1))
    pok = ppos >= 0
    Pp[pok] = 0.97 * pooled.to_numpy()[ppos[pok]] + 0.03 * g

    # pitcher's labelled pitches so far this game (excluding the current one)
    oh = np.zeros((len(ev), K))
    lab = (ev.y >= 0).to_numpy()
    oh[np.flatnonzero(lab), ev.y.to_numpy()[lab]] = 1.0
    seq = (ev.game_pk.astype("int64") * 10_000_000 + ev.pitcher_id).to_numpy()
    new = np.r_[True, seq[1:] != seq[:-1]]
    sid = np.cumsum(new) - 1
    cs = np.cumsum(oh, axis=0)
    base = cs[np.flatnonzero(new)] - oh[np.flatnonzero(new)]  # cumulative before each sequence start
    seen = cs - oh - base[sid]

    cf = count_factor[ev["count"].to_numpy()]

    def reweight(P):
        Q = P * cf
        return Q / Q.sum(1, keepdims=True)

    def in_game(beta):
        n = seen.sum(1, keepdims=True)
        return reweight((seen + beta * M) / (n + beta))

    split = ev.split.to_numpy()
    y = ev.y.to_numpy()
    keep = y >= 0
    betas = [a.beta] if a.beta else [1, 2, 5, 10, 20, 40]
    val = keep & (split == "val")
    best_beta = min(betas, key=lambda b: score(in_game(b)[val], y[val])[1])
    print(f"in-game prior weight beta = {best_beta} (chosen on val log loss)")

    models = {"global": np.tile(g, (len(ev), 1)), "pitcher": Pp, "prior_mix": M,
              "prior_mix_count": reweight(M), "in_game_count": in_game(best_beta)}
    rows = []
    for s in ("val", "test"):
        m = keep & (split == s)
        for name, P in models.items():
            acc, ll = score(P[m], y[m])
            rows.append({"split": s, "model": name, "n": int(m.sum()), "top1_acc": round(acc, 4),
                         "log_loss": round(ll, 4)})
    print(pd.DataFrame(rows).to_string(index=False))
    t = keep & (split == "test")
    print(f"test rows with a prior-season mix: {ok[t].mean():.1%}")

    in26 = keep & (split == "test_2026")
    if in26.any():
        post = (ev.game_type != "R").to_numpy()
        subsets = {"2026 postseason, all pitchers": in26 & post, "2026 regular season, all pitchers": in26 & ~post}
        if a.pitcher_id:
            pit = (ev.pitcher_id == a.pitcher_id).to_numpy()
            subsets[f"2026 postseason, pitcher {a.pitcher_id}"] = in26 & post & pit
            subsets[f"2026 regular season, pitcher {a.pitcher_id}"] = in26 & ~post & pit
        rows = []
        for sname, m in subsets.items():
            if not m.any():
                rows.append({"subset": sname, "n": 0})
                continue
            for name, P in models.items():
                acc, ll = score(P[m], y[m])
                rows.append({"subset": sname, "model": name, "n": int(m.sum()),
                             "top1_acc": round(acc, 4), "log_loss": round(ll, 4)})
        print(pd.DataFrame(rows).to_string(index=False))


if __name__ == "__main__":
    main()
