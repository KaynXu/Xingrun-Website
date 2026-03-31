# Consultation AI Batch Design

## Goal

Add a minimal-intrusion AI-assisted batch entry flow to the existing `咨询记录` tab so staff can paste one block of natural language, preview multiple consultation record creates and explicit-ID updates, then confirm before any data is written.

## Why This Change

The current consultation workspace already supports stable single-record CRUD and a small quick-entry parser, but it still assumes one record per interaction.

Real usage is already beyond that shape:

- staff often receive several consultation updates in one burst
- the input is frequently free-form natural language rather than structured fields
- some source material comes from WeChat merged-forward text that contains several conversation fragments in one paste

The practical gap is not storage. The gap is preprocessing. The right first release is to add an AI parsing layer that produces reviewable drafts while keeping the existing storage model and CRUD endpoints intact.

## Product Decision

### Keep Existing Single-Record Flow

The existing `新增记录`, `编辑`, `查看`, `删除`, and direct search flow stays in place.

The new AI feature is an additional entry path, not a replacement.

This keeps current staff habits intact and limits regression risk in the existing consultation workflow.

### Add Draft-First AI Batch Flow

The first release must follow this sequence:

1. user pastes raw text
2. backend parses the text into structured draft items
3. frontend shows a preview list of proposed create or update actions
4. user removes or edits any unwanted draft items
5. user confirms import
6. frontend writes each confirmed item through existing create or update APIs

The AI must not write directly into storage in the first release.

### Explicit-ID Rule For Updates

The first release only allows `update` actions when the pasted text explicitly includes a consultation record identifier.

Accepted examples:

- `ID 182`
- `记录182`
- `#182`

If explicit ID evidence is missing, the parser must treat the item as `create`.

This is the key safety boundary for a minimal-risk release.

## Scope

### Included In First Release

- AI batch parse entry inside the existing `咨询记录` workspace
- parsing one pasted text block into multiple draft consultation actions
- support for mixed `create` and explicit-ID `update` items in the same batch
- support for pasted WeChat merged-forward text after lightweight cleanup
- preview before save
- confirm import using existing single-record endpoints
- lightweight warnings for low-confidence or incomplete items

### Explicitly Out Of Scope

- AI direct write-to-database behavior
- fuzzy matching old records by parent name plus date
- screenshot OCR
- native import of WeChat export files or proprietary chat formats
- automatic attachment parsing
- large workflow redesign of the consultation tab
- replacing CSV storage in this phase

## UX Design

### Entry Point

Inside the existing consultation page header actions, add one new button next to `刷新` and `新增记录`:

- `AI 批量整理`

This opens a modal instead of navigating to a new page.

### Batch Modal Structure

The modal should remain intentionally compact and should not become a second full consultation workspace.

It contains three sections.

#### 1. Raw Input

One large textarea for pasted text.

Helper copy should tell users the two preferred input styles:

- plain natural-language batch notes
- pasted WeChat merged-forward text

Example helper text should also explain the explicit-ID rule for updates.

#### 2. Parse Preview

After clicking `智能解析`, show a vertical list of draft items.

Each item must show:

- action badge: `新增` or `更新`
- target record ID when action is update
- parsed key fields summary
- warnings when the item is incomplete or ambiguous
- remove button so the user can drop the item from this import batch

The first release may allow only light inline edits in preview. It does not need full field-by-field editing if that would significantly increase complexity.

#### 3. Confirm Import

The footer must show:

- count of draft items ready to write
- cancel button
- confirm import button

After confirm:

- for `create`, call `POST /api/consultations`
- for `update`, call `PUT /api/consultations/<id>`

If one item fails, the UI should report which item failed. The first release does not need transactional all-or-nothing rollback.

## Parsing Behavior

### Input Shapes To Support

The parser should handle two broad input styles.

#### A. Structured Natural Language

Examples:

- `新增：张妈妈，五年级数学，雷文浩接待，转介绍，想补基础`
- `修改 ID 182：跟进状态改成跟进中，备注改为已约周四试听`
- `新增：李爸爸，初一英语，朋友圈来的，想先测评`

#### B. WeChat Merged-Forward Text

Expected properties:

- multiple message fragments in one pasted block
- sender labels or speaker prefixes
- timestamps or system lines
- empty lines between fragments

The first release only needs lightweight cleanup before AI parsing:

- remove obvious timestamps and separator noise
- merge message fragments into readable semantic blocks
- preserve content words that help identify parent, teacher, grade, subject, need, and follow-up state

### Output Contract

The parser returns a stable JSON payload with:

- `items`
- `warnings`

Each `item` must have:

