# Upstream PR P5 (held, not opened)

Target `aisepucrio/annotaise:main`.

## Title

fix(permissions): hide other annotators' answers and vote counts from annotators

## Body

### Summary

Any logged-in user could read, through the API, every answer of a labeling
(including `answered_by_email`), the per-item vote counts (`decision_payload`),
and the agreement summary, because these views only required a login (or, for
the item list, a labeling membership). Annotators therefore saw other
annotators' answers and e-mail addresses.

`GET labelings/<id>/answers/`, `GET labelings/<id>/items/` and
`GET labelings/<id>/agreement-summary/` now require an admin account or a
labeling `owner`/`admin` membership (`IsAdminAccount | CanEditLabelingPermission`,
the helpers already used elsewhere). Annotators and non-members get `403`
(`404` on agreement-summary for non-members, as before, because the queryset is
membership-scoped).

The frontend calls these three only from the labeling management pages
(`labelings_manage/...`), never from the annotator screens, so no UI change is
needed. Item serving (`items/<id>/`), `POST /answers/` and the structure `GET`
are untouched. The old `401` for non-members of the item list is now `403`.

### Tests

New tests for each endpoint: annotator and non-member get 403 (and no
e-mail/vote data in the body), owner and admin account still get 200, and an
annotator can still be served an item and submit an answer.
