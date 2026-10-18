"""Batter / matchup feature groups for the pitch-sequence model. All are leak-free:
every value for a pitch uses only information available before that pitch.

  tend    batter's previous-season swing/zone-swing/chase/whiff rates, overall and per pitch class
  hist    pitcher's pitch mix against this batter in all earlier games (any season) and its size
  ingame  pitcher's pitches to this batter earlier in this game (previous plate appearances only,
          by class) and the result of the previous plate appearance against him
  sit     pitcher's previous-season mix in the current count x batter-side situation (shrunk to his
          overall previous-season mix)
  trend   pitcher's mix over his earlier games this season and over his last 3 appearances

`df` must be sorted by (game_pk, pitcher_id, game_pitch_number) and carry the columns used below.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

K = 11
SWING = {"S", "W", "F", "T", "X", "D", "E", "L", "M"}
WHIFF = {"S", "W", "T", "M"}
MIN_BATTER_PITCHES = 200
PA_CATS = ["strikeout", "walk", "hit", "ball_in_play_out"]
HIT_TYPES = {"single", "double", "triple", "home_run"}
WALK_TYPES = {"walk", "intent_walk", "hit_by_pitch"}


def _onehot(y: np.ndarray) -> np.ndarray:
    oh = np.zeros((len(y), K), dtype=np.float32)
    ok = y >= 0
    oh[np.flatnonzero(ok), y[ok]] = 1.0
    return oh


def tend_features(df: pd.DataFrame) -> np.ndarray:
    d = pd.DataFrame({"batter_id": df.batter_id, "season": df.season, "y": df.y})
    sw = df.call_code.isin(SWING)
    wh = df.call_code.isin(WHIFF)
    z = df.zone
    iz = (z >= 1) & (z <= 9)
    oz = z >= 11
    d["n"] = 1.0
    d["sw"], d["wh"], d["iz"], d["oz"] = sw.astype(float), wh.astype(float), iz.astype(float), oz.astype(float)
    d["izsw"], d["ozsw"] = (iz & sw).astype(float), (oz & sw).astype(float)
    base = ["n", "sw", "wh", "iz", "oz", "izsw", "ozsw"]
    train = (df.split == "train").to_numpy()
    lg = d.loc[train, base].sum()
    lg_sw, lg_iz, lg_oz = lg.sw / lg.n, lg.izsw / lg.iz, lg.ozsw / lg.oz
    lg_wh = lg.wh / lg.sw

    tot = d.groupby(["batter_id", "season"])[base].sum()
    tot = tot[tot.n >= MIN_BATTER_PITCHES]
    out = pd.DataFrame(index=tot.index)
    out["sw"] = (tot.sw + 100 * lg_sw) / (tot.n + 100)
    out["izsw"] = (tot.izsw + 50 * lg_iz) / (tot.iz + 50)
    out["ozsw"] = (tot.ozsw + 50 * lg_oz) / (tot.oz + 50)
    out["wh"] = (tot.wh + 50 * lg_wh) / (tot.sw + 50)
    out["logn"] = np.log1p(tot.n) / 10

    lab = d[d.y >= 0]
    cls = lab.groupby(["batter_id", "season", "y"])[["n", "sw", "wh"]].sum().unstack(fill_value=0)
    lt = d[train & (d.y >= 0).to_numpy()].groupby("y")[["n", "sw", "wh"]].sum()
    lg_sw_c = (lt.sw / lt.n).reindex(range(K)).fillna(lg_sw)
    lg_wh_c = (lt.wh / lt.sw.clip(lower=1)).reindex(range(K)).fillna(lg_wh)
    cls = cls.reindex(out.index).fillna(0)
    for c in range(K):
        n_c, sw_c, wh_c = cls[("n", c)], cls[("sw", c)], cls[("wh", c)]
        out[f"swc{c}"] = (sw_c + 30 * lg_sw_c[c]) / (n_c + 30)
        out[f"whc{c}"] = (wh_c + 15 * lg_wh_c[c]) / (sw_c + 15)
    out = out.reset_index()
    out["season"] += 1
    cols = [c for c in out.columns if c not in ("batter_id", "season")]

    league = np.array([lg_sw, lg_iz, lg_oz, lg_wh, 0.0] +
                      sum(([lg_sw_c[c], lg_wh_c[c]] for c in range(K)), []), dtype=np.float32)
    m = df[["batter_id", "season"]].merge(out, on=["batter_id", "season"], how="left")
    arr = m[cols].to_numpy(np.float32)
    has = ~np.isnan(arr[:, 0])
    arr[~has] = league
    return np.concatenate([arr, has[:, None].astype(np.float32)], axis=1)


def hist_features(df: pd.DataFrame, oh: np.ndarray) -> np.ndarray:
    gkey = df[["game_date", "game_pk"]].drop_duplicates().sort_values(["game_date", "game_pk"])
    gkey["g"] = np.arange(len(gkey))
    cols = [f"c{i}" for i in range(K)]
    t = pd.DataFrame(oh, columns=cols)
    t["pitcher_id"], t["batter_id"], t["game_pk"] = df.pitcher_id.values, df.batter_id.values, df.game_pk.values
    per = t.groupby(["pitcher_id", "batter_id", "game_pk"], sort=False)[cols].sum().reset_index()
    per = per.merge(gkey[["game_pk", "g"]], on="game_pk").sort_values(["pitcher_id", "batter_id", "g"])
    cum = per.groupby(["pitcher_id", "batter_id"], sort=False)[cols].cumsum() - per[cols]
    per[cols] = cum.to_numpy(np.float32)
    m = df[["pitcher_id", "batter_id", "game_pk"]].merge(per[["pitcher_id", "batter_id", "game_pk"] + cols],
                                                         on=["pitcher_id", "batter_id", "game_pk"], how="left")
    c = m[cols].fillna(0).to_numpy(np.float32)
    n = c.sum(1, keepdims=True)
    share = np.divide(c, n, out=np.zeros_like(c), where=n > 0)
    return np.concatenate([share, np.log1p(n) / 6], axis=1)


def ingame_features(df: pd.DataFrame, oh: np.ndarray) -> np.ndarray:
    cols = [f"c{i}" for i in range(K)]
    t = pd.DataFrame(oh, columns=cols)
    gb = [df.game_pk.values, df.pitcher_id.values, df.batter_id.values]
    cs_gb = t.groupby(gb, sort=False)[cols].cumsum().to_numpy(np.float32)
    cs_pa = t.groupby(gb + [df.at_bat_index.values], sort=False)[cols].cumsum().to_numpy(np.float32)
    c = cs_gb - cs_pa                                    # pitches from earlier plate appearances only
    n = c.sum(1, keepdims=True)
    share = np.divide(c, n, out=np.zeros_like(c), where=n > 0)

    et = df.pa_event_type
    cat = np.where(et == "strikeout", 0, np.where(et.isin(WALK_TYPES), 1, np.where(et.isin(HIT_TYPES), 2, 3)))
    pa = pd.DataFrame({"game_pk": df.game_pk.values, "pitcher_id": df.pitcher_id.values,
                       "batter_id": df.batter_id.values, "at_bat_index": df.at_bat_index.values, "cat": cat})
    pa = pa.drop_duplicates(["game_pk", "pitcher_id", "batter_id", "at_bat_index"])
    pa["prev"] = pa.groupby(["game_pk", "pitcher_id", "batter_id"], sort=False)["cat"].shift(1)
    m = df[["game_pk", "pitcher_id", "batter_id", "at_bat_index"]].merge(
        pa[["game_pk", "pitcher_id", "batter_id", "at_bat_index", "prev"]],
        on=["game_pk", "pitcher_id", "batter_id", "at_bat_index"], how="left")
    prev = m["prev"].to_numpy()
    pr = np.zeros((len(df), len(PA_CATS)), dtype=np.float32)
    ok = ~np.isnan(prev)
    pr[np.flatnonzero(ok), prev[ok].astype(int)] = 1.0
    return np.concatenate([share, np.log1p(n) / 3, pr], axis=1)


def sit_features(df: pd.DataFrame, oh: np.ndarray, alpha: float = 100.0) -> np.ndarray:
    train = (df.split == "train").to_numpy()
    g = oh[train].sum(0)
    g = g / g.sum()
    cols = [f"c{i}" for i in range(K)]
    t = pd.DataFrame(oh, columns=cols)
    t["pitcher_id"], t["season"] = df.pitcher_id.values, df.season.values
    t["cnt"] = (df.balls.astype(int) * 3 + df.strikes.astype(int)).values
    t["side"] = (df.batter_stands == "R").astype(int).values
    ps = t.groupby(["pitcher_id", "season"])[cols].sum()
    ps = ps[ps.sum(axis=1) >= MIN_BATTER_PITCHES]
    cell = t.groupby(["pitcher_id", "season", "cnt", "side"])[cols].sum()
    pos = ps.index.get_indexer(pd.MultiIndex.from_arrays([df.pitcher_id, df.season - 1]))
    mix = np.tile(g.astype(np.float32), (len(df), 1))
    ok = pos >= 0
    mix[ok] = 0.97 * (ps.to_numpy()[pos[ok]] / ps.to_numpy()[pos[ok]].sum(1, keepdims=True)) + 0.03 * g
    cpos = cell.index.get_indexer(pd.MultiIndex.from_arrays(
        [df.pitcher_id, df.season - 1, t["cnt"], t["side"]]))
    c = np.where((cpos >= 0)[:, None], cell.to_numpy()[np.clip(cpos, 0, None)], 0.0).astype(np.float32)
    c[~ok] = 0.0
    n = c.sum(1, keepdims=True)
    post = (c + alpha * mix) / (n + alpha)
    return np.concatenate([post.astype(np.float32), np.log1p(n) / 6], axis=1)


def trend_features(df: pd.DataFrame, oh: np.ndarray) -> np.ndarray:
    gkey = df[["game_date", "game_pk"]].drop_duplicates().sort_values(["game_date", "game_pk"])
    gkey["g"] = np.arange(len(gkey))
    cols = [f"c{i}" for i in range(K)]
    t = pd.DataFrame(oh, columns=cols)
    t["pitcher_id"], t["game_pk"], t["season"] = df.pitcher_id.values, df.game_pk.values, df.season.values
    per = t.groupby(["pitcher_id", "game_pk", "season"], sort=False)[cols].sum().reset_index()
    per = per.merge(gkey[["game_pk", "g"]], on="game_pk").sort_values(["pitcher_id", "g"]).reset_index(drop=True)
    std = per.groupby(["pitcher_id", "season"], sort=False)[cols].cumsum() - per[cols]
    rec = per.groupby("pitcher_id", sort=False)[cols].transform(lambda s: s.shift(1).rolling(3, min_periods=1).sum())
    out = {}
    for name, c in (("std", std.to_numpy(np.float32)), ("rec", rec.fillna(0).to_numpy(np.float32))):
        n = c.sum(1, keepdims=True)
        share = np.divide(c, n, out=np.zeros_like(c), where=n > 0)
        out[name] = np.concatenate([share, np.log1p(n) / 6], axis=1)
    feat = pd.DataFrame(np.concatenate([out["std"], out["rec"]], axis=1))
    feat["pitcher_id"], feat["game_pk"] = per.pitcher_id.values, per.game_pk.values
    m = df[["pitcher_id", "game_pk"]].merge(feat, on=["pitcher_id", "game_pk"], how="left")
    return m.drop(columns=["pitcher_id", "game_pk"]).fillna(0).to_numpy(np.float32)


def group_features(df: pd.DataFrame, groups: list) -> np.ndarray:
    if not groups:
        return np.zeros((len(df), 0), dtype=np.float32)
    oh = _onehot(df.y.to_numpy())
    parts = []
    if "tend" in groups:
        parts.append(tend_features(df))
    if "hist" in groups:
        parts.append(hist_features(df, oh))
    if "ingame" in groups:
        parts.append(ingame_features(df, oh))
    if "sit" in groups:
        parts.append(sit_features(df, oh))
    if "trend" in groups:
        parts.append(trend_features(df, oh))
    return np.concatenate(parts, axis=1)
