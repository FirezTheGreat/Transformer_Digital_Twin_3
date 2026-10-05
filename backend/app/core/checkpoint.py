"""Deterministic TwinState Checkpointing and Serialization Store.

Provides checkpoint saving, verification, and restoration backed by DuckDB storage.
Computes deterministic SHA-256 state hashes to ensure state immutability and integrity.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from app.core.storage import StorageEngine
from app.models.twin_state import TwinState


def compute_twin_state_hash(state_dict: dict[str, Any]) -> str:
    """Compute deterministic SHA-256 hash of a TwinState dictionary.

    Excludes the 'state_hash' field itself to produce a pure content digest.
    """
    hashable = {k: v for k, v in state_dict.items() if k != "state_hash"}
    serialized = json.dumps(hashable, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(serialized).hexdigest()


class CheckpointStore:
    """Manages persistent deterministic TwinState checkpoints in DuckDB storage."""

    def __init__(self, storage: StorageEngine) -> None:
        """Initialize CheckpointStore with a StorageEngine."""
        self.storage = storage

    def save_checkpoint(
        self,
        state: TwinState,
        checkpoint_id: str | None = None,
    ) -> str:
        """Serialize and persist a TwinState checkpoint.

        Returns:
            str: Deterministic checkpoint ID.
        """
        raw_dict = state.model_dump(mode="json")
        computed_hash = compute_twin_state_hash(raw_dict)

        # Update state with computed hash if not already set or matching
        if state.state_hash != computed_hash:
            state = state.model_copy(update={"state_hash": computed_hash})
            raw_dict["state_hash"] = computed_hash

        state_json = state.model_dump_json()

        ts_epoch = int(state.state_time_utc.timestamp())
        cid = checkpoint_id or f"chk_{state.asset_id}_{state.state_sequence:08d}_{ts_epoch}"

        self.storage.insert_checkpoint(
            checkpoint_id=cid,
            asset_id=state.asset_id,
            state_time_utc=state.state_time_utc,
            last_processed_event_id=state.last_processed_event_id,
            state_sequence=state.state_sequence,
            state_json=state_json,
            state_hash=computed_hash,
            created_at_utc=datetime.now(timezone.utc),
        )
        return cid

    def load_latest_checkpoint(self, asset_id: str) -> TwinState | None:
        """Retrieve and validate the most recent checkpoint for an asset."""
        row = self.storage.get_latest_checkpoint(asset_id)
        if not row:
            return None
        return self._validate_and_reconstruct(row)

    def load_checkpoint_by_id(self, checkpoint_id: str) -> TwinState | None:
        """Retrieve and validate a specific checkpoint by ID."""
        row = self.storage.get_checkpoint_by_id(checkpoint_id)
        if not row:
            return None
        return self._validate_and_reconstruct(row)

    def get_checkpoint_count(self, asset_id: str | None = None) -> int:
        """Get total number of checkpoints stored."""
        return self.storage.get_checkpoint_count(asset_id)

    def _validate_and_reconstruct(self, row: dict[str, Any]) -> TwinState:
        """Validate state hash integrity and reconstruct typed TwinState model."""
        state_json = row["state_json"]
        recorded_hash = row["state_hash"]

        parsed_dict = json.loads(state_json)
        computed_hash = compute_twin_state_hash(parsed_dict)

        if computed_hash != recorded_hash:
            raise ValueError(
                f"Checkpoint integrity verification failed for asset '{row['asset_id']}': "
                f"recorded hash '{recorded_hash}' != computed hash '{computed_hash}'"
            )

        return TwinState.model_validate_json(state_json)
