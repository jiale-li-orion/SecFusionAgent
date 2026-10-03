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
artifact refs. It then writes both JSON and Markdown. The reviewed run set currently composes M1,
structured M3, Red Hat CSAF/VEX, controlled fault recovery, Product QA and session QA under one
DeploymentRevision. Evaluation areas not selected into this report remain explicit
`not_evaluated` states even when separate controlled/diagnostic suites exist for them; preflight
fixtures, synthetic smoke runs and unrelated historical runs are never inserted merely to fill
report cells.
