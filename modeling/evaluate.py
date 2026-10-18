"""Score a trained GRU checkpoint on 2026 subsets (postseason / regular season, optional pitcher).

    python modeling/evaluate.py --name gru_mix --pitcher-id 660271
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
import torch

import train_sequence as T


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", type=Path, default=T.ROOT / "data" / "pitches.parquet")
    ap.add_argument("--runs", type=Path, default=T.ROOT / "modeling" / "runs")
    ap.add_argument("--name", default="gru_mix")
    ap.add_argument("--pitcher-id", type=int, default=None)
    a = ap.parse_args()

    device = "mps" if torch.backends.mps.is_available() else "cpu"
    cfg = json.loads((a.runs / f"{a.name}.json").read_text())["args"]
    groups = [g for g in cfg.get("groups", "").split(",") if g]
    D = T.load(a.data, int(cfg["train_from"]), int(cfg["min_id_pitches"]), groups)
    model = T.PitchGRU(D["X"].shape[1], D["n_pitchers"], cfg["pitcher_emb"] == "True",
                       int(cfg["hidden"]), int(cfg["layers"]), 0.0).to(device)
    model.load_state_dict(torch.load(a.runs / f"{a.name}.pt"))

    in26 = D["split"] == "test_2026"
    post = D["game_type"] != "R"
    subsets = {"2026 postseason, all pitchers": in26 & post, "2026 regular season, all pitchers": in26 & ~post}
    if a.pitcher_id:
        pit = D["pitcher"] == a.pitcher_id
        subsets[f"2026 postseason, pitcher {a.pitcher_id}"] = in26 & post & pit
        subsets[f"2026 regular season, pitcher {a.pitcher_id}"] = in26 & ~post & pit
    rows = []
    for name, mask in subsets.items():
        idx = np.flatnonzero(mask)
        if len(idx) == 0:
            rows.append({"subset": name, "n": 0})
            continue
        r = T.evaluate(model, D, idx, device)["all"]
        rows.append({"subset": name, "model": a.name, "n": r["n"], "top1_acc": r["acc"], "log_loss": r["log_loss"]})
    print(pd.DataFrame(rows).to_string(index=False))


if __name__ == "__main__":
    main()
