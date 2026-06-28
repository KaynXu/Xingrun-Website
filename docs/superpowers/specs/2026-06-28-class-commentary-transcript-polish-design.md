# Class Commentary Transcript Polish Design

## Status

- Date: 2026-06-28
- Stage: design approved in conversation, pending implementation plan
- Target feature: `class-commentary`
- Scope: backend transcript quality improvement only

## Background

The class-commentary tab already supports selecting a class, uploading a lesson audio file, polling transcription, editing the transcript, selecting a colleague skill, generating one sendable feedback package, and copying the result.

Tencent Cloud ASR is now configured and deployed as the audio transcription provider. A real 5.8 MB classroom recording was transcribed successfully with `provider=tencent` and `model=flash-16k_zh`.

The next quality problem is not the upload UI. The problem is that raw ASR text can misrecognize student names and math terms. The chosen direction is:

```text
Tencent ASR raw text -> LLM transcript polish with roster constraints -> teacher-visible transcript -> feedback generation
```

## Confirmed Decisions

- Do not change the current frontend flow in this phase.
- Do not ask teachers to type student names.
- Use the selected `class_id` to fetch the existing class roster from the backend.
- Do not create or manage Tencent Cloud hotword tables in this phase.
- The teacher-facing transcript box should show the LLM-polished transcript by default.
- The raw Tencent ASR transcript should be stored server-side for audit/debugging.
- If transcript polishing fails after ASR succeeds, the task should still become `transcribed` with the raw ASR text visible, so teachers can manually edit and continue.
- Feedback generation continues to use `confirmed_transcript_text`, not the raw ASR text.

## Non-Goals

- No frontend layout change.
- No extra "raw transcript vs polished transcript" two-column UI.
- No teacher-managed student-name or term input.
- No Tencent Cloud hotword table creation, update, reuse, or deletion.
- No per-student independent copy/send workflow.
- No sending-channel integration.
- No fuzzy nickname or same-pronunciation student resolution beyond the selected class roster.

## Product Behavior

The current page remains the same:

1. Teacher selects a class.
2. Teacher uploads audio.
3. Backend transcribes and polishes the transcript.
4. Page shows the polished transcript in the existing editable transcript area.
5. Teacher can edit the transcript.
6. Teacher selects a colleague skill and generates feedback.
7. Page shows the generated feedback package.

The visible transcript should feel like a cleaned-up version of what the teacher said. It should preserve the teacher's meaning and student-specific facts while fixing obvious ASR name, term, punctuation, and sentence-boundary errors.

## Backend Flow

### Upload

`POST /api/class-commentary/tasks` keeps the existing request and response contract:

- Request: multipart `class_id`, `audio`
- Response: task JSON with `status=transcribing`

No new frontend fields are required.

### Transcription Worker

The worker changes from:

```text
transcribe_audio(audio_path) -> transcript_text
```

to:

```text
class_id -> class roster
audio_path -> Tencent ASR raw transcript
raw transcript + roster + math terms -> LLM polished transcript
save raw transcript and polished transcript
```

The saved task should use:

- `raw_transcript_text`: the direct Tencent ASR text.
- `transcript_text`: the teacher-visible polished transcript if polishing succeeds, otherwise the raw ASR text.
- `confirmed_transcript_text`: copied from `transcript_text` as the initial editable value.
- `transcript_polish_error`: empty on success, otherwise the polish error message.
- `transcript_polished_at`: timestamp when polish succeeds, otherwise empty.

### Generation

`POST /api/class-commentary/tasks/<id>/generate` stays the same from the frontend's point of view. It continues to use the teacher-confirmed `confirmed_transcript_text`.

## Roster Constraint

The transcript polish prompt must receive a roster payload built from `list_students_for_class(class_id)`.

The prompt should enforce:

- Student names may only be corrected to names in the selected class roster.
- If the raw text contains a likely name but it cannot be confidently mapped to one roster student, keep the raw wording rather than inventing a student.
- Do not add students who are not clearly mentioned.
- Do not remove teacher comments just because the student name is uncertain.
- Preserve praise, criticism, reminders, and next-step instructions.
- Preserve the order of the teacher's spoken commentary as much as possible.

This is intentionally an LLM prompt constraint, not a Tencent hotword table.

## Math Term Constraint

The polish prompt should also receive a small built-in math term list. First version can be static and backend-owned.

Examples:

- 绝对值
- 整式
- 单项式
- 多项式
- 方程
- 不等式
- 计算
- 推理
- 分类讨论
- 流程图
- 取值无关
- 解题过程

