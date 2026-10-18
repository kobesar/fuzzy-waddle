"""Collect pitch-by-pitch data from the MLB Stats API live game feed.

One row per pitch. Output is month-sharded Parquet, resumable at shard level:

    <out>/<season>/<YYYY-MM>.parquet

Usage:
    python statsapi_pitch_collector.py --start-year 2022 --end-year 2025
    python statsapi_pitch_collector.py --start-date 2024-04-01 --end-date 2024-04-03

Leakage notes for modelers:
  * `balls`, `strikes`, `outs` are the state BEFORE the pitch (the feed reports the
    count AFTER the pitch; this module shifts it).
  * `home_score`/`away_score` are the score before the plate appearance.
  * `on_1b/on_2b/on_3b` are base occupancy at the start of the plate appearance;
    steals, pickoffs and wild pitches inside a PA are not reflected.
  * `pa_event`/`pa_event_type`/`pa_pitches` describe the whole PA outcome and must
    not be used as features.
  * Spin/break fields are null before 2017 (no Statcast in the feed).
"""
from __future__ import annotations

import argparse
import logging
import sys
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
import requests
from requests.adapters import HTTPAdapter

SCHEDULE_URL = "https://statsapi.mlb.com/api/v1/schedule"
FEED_URL = "https://statsapi.mlb.com/api/v1.1/game/{pk}/feed/live"
# Regular season + postseason (wild card, division, league, world series).
GAME_TYPES = "R,F,D,L,W"
BASES = ("1B", "2B", "3B")

log = logging.getLogger("statsapi_collector")


def make_session(workers: int) -> requests.Session:
    s = requests.Session()
    adapter = HTTPAdapter(pool_connections=workers, pool_maxsize=workers)
    s.mount("https://", adapter)
    s.headers["User-Agent"] = "pitch-sequence-collector/1.0"
    return s


def get_json(session: requests.Session, url: str, params: Optional[dict] = None,
             retries: int = 5, timeout: int = 60) -> dict:
    last: Optional[Exception] = None
    for attempt in range(retries):
        try:
            r = session.get(url, params=params, timeout=timeout)
            if r.status_code == 200:
                return r.json()
            if r.status_code not in (429, 500, 502, 503, 504):
                r.raise_for_status()
            last = RuntimeError(f"HTTP {r.status_code}")
        except requests.RequestException as e:
            last = e
        time.sleep(min(2 ** attempt, 30))
    raise RuntimeError(f"GET {url} failed after {retries} attempts: {last}")


def get_games(session: requests.Session, start: date, end: date) -> List[dict]:
    """Final games between start and end (inclusive). Skips postponed/suspended/unfinished."""
    data = get_json(session, SCHEDULE_URL, {
        "sportId": 1, "startDate": start.isoformat(), "endDate": end.isoformat(),
        "gameType": GAME_TYPES,
    })
    games = []
    for d in data.get("dates", []):
        for g in d["games"]:
            # A suspended game is listed on its start date and again on its resume date;
            # the feed holds the whole game, so only keep the original entry.
            if g["status"]["codedGameState"] == "F" and "resumedFrom" not in g:
                games.append({"game_pk": g["gamePk"], "game_date": g["officialDate"],
                              "game_type": g["gameType"], "season": int(g["season"])})
    return games


def _start_runners(play: dict) -> Dict[str, bool]:
    occ = {b: False for b in BASES}
    for r in play.get("runners", []):
        start = r.get("movement", {}).get("originBase")
        if start in occ:
            occ[start] = True
    return occ


