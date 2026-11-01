#!/usr/bin/env python3
"""Server-side Trackwrestling Ajax client.

IMPORTANT (verified 2026-11-01 from this box):
  - Chrome-like User-Agent headers → HTTP 406 on almost every TW URL.
  - Default / non-browser UA → LoadBalance shell + AjaxFunctions succeed for
    getTeamSchedule, getWrestlers, getTeams, getSeasonGBs, getTeamReports.
  - Bout grids (getEventMatchesJSP), Win-Types report bodies, and season-picker
    pages still need a browser capture → see docs/TW_PULL.md.

Never scrape cookies from a signed-in session or use credentials.
"""

from __future__ import annotations

import json
import logging
import re
import time
from typing import Any, Dict, List, Optional

import requests

logger = logging.getLogger("tw.client")

TW_ORIGIN = "https://www.trackwrestling.com"
AJAX = f"{TW_ORIGIN}/tw/seasons/AjaxFunctions.jsp"
LOAD_BALANCE = f"{TW_ORIGIN}/tw/seasons/LoadBalance.jsp"

SAFE_HEADERS = {
    "Accept": "*/*",
    "User-Agent": "ShawneeWrestlingDataBot/1.0 (+local; non-browser Ajax)",
}


class TwClientError(RuntimeError):
    pass


