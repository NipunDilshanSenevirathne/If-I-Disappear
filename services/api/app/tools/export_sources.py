"""Print a fixture household's sources (including evidence sources) as JSON.

Used by apps/web/scripts/render-samples.mjs to draw the SAMPLE documents from
exactly the text the claims quote, so images and transcripts never drift apart.

    python -m app.tools.export_sources perera > /tmp/sources.json
"""

from __future__ import annotations

import json
import sys

from ..domain.household import load_household, load_stage


def main(household_id: str = "perera") -> None:
    h = load_household(household_id)
    sources = list(h.sources)
    stage = load_stage(household_id)
    if stage:
        sources += stage.sources
    out = [s.model_dump(mode="json") for s in sources if s.file]
    json.dump({"household": household_id, "sources": out}, sys.stdout, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main(*sys.argv[1:])
