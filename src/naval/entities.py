"""Extract people, ships and battles from a naval-history narration script.

Heuristic, regex based: no ML model needed for scripts of this genre, where
ships are prefixed with HMS/HMY etc. and people are introduced with a rank
or title. Entities keep the order of first appearance so slides can follow
the narration.
"""
import json
import re
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import List

SHIP_PREFIXES = r"(?:HMS|HMY|HMAS|HMCS|HMNZS|RMS|SS|USS)"
NAME = r"[A-Z][a-zA-Z'\-]+"

RANKS = (
    "Admiral of the Fleet|Vice[- ]Admiral|Rear[- ]Admiral|Admiral|Commodore|"
    "Captain|Commander|Lieutenant[- ]Commander|Lieutenant|First Sea Lord|"
    "Sir|Lord|Lady|King|Queen|Prince|Princess|General|Sergeant|Midshipman|"
    "Boatswain|Dr\\.?|Prime Minister"
)

RE_SHIP = re.compile(rf"\b({SHIP_PREFIXES})\s+({NAME}(?:\s+{NAME})?)")
RE_PERSON = re.compile(rf"\b({RANKS})\s+({NAME}(?:\s+{NAME}){{0,2}})")
RE_BATTLE = re.compile(rf"\b(Battle|Siege|Raid|Blockade)\s+of\s+({NAME}(?:\s+{NAME})?)")

# Words that regularly follow a rank but are not part of a name.
STOPWORDS = {
    "The", "This", "That", "His", "Her", "Their", "But", "And", "When", "Who",
    "However", "Royal", "British", "Navy", "Fleet", "George", # George alone is kept via titles
}


@dataclass
class Entity:
    name: str          # display name, e.g. "Admiral Horatio Nelson" or "HMS Victory"
    kind: str          # "person" | "ship" | "battle" | "asset" ...
    query: str         # search engine query
    caption: str       # caption rendered under the image
    first_pos: int     # character offset of first mention (narration order)
    mentions: int = 1
    aliases: List[str] = field(default_factory=list)
    image: str = ""    # user-provided image file: used instead of scraping
    color: bool = False  # keep original colours (e.g. maps) instead of B&W


def _clean_person(rank: str, name: str) -> str:
    parts = [p for p in name.split() if p not in STOPWORDS or p == "George"]
    return f"{rank} {' '.join(parts)}".strip() if parts else ""


def extract_entities(text: str) -> List[Entity]:
    found = {}

    def add(key, entity: Entity):
        key = key.lower()
        if key in found:
            found[key].mentions += 1
        else:
            found[key] = entity

    for m in RE_SHIP.finditer(text):
        prefix, name = m.group(1), m.group(2)
        # Trim trailing capitalised word that is actually a new sentence start
        display = f"{prefix} {name}"
        add(display, Entity(
            name=display, kind="ship",
            query=f"{display} Royal Navy ship",
            caption=display, first_pos=m.start(),
        ))

    for m in RE_PERSON.finditer(text):
        rank, name = m.group(1), m.group(2)
        display = _clean_person(rank, name)
        if not display or len(display.split()) < 2:
            continue
        add(display, Entity(
            name=display, kind="person",
            query=f"{display} Royal Navy portrait",
            caption=display, first_pos=m.start(),
        ))

    for m in RE_BATTLE.finditer(text):
        display = f"{m.group(1)} of {m.group(2)}"
        add(display, Entity(
            name=display, kind="battle",
            query=f"{display} naval painting",
            caption=display, first_pos=m.start(),
        ))

    return sorted(found.values(), key=lambda e: e.first_pos)


def save_entities(entities: List[Entity], path: Path):
    path.write_text(json.dumps([asdict(e) for e in entities], indent=2))


def load_entities(path: Path) -> List[Entity]:
    data = json.loads(path.read_text())
    return [Entity(**{k: v for k, v in d.items() if k in Entity.__dataclass_fields__})
            for d in data]