class TwClient:
    """Minimal TW Ajax client that works server-side from this box."""

    def __init__(
        self,
        season_id: str,
        team_id: Optional[str] = None,
        gb_id: str = "36",
        timeout: float = 60.0,
    ):
        self.season_id = str(season_id)
        self.team_id = str(team_id) if team_id else None
        self.gb_id = str(gb_id)
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(SAFE_HEADERS)
        self.tw_session_id: Optional[str] = None

    def mint_session(self, page_name: str = "TeamSchedule.jsp") -> str:
        page = page_name
        if self.team_id and "teamId=" not in page:
            page = f"{page};teamId={self.team_id}"
        url = (
            f"{LOAD_BALANCE}?seasonId={self.season_id}&gbId={self.gb_id}"
            f"&pageName={page}"
        )
        r = self.session.get(url, timeout=self.timeout)
        if r.status_code == 406:
            raise TwClientError(
                "LoadBalance returned 406 — refuse Chrome-like UAs; "
                "check that SAFE_HEADERS is in use."
            )
        if r.status_code != 200:
            raise TwClientError(f"LoadBalance HTTP {r.status_code}")
        m = re.search(r"twSessionId=([A-Za-z0-9]+)", r.text)
        if not m:
            raise TwClientError("No twSessionId in LoadBalance shell")
        self.tw_session_id = m.group(1)
        logger.info("Minted twSessionId=%s…", self.tw_session_id[:8])
        return self.tw_session_id

    def ajax(self, function: str, **params: Any) -> Any:
        if not self.tw_session_id:
            self.mint_session()
        q = {
            "TIM": str(int(time.time() * 1000)),
            "twSessionId": self.tw_session_id,
            "function": function,
            "seasonId": self.season_id,
        }
        if self.team_id:
            q["teamId"] = self.team_id
        for k, v in params.items():
            if v is not None:
                q[k] = str(v)
        r = self.session.get(AJAX, params=q, timeout=self.timeout)
        if r.status_code == 406:
            raise TwClientError(
                f"Ajax {function} HTTP 406 (Chrome-like UA blocked on this box)"
            )
        if r.status_code != 200:
            raise TwClientError(f"Ajax {function} HTTP {r.status_code}")
        text = r.text.strip()
        if text.startswith("'") and text.endswith("'") and "not a valid function" in text:
            raise TwClientError(text.strip("'"))
        if text == "null" or text == "":
            return None
        try:
            data = json.loads(text)
        except json.JSONDecodeError as e:
            raise TwClientError(f"Ajax {function} JSON error: {e}: {text[:120]!r}") from e
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except json.JSONDecodeError:
                pass
        return data

    def get_team_schedule(self) -> List[Any]:
        data = self.ajax("getTeamSchedule")
        if data is None:
            return []
        if not isinstance(data, list):
            raise TwClientError(f"getTeamSchedule expected list, got {type(data)}")
        return data

    def get_wrestlers(self) -> List[Any]:
        data = self.ajax("getWrestlers")
        if data is None:
            return []
        if not isinstance(data, list):
            raise TwClientError(f"getWrestlers expected list, got {type(data)}")
        return data

    def get_teams(self, gb_id: Optional[str] = None) -> List[Any]:
        data = self.ajax("getTeams", gbId=gb_id or self.gb_id)
        if data is None:
            return []
        if not isinstance(data, list):
            raise TwClientError(f"getTeams expected list, got {type(data)}")
        return data

    def get_season_gbs(self) -> List[Any]:
        data = self.ajax("getSeasonGBs")
        if data is None:
            return []
        if not isinstance(data, list):
            raise TwClientError(f"getSeasonGBs expected list, got {type(data)}")
        return data

    def get_team_reports(self) -> List[Any]:
        data = self.ajax("getTeamReports")
        if data is None:
            return []
        if not isinstance(data, list):
            raise TwClientError(f"getTeamReports expected list, got {type(data)}")
        return data

    def probe_server_side(self) -> Dict[str, Any]:
        report: Dict[str, Any] = {
            "season_id": self.season_id,
            "team_id": self.team_id,
            "gb_id": self.gb_id,
            "capabilities": {},
            "blocked": [],
        }
        try:
            self.mint_session()
            report["capabilities"]["load_balance_session"] = True
        except TwClientError as e:
            report["capabilities"]["load_balance_session"] = False
            report["blocked"].append(str(e))
            return report

        for name, fn in [
            ("getTeamSchedule", self.get_team_schedule),
            ("getWrestlers", self.get_wrestlers),
            ("getTeams", self.get_teams),
            ("getSeasonGBs", self.get_season_gbs),
            ("getTeamReports", self.get_team_reports),
        ]:
            try:
                data = fn()
                report["capabilities"][name] = {
                    "ok": True,
                    "count": len(data) if isinstance(data, list) else None,
                }
            except TwClientError as e:
                report["capabilities"][name] = {"ok": False, "error": str(e)}

        try:
            raw = self.ajax("getEventMatchesJSP", eventId="0")
            report["capabilities"]["getEventMatchesJSP"] = {
                "ok": raw is not None,
                "note": "null without a browser EventMatches session",
            }
        except TwClientError as e:
            report["capabilities"]["getEventMatchesJSP"] = {"ok": False, "error": str(e)}

        report["browser_required"] = [
            "seasonId discovery (no public getSeasons / PreDefinedSeasons Ajax)",
            "EventMatches bout grids (getEventMatchesJSP returns null server-side)",
            "Win Types / Stats by Wrestler report HTML bodies",
            "NJSIAA District/Region/State placement grids when not in event captures",
        ]
        return report


def schedule_url(season_id: str, team_id: str, gb_id: str = "36") -> str:
    return (
        f"{LOAD_BALANCE}?seasonId={season_id}&gbId={gb_id}"
        f"&pageName=TeamSchedule.jsp;teamId={team_id}"
    )


def roster_url(season_id: str, team_id: str, gb_id: str = "36") -> str:
    return (
        f"{LOAD_BALANCE}?seasonId={season_id}&gbId={gb_id}"
        f"&pageName=TeamRoster.jsp;teamId={team_id}"
    )


def statistics_url(season_id: str, team_id: str, gb_id: str = "36") -> str:
    return (
        f"{LOAD_BALANCE}?seasonId={season_id}&gbId={gb_id}"
        f"&pageName=Statistics.jsp;teamId={team_id}"
    )


def event_matches_url(season_id: str, event_id: str, gb_id: str = "36") -> str:
    return (
        f"{LOAD_BALANCE}?seasonId={season_id}&gbId={gb_id}"
        f"&pageName=EventMatches.jsp;eventId={event_id}"
    )
