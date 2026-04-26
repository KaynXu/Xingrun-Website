# RQ Wrong Question Upload Design

## Goal

Move parent wrong-question uploads from synchronous AI processing to a Redis/RQ-backed background flow so the mini program can return quickly after upload while server workers finish transcription, classification, recognition, storage, and PDF rebuild.

## Architecture

The website Flask app remains the request entry point. It validates the parent binding, creates a durable upload task row in SQLite, enqueues the task ID into an RQ queue, and returns `202` with the task snapshot. A separate RQ worker process imports the same project code, loads the task by ID, performs the existing AI and PDF work, then updates the task to `ready` or `failed`.

Redis is only the queue broker. SQLite remains the source of truth for task status and final wrong-question records.

## Data Flow

1. The mini program uploads voice files to the bridge `/upload` endpoint when needed.
2. The final wrong-question image upload goes to bridge `/wechat/parent/wrong-questions`.
3. The bridge stores the image file and forwards `image_url`, optional `child_reason_audio_url`, and existing metadata to website `/api/wechat/wrong-questions`.
4. The website creates a `wechat_wrong_question_upload_tasks` row with `pending` status.
5. The website enqueues `process_wechat_wrong_question_upload_task(task_id)` to RQ and returns `202`.
6. The worker marks the task `processing`, transcribes audio when present, classifies the child reason, recognizes the image, creates the wrong-question submission, rebuilds the student PDF, and marks the task `ready`.
7. If processing fails, the worker marks the task `failed` with the error message and leaves the task visible for status checks.

## API Contract

`POST /api/wechat/wrong-questions` returns:

```json
{
  "task": {
    "id": 1,
    "status": "pending",
    "record_id": "",
    "error_message": ""
  },
  "student_library_pdf_url": "/api/wechat/student-libraries/123"
}
```

The bridge maps this through to the mini program. A new website status endpoint exposes `GET /api/wechat/wrong-question-upload-tasks/<task_id>?open_id=...`, and the bridge exposes `GET /wechat/parent/wrong-question-upload-tasks/<task_id>?openId=...`.

## Error Handling

If Redis/RQ enqueue fails after the task row is created, the website marks the task `failed` and returns `502` with `retryable: true`. Worker failures are persisted to the task row as `failed`.

## Testing

Backend tests cover task creation, RQ enqueue behavior, worker success, worker failure, and status scoping by parent `open_id`. Bridge and mini program tests cover `202` task responses and the new status query helper.
