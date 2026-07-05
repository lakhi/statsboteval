from statsboteval_pipeline.contract import Aggregates, dump_doc

from .factories import make_synthetic_aggregates


def test_factory_produces_valid_document() -> None:
    assert make_synthetic_aggregates().data_provenance == "synthetic"


def test_round_trip_equality() -> None:
    doc = dump_doc(make_synthetic_aggregates())
    assert dump_doc(Aggregates.model_validate(doc)) == doc


def test_round_trip_strips_unknown_fields() -> None:
    # Readers ignore unknown fields (invariant 5); the writer-side extras guard is
    # exactly this asymmetry: extras never survive validate->dump.
    doc = dump_doc(make_synthetic_aggregates())
    doc["sections"]["temporal_usage"]["weekly"]["messages"]["stray_field"] = "should not survive"
    assert dump_doc(Aggregates.model_validate(doc)) != doc


def test_generated_at_serializes_utc_z() -> None:
    doc = dump_doc(make_synthetic_aggregates())
    assert doc["generated_at"].endswith("Z")
