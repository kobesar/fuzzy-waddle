"""Causal GRU over pitcher-game pitch sequences. Predicts the pitch class of every pitch.

Input at step t (all known before pitch t is thrown):
  count/outs/inning/runners/score/handedness/times-through-order/pitch count,
  previous pitch in the sequence (class, call, speed, location),
  the pitcher's pitch mix from the previous season (zeros + flag if unavailable),
  optionally a pitcher-id embedding (--pitcher-emb).

Metrics use the same rows as data_prep/baselines.py: pitches with a real label.
Run data_prep/build_dataset.py first.
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import torch.nn.functional as F

ROOT = Path(__file__).resolve().parent.parent
K = 11                      # classes incl. OTHER
PREV_VOCAB = K + 2          # 0 = start of sequence, 1..K = class, K+1 = unknown label
CALL_CODES = ["B", "C", "S", "F", "X", "D", "E", "T", "L", "M", "W", "*B", "I", "P", "R", "V", "Q", "O", "H"]
MIN_PRIOR_PITCHES = 200
MAX_LEN = 160


def load(path: Path, train_from: int, min_id_pitches: int):
    cols = ["game_pk", "pitcher_id", "game_pitch_number", "season", "split", "y", "p1", "balls",
            "strikes", "outs", "inning", "is_top", "on_1b", "on_2b", "on_3b", "pitcher_score_diff",
            "batter_stands", "pitcher_throws", "times_through_order", "pitcher_pitch_count",
            "pitch_number", "call_code", "start_speed", "plate_x", "plate_z", "game_type"]
    df = pd.read_parquet(path, columns=cols)
    df = df.sort_values(["game_pk", "pitcher_id", "game_pitch_number"], kind="stable").reset_index(drop=True)

    # prior-season pitch mix per pitcher (labels from season-1 only)
    lab = df[df.y >= 0]
    cnt = lab.groupby(["pitcher_id", "season", "y"]).size().unstack(fill_value=0).reindex(columns=range(K), fill_value=0)
    cnt = cnt[cnt.sum(axis=1) >= MIN_PRIOR_PITCHES]
    mix = cnt.div(cnt.sum(axis=1), axis=0)
    mix.columns = [f"mix{i}" for i in range(K)]
    mix = mix.reset_index()
    mix["season"] += 1
    df = df.merge(mix, on=["pitcher_id", "season"], how="left")
    has_prior = df["mix0"].notna()
    mixcols = [f"mix{i}" for i in range(K)]
    df[mixcols] = df[mixcols].fillna(0.0)

    g = df.groupby(["game_pk", "pitcher_id"], sort=False)
    prev_call = g["call_code"].shift(1)
    prev_speed = g["start_speed"].shift(1)
    prev_x = g["plate_x"].shift(1)
    prev_z = g["plate_z"].shift(1)
    call_map = {c: i + 1 for i, c in enumerate(CALL_CODES)}
    call_id = prev_call.map(call_map).fillna(len(CALL_CODES) + 1)
    call_id = call_id.where(prev_call.notna(), 0).astype(np.int64)

    def num(s, scale, fill=0.0):
        return (s.astype(np.float32) / scale).fillna(fill).to_numpy(np.float32)

    feats = [
        num(df.balls, 3), num(df.strikes, 2), num(df.outs, 2), num(df.inning.clip(upper=12), 12),
        df.is_top.astype(np.float32).to_numpy(),
        df.on_1b.astype(np.float32).to_numpy(), df.on_2b.astype(np.float32).to_numpy(),
        df.on_3b.astype(np.float32).to_numpy(),
        num(df.pitcher_score_diff.clip(-10, 10), 10),
        (df.batter_stands == "R").astype(np.float32).to_numpy(),
        (df.pitcher_throws == "R").astype(np.float32).to_numpy(),
        num(df.times_through_order.clip(upper=4), 4), num(df.pitcher_pitch_count.clip(upper=130), 100),
        (df.pitch_number == 1).astype(np.float32).to_numpy(),
        num(prev_speed - 85, 10), prev_speed.isna().astype(np.float32).to_numpy(),
        num(prev_x.clip(-3, 3), 2), num(prev_z.clip(-1, 6) - 2.5, 2),
        has_prior.astype(np.float32).to_numpy(),
    ] + [df[c].to_numpy(np.float32) for c in mixcols]
    X = np.stack(feats, axis=1)

    prev_cls = (df.p1.to_numpy() + 1).astype(np.int64)         # -1 start -> 0, class c -> c+1
    prev_cls = np.where(prev_cls > K, K + 1, prev_cls)         # UNK class id (K) -> K+1
    y = df.y.to_numpy(np.int64)

    key = df.game_pk.to_numpy() * 10_000_000 + df.pitcher_id.to_numpy()
    new = np.r_[True, key[1:] != key[:-1]]
    starts = np.flatnonzero(new)
    lens = np.diff(np.r_[starts, len(df)])
    seq_split = df.split.to_numpy()[starts]

    # pitcher vocab from training rows
    tr = df[(df.split == "train") & (df.season >= train_from) & (df.y >= 0)]
    c = tr.pitcher_id.value_counts()
    vocab = {pid: i + 1 for i, pid in enumerate(c[c >= min_id_pitches].index)}
    seq_pitcher = df.pitcher_id.to_numpy()[starts]
    seq_pid = np.array([vocab.get(p, 0) for p in seq_pitcher], dtype=np.int64)
    seen_train = np.isin(seq_pitcher, c.index.to_numpy())
    seq_season = df.season.to_numpy()[starts]
    return dict(X=X, prev_cls=prev_cls, pitcher=seq_pitcher, game_type=df.game_type.to_numpy()[starts], call_id=call_id.to_numpy(), y=y, starts=starts, lens=lens,
                split=seq_split, pid=seq_pid, seen=seen_train, season=seq_season, n_pitchers=len(vocab) + 1)


class PitchGRU(nn.Module):
    def __init__(self, n_num, n_pitchers, use_pitcher, hidden, layers, dropout):
        super().__init__()
        self.use_pitcher = use_pitcher
        self.prev_emb = nn.Embedding(PREV_VOCAB, 16)
        self.call_emb = nn.Embedding(len(CALL_CODES) + 2, 8)
        self.pit_emb = nn.Embedding(n_pitchers, 32) if use_pitcher else None
        d_in = n_num + 16 + 8 + (32 if use_pitcher else 0)
        self.inp = nn.Sequential(nn.Linear(d_in, hidden), nn.GELU(), nn.Dropout(dropout))
        self.gru = nn.GRU(hidden, hidden, layers, batch_first=True, dropout=dropout if layers > 1 else 0)
        self.head = nn.Sequential(nn.Linear(2 * hidden, hidden), nn.GELU(), nn.Dropout(dropout),
                                  nn.Linear(hidden, K))

    def forward(self, x, prev_cls, call_id, pid):
        parts = [x, self.prev_emb(prev_cls), self.call_emb(call_id)]
        if self.use_pitcher:
            if self.training:  # id dropout so the model also works for unseen pitchers
                pid = torch.where(torch.rand(pid.shape, device=pid.device) < 0.2, torch.zeros_like(pid), pid)
            parts.append(self.pit_emb(pid)[:, None, :].expand(-1, x.shape[1], -1))
        h0 = self.inp(torch.cat(parts, -1))
        out, _ = self.gru(h0)
        return self.head(torch.cat([out, h0], -1))


def batches(D, seq_idx, batch, shuffle, rng, device):
    lens = np.minimum(D["lens"][seq_idx], MAX_LEN)
    if shuffle:
        order = rng.permutation(len(seq_idx))
        chunk = batch * 50
        parts = []
        for i in range(0, len(order), chunk):
            c = order[i:i + chunk]
            parts.append(c[np.argsort(lens[c], kind="stable")])
        groups = [p[j:j + batch] for p in parts for j in range(0, len(p), batch)]
        rng.shuffle(groups)
    else:
        order = np.argsort(lens, kind="stable")
        groups = [order[j:j + batch] for j in range(0, len(order), batch)]
    for gi in groups:
        si = seq_idx[gi]
        L = int(lens[gi].max())
        ar = np.arange(L)[None, :]
        valid = ar < lens[gi][:, None]
        idx = np.where(valid, D["starts"][si][:, None] + ar, 0)
        yb = np.where(valid, D["y"][idx], -1)
        t = lambda a, dt=None: torch.as_tensor(a, dtype=dt).to(device)
        yield (si, t(D["X"][idx]), t(D["prev_cls"][idx]), t(D["call_id"][idx]), t(D["pid"][si]), t(yb))


@torch.no_grad()
def evaluate(model, D, seq_idx, device, batch=1024):
    model.eval()
    nll = {"all": 0.0, "seen": 0.0, "unseen": 0.0}
    hit = dict(nll)
    n = dict(nll)
    for si, x, pc, ci, pid, y in batches(D, seq_idx, batch, False, None, device):
        logits = model(x, pc, ci, pid)
        m = y >= 0
        lp = F.log_softmax(logits, -1)
        yy = y.clamp(min=0)
        tok_nll = -lp.gather(-1, yy[..., None])[..., 0]
        tok_hit = (lp.argmax(-1) == yy)
        seen = torch.as_tensor(D["seen"][si]).to(device)[:, None].expand_as(m)
        for name, mm in (("all", m), ("seen", m & seen), ("unseen", m & ~seen)):
            nll[name] += float(tok_nll[mm].sum())
            hit[name] += float(tok_hit[mm].sum())
            n[name] += float(mm.sum())
    return {k: {"n": int(n[k]), "acc": round(hit[k] / max(n[k], 1), 4), "log_loss": round(nll[k] / max(n[k], 1), 4)}
            for k in n}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", type=Path, default=ROOT / "data" / "pitches.parquet")
    ap.add_argument("--out", type=Path, default=ROOT / "modeling" / "runs")
    ap.add_argument("--name", default="gru")
    ap.add_argument("--train-from", type=int, default=2017)
    ap.add_argument("--pitcher-emb", action="store_true")
    ap.add_argument("--min-id-pitches", type=int, default=1000)
    ap.add_argument("--hidden", type=int, default=192)
    ap.add_argument("--layers", type=int, default=2)
    ap.add_argument("--dropout", type=float, default=0.2)
    ap.add_argument("--epochs", type=int, default=8)
    ap.add_argument("--batch", type=int, default=256)
    ap.add_argument("--lr", type=float, default=2e-3)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--max-seqs", type=int, default=0, help="debug: limit training sequences")
    a = ap.parse_args()

    torch.manual_seed(a.seed)
    rng = np.random.default_rng(a.seed)
    device = "mps" if torch.backends.mps.is_available() else "cpu"
    t0 = time.time()
    D = load(a.data, a.train_from, a.min_id_pitches)
    tr = np.flatnonzero((D["split"] == "train") & (D["season"] >= a.train_from))
    if a.max_seqs:
        tr = tr[: a.max_seqs]
    va = np.flatnonzero(D["split"] == "val")
    te = np.flatnonzero(D["split"] == "test")
    print(f"device {device}; load {time.time() - t0:.0f}s; sequences train {len(tr):,} val {len(va):,} "
          f"test {len(te):,}; features {D['X'].shape[1]}; pitcher vocab {D['n_pitchers']}", flush=True)

    model = PitchGRU(D["X"].shape[1], D["n_pitchers"], a.pitcher_emb, a.hidden, a.layers, a.dropout).to(device)
    opt = torch.optim.AdamW(model.parameters(), lr=a.lr, weight_decay=1e-2)
    steps = a.epochs * int(np.ceil(len(tr) / a.batch))
    sched = torch.optim.lr_scheduler.OneCycleLR(opt, max_lr=a.lr, total_steps=steps, pct_start=0.1)
    a.out.mkdir(parents=True, exist_ok=True)
    best, best_state, log = 1e9, None, []
    for ep in range(1, a.epochs + 1):
        model.train()
        tot, cnt, t1 = 0.0, 0, time.time()
        for si, x, pc, ci, pid, y in batches(D, tr, a.batch, True, rng, device):
            logits = model(x, pc, ci, pid)
            loss = F.cross_entropy(logits.reshape(-1, K), y.reshape(-1), ignore_index=-1)
            opt.zero_grad(set_to_none=True)
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            opt.step()
            sched.step()
            tot += float(loss) * int((y >= 0).sum())
            cnt += int((y >= 0).sum())
        v = evaluate(model, D, va, device)
        log.append({"epoch": ep, "train_loss": round(tot / cnt, 4), "val": v["all"]})
        print(f"epoch {ep}: train {tot / cnt:.4f} | val acc {v['all']['acc']} ll {v['all']['log_loss']} "
              f"({time.time() - t1:.0f}s)", flush=True)
        if v["all"]["log_loss"] < best:
            best = v["all"]["log_loss"]
            best_state = {k: t.detach().cpu().clone() for k, t in model.state_dict().items()}
    model.load_state_dict(best_state)
    res = {"args": {k: str(v) for k, v in vars(a).items()}, "val": evaluate(model, D, va, device),
           "test": evaluate(model, D, te, device), "epochs": log}
    (a.out / f"{a.name}.json").write_text(json.dumps(res, indent=2))
    torch.save(best_state, a.out / f"{a.name}.pt")
    print(json.dumps({"val": res["val"], "test": res["test"]}, indent=1))


if __name__ == "__main__":
    main()
