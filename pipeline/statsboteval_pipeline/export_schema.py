"""Export the contract JSON Schema artifact.

Run from pipeline/: python -m statsboteval_pipeline.export_schema
Writes schema/aggregates.schema.json at the repo root (contract §1).
"""

import json
from pathlib import Path
from typing import Any

from statsboteval_pipeline.contract import Aggregates

REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = REPO_ROOT / "schema" / "aggregates.schema.json"


def generate_schema() -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://raw.githubusercontent.com/lakhi/statsboteval/main/schema/aggregates.schema.json",
        **Aggregates.model_json_schema(),
    }


def main() -> None:
    SCHEMA_PATH.parent.mkdir(parents=True, exist_ok=True)
    SCHEMA_PATH.write_text(json.dumps(generate_schema(), indent=2, sort_keys=True) + "\n")
    print(f"wrote {SCHEMA_PATH}")


if __name__ == "__main__":
    main()
