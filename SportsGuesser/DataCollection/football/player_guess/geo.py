"""
Map nationality strings (as in superlig_data) to a coarse continent code for hint logic.
Codes: EU, AS, AF, NA, SA, OC (Oceania). Türkiye / Turkey → EU (UEFA context).
"""

from __future__ import annotations

import re
import unicodedata
from typing import Optional

# Lowercased keys after normalize
_NATIONALITY_CONTINENT: dict[str, str] = {}

def _add(names: list[str], code: str) -> None:
    for n in names:
        k = _norm_key(n)
        if k:
            _NATIONALITY_CONTINENT[k] = code


def _norm_key(s: str) -> str:
    if not s or not str(s).strip():
        return ""
    t = unicodedata.normalize("NFKD", str(s).strip().lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = re.sub(r"\s+", " ", t)
    return t


def continent_for_nationality(nationality: Optional[str]) -> Optional[str]:
    """Return continent code or None if unknown."""
    if not nationality or not str(nationality).strip():
        return None
    k = _norm_key(nationality)
    if not k:
        return None
    return _NATIONALITY_CONTINENT.get(k)


# —— Seed maps (extend as needed) ——
_add(["türkiye", "turkey", "turkiye"], "EU")

# Europe (UEFA + common)
for n in [
    "albania", "andorra", "armenia", "austria", "azerbaijan", "belarus", "belgium",
    "bosnia and herzegovina", "bosnia-herzegovina", "bulgaria", "croatia", "cyprus",
    "czech republic", "czechia", "denmark", "england", "estonia", "faroe islands",
    "finland", "france", "georgia", "germany", "gibraltar", "greece", "hungary",
    "iceland", "ireland", "israel", "italy", "kazakhstan", "kosovo", "latvia",
    "liechtenstein", "lithuania", "luxembourg", "malta", "moldova", "montenegro",
    "netherlands", "north macedonia", "macedonia", "northern ireland", "norway",
    "poland", "portugal", "romania", "russia", "san marino", "scotland", "serbia",
    "slovakia", "slovenia", "spain", "sweden", "switzerland", "ukraine", "wales",
    "united kingdom", "uk",
]:
    _add([n], "EU")

_add(["russian federation"], "EU")

# Americas
for n in ["united states", "usa", "canada", "mexico", "costa rica", "honduras",
        "guatemala", "panama", "jamaica", "trinidad and tobago", "el salvador"]:
    _add([n], "NA")

for n in ["brazil", "argentina", "uruguay", "colombia", "chile", "peru", "ecuador",
        "paraguay", "bolivia", "venezuela"]:
    _add([n], "SA")

# Africa
for n in ["algeria", "angola", "benin", "botswana", "burkina faso", "burundi",
        "cameroon", "cape verde", "central african republic", "chad", "comoros",
        "congo", "dr congo", "democratic republic of congo", "côte d'ivoire",
        "ivory coast", "cote d'ivoire", "djibouti", "egypt", "equatorial guinea",
        "eritrea", "eswatini", "swaziland", "ethiopia", "gabon", "gambia", "ghana",
        "guinea", "guinea-bissau", "kenya", "lesotho", "liberia", "libya",
        "madagascar", "malawi", "mali", "mauritania", "mauritius", "morocco",
        "mozambique", "namibia", "niger", "nigeria", "rwanda", "sao tome and principe",
        "senegal", "seychelles", "sierra leone", "somalia", "south africa", "south sudan",
        "sudan", "tanzania", "togo", "tunisia", "uganda", "zambia", "zimbabwe",
        "cape verde islands"]:
    _add([n], "AF")

# Asia (incl. Middle East for dataset)
for n in ["afghanistan", "bahrain", "bangladesh", "bhutan", "brunei", "cambodia",
        "china", "east timor", "timor-leste", "hong kong", "india", "indonesia",
        "iran", "iraq", "japan", "jordan", "kuwait", "kyrgyzstan", "laos", "lebanon",
        "macau", "malaysia", "maldives", "mongolia", "myanmar", "burma", "nepal",
        "north korea", "south korea", "korea republic", "oman", "pakistan",
        "palestine", "philippines", "qatar", "saudi arabia", "singapore", "sri lanka",
        "syria", "taiwan", "tajikistan", "thailand", "turkmenistan", "uae",
        "united arab emirates", "uzbekistan", "vietnam", "yemen", "korea dpr"]:
    _add([n], "AS")

# Oceania
for n in ["australia", "new zealand", "fiji", "papua new guinea", "samoa", "tonga"]:
    _add([n], "OC")