The term list is a correction aid, not a source of new content. The model may fix obvious ASR mistakes such as malformed math terms, but must not add mathematical topics the teacher did not mention.

## Prompt Contract

Add a backend AI helper, conceptually:

```python
polish_class_commentary_transcript(
    class_record: dict,
    students: list[dict],
    raw_transcript_text: str,
    math_terms: list[str],
    include_usage: bool = False,
)
```

Expected output is plain text only. No Markdown, no JSON, no analysis notes.

System intent:

- You are correcting ASR text for a teacher's spoken post-class student commentary.
- Only correct recognition errors, punctuation, light sentence boundaries, and roster-name mistakes.
- Do not rewrite the teacher's content into polished feedback.
- Do not change meaning, tone, praise/criticism balance, or factual claims.
- Do not invent absent students or facts.

## Data Model

Extend `class_commentary_tasks` with:

- `raw_transcript_text`: text not null default empty
- `transcript_polish_error`: text not null default empty
- `transcript_polished_at`: text not null default empty

Existing fields keep their meaning:

- `transcript_text`: teacher-visible transcript, preferably polished
- `confirmed_transcript_text`: teacher-edited transcript used for generation
- `transcription_error`: only for ASR/transcription-stage failure
- `generation_error`: only for feedback-generation failure

No frontend type changes are required if the API does not return the new raw/debug fields.

## API Contract

Existing API routes remain unchanged:

- `POST /api/class-commentary/tasks`
- `GET /api/class-commentary/tasks/<id>`
- `PUT /api/class-commentary/tasks/<id>/transcript`
- `POST /api/class-commentary/tasks/<id>/generate`

Task response remains compatible with the current frontend. New raw/debug fields are not returned in this phase.

If future debugging UI is needed, a separate admin-only endpoint can expose raw transcript fields later.

## Error Handling

### ASR Fails

If Tencent ASR fails or returns empty text:

- `status=failed`
- `failure_stage=transcription`
- `transcription_error=<error>`
- no polishing attempt

### ASR Succeeds But Polish Fails

If ASR succeeds and LLM polish fails:

- `status=transcribed`
- `raw_transcript_text=<raw ASR text>`
- `transcript_text=<raw ASR text>`
- `confirmed_transcript_text=<raw ASR text>`
- `transcript_polish_error=<error>`
- `failure_stage=''`
- `transcription_error=''`

The teacher can manually edit the raw text and continue.

### Polish Returns Empty Text

Treat empty polished text as a polish failure and fall back to raw ASR.

## AI Usage And Charging

Transcription currently runs through the `class_commentary_transcribe` feature key.

For first implementation, the ASR call and polish call can remain inside the same transcription worker, but usage attribution must be explicit:

- Tencent ASR usage: provider `tencent`, model like `flash-16k_zh`
- Transcript polish usage: provider/model from the existing chat model config

Preferred implementation is to call the polish helper through the existing charge/usage wrapper with a distinct feature key:

- `class_commentary_transcript_polish`

If adding a new feature key would create too much unrelated pricing work, the implementation plan may keep it under `class_commentary_transcribe` but must still record provider/model usage clearly.

## Testing

Backend tests should cover:

- Upload task still returns the same response shape expected by the frontend.
- Worker fetches the class roster before polishing.
- Successful ASR plus successful polish stores raw ASR separately and exposes polished text as `transcript_text` and `confirmed_transcript_text`.
- Successful ASR plus polish failure falls back to raw ASR and still marks the task `transcribed`.
- ASR failure still marks `failure_stage=transcription`.
- Feedback generation still uses `confirmed_transcript_text`.
- Prompt payload includes class roster and math terms.
- Prompt forbids inventing students outside the roster.

No frontend tests are required unless the API response shape changes. The implementation should avoid changing that shape.

## Rollout

This is safe to roll out behind existing backend configuration because the frontend contract remains unchanged. After deployment, verify with a real class-commentary audio file:

1. Upload audio in the existing tab.
2. Confirm `transcript_text` shown in the page is polished.
3. Confirm raw ASR text is stored server-side.
4. Generate feedback using a colleague skill.
5. Confirm only mentioned roster students appear in the final feedback.

## References

- Tencent Cloud Recording File Recognition Flash Edition: `https://cloud.tencent.com/document/product/1093/52097`
- Tencent Cloud Create Hotword Table: `https://cloud.tencent.com/document/product/1093/41111`

Hotword table support is documented by Tencent Cloud, but this design intentionally does not use it in phase one.
