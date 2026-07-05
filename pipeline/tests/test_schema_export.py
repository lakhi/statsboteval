import json

import jsonschema

from statsboteval_pipeline.contract import dump_doc
from statsboteval_pipeline.export_schema import SCHEMA_PATH, generate_schema

from .factories import make_synthetic_aggregates


def test_committed_schema_matches_models() -> None:
    # THE drift guard: regenerating must produce exactly the committed artifact.
    # If this fails: run `python -m statsboteval_pipeline.export_schema` and commit the diff
    # (after confirming the model change was additive — contract §10).
    assert json.loads(SCHEMA_PATH.read_text()) == generate_schema()


def test_synthetic_example_validates_against_committed_schema() -> None:
    schema = json.loads(SCHEMA_PATH.read_text())
    jsonschema.validate(dump_doc(make_synthetic_aggregates()), schema)


def test_schema_declares_dialect_and_id() -> None:
    schema = generate_schema()
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert schema["$id"].endswith("schema/aggregates.schema.json")


def test_schema_is_permissive_to_unknown_fields() -> None:
    # Invariant 5: readers ignore unknown fields — the exported schema must not
    # forbid additional properties anywhere.
    def walk(node):
        if isinstance(node, dict):
            assert node.get("additionalProperties") is not False
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(generate_schema())
