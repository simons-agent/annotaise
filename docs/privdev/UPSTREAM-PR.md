# Upstream PR (held, not opened)

Branch: `feat/export-created-at-responded-as` on the fork `simons-agent/annotaise`,
target `aisepucrio/annotaise:main`.

## Title

feat(export): add created_at and responded_as columns to the answer CSV export

## Body

### Summary

`Answer` stores `created_at` and `responded_as` (the user group whose quota slot
the answer filled), but the answer CSV export (`ExportAnswersView`) omitted both.
This adds two columns:

- `created_at`: `answer.created_at.isoformat()` (timezone-aware, UTC offset included).
- `responded_as`: the group name, or empty when `responded_as` is null (the residual "any" slot, LLM tiebreak answers).

`responded_as` is added to `select_related`, so no extra queries per row.

### Tests

New `ExportAnswersColumnsTest.test_export_has_created_at_and_responded_as`: two
users in two groups answer one item of a labeling with group quotas; the export
header contains both columns, rows carry the right group names, and every
`created_at` parses with `datetime.fromisoformat` and is timezone-aware.

Full backend suite: `docker compose run --rm api uv run manage.py test` passes.
