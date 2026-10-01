# Competition report evidence

`current-run-set.json` is the explicit composition policy for the reviewed competition report. It
pins one DeploymentRevision, an ordered list of completed BenchmarkRun IDs, and the frozen artifact
coordinates needed to audit their provider worlds. Report generation never searches for a latest run.

`current.json` is the durable CompetitionReport projection for that run set. `current.md` is generated
from the JSON by `scripts/render_competition_status.py`; it contains no independently maintained
metric values. Use `make competition-doc-check` in CI or review to detect a stale Markdown projection
without contacting providers or querying benchmark state.

To regenerate the report from durable PostgreSQL benchmark rows, use `make competition-report`. This
reads `current-run-set.json`, verifies that all selected runs belong to the pinned deployment, and
fails closed if a provider snapshot bound by a selected run or case is absent from the run-set
artifact refs. It then writes both JSON and Markdown. Missing QA/Agent/fault-recovery measurements remain explicit
`not_evaluated` states; preflight fixtures and synthetic harness runs are not inserted to fill those
cells.
