"""The safe delete rule (PayCore D4, R10.3, C20), as one pure decision.

A full run may delete what the source no longer lists only when all of these hold:
1. the listing finished without an exception (`listing_failed` otherwise);
2. the source's own count was taken before and after the listing, both are known, equal, and
   equal to the distinct items seen (`count_mismatch` otherwise; `force` does not pass it: a
   half listing must never look like a mass deletion);
3. the share to delete, over the source's total (C20: the count after listing, not the size of
   the batch), does not exceed the ratio limit; over it is `prune_refused` unless the run was
   started with an explicit `force_prune` (then `forced`, audited by the caller).

A delta run deletes only on a driver whose listing carries tombstones (SharePoint/Graph
`@removed`, R10.3); on the others it never deletes, whatever is passed. A tombstone delta gets
the same count and ratio checks, the ratio still over the source's total.

The deletion order itself (vector store first; nothing else when that fails; database, then
files; borrowed attachment files kept) is the engine's (`engine.prune_items`).
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class PruneInput:
    mode: str  # "full" | "delta"
    tombstones: bool  # the driver's listing reports deletions
    listing_ok: bool
    count_before: int | None
    count_after: int | None
    seen: int  # distinct items listed (full) or listed in the delta
    to_delete: int  # items known here that the source no longer has (full) or tombstones
    max_ratio: float
    force: bool = False


@dataclass(frozen=True)
class PruneDecision:
    decision: str  # none | done | forced | count_mismatch | prune_refused | listing_failed
    ratio: float | None = None

    @property
    def allowed(self) -> bool:
        return self.decision in ("done", "forced")


def decide(i: PruneInput) -> PruneDecision:
    if i.mode not in ("full", "delta"):
        raise ValueError(f"unknown sync mode {i.mode!r}")
    if i.mode == "delta" and not i.tombstones:
        # R10.3: no tombstones, no deletion in a delta run; a caller passing a count here is a
        # programming error, not a decision.
        if i.to_delete:
            raise ValueError("a delta run of a driver without tombstones has nothing to delete")
        return PruneDecision("none")
    if not i.listing_ok:
        return PruneDecision("listing_failed")
    if i.to_delete == 0:
        return PruneDecision("none")
    counts_known = i.count_before is not None and i.count_after is not None
    if not counts_known or i.count_before != i.count_after:
        return PruneDecision("count_mismatch")
    if i.mode == "full" and i.count_after != i.seen:
        return PruneDecision("count_mismatch")
    total = i.count_after
    ratio = float("inf") if total == 0 else i.to_delete / total
    if ratio > i.max_ratio:
        return PruneDecision("forced" if i.force else "prune_refused", ratio)
    return PruneDecision("done", ratio)
