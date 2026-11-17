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
stay open to annotators (their response bodies change, see below). The old `401`
for non-members of the item list is now `403`.

The served item (`items/<id>/` and the anonymous variant) also embedded the full
`ItemSerializer`, so in decision mode an annotator received earlier annotators'
vote tallies (`decision_payload`) and the decision outcome
(`llm_tiebreak_result`, `final_decision_source`, `final_decision_value`,
`llm_tiebreak_attempted`) for the item about to be answered. `NextItemResponseSerializer`
now nests an `AnnotatorItemSerializer` with only `id`, `labeling`, `payload`,
`row_index`, `status`. The frontend reads those fields only on the management
pages (via the answers list), not on the served item.

`POST /answers/` returned the new answer with the same full `ItemSerializer` as
`item_detail`, so right after submitting, an annotator received the item's tally
including earlier annotators' votes. The create response now uses
`AnnotatorAnswerSerializer`, whose `item_detail` is the `AnnotatorItemSerializer`
field set. The annotator answer page reads only `decision_warning` from that
response; the management pages read `item_detail` from the answers list, which
keeps the full serializer.

### Tests

New tests for each endpoint: annotator and non-member get 403 (and no
e-mail/vote data in the body), owner and admin account still get 200, and an
annotator can still be served an item and submit an answer.

New `ServedItemHidesVoteTalliesTest`: in a decision labeling where one annotator
already answered, the item served to a second annotator has none of the tally
or decision fields and no vote key in the body.
The same test class checks that the `POST /answers/` response to the second
annotator carries none of those fields in `item_detail` (and no vote key),
while the stored tally does count both votes.
