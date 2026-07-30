"""Phase B Task 13: topics section (schema 1.1.0, additive; by_status per D-39).

1.2.0 addition: optional TopicItem.description (emergent themes' reviewed
one-line definitions; absent everywhere else)."""

import json

import jsonschema
import pytest
from pydantic import ValidationError

from statsboteval_pipeline.contract import (
    SCHEMA_VERSION,
    Aggregates,
    TopicDistribution,
    TopicGroup,
    TopicItem,
    TopicsSection,
    TopicsWindowEntry,
    dump_doc,
    ok,
    suppressed,
)
from statsboteval_pipeline.export_schema import generate_schema
from tests.factories import make_synthetic_aggregates


def distribution(footnotes: list[str] | None = None) -> TopicDistribution:
    return TopicDistribution(
        items=[
            TopicItem(label="Synthetic Alpha", cell=ok(12), description="Synthetic one-line description."),
            TopicItem(label="Synthetic Beta", cell=suppressed()),
        ],
        n_total=ok(40),
        footnote_ids=footnotes,
    )


def group() -> TopicGroup:
    return TopicGroup(deductive=distribution(), method_themes=distribution(), software_themes=distribution())


def with_topics(doc: Aggregates, topics: TopicsSection) -> Aggregates:
    # Rebuild via model_validate so the cross-document validator runs (model_copy skips it).
    dumped = dump_doc(doc)
    dumped["sections"]["topics"] = dump_doc(topics)
    return Aggregates.model_validate(dumped)


def topics_for(doc: Aggregates, *, by_status: dict[str, TopicGroup] | None = None) -> TopicsSection:
    entry = TopicsWindowEntry(**group().model_dump(), by_status=by_status)
    return TopicsSection(per_window={w.id: entry for w in doc.windows})


def test_schema_version_bumped_minor() -> None:
    # Deliberate tripwire: every additive section bump edits this line, which forces the
    # bump to be a decision rather than a side effect. 1.3.0 adds trends (D-49); 1.4.0 adds
    # the Adoption additions — retention, signup activation, frequent, by_status (D-50);
    # 1.5.0 adds per_student and withdraws tokens (D-53); 1.6.0 adds the dayparts registry,
    # the coarse daypart heatmap/totals and semester profiles (D-54).
    assert SCHEMA_VERSION == "1.6.0"


def test_description_optional_and_absent_not_null() -> None:
    # Additive proof for 1.2.0: items without a description dump without the key
    # (a 1.1.0-shaped document stays valid), and a set description round-trips.
    dumped = dump_doc(distribution())
    assert dumped["items"][0]["description"] == "Synthetic one-line description."
    assert "description" not in dumped["items"][1]
    assert TopicDistribution.model_validate(dumped) == distribution()


def test_topics_document_round_trips_and_validates() -> None:
    doc = with_topics(make_synthetic_aggregates(), topics_for(make_synthetic_aggregates()))
    dumped = dump_doc(doc)
    assert Aggregates.model_validate(dumped) == doc
    jsonschema.validate(dumped, generate_schema())
    assert "emergent_themes" not in json.dumps(dumped)  # omitted, not null (designed state)


def test_by_status_round_trips_with_known_keys() -> None:
    base = make_synthetic_aggregates()
    doc = with_topics(base, topics_for(base, by_status={"bachelor": group(), "master": group(), "unknown": group()}))
    dumped = dump_doc(doc)
    assert Aggregates.model_validate(dumped) == doc
    jsonschema.validate(dumped, generate_schema())


def test_by_status_unknown_key_rejected() -> None:
    with pytest.raises(ValidationError, match="by_status"):
        TopicsWindowEntry(**group().model_dump(), by_status={"phd": group()})


def test_1_0_0_document_still_validates_against_1_1_0_schema() -> None:
    # Additive proof: a document without topics (the committed 1.0.0 shape) stays valid.
    dumped = dump_doc(make_synthetic_aggregates())
    dumped["schema_version"] = "1.0.0"
    assert "topics" not in dumped["sections"]
    jsonschema.validate(dumped, generate_schema())
    Aggregates.model_validate(dumped)


def test_topics_window_keys_validated_against_registry() -> None:
    base = make_synthetic_aggregates()
    bad = TopicsSection(per_window={"2099W": TopicsWindowEntry(**group().model_dump())})
    with pytest.raises(ValidationError, match="topics"):
        with_topics(base, bad)


def test_theme_set_version_optional_and_preserved() -> None:
    base = make_synthetic_aggregates()
    topics = topics_for(base)
    assert topics.theme_set_version is None
    versioned = topics.model_copy(update={"theme_set_version": "statsboteval-themes-v1"})
    doc = with_topics(base, versioned)
    assert dump_doc(doc)["sections"]["topics"]["theme_set_version"] == "statsboteval-themes-v1"


def test_classification_label_version_key_allowed() -> None:
    base = make_synthetic_aggregates()
    doc = base.model_copy(
        update={"label_versions": {**base.label_versions, "classification": "statsboteval-v1"}}
    )
    assert Aggregates.model_validate(dump_doc(doc)).label_versions["classification"] == "statsboteval-v1"