def parse_game(feed: dict, meta: dict) -> List[Dict[str, Any]]:
    plays = feed["liveData"]["plays"]["allPlays"]
    rows: List[Dict[str, Any]] = []
    home_score = away_score = 0
    game_pitch = 0
    pitcher_pitches: Dict[int, int] = defaultdict(int)
    pitcher_pa: Dict[int, int] = defaultdict(int)
    pa_seen: Dict[tuple, int] = defaultdict(int)  # (pitcher, batter) -> prior PAs

    for play in plays:
        about = play["about"]
        matchup = play["matchup"]
        pitcher = matchup["pitcher"]["id"]
        batter = matchup["batter"]["id"]
        top = about["isTopInning"]
        runners = _start_runners(play)
        pitch_events = [e for e in play["playEvents"] if e.get("isPitch")]
        pitcher_pa[pitcher] += 1
        tto = pa_seen[(pitcher, batter)] + 1
        pa_seen[(pitcher, batter)] = tto

        balls, strikes = 0, 0
        for ev in pitch_events:
            game_pitch += 1
            pitcher_pitches[pitcher] += 1
            det = ev["details"]
            pd_ = ev.get("pitchData", {})
            co = pd_.get("coordinates", {})
            br = pd_.get("breaks", {})
            ptype = det.get("type", {})
            cnt = ev["count"]
            rows.append({
                "game_pk": meta["game_pk"],
                "game_date": meta["game_date"],
                "season": meta["season"],
                "game_type": meta["game_type"],
                "at_bat_index": play["atBatIndex"],
                "pitch_number": ev.get("pitchNumber"),
                "game_pitch_number": game_pitch,
                "pitcher_id": pitcher,
                "batter_id": batter,
                "pitcher_throws": matchup["pitchHand"]["code"],
                "batter_stands": matchup["batSide"]["code"],
                "inning": about["inning"],
                "is_top": top,
                "outs": cnt["outs"],
                "balls": balls,
                "strikes": strikes,
                "on_1b": runners["1B"], "on_2b": runners["2B"], "on_3b": runners["3B"],
                "home_score": home_score, "away_score": away_score,
                "pitcher_pitch_count": pitcher_pitches[pitcher],
                "pitcher_pa_number": pitcher_pa[pitcher],
                "times_through_order": tto,
                # target and pitch outcome
                "pitch_type": ptype.get("code"),
                "pitch_type_desc": ptype.get("description"),
                "type_confidence": pd_.get("typeConfidence"),
                "call_code": det.get("code"),
                "call_desc": det.get("description"),
                "is_strike": det.get("isStrike"),
                "is_ball": det.get("isBall"),
                "is_in_play": det.get("isInPlay"),
                # physical
                "start_speed": pd_.get("startSpeed"),
                "end_speed": pd_.get("endSpeed"),
                "plate_x": co.get("pX"), "plate_z": co.get("pZ"),
                "sz_top": pd_.get("strikeZoneTop"), "sz_bot": pd_.get("strikeZoneBottom"),
                "zone": pd_.get("zone"),
                "pfx_x": co.get("pfxX"), "pfx_z": co.get("pfxZ"),
                "release_x": co.get("x0"), "release_z": co.get("z0"),
                "extension": pd_.get("extension"),
                "plate_time": pd_.get("plateTime"),
                "spin_rate": br.get("spinRate"), "spin_dir": br.get("spinDirection"),
                "break_h": br.get("breakHorizontal"),
                "break_v": br.get("breakVertical"),
                "break_v_induced": br.get("breakVerticalInduced"),
                # PA-level outcome (do not use as features)
                "pa_event": play["result"].get("event"),
                "pa_event_type": play["result"].get("eventType"),
                "pa_pitches": len(pitch_events),
            })
            balls, strikes = min(cnt["balls"], 3), min(cnt["strikes"], 2)

        res = play["result"]
        home_score = res.get("homeScore", home_score)
        away_score = res.get("awayScore", away_score)
    return rows


def collect_game(session: requests.Session, meta: dict) -> List[Dict[str, Any]]:
    feed = get_json(session, FEED_URL.format(pk=meta["game_pk"]))
    return parse_game(feed, meta)


def month_ranges(start: date, end: date):
    cur = date(start.year, start.month, 1)
    while cur <= end:
        nxt = date(cur.year + (cur.month == 12), cur.month % 12 + 1, 1)
        yield max(cur, start), min(nxt - timedelta(days=1), end)
        cur = nxt


def collect_range(start: date, end: date, out: Path, workers: int, force: bool) -> None:
    session = make_session(workers)
    for m_start, m_end in month_ranges(start, end):
        full_month = (m_start.day == 1 and
                      (m_end + timedelta(days=1)).month != m_end.month)
        name = f"{m_start:%Y-%m}" if full_month else f"{m_start:%Y-%m}_{m_start:%d}-{m_end:%d}"
        shard = out / str(m_start.year) / f"{name}.parquet"
        if shard.exists() and not force:
            log.info("skip %s (exists)", shard)
            continue
        games = get_games(session, m_start, m_end)
        if not games:
            log.info("%s..%s no games", m_start, m_end)
            continue
        t0 = time.time()
        rows: List[Dict[str, Any]] = []
        failed: List[int] = []
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futs = {pool.submit(collect_game, session, g): g for g in games}
            for f in as_completed(futs):
                g = futs[f]
                try:
                    rows.extend(f.result())
                except Exception as e:  # noqa: BLE001 - record and continue, fail shard below
                    log.error("game %s failed: %s", g["game_pk"], e)
                    failed.append(g["game_pk"])
        if failed:
            raise SystemExit(f"{len(failed)} games failed in {m_start:%Y-%m}: {failed[:10]}; "
                             "shard not written, rerun to retry")
        df = pd.DataFrame(rows).sort_values(["game_date", "game_pk", "game_pitch_number"],
                                            kind="stable").reset_index(drop=True)
        shard.parent.mkdir(parents=True, exist_ok=True)
        tmp = shard.with_suffix(".tmp")
        df.to_parquet(tmp, index=False)
        tmp.replace(shard)
        log.info("%s: %d games, %d pitches, %.0fs, null pitch_type %.2f%%",
                 shard.name, len(games), len(df), time.time() - t0,
                 100 * df.pitch_type.isna().mean())


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--start-year", type=int)
    ap.add_argument("--end-year", type=int)
    ap.add_argument("--start-date", type=date.fromisoformat)
    ap.add_argument("--end-date", type=date.fromisoformat)
    ap.add_argument("--out", type=Path, default=Path(__file__).resolve().parent.parent / "data" / "raw")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--force", action="store_true", help="re-collect shards that already exist")
    a = ap.parse_args(argv)

    if a.start_date and a.end_date:
        start, end = a.start_date, a.end_date
    elif a.start_year and a.end_year:
        start, end = date(a.start_year, 1, 1), date(a.end_year, 12, 31)
        end = min(end, date.today())
    else:
        ap.error("give --start-year/--end-year or --start-date/--end-date")

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
                        stream=sys.stdout)
    collect_range(start, end, a.out, a.workers, a.force)


if __name__ == "__main__":
    main()
