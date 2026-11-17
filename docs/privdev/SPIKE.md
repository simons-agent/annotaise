# P4 behaviour spike: AnnotAISE contract gate (Study 1)

Run on 2026-11-17 against `annotaise-test` (Tailnet-only,
https://agentbox.tail289ef2.ts.net:9446/annotaise-test/), fork branch
`privdev/study1` at d08480c. All data are synthetic; all accounts use
`@example.invalid`. Every result below was **observed** through the HTTP API
or the browser UI (headless Chromium via Playwright). Source citations
(`file:line` at d08480c, paths relative to the repo root) only explain what was
observed. Tokens and passwords are shown as `<redacted>`.

## Facts for PrivDev tools

| Topic | Fact (observed) |
|---|---|
| Base URL | `<instance URL>/backend` — test: `https://agentbox.tail289ef2.ts.net:9446/annotaise-test/backend`; on the host also `http://127.0.0.1:8471/backend`. All paths below are relative to it. Most API paths end in `/`; the structure path does **not** (`labelings/<id>/structure`). |
| Login | `POST /api/auth/token/` with JSON `{"email": "...", "password": "..."}` → `200 {"refresh": "<redacted>", "access": "<redacted>"}`. Token field: **`access`** (lifetime 500 min, refresh 10 days; `backend/annotaise/settings.py:206-209`). Refresh: `POST /api/auth/token/refresh/ {"refresh": ...}` → `200 {"access": "<redacted>"}`. Wrong password → `401 {"detail": "No active account found with the given credentials"}`; invalid/expired token → `401 {"code": "token_not_valid", ...}` (G2's re-login-on-401 applies). |
| Auth header | `Authorization: Bearer <access>` (simplejwt, `backend/annotaise/settings.py:170-172`). |
| Structure PUT | `PUT /labelings/<id>/structure` (main) or `PUT /labelings/<id>/structure?form_type=background`, body `{"sections": [ {title, order, elements: [ {order, text, required, question_type, context_type?, column_name?, allow_multiple?, multiple_choice_items?: [ {text, value, order, follow_up_question?: {text, required, question_type, multiple_choice_items?...}} ]} ]} ]}`. `200` returns the same list the GET returns. Any invalid body → `400 {"detail": "estrutura do form inválida. cheque possiveis erros ou campos vazios", "code": "INVALID_FORM_STRUCTURE"}` with **no field detail**. **Matching rule:** sections are matched by `id` among the labeling's existing sections of that `form_type`, and elements by `id` among the existing elements **of the same section** (`backend/labeling/views.py:537`, `553`, `564`) — never by question text. An element without an `id`, or with an `id` not in that section, is created new, and every existing element of the section not matched is deleted (`backend/labeling/views.py:633-636`; sections likewise at 638-641). Options are always deleted and recreated, keeping a supplied option `id`; follow-up elements are always recreated with new IDs (589-631). So a mismatched `id` silently replaces the element. Example: [`probe-structure.json`](probe-structure.json). |
| Structure GET | `GET /labelings/<id>/structure[?form_type=background]` → a **list** of sections `{id, title, order, elements: [...]}`; element `{id, order, text, required, question_type, column_name, allow_multiple, multiple_choice_items: [{id, text, value, order, follow_up_question: <element or null>}], question_range, context_type}`. Follow-up elements appear **only** nested under their option (not in `elements`); they get `order` 10001, 10002, … |
| Answer payload | `POST /answers/ {"labeling": L, "item": I, "answer_payload": {...}}`. Keys: `"<element id>"` → value; multiple-choice value is the **option text** (`"inherent"`); follow-up key `followup_<parent element id>_<option id>`. The UI sends every follow-up key (unselected ones as `""`). |
| Export | `GET /labelings/<id>/answers/export/` (account_type `admin` only) → `text/csv`, UTF-8, no BOM, `\n` row ends, one row per answer ordered by item `row_index` then answer id. |
| Export header (real, synthetic data) | `context_id,user_id,created_at,responded_as,Q : P4 step 1: does the criterion apply?,Q : P4 step 2: how is the right affected?,Q : P4 justification,Q : P4 step 2: how is the right affected? > inherent > P4 threat,Q : P4 step 2: how is the right affected? > conditional > P4 threat,C : record_id,C : record_text` |
| Column scheme | `context_id` = row_index + 1; `user_id` = internal user id (`anonymous` / empty for the LLM bot); `LLM` (`YES`/empty) **only present when at least one LLM answer exists** (dropped otherwise, `backend/answer/views.py:640-641`); `created_at` ISO-8601 with microseconds and `+00:00`; `responded_as` = group name or empty (= the `any` slot); questions `Q : <question text>`; follow-ups `Q : <parent text> > <option text> > <follow-up text>`; record columns literally `C : record_id`, `C : record_text`. The column order is not guaranteed: pandas takes columns in first-seen order across rows (`backend/answer/views.py:639`), so the `Q :`-before-`C :` order of the sample header holds only because the first exported row had answer keys; do not rely on it. A question column exists only if some answer's payload has its key; column order follows payload key order, not the form. Address columns **by name**. |
| Background answers | `GET /labelings/<id>/background-answers/` (needs labeling role owner/admin) → JSON list of `{id, labeling, answered_by, user_first_name, user_last_name, user_email, answer_payload, created_at, updated_at}`; `answer_payload` keys are **background element ids** (and `followup_<el>_<opt>`), not texts; numbers stay numbers. |
| Conditional "required" | **Only for a follow-up of one option of one multiple-choice question**: a follow-up with `required: true` blocks submit only while its option is selected (UI-only check; the backend validates nothing). A top-level question's `required` is unconditional, and an option holds at most one follow-up. The justification rule of design §5.3 (several conditions over several questions) **cannot** be expressed → use "required always". |
| add-items-csv | **Works** on a running decision labeling: `POST /labelings/<id>/add-items-csv/` (multipart `file`, name must end `.csv`) → `200`; new rows get `row_index` after the existing ones and are served. Also works after the labeling auto-finished: its status changes `finished` → `in_progress` and serving resumes. |

## Setup used

- Project 2 "P4 spike 2026-11-17", created via `POST /projects/` as the superuser.
- Labelings (all in project 2):
  - **2 "P4 decision"**: `decision=true`, `decision_mode="manual"`, `distribution_strategy="auto"`, `users_per_item=3`, `items_per_group={"legal":1,"technical":1}` (the API returned `{"legal":1,"technical":1,"any":1}`), `block_section_back=true`, no background; `decisive_question` = step 2 element (5) via `PATCH /labelings/2/ {"decisive_question": 5}`; 6 records, later +2 by add-items-csv.
  - **3 "P4 form mode"**: `form_mode=true`, `users_per_item=1`, `block_section_back=false`, `has_background_form=true`; 6 records; background structure `probe-background` (consent, main field with follow-up text on `other`, years as `number`).
  - 4 "P4 finished then add", 5 "P4 re-PUT and collisions", 6 "P4 MC follow-up", 7 "P4 QUOTE_ALL upload": small edge-case labelings (below).
- Order per labeling: `POST /labelings/` → `PUT /labelings/<id>/import-items-csv/` (multipart) → `PUT /labelings/<id>/structure` → `PATCH /labelings/<id>/` (decisive question). Labeling `status` stayed `draft` throughout; serving does not need `active`.
- Accounts via `create_study_accounts --project 2 --labelings 2,3` (run in a one-off `api` container with the scratch directory mounted): `created=6 updated=0 reset=0`. User ids: P4-L1 2, P4-L2 3, P4-L3 4 (legal); P4-T1 5, P4-T2 6 (technical); P4-EXPORT 7 (account_type `admin`, labeling role `admin`). The superuser `admin@annotaise.invalid` (id 1, `is_staff`) owns the labelings.
- Records (`records.csv`, Python `csv` default dialect, CRLF):
  `P4-R1` = `Commas, "double quotes", a newline⏎second line,⇥a tab and é (e-acute) — plus ü`; R2–R4 plain; R5 = two leading and two trailing spaces; R6 = text with an embedded CRLF, semicolons and single quotes. Added later (`records-add.csv`): `P4-R7` plain, `P4-R8` = `NA`.

## Checklist

### 1. Structure endpoint accepts our form JSON — PASS

- Claim: `PUT labelings/<id>/structure` accepts a hand-written form; GET returns IDs and texts.
- Steps: PUT [`probe-structure.json`](probe-structure.json) on labelings 2 and 3; GET back.
- Observed: `200` both; PUT response is byte-identical to the following GET (`cmp` exit 0). Labeling 2 IDs: section 1 = context 2, step 1 = 3 (options yes 1, no 2, unclear 3); section 2 = context 4, step 2 = 5 (options inherent 4 → follow-up element 6, conditional 5 → follow-up element 7, none 6), justification 8. Excerpt of the GET:

```json
{"id": 5, "order": 2, "text": "P4 step 2: how is the right affected?", "required": true,
 "question_type": "multiple_choice", "column_name": "", "allow_multiple": false,
 "multiple_choice_items": [
  {"id": 4, "text": "inherent", "value": false, "order": 1,
   "follow_up_question": {"id": 6, "order": 10001, "text": "P4 threat", "required": true,
     "question_type": "text", "column_name": "", "allow_multiple": false,
     "multiple_choice_items": [], "question_range": null, "context_type": null}},
  {"id": 5, "text": "conditional", "value": false, "order": 2, "follow_up_question": {"id": 7, "...": "..."}},
  {"id": 6, "text": "none", "value": false, "order": 3, "follow_up_question": null}],
 "question_range": null, "context_type": null}
```

- A follow-up of type `multiple_choice` (the 37-threat design) is accepted too (labeling 6): `follow_up_question` with its own `multiple_choice_items`; the answer value is the option text, e.g. `"Threat label A, with comma"`, exported quoted under `Q : P4 step 2 (mc fu) > conditional > P4 threat (catalogue)`.
- `PUT ?form_type=background` on a labeling with `has_background_form=false` → `400 {"detail": "Esta rotulação não está configurada com formulário background.", "code": "BACKGROUND_DISABLED"}`; GET there → `200 []`.
- An invalid element (`question_type: "nope"`) → `400 INVALID_FORM_STRUCTURE`, no field detail.
- **Re-PUT behaviour (labeling 5):**
  - Re-PUT of the GET body (with `id`s): section, element and option IDs are kept; follow-up **element** IDs change (32→36, 33→37) but follow-up answer keys use parent element id + option id, so the existing answer still exported fully.
  - Re-PUT of the original file (no `id`s): every element and option gets a new ID; the existing answer then exported **only** `context_id,user_id,created_at,responded_as,C : record_id,C : record_text` — all `Q : …` columns vanished (export drops payload keys not in the current form, `backend/answer/views.py:615-629`). Deleting the decisive element also nulls `decisive_question` (`on_delete=SET_NULL`, `backend/labeling/models.py:53`), after which answers are refused (`backend/answer/views.py:173-177`).
- Mechanism: `backend/labeling/views.py:458-468` (GET), `475-645` (PUT; IDs matched at 537-575, options and follow-ups recreated at 589-631).

### 2. Group quotas and the `any` slot — PASS

- Claim: quota `{legal:1, technical:1, any:1}`, `users_per_item=3`: a 2nd legal user takes `any`; a 3rd legal user is refused that item.
- Steps / observed on labeling 2 (`GET /items/2/` = next item; `POST /answers/`):
  1. L1 next → item 5 (P4-R1, random among 0-answer items); answer → `201`, `responded_as_name: "legal"`.
  2. L2 next → item 5 (partly answered items first); answer → `201`, `responded_as_name: null` (export `responded_as` empty = `any`).
  3. L3 next → item 7 (P4-R3), **not** item 5 (remaining `{technical:1}`). L3 `POST /answers/` on item 5 without a reservation → `403 {"detail": "Você não pode responder a esse item da rotulação."}`.
  4. T1 next → item 5; answer → `responded_as_name: "technical"`.
- Mechanism: `backend/item/models.py:86-112` (remaining quotas), `136-157` (slot choice), `backend/item/views.py:297-319` (candidate order `-answer_count`, then random).

### 3. Tie → extra slot → unique leader (LLM off) — PASS

- Claim: 1/1/1 leaves the item `pending` and serves it to a 4th user; 2/1/1 then finishes it.
- Observed on item 5 (decisive = step 2):
  - After L1 `inherent`, L2 `conditional`, T1 `none`: `status: "pending"`, `decision_payload: {"none": 1, "inherent": 1, "conditional": 1}`, `final_decision_value: null`.
  - L3 (legal, already refused in item 2) answered item 7, then next → **item 5** (the extra `any` slot). L3 `inherent` → `responded_as` empty; item 5 `status: "finished"`, `decision_payload: {"none":1,"inherent":2,"conditional":1}`, `final_decision_source: "human"`, `final_decision_value: "inherent"`.
  - T2 next afterwards → item 7, not item 5.
- Rule: the unique top count wins, a strict majority is not needed (`_resolve_vote_winner`, `backend/answer/views.py:92-103`; finish check 238-254; extra slot `backend/item/models.py:104-110`). The API value for "LLM off" is `decision_mode: "manual"`; `"human"` → `400 {"decision_mode": ["\"human\" is not a valid choice."]}` (`backend/labeling/models.py:19-21`).
- Items API: `GET /labelings/<id>/items/` lists `{id, labeling, payload, row_index, status, decision_payload, llm_tiebreak_attempted, llm_tiebreak_result, final_decision_source, final_decision_value}`; item statuses seen: `pending`, `finished`.

### 4. `form_mode` serves every annotator every item, in row order — PASS

- Labeling 3: T1, T2 and L2 each looped next → answer until refused. Each was served `P4-R1, P4-R2, P4-R3, P4-R4, P4-R5, P4-R6`, then `400 {"code": "NO_LABELINGS_TO_ANSWER"}`. With `users_per_item=1` no item was ever closed by others' answers.
- The dummy item created with a form-mode labeling (`backend/labeling/serializers.py:42-49`) was gone after `import-items-csv` (which deletes existing items first, `backend/item/views.py:65-68`): the item list showed exactly the 6 records.
- Mechanism: `backend/item/views.py:447-458` (`order_by('row_index','id')`, excluding answered items).

### 5. `block_section_back` and editing a submitted answer — PASS (no edits possible for annotators)

- UI, labeling 2 (`block_section_back=true`), as T1: section 1 shows only **Avançar**, section 2 only **Enviar resposta** — no back control. Avançar with nothing selected → toast "Preencha todas as perguntas obrigatórias antes de avançar." (screenshots in the scratch run).
- UI, labeling 3 (`block_section_back=false`), as L1: arrow buttons; on section 2 the back arrow returned to section 1 with the typed follow-up text still kept on returning to section 2. After submit the next item loads (`Item #1` → `Item #2`); there is no control to return to a submitted item.
- No UI path edits a submitted answer: annotators' sidebar has only "Rotular"; `updateAnswer` (`frontend/src/modules/labelings/labelingService.ts:238`) is not used by any page.
- API, `PATCH /answers/<id>/ {"answer_payload": {...}}`:
  - L1 on own answer, labeling 2 (blocked) → `403 {"detail": "You do not have permission to perform this action."}`;
  - T1 on own answer, labeling 3 (not blocked) → same `403`; L1 `GET /answers/<id>/` → `403` (the answers viewset needs account_type `admin`, `backend/answer/views.py:37-43`);
  - export account (admin, not staff) on L1's answer, labeling 2 → `403 {"detail": "Edições estão bloqueadas para esta rotulação."}`; on T1's answer, labeling 3 → `403 {"detail": "Você não pode editar esta resposta."}`;
  - the superuser (`is_staff`) → `200` (it edited its own scratch answer on labeling 5; staff bypass, `backend/answer/views.py:340-347`). An edit does not recount `decision_payload`.
- Double answers by one annotator on one item could not be produced: next-item excludes answered items and `POST /answers/` needs a live reservation (`backend/answer/views.py:143-152`).

### 6. Follow-ups on two options and their export columns — PASS

- UI (labeling 2, T1): selecting `inherent` shows "P4 threat *" under it; selecting `conditional` hides that one and shows the second "P4 threat *" under `conditional`; `none` shows none. Display happens at selection time, before submit.
- Payload sent by the UI: `{"3":"yes","5":"conditional","8":"","followup_5_4":"","followup_5_5":"UI threat for conditional"}`.
- Export columns: `Q : P4 step 2: how is the right affected? > inherent > P4 threat` and `Q : P4 step 2: how is the right affected? > conditional > P4 threat` (`backend/answer/views.py:576-591`).
- **Stale follow-up text:** T1 selected `inherent`, typed "stale threat typed under inherent", switched to `none`, submitted. The UI sent `{"3":"no","5":"none","8":"","followup_5_4":"stale threat typed under inherent","followup_5_5":""}` and the export row shows step 2 `none` **with** a non-empty `… > inherent > P4 threat` cell. Consumers must read a follow-up column only when its option is the selected step 2 value.
- **Duplicate question texts collide** (labeling 5): two questions both titled `Confidence` (one per section) produced a single column `Q : Confidence`; the answer had `"29":"high"` and `"34":"low"`, the export showed only `low` (dict keyed by column name, `backend/answer/views.py:629-634`).

### 7. Conditionally required text — VERDICT: only per-option follow-ups

- UI (labeling 2): `conditional` selected with the required follow-up empty → "Enviar resposta" sent **no** request and showed "Preencha todas as perguntas obrigatórias antes de avançar."; after filling it, submit sent `POST /answers/` → `201` even though "P4 justification" (`required: false`) was empty. With `none` selected (follow-ups hidden) submit succeeded.
- Check is frontend-only (`frontend/src/components/context-question/question-modules/MultipleChoice.tsx:121-144`, `frontend/src/components/context-question/page-type/user-labeling/helpers.ts:42-55`); the backend stores any payload (`backend/answer/serializers.py:6-85` has no required logic), as the API answers without step 1 keys in labeling 4 showed.
- There is no field for a condition on a top-level question, and each option has one `follow_up_question`. The threat already occupies the follow-ups of `inherent`/`conditional`, so the design's justification rule cannot be expressed: **justification must be required always** (design §5.3's fallback).

### 8. `add-items-csv` on a running decision labeling — PASS

- Labeling 2 (8 answers on 6 items, item 5 finished): `POST /labelings/2/add-items-csv/` with `records-add.csv` → `200 {"detail": "Itens adicionados a rotulação com sucesso"}`. New items 17 (`row_index` 6, P4-R7) and 18 (`row_index` 7, P4-R8). L1 then looped next/answer and was served R3, **R7**, R6, R4, R2, **R8**, R5, then `NO_LABELINGS_TO_ANSWER`.
- Labeling 4 (`users_per_item=1`, 1 record): after the only answer the labeling status became `finished` and next → `400 {"detail": "Essa rotulação já foi finalizada", "code": "ROTULACAO_FINALIZADA"}`. add-items-csv → `200`, status `in_progress`, next served P4-R7.
- Columns are matched by name; extra upload columns are dropped and missing ones filled with `Valor Nulo` (`backend/item/views.py:167-183`).

### 9. Background form per labeling; background-answers JSON — PASS

- Per labeling: labeling 2 (`has_background_form=false`) refuses a background structure (see 1); labeling 3 has its own. On labeling 3, next-item before a background answer → `403 {"detail": "Você precisa responder o formulário background antes de rotular.", "code": "BACKGROUND_REQUIRED"}`.
- Own answer: `GET /labelings/3/background-answer/` → `200` with an empty body before answering. `PUT /labelings/3/background-answer/ {"answer_payload": {...}}` → `201` first time, `200` on a repeat (update in place; `updated_at` changes). The UI page is `/labelings/<id>/background` ("Enviar Background"); it sent `{"answer_payload":{"16":"I consent","17":"other","19":4,"followup_17_16":"privacy engineering"}}`.
- Export account: `GET /labelings/3/background-answers/` → `200`:

```json
{"id": 1, "labeling": 3, "answered_by": 5, "user_first_name": "P4-T1", "user_last_name": "",
 "user_email": "p4-tech1@example.invalid",
 "answer_payload": {"16": "I consent", "17": "computing", "19": 7, "followup_17_16": ""},
 "created_at": "2026-11-17T20:28:16.788543Z", "updated_at": "2026-11-17T20:28:20.694293Z"}
```

- L1 (annotator) → `403 {"detail": "Você não tem permissão para visualizar essas respostas."}`; export account on labeling 4 (not a labeling member) → same `403`; on labeling 2 (no background) → `200 []`.

### 10. Export account: login, export, annotator 403 — PASS

- Login `POST /api/auth/token/` → `200`, keys `["access", "refresh"]` (all 6 accounts via the Tailnet URL; the export account also via loopback `127.0.0.1:8471/backend`).
- `GET /labelings/{2,3,4}/answers/export/` as the export account → `200`, `Content-Type: text/csv`, `Content-Disposition: attachment; filename="exported_answers_P4 decision.csv"`. P1's `created_at` and `responded_as` columns are present.
- The export checks only account_type `admin` (`backend/user/permissions.py:18-30`; its docstring says "staff or admin" but the code tests only `account_type == "admin"`, `backend/answer/views.py:558-559`): it also worked on labeling 4, where the export account has no labeling role.
- L1 → `403 {"detail": "You do not have permission to perform this action."}`.
- Rows of labeling 2 (excerpt, columns `context_id,user_id,responded_as,step 2,… > inherent > P4 threat,… > conditional > P4 threat,C : record_id`):

```
1,2,legal,inherent,T-a,,P4-R1
1,3,,conditional,,T-b,P4-R1
1,5,technical,none,,,P4-R1
1,4,,inherent,T-c,,P4-R1
4,5,technical,none,stale threat typed under inherent,,P4-R4
```

- `GET /labelings/<id>/imported-items-csv/` (export account) rebuilds the uploaded CSV; its first 292 bytes are byte-identical to `records.csv`.

### 11. Record text round-trip — PASS for real text, with one exception

- For P4-R1 (commas, double quotes, LF, tab, `é`, `—`, `ü`), R5 (leading/trailing spaces), R6 (embedded CRLF) and the plain rows, `C : record_text` parsed with `csv.DictReader` equals the uploaded value and its UTF-8 bytes (both labelings). A `csv.QUOTE_ALL`, `\n`-terminated upload (G1's format, labeling 7) round-trips the same way.
- **Exception:** values pandas reads as missing are replaced by the literal `Valor Nulo` at upload: observed for `NA` (export shows `Valor Nulo`), `""`, `None` and `n/a` (`pd.read_csv(..., dtype=str)` + `fillna("Valor Nulo")`, `backend/item/views.py:92,100,167,183`).
- Display: a single `\n` renders as a space in the answer page (R1 shows "a newline second line"); `\n\n` renders as two paragraphs.

## Other observations

- **Annotators can read everyone's answers.** As T2 (annotator): `GET /labelings/2/answers/` → `200`, 13 answers with `answered_by_email` and full payloads; `GET /labelings/2/items/` → `200` with `decision_payload` vote counts (a user who is not a member of the labeling gets `401 {"detail": "Você não tem acesso a essa rotulação"}` instead: observed for P4-L1 on labeling 4; `backend/item/views.py:39-48`); `GET /labelings/2/agreement-summary/` → `200`. These views only need a login or a labeling membership (`backend/answer/views.py:446-463`, `backend/item/views.py:31-49`, default `IsAuthenticated` in `backend/annotaise/settings.py:174-176`). The UI does not link to them for annotators.
- The superuser is `is_staff` and may edit any answer despite `block_section_back`.
- `GET /api/health/` returned `500` on the test instance (not investigated; unrelated to the checklist).
- The export file name contains the labeling title with spaces.

## Contradictions with the plan

| # | Claim (plan / design) | Observed | Smallest plan change |
|---|---|---|---|
| C1 | Design §5.3: Form B `decision_mode = human`. | Valid values are `manual` and `llm`; `"human"` → `400`. `final_decision_source` is `"human"`. | Write `decision_mode = "manual"` in §5.3 and in L-task setup. |
| C2 | G2 `build_form`/`question_texts`: step 1 and step 2 both have a "confidence"; G4 maps headers via `question_texts`. | Export columns are keyed by question **text**; two questions with the same text share one column and the later value wins. | G2: every main-form question text unique (e.g. "Step 1 confidence", "Step 2 confidence"); add `test_question_texts_unique`. |
| C3 | G2 `push` sends a form with `PUT labelings/<id>/structure` (nothing on re-push, nor on the decisive question). | Elements are matched only by `id` within the same section, never by text; an element whose `id` is missing or belongs to another section is created new and the old one deleted. A PUT without element `id`s therefore recreates all elements: old answers lose every `Q :` export column and `decisive_question` becomes null. The decisive question must be set by `PATCH labelings/<id>/ {"decisive_question": <element id>}` after the PUT. | G2 `push`: refuse when the labeling has answers unless every section and element carries the `id` a prior GET returned for it in the same section; after the PUT, GET, then PATCH `decisive_question` (Form B, step 2). Never change question texts after answers exist. |
| C4 | G4 `build_background(snapshot, roster)` gets "the six answers" from `background.json`. | Background `answer_payload` is keyed by element **id** (`"16"`, `followup_17_16`); the texts are only in `GET labelings/<id>/structure?form_type=background`. | G4 `pull`: also save `structure-main.json` and `structure-background.json` in each snapshot; map IDs to G2 keys from them. |
| C5 | G4 parses `threat_id` "from the follow-up column". | The UI submits a stale follow-up text for an option that is no longer selected (observed: step 2 `none` with a filled `… > inherent > …` cell). | G4: read only the follow-up column whose option equals the row's step 2 value; add `test_stale_followup_ignored`. |
| C6 | G1: the CSV round-trips text exactly. | `NA`, `n/a`, `None` and empty values become `Valor Nulo` on upload. | G1: `write_csv` raises on an empty `record_id`/`record_text` or a value in pandas' default NA set; add a test. |
| C7 | Design §4/§5.1: only three fork changes; annotators judge independently (design §5.3: threat shown only after the annotator's own answer). | Any annotator can fetch all answers (with emails) and vote counts via the API (see "Other observations"). | Add a fork task: restrict `labelings/<id>/answers/`, `labelings/<id>/items/` and `agreement-summary` to edit roles (plus a Django test), or record the accepted risk in the design. |

Not contradictions, for the record: the justification can only be "required always" (design's fallback); the `LLM` column is absent unless an LLM answer exists (G4's LLM-row check must tolerate the missing column); a question column is absent until some answer contains its key.

## Test data left on `annotaise-test`

Project 2 "P4 spike 2026-11-17" with labelings 2–7 and their items/answers;
users 2–7 (`p4-*@example.invalid`, P4-L1…P4-EXPORT); groups `legal`,
`technical`. The P1 restore-check data were not touched. The password file was
shredded after the run.
