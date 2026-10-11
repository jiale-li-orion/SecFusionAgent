# Canonical knowledge reads

`read.py` retains the existing object and outgoing-relation read contracts. `network.py`
adds the bounded product graph projection; it performs no enrichment, inference, or writes.

## Network API

`GET /api/v1/intelligence/objects/{object_id}/network`

Parameters:

- `limit`: 2–80, default 40. This bounds newly returned neighbors plus the center/focus
  anchors. The initial request therefore returns at most 40 nodes by default.
- `focus_id`: expand this object's incoming and outgoing neighbors while preserving the
  original `object_id` as `center_id`.
- `existing_ids`: comma-separated already displayed object IDs, at most 200. Existing
  nodes are additional to the page budget and enable induced cross edges with new nodes.
- `revision`: pin the upper creation revision; omitted means latest knowledge revision.
- `cursor`: opaque keyset continuation, scoped to center/focus and pinned revision.
  Pass the returned cursor and accumulated existing IDs to load the next page. A cursor
  with a different explicit revision or focus is rejected with 422.

`NetworkView` returns `center_id`, `nodes`, `edges`, `snapshot_revision`, `next_cursor`,
`remaining_count`, and `history_scope`. Nodes expose identity, type, display label,
canonical key, creation revision and its commit timestamp. Edges expose both endpoint
IDs, relation type, origin, qualifiers, creation/supersession revisions and commit
timestamps, and the existing `EvidenceRef` payload. Pagination ranks distinct neighbors
by total linked evidence count, newest accepted relation revision, then object ID.
Remaining count describes unseen eligible neighbors after the current cursor/page.
Evidence metadata is not revisioned, so evidence additions can change ranking during
concurrent pagination; the cursor pins creation eligibility, not an immutable ranking.

All accepted relations between returned nodes are included, including superseded rows.
Consumers replay a revision `r` with `created_revision <= r` and
`superseded_revision is null or superseded_revision > r`. Node creation is also capped
by the requested snapshot. Timestamps represent knowledge revision commits rather than
source publication dates. History covers stored relation lifetimes in this loaded
subgraph: labels, evidence, and overwritten/reactivated relation lifetimes cannot be
fully reconstructed from the current schema. `history_scope` discloses this limit.
This projection must not be used as an exact historical reasoning snapshot.

The read performs indexed adjacency lookups on the focus, grouped neighbor ranking,
bounded object fetches, and induced edge/evidence reads restricted to returned IDs.
It never materializes the complete graph. Edge count follows the actual induced
subgraph; parallel relations are preserved. Missing center/focus at the snapshot is 404.
Existing `/graph`, object and search contracts are unchanged.

Verification:

```sh
.venv/bin/pytest -q packages/intelligence/knowledge/tests/test_network.py
.venv/bin/ruff check packages/intelligence/knowledge/network.py packages/intelligence/knowledge/tests/test_network.py apps/api/routes/knowledge.py
```

## Incident association network

`GET /api/v1/incidents/{incident_id}/network` uses the same page/expansion parameters
and `NetworkView`, with `revision_domain="incident"` (canonical networks use `knowledge`).
Node optional fields `evidence_ref`, `canonical_object_id`, and `event_time` support
source inspection, actual claim-subject navigation, and original event dates.

Incident networks contain `Incident`, `IncidentEvent`, `Evidence`, and `Claim` nodes.
The edges project actual incident source-link records and timeline observation/claim
references: `has_event`, `has_source_evidence`, `references_evidence`, and
`references_claim`. Their origin is `incident_record`; qualifiers identify
`projection="incident_association"`. They are never persisted as canonical relations.
Unresolved observation/claim references produce no invented nodes or edges.

All creation and supersession coordinates in this response are **incident revisions**.
An Evidence/Claim node's creation revision is its earliest association in the bounded
projection, not its knowledge creation revision. Event correction links supersede
previous event associations at the correcting incident revision. Association timestamps
come from incident revision commits; `event_time` remains distinct. Referenced claim
bodies and source metadata are current stored values, explicitly disclosed as such.

Reads inspect at most the newest 200 timeline records and 200 source-link records at
the incident snapshot, 200 referenced claims and 400 referenced observations. The
response discloses whether this bounded scope was truncated. Paging and remaining
counts operate within this scope. Expand a timeline event to load its referenced claims;
source evidence and event links form real crosslinks within the loaded union.
Distinct-focus expansion requires `limit >= 3` to include both anchors and a neighbor.

Both network endpoints enforce a hard 200-node response cap, including center/focus and
valid existing IDs. Expansion consumes only the remaining capacity. At capacity,
`remaining_count` still reports omitted eligible neighbors but `next_cursor` is null;
clients must remove displayed nodes before another expansion. Requests whose valid
existing nodes plus anchors already exceed 200 are rejected with 422.