- `action`: `create` or `update`
- `target_id`: integer or `null`
- `reason`: short explanation of why the action was chosen
- `fields`: normalized consultation payload
- `warnings`: per-item warning strings

### Allowed Fields

The parser should only output fields already supported by the consultation editing flow:

- `date`
- `parent_wechat_name`
- `child_name`
- `grade`
- `receiving_teacher`
- `teacher_id`
- `consultation_subject`
- `need_detail`
- `source_channel`
- `source_channel_note`
- `follow_up_status`
- `follow_up_note`

The server must filter AI output back through the existing editable-field allowlist before any save.

### Normalization Rules

The new batch parser should reuse the same domain rules already used by the consultation page wherever possible:

- grade normalization
- source channel normalization
- teacher alias matching

This keeps batch parsing consistent with current single-record behavior.

## Architecture

### Frontend

The existing consultation page in `frontend/src/App.tsx` remains the integration surface.

Recommended first-release additions:

- one new local modal state for batch parsing
- one API call to parse raw text
- one preview list renderer
- one confirm handler that loops through draft items and calls existing write endpoints

The consultation page should reload the current list after confirm completes.

### Backend

The backend should add one parse-only endpoint:

- `POST /api/consultations/ai-parse`

This endpoint:

- requires normal authenticated staff access
- accepts raw pasted text
- performs lightweight preprocessing for WeChat merged-forward content
- calls an AI parser with a tightly-scoped JSON response contract
- normalizes and filters the returned items
- does not write any consultation records

The backend should not add a new storage model for this phase.

### AI Layer

The AI responsibility is narrow:

- split one text block into multiple consultation actions
- classify each action as create or explicit-ID update
- extract only allowed consultation fields
- return strict JSON only

The prompt should explicitly forbid inferential updates when no record ID is present.

## API Design

### `POST /api/consultations/ai-parse`

Request body:

- `raw_text`: required string

Optional future-compatible body fields may be accepted but are not required for first release.

Response body:

```json
{
  "items": [
    {
      "action": "create",
      "target_id": null,
      "reason": "未检测到显式记录ID，按新增处理",
      "fields": {
        "date": "2026-03-31",
        "parent_wechat_name": "张妈妈",
        "child_name": "",
        "grade": "五年级",
        "receiving_teacher": "雷文浩",
        "teacher_id": "teacher-1",
        "consultation_subject": "数学",
        "need_detail": "想补基础",
        "source_channel": "转介绍",
        "source_channel_note": "张裕空",
        "follow_up_status": "待邀约",
        "follow_up_note": ""
      },
      "warnings": []
    },
    {
      "action": "update",
      "target_id": 182,
      "reason": "文本显式提到记录 ID 182",
      "fields": {
        "follow_up_status": "跟进中",
        "follow_up_note": "已约周四试听"
      },
      "warnings": []
    }
  ],
  "warnings": []
}
```

### Existing Save Endpoints Stay Unchanged

The first release should continue writing through:

- `POST /api/consultations`
- `PUT /api/consultations/<id>`

No new batch-write endpoint is required for first release.

This keeps the write path aligned with the already-tested CRUD layer.

## Permissions

The new parse endpoint should follow the same access level as normal consultation viewing and creating.

Rules:

- authenticated staff can open the AI batch modal
- authenticated staff can call parse
- create permissions remain aligned with current consultation create rules
- update permissions remain aligned with current consultation update rules

The preview UI must not imply that a user can save an update they are not authorized to write.

## Error Handling

### Parse Failure

- show a clear parse error banner in the modal
- keep the raw input intact for retry
- do not clear any existing preview until the next successful parse

### Partial Save Failure

- show which preview item failed
- preserve the preview list in the modal
- keep already-saved results visible so the user does not retry blindly

### Low-Confidence Parse

If key fields are missing or action choice is uncertain, the parser should still return an item when possible, but attach warnings such as:

- missing teacher match
- missing subject
- ambiguous source channel
- update rejected because explicit ID was not found

## Testing Strategy

### Backend

Add focused regression coverage in `tests/test_consultation_flow.py` for:

- mixed create and explicit-ID update parsing
- WeChat merged-forward text cleanup producing multiple draft items
- no explicit-ID means no update action

### Frontend

Add minimal source-level assertions in existing frontend tests for:

- presence of the `AI 批量整理` entry point
- presence of parse preview and confirm import copy

The first release does not require high-fidelity interaction tests if the source-level assertions already match the current repo test style.

## Rollout Notes

This feature is intentionally a thin AI assist layer on top of the current consultation workspace.

If usage proves stable, later phases can consider:

- richer inline editing in preview
- fuzzy candidate matching for updates
- transactional batch write behavior
- screenshot OCR or file import

None of those are required to make the first release useful.