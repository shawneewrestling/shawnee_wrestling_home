#!/usr/bin/env python3
"""Normalized NJ school alias table + logo lookup for Shawnee Wrestling site-v2.

Trackwrestling remains the sole schedule source. Logos are looked up from
data/logos.json (GoBound / school sites). Missing logos fall back to an initials badge PNG.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

ROOT = Path(__file__).resolve().parent

# Canonical slug -> display name + common TW/GoBound aliases (lowercase).
# Keep aliases broad: typos, spacing, abbreviations, mascot suffixes.
SCHOOLS: Dict[str, Dict[str, Any]] = {
    "shawnee": {"name": "Shawnee", "aliases": ["shawnee high school", "shawnee hs", "shaw"]},
    "cherry-hill-west": {"name": "Cherry Hill West", "aliases": ["cherry hill  west", "cherry hill west", "chw", "cherryhill west"]},
    "cherry-hill-east": {"name": "Cherry Hill East", "aliases": ["cherry hill  east", "cherry hill east", "che", "cherryhill east"]},
    "moorestown": {"name": "Moorestown", "aliases": ["moorestown hs", "moorestown high school"]},
    "bishop-eustace": {"name": "Bishop Eustace Prep", "aliases": ["bishop eustace", "bishop eustace preparatory", "eustace"]},
    "paul-vi": {"name": "Paul VI", "aliases": ["paul vi", "paul vi hs", "paulvi"]},
    "eastern": {"name": "Eastern Regional", "aliases": ["eastern", "eastern regional", "eastern regional hs"]},
    "rancocas-valley": {"name": "Rancocas Valley", "aliases": ["rancocas valley", "rancocas valley regional", "rv", "rvr"]},
    "notre-dame": {"name": "Notre Dame", "aliases": ["notre dame", "notre dame irish", "notre dame hs", "notre dame hs - green pond"]},
    "point-pleasant-boro": {"name": "Point Pleasant Boro", "aliases": ["point pleasant boro", "point pleasant borough", "ppb", "ppborough"]},
    "delran": {"name": "Delran", "aliases": ["delran", "delran bears", "delran hs"]},
    "cinnaminson": {"name": "Cinnaminson", "aliases": ["cinnaminson", "cinn.", "cinn", "cinnaminson pirates"]},
    "collingswood": {"name": "Collingswood", "aliases": ["collingswood", "colls", "collingswood panthers"]},
    "pemberton": {"name": "Pemberton", "aliases": ["pemberton", "pemberton township", "pemberton township hornets"]},
    "highland-regional": {"name": "Highland Regional", "aliases": ["highland", "highland regional", "highland regional/triton"]},
    "triton-regional": {"name": "Triton Regional", "aliases": ["triton", "triton regional", "trn"]},  # note: TW also uses TRN for Toms River North — see below
    "washington-township": {"name": "Washington Township", "aliases": ["washington township", "wash twp"]},
    "delsea": {"name": "Delsea Regional", "aliases": ["delsea", "delsea regional"]},
    "northern-burlington": {"name": "Northern Burlington", "aliases": [
        "northern burlington", "northern burlington ( columbus)", "northern  burlington ( columbus)",
        "northern burlington columbus", "northern burlington greyhounds", "nburl",
    ]},
    "haddonfield": {"name": "Haddonfield", "aliases": [
        "haddonfield", "haddonfield high schol", "haddonfield high school", "haddonfield memorial", "hmemorial",
    ]},
    "robbinsville": {"name": "Robbinsville", "aliases": ["robbinsville", "robbinsville hs"]},
    "absegami": {"name": "Absegami", "aliases": ["absegami", "absegami hs"]},
    "lacey": {"name": "Lacey Township", "aliases": ["lacey", "lacey township", "lacey township hs"]},
    "toms-river-north": {"name": "Toms River North", "aliases": [
        "toms river north", "toms river  north", "tr north", "t.r. north",
    ]},
    "camden-catholic": {"name": "Camden Catholic", "aliases": ["camden catholic", "camden catholic hs"]},
    "west-deptford": {"name": "West Deptford", "aliases": ["west deptford", "west deptford hs", "westdeptford"]},
    "west-windsor-plainsboro-north": {"name": "West Windsor-Plainsboro North", "aliases": [
        "west windsor-plainsboro north", "west windsor plainsboro north", "wwpn", "ww-p north",
    ]},
    "seneca": {"name": "Seneca", "aliases": ["seneca", "seneca hs"]},
    "cherokee": {"name": "Cherokee", "aliases": ["cherokee", "cherokee hs"]},
    "lenape": {"name": "Lenape", "aliases": ["lenape", "lenape hs"]},
    "st-joseph-hammonton": {"name": "St. Joseph (Hammonton)", "aliases": [
        "st joseph (hammonton) hs", "st. joes (hamm)", "st joes (hamm)", "st. joseph hammonton",
        "st joseph hammonton", "st. joe's hammonton", "sjhh", "st joes hammonton",
    ]},
    "pennsauken": {"name": "Pennsauken", "aliases": ["pennsauken", "pc", "pennsauken hs"]},
    "timber-creek": {"name": "Timber Creek", "aliases": ["timber creek", "timber creek hs"]},
    "kingsway": {"name": "Kingsway Regional", "aliases": ["kingsway", "kingsway regional"]},
    "ocean-city": {"name": "Ocean City", "aliases": ["ocean city"]},
    "woodstown": {"name": "Woodstown", "aliases": ["woodstown"]},
    "overbrook": {"name": "Overbrook", "aliases": ["overbrook"]},
    "gloucester-city": {"name": "Gloucester City", "aliases": ["gloucester city jr/sr", "gloucester city"]},
    "maple-shade": {"name": "Maple Shade", "aliases": ["maple shade"]},
    "pingry": {"name": "Pingry School", "aliases": ["pingry school", "pingry"]},
    "manasquan": {"name": "Manasquan", "aliases": ["manasquan"]},
    "paramus-catholic": {"name": "Paramus Catholic", "aliases": ["paramus catholic"]},
    "high-point": {"name": "High Point Regional", "aliases": ["high point regional", "high point"]},
    "st-peters-prep": {"name": "St. Peter's Prep", "aliases": ["st peters preparatory school", "st. peters preparatory school", "st peter's prep"]},
    "peddie": {"name": "Peddie School", "aliases": ["the peddie school", "peddie"]},
    "hunterdon-central": {"name": "Hunterdon Central", "aliases": ["hunterdon central reg", "hunterdon central"]},
    "southern-regional": {"name": "Southern Regional", "aliases": ["southern regional"]},
    "toms-river-east": {"name": "Toms River East", "aliases": ["toms river east h.s.", "toms river east"]},
    "immaculata": {"name": "Immaculata", "aliases": ["immaculata"]},
    "nutley": {"name": "Nutley", "aliases": ["nutley"]},
    "livingston": {"name": "Livingston", "aliases": ["livingston"]},
    "morris-hills": {"name": "Morris Hills", "aliases": ["morris hills"]},
}


def _norm(s: str) -> str:
    s = (s or "").lower()
    s = s.replace("`", "'")
    s = re.sub(r"[^a-z0-9]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


# Build reverse alias index
_ALIAS_TO_SLUG: Dict[str, str] = {}
for slug, info in SCHOOLS.items():
    _ALIAS_TO_SLUG[_norm(slug.replace("-", " "))] = slug
    _ALIAS_TO_SLUG[_norm(info["name"])] = slug
    for a in info.get("aliases") or []:
        _ALIAS_TO_SLUG[_norm(a)] = slug


def slugify_raw(name: str) -> str:
    s = (name or "").lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s


def resolve_school(name: str) -> Tuple[Optional[str], Optional[str]]:
    """Return (canonical_slug, display_name) or (None, cleaned name)."""
    if not name or not str(name).strip():
        return None, None
    raw = str(name).strip()
    if raw in ("0", "-", "—"):
        return None, None
    n = _norm(raw)
    if n in _ALIAS_TO_SLUG:
        slug = _ALIAS_TO_SLUG[n]
        return slug, SCHOOLS[slug]["name"]
    # fuzzy contains / startswith on alias keys (longest first)
    for alias in sorted(_ALIAS_TO_SLUG.keys(), key=len, reverse=True):
        if len(alias) < 4:
            continue
        if alias in n or n in alias:
            slug = _ALIAS_TO_SLUG[alias]
            return slug, SCHOOLS[slug]["name"]
    # special: TRN in multi-meet context means Toms River North (not Triton)
    if n in ("trn",):
        return "toms-river-north", SCHOOLS["toms-river-north"]["name"]
    return slugify_raw(raw) or None, re.sub(r"\s+", " ", raw)


def initials_for(name: str) -> str:
    parts = [p for p in re.split(r"[^A-Za-z0-9]+", name or "") if p]
    if not parts:
        return "?"
    if len(parts) == 1:
        return parts[0][:2].upper()
    return (parts[0][0] + parts[-1][0]).upper()


def ensure_initials_badge(slug: str, display: str, logos_dir: Path) -> str:
    """Create a simple initials PNG if missing; return assets-relative path."""
    logos_dir.mkdir(parents=True, exist_ok=True)
    out = logos_dir / f"{slug}-initials.png"
    rel = f"assets/logos/{out.name}"
    if out.exists():
        return rel
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        # Minimal 1x1 placeholder written as SVG-like text fallback via tiny PNG manually
        # Write a tiny valid PNG with no pillow — skip and return empty
        return ""
    img = Image.new("RGBA", (128, 128), (0, 32, 96, 255))
    draw = ImageDraw.Draw(img)
    text = initials_for(display)
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 48)
    except Exception:
        font = ImageFont.load_default()
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text(((128 - tw) / 2, (128 - th) / 2 - 4), text, fill=(255, 255, 255, 255), font=font)
    img.save(out)
    return rel


def load_logos_map(path: Path | None = None) -> Dict[str, Any]:
    path = path or (ROOT / "data" / "logos.json")
    if not path.exists():
        return {}
    import json
    raw = json.loads(path.read_text())
    return raw if isinstance(raw, dict) and "logos" not in raw else raw.get("logos", raw)


def lookup_logo(
    name_or_slug: str,
    logos_map: Dict[str, Any] | None = None,
    *,
    make_badge: bool = True,
) -> Dict[str, Optional[str]]:
    """Resolve opponent to logo fields."""
    logos_map = logos_map if logos_map is not None else load_logos_map()
    slug, display = resolve_school(name_or_slug)
    if not slug:
        return {
            "opponent": display,
            "opponent_slug": None,
            "opponent_logo": None,
            "opponent_logo_local": None,
            "logo_source": None,
        }
    display = display or name_or_slug
    info = logos_map.get(slug)
    if not info:
        # fuzzy key match
        for k, v in logos_map.items():
            if k in slug or slug in k:
                info = v
                slug = k
                break
    local = None
    url = None
    source = None
    if info:
        local = info.get("local") or info.get("path")
        url = info.get("logo_url")
        source = info.get("source")
        if local and local.startswith("logos/"):
            local = "assets/" + local
        elif local and not local.startswith("assets/"):
            local = f"assets/logos/{Path(local).name}"
        # verify file exists; if not, try basename in assets/logos
        if local:
            p = ROOT / local
            if not p.exists():
                alt = ROOT / "assets" / "logos" / Path(local).name
                local = f"assets/logos/{alt.name}" if alt.exists() else local
    if not local and make_badge:
        local = ensure_initials_badge(slug, display, ROOT / "assets" / "logos")
        source = source or ("initials-badge" if local else None)
    return {
        "opponent": display,
        "opponent_slug": slug,
        "opponent_logo": url,
        "opponent_logo_local": local,
        "logo_source": source,
    }
