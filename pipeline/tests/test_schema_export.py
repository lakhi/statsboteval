import json

import jsonschema
import pytest

from statsboteval_pipeline.contract import SCHEMA_VERSION, Aggregates, dump_doc
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


def test_design_fixture_is_a_valid_document() -> None:
    """The dashboard's design fixture must obey the same contract as a real publish.

    Nothing validated it before, and it drifted: `generate.mjs` published a semester's
    *covered* weeks as its `weeks` while indexing a slice's `semester_weeks` against full
    membership, so the two were one week apart — precisely the D-54 confusion
    `_check_windows` exists to catch. A fixture that cannot occur is worse than no fixture,
    because the page gets designed against shapes the pipeline will never send.

    Cross-package on purpose: the fixture is dashboard-side, but the law it must obey lives
    here, and a JS generator cannot check itself against pydantic models.
    """
    fixture = SCHEMA_PATH.parent.parent / "dashboard" / "dev-fixtures" / "aggregates.fixture.json"
    if not fixture.is_file():
        pytest.skip("dashboard checkout not present")
    doc = json.loads(fixture.read_text())
    Aggregates.model_validate(doc)
    jsonschema.validate(doc, json.loads(SCHEMA_PATH.read_text()))
    assert doc["schema_version"] == SCHEMA_VERSION, "the fixture must declare the version it emits"
