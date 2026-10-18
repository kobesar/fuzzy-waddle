"""Build the model-ready pitch table from the raw Stats API shards.

Reads   data/raw/<season>/*.parquet                (statsapi_pitch_collector.py)
Writes  data/pitches.parquet                        one row per pitch, sorted by game then pitch
        data/vocab.json                             pitch-class vocabulary and split definition

A pitch sequence is the ordered pitches of one pitcher in one game, i.e. rows grouped by
(game_pk, pitcher_id) and ordered by game_pitch_number. Every feature outside LEAKY_COLUMNS
is known before the pitch is thrown, so a causal model may use it as step-t input to predict
`y` at step t.

Pitch classes: the 10 common types keep their own id, any other real pitch type is OTHER,
and missing/non-pitch labels (null, PO, UN, '') get y = -1 and are excluded from training
targets but stay in the sequence as context (class id UNK in p1..p3).

Splits are by season: train <= 2023, val 2024, test 2025, test_2026 (season in progress; refresh
by recollecting the 2026 shards and rebuilding).
"""
from __future__ import annotations

import argparse
import glob
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
CLASSES = ["FF", "SI", "SL", "CH", "CU", "FC", "ST", "KC", "FS", "SV"]
OTHER = len(CLASSES)        # any other real pitch type (KN, EP, FO, CS, SC, FA)
UNK = len(CLASSES) + 1      # missing or non-pitch label
NON_PITCH = {"PO", "UN", ""}
SPLITS = {"train": (2017, 2023), "val": (2024, 2024), "test": (2025, 2025), "test_2026": (2026, 2026)}

# Describe the outcome of the pitch itself or of the whole plate appearance. Never inputs.
LEAKY_COLUMNS = [
    "pitch_type", "pitch_type_desc", "type_confidence", "call_code", "call_desc",
    "is_strike", "is_ball", "is_in_play", "start_speed", "end_speed", "plate_x", "plate_z",
    "zone", "pfx_x", "pfx_z", "release_x", "release_z", "extension", "plate_time",
    "spin_rate", "spin_dir", "break_h", "break_v", "break_v_induced",
    "pa_event", "pa_event_type", "pa_pitches", "y",
]


def load_raw(raw_dir: Path) -> pd.DataFrame:
    files = sorted(glob.glob(str(raw_dir / "*" / "*.parquet")))
    if not files:
        raise SystemExit(f"no shards under {raw_dir}")
    df = pd.concat((pd.read_parquet(f) for f in files), ignore_index=True)
    dup = df.duplicated(["game_pk", "game_pitch_number"]).sum()
    if dup:
        raise SystemExit(f"{dup} duplicated (game_pk, game_pitch_number) rows; recollect the shards")
    return df


def class_ids(pitch_type: pd.Series) -> pd.Series:
    mapping = {c: i for i, c in enumerate(CLASSES)}
    ids = pitch_type.map(mapping)
    other = ids.isna() & pitch_type.notna() & ~pitch_type.isin(NON_PITCH)
    ids = ids.where(~other, OTHER)
    return ids.fillna(UNK).astype("int16")


def build(df: pd.DataFrame) -> pd.DataFrame:
    df = df.sort_values(["game_pk", "game_pitch_number"], kind="stable").reset_index(drop=True)
    cls = class_ids(df["pitch_type"])
    df["y"] = cls.where(cls != UNK, -1).astype("int16")

    # previous pitches by the same pitcher in the same game (crosses plate appearances)
    g = cls.groupby([df["game_pk"], df["pitcher_id"]])
    for k in (1, 2, 3):
        df[f"p{k}"] = g.shift(k).fillna(-1).astype("int16")  # -1 = start of pitcher's game

    # previous pitch within the same plate appearance
    pa = df.groupby(["game_pk", "at_bat_index"])
    df["prev_call_code"] = pa["call_code"].shift(1)
    for col, new in (("start_speed", "prev_speed"), ("plate_x", "prev_plate_x"),
                     ("plate_z", "prev_plate_z")):
        df[new] = pa[col].shift(1)

    df["pitcher_score_diff"] = np.where(df["is_top"], df["home_score"] - df["away_score"],
                                        df["away_score"] - df["home_score"])
    df["runners_on"] = df[["on_1b", "on_2b", "on_3b"]].sum(axis=1).astype("int8")
    df["pitcher_idx"] = df.groupby(["game_pk", "pitcher_id"]).cumcount().astype("int32")

    df["split"] = ""
    for name, (lo, hi) in SPLITS.items():
        df.loc[df["season"].between(lo, hi), "split"] = name
    if (df["split"] == "").any():
        raise SystemExit("rows outside split definition")
    return df


def vocab() -> dict:
    return {
        "classes": CLASSES + ["OTHER"], "other_id": OTHER, "unk_id": UNK,
        "splits": SPLITS, "leaky_columns": LEAKY_COLUMNS,
        "sequence_key": ["game_pk", "pitcher_id"], "sequence_order": "game_pitch_number",
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--raw", type=Path, default=ROOT / "data" / "raw")
    ap.add_argument("--out", type=Path, default=ROOT / "data")
    a = ap.parse_args()
    df = build(load_raw(a.raw))
    a.out.mkdir(parents=True, exist_ok=True)
    df.to_parquet(a.out / "pitches.parquet", index=False)
    (a.out / "vocab.json").write_text(json.dumps(vocab(), indent=2))
    print(f"{len(df):,} pitches, {df.game_pk.nunique():,} games, "
          f"{df.groupby(['game_pk', 'pitcher_id']).ngroups:,} pitcher-game sequences")
    print(df.groupby("split").agg(pitches=("y", "size"), targets=("y", lambda s: (s >= 0).sum())))


if __name__ == "__main__":
    main()
