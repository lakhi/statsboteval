"""Publish guard + the §9 blob protocol (docs/aggregates-contract.md).

guard() is blocking and runs on every publish path: model re-validation,
jsonschema against the committed artifact (drift tripwire), and a dump-walk
proving no suppressed cell carries a payload. publish() then uploads the
immutable versioned blob and overwrites v1/latest.json with identical bytes.
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
