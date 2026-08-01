"""Publish guard + the §9 blob protocol (docs/aggregates-contract.md).

guard() is blocking and runs on every publish path: model re-validation,
jsonschema against the committed artifact (drift tripwire), and two dump-walks —
one proving no suppressed cell carries a payload, one proving no published
`n_students` sits below the floor. publish() then uploads the immutable versioned
blob and overwrites v1/latest.json with identical bytes.
"""

from __future__ import annotations

import json
from typing import Any

import jsonschema
from azure.core.exceptions import ResourceExistsError
from azure.storage.blob import BlobServiceClient
from pydantic import ValidationError

from .contract import Aggregates, dump_doc
from .export_schema import SCHEMA_PATH

LATEST_BLOB = "v1/latest.json"


class PublishGuardError(Exception):
    pass


def _assert_suppressed_bare(node: Any) -> None:
    if isinstance(node, dict):
        if node.get("status") == "suppressed" and set(node) != {"status"}:
            raise PublishGuardError(
                f"suppressed cell carries extra fields: {sorted(set(node) - {'status'})}"
            )
        for value in node.values():
            _assert_suppressed_bare(value)
    elif isinstance(node, list):
        for item in node:
            _assert_suppressed_bare(item)


def _assert_floor_respected(node: Any, floor_n: int, path: str = "$") -> None:
    """No `n_students` anywhere in the outgoing bytes may sit below the floor.

    Deliberately generic rather than trends-specific. Every model that publishes an
    `n_students` does so only after a floor test — OkSummaryStats through `_summary()`,
    MeasureValue and TrajectoryPoint through the trends gate — so the universal statement
    is the true one, and it keeps holding when a later section adds a fourth such model.
    Suppressed cells carry no `n_students` at all, and a measured zero publishes as a bare
    ok(0) with no student count, so there is nothing legitimate for this to catch.

    Redundant with the Aggregates validators by design: those check the object graph, this
    checks the bytes that actually leave the machine (constraint 2).
    """
    if isinstance(node, dict):
        n_students = node.get("n_students")
        if isinstance(n_students, int) and n_students < floor_n:
            raise PublishGuardError(
                f"{path} publishes n_students={n_students}, below the floor of {floor_n}"
            )
        for key, value in node.items():
            _assert_floor_respected(value, floor_n, f"{path}.{key}")
    elif isinstance(node, list):
        for index, item in enumerate(node):
            _assert_floor_respected(item, floor_n, f"{path}[{index}]")


# Measures where every unit belongs to exactly ONE program level, so the levels partition
# the window total. `active_students`, `new_users` and `returning_users` are absent on
# purpose: a bachelor→master transitioner is counted under both levels (`status_multi`),
# so those sums can exceed the total and a remainder is not a value.
_PARTITIONING_MEASURES = ("messages", "sessions", "new_registrations", "new_registrations_active")


def _assert_no_recoverable_partition(dumped: dict[str, Any]) -> None:
    """A lone withheld level cell is not withheld — it is `total − the others` (D-59).

    The floor protects what a reader can *learn*, so a cell can pass `floored_count` and
    still be published in effect. That happens when a measure partitions the window
    exactly and exactly one level is suppressed: subtract the published levels from the
    published total and the withheld number falls out, exact. Two or more suppressed and
    the remainder is a sum of unknowns, which is safe.

    Blocking, in the guard rather than in a test, because this is a property of the bytes
    leaving the machine and it depends on the data: a document that is clean this week can
    trip next week on the same code. `aggregate._joint_partition_floor` keeps every partitioning measure
    clear of it by construction, so this should never fire on a document this pipeline
    built; it fires on a hand-edited or replayed one, and on the day a new partitioning
    measure is added and forgotten.
    """
    for window_id, window in (dumped.get("sections", {}).get("usage_context", {}).get("per_window", {})).items():
        by_status = window.get("by_status") or {}
        if not by_status:
            continue
        for measure in _PARTITIONING_MEASURES:
            total = window.get("totals", {}).get(measure)
            if not isinstance(total, dict) or total.get("status") != "ok":
                continue  # a withheld total leaves nothing to subtract from
            cells = [level.get(measure) for level in by_status.values()]
            present = [c for c in cells if isinstance(c, dict)]
            withheld = [c for c in present if c.get("status") == "suppressed"]
            if len(withheld) != 1:
                continue
            published = sum(c["value"] for c in present if c.get("status") == "ok")
            raise PublishGuardError(
                f"$.sections.usage_context.per_window.{window_id}: one level's `{measure}` is "
                f"suppressed while the others and the window total are published, so it is "
                f"recoverable as {total['value']} - {published} = {total['value'] - published}. "
                "Levels partition this measure exactly — withhold it on every level "
                "(see aggregate._joint_partition_floor) or do not publish the total."
            )


def guard(doc: Aggregates) -> dict[str, Any]:
    dumped = dump_doc(doc)
    try:
        Aggregates.model_validate(dumped)
    except ValidationError as exc:
        raise PublishGuardError(f"model re-validation failed: {exc}") from exc
    try:
        jsonschema.validate(dumped, json.loads(SCHEMA_PATH.read_text()))
    except jsonschema.ValidationError as exc:
        raise PublishGuardError(f"committed-schema validation failed: {exc.message}") from exc
    _assert_suppressed_bare(dumped)
    _assert_floor_respected(dumped, doc.privacy_floor_n)
    _assert_no_recoverable_partition(dumped)
    return dumped


def render(doc: Aggregates) -> bytes:
    """Guarded, byte-stable rendering — the same bytes go to both blobs and --out."""
    return (json.dumps(guard(doc), indent=2, sort_keys=True) + "\n").encode()


def publish(doc: Aggregates, *, connection_string: str, container: str = "aggregates") -> tuple[str, str]:
    payload = render(doc)
    immutable = f"v1/aggregates_{doc.data_through_week}_{doc.generated_at:%Y%m%dT%H%M%SZ}.json"
    client = BlobServiceClient.from_connection_string(connection_string).get_container_client(container)
    try:
        client.create_container()  # Azurite/dev convenience; harmless when it exists
    except ResourceExistsError:
        pass
    client.upload_blob(immutable, payload)  # no overwrite: versioned blobs are immutable (§9)
    client.upload_blob(LATEST_BLOB, payload, overwrite=True)  # atomic PUT: readers see old-or-new
    return immutable, LATEST_BLOB
