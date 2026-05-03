# Production Upload Pipeline Smoke Runbook

Use this before asking parents to try the production upload flow. The checks cover Flask, the WeChat bridge, Redis, the RQ worker, upload limits, task status, and wrongbook/PDF visibility.

All commands are read-only unless the heading says `[MUTATING]`.

## Setup

Run these commands on the production server as `ubuntu`.

```bash
export APP_DIR=/home/ubuntu/Xingrun-Website
export FLASK_URL=http://127.0.0.1:5001
export BRIDGE_URL=http://127.0.0.1:3001
export XR_REDIS_URL="${XR_REDIS_URL:-redis://127.0.0.1:6379/0}"
export QUEUE="${XR_WRONG_QUESTION_UPLOAD_QUEUE:-wrong_question_uploads}"

# Fill these from a recent parent upload when checking a real task.
export OPEN_ID="replace-with-parent-open-id"
export STUDENT_ID="replace-with-student-id"
export TASK_ID="replace-with-upload-task-id"
```

Expected: `APP_DIR` is `/home/ubuntu/Xingrun-Website`, `FLASK_URL` is local Flask, `BRIDGE_URL` is local bridge, and `QUEUE` is `wrong_question_uploads` unless production intentionally overrides it.

## 1. PM2 Services

```bash
pm2 status xingrun xingrun-bridge xingrun-rq-worker
pm2 show xingrun | sed -n '1,80p'
pm2 show xingrun-bridge | sed -n '1,80p'
pm2 show xingrun-rq-worker | sed -n '1,100p'
```

Expected healthy result:
- `xingrun`, `xingrun-bridge`, and `xingrun-rq-worker` are `online`.
- Restart counts are stable during the smoke window.
- `xingrun-rq-worker` points at the current repo and uses the same Redis URL and queue name as Flask.

## 2. Redis And RQ Worker Health

```bash
redis-cli -u "$XR_REDIS_URL" ping
cd "$APP_DIR"
.venv/bin/rq info --url "$XR_REDIS_URL" "$QUEUE"
redis-cli -u "$XR_REDIS_URL" llen "rq:queue:$QUEUE"
redis-cli -u "$XR_REDIS_URL" --scan --pattern 'rq:worker:*' | head
```

Expected healthy result:
- `redis-cli ping` returns `PONG`.
- `rq info` lists `wrong_question_uploads`.
- At least one worker is visible.
- Queue length is usually `0` or drains down while the worker is online.

## 3. Flask Health

```bash
curl -sS -D - -o /dev/null "$FLASK_URL/" | sed -n '1,8p'
```

Expected healthy result:
- HTTP status is usually `302 FOUND`.
- `Location` points to the configured browser/frontend URL.
- No connection refused or 5xx response.

## 4. Bridge Health

```bash
curl -fsS "$BRIDGE_URL/healthz" | python3 -m json.tool
```

Expected healthy result:
- JSON contains `"ok": true`.
- JSON contains `"service": "xingrun-parent-wechat-bridge"`.

## 5. Upload Size Limits

```bash
cd "$APP_DIR"
.venv/bin/python - <<'PY'
from app import app
print(app.config["MAX_CONTENT_LENGTH"])
PY

grep -n "fileSize: 10 \\* 1024 \\* 1024" miniprogram/backend/src/upload.ts
sudo nginx -T 2>/dev/null | grep -n "client_max_body_size" || true
```

Expected healthy result:
- Flask prints `209715200` (`200 MB`).
- Bridge upload limit is `10 MB`.
- Nginx must not enforce a lower effective limit on `/upload` or `/wechat/parent/wrong-questions`.

## 6. Sample Task Status

Check the website task endpoint:

```bash
curl -fsS "$FLASK_URL/api/wechat/wrong-question-upload-tasks/$TASK_ID?open_id=$OPEN_ID" | python3 -m json.tool
```

Check the bridge proxy endpoint:

```bash
curl -fsS "$BRIDGE_URL/wechat/parent/wrong-question-upload-tasks/$TASK_ID?openId=$OPEN_ID" | python3 -m json.tool
```

Expected healthy result:
- Both responses contain `task.id`.
- `task.state` is one of `pending`, `processing`, `ready`, `failed`, or `missing_record`.
- `retryable`, `record_status`, `record_missing`, and `is_stale` are present when relevant.
- A `ready` task has a visible `record_id`.
- A `failed` task includes a parent-safe error and enough maintainer detail for logs.

## 7. Wrongbook And PDF Checks

Wrongbook list through bridge:

```bash
curl -fsS "$BRIDGE_URL/wechat/parent/children/$STUDENT_ID/wrong-questions?openId=$OPEN_ID" | python3 -m json.tool
```

Wrongbook PDF metadata through bridge:

```bash
curl -fsS "$BRIDGE_URL/wechat/parent/children/$STUDENT_ID/wrong-question-library?openId=$OPEN_ID" | python3 -m json.tool
```

Expected healthy result:
- Wrongbook list returns `items` and `total`.
- Items do not claim recognition succeeded unless `recognition_status` is ready/recognized.
- PDF metadata returns `pdf_url` as `/api/wechat/student-libraries/<student_id>` and `total_items` matches the wrongbook library count.

### [MAY MUTATE PDF CACHE] Download The PDF

The PDF endpoint may rebuild a stale cached PDF before serving it.

```bash
curl -sS -D /tmp/xr-student-library-headers.txt \
  -o /tmp/xr-student-library-smoke.pdf \
  "$FLASK_URL/api/wechat/student-libraries/$STUDENT_ID"
sed -n '1,12p' /tmp/xr-student-library-headers.txt
ls -lh /tmp/xr-student-library-smoke.pdf
rm -f /tmp/xr-student-library-headers.txt /tmp/xr-student-library-smoke.pdf
```

Expected healthy result:
- Status is `200 OK`.
- `Content-Type` is `application/pdf`.
- Downloaded file is non-empty.

## If Tasks Stay Pending

1. Re-run Redis/RQ checks and confirm the queue has at least one worker.
2. Check worker logs:

```bash
tail -n 120 /home/ubuntu/.pm2/logs/xingrun-rq-worker-out.log
tail -n 120 /home/ubuntu/.pm2/logs/xingrun-rq-worker-error.log
```

3. Check the task status JSON for `is_stale: true`.
4. Do not ask parents to retry until the worker is online and new queue length drains.

### [MUTATING] Restart The Worker

```bash
pm2 restart xingrun-rq-worker
pm2 save
```

Expected healthy result: `pm2 status xingrun-rq-worker` returns `online`, and `rq info` shows the queue draining.

## If Enqueue Fails

Symptoms:
- Website `POST /api/wechat/wrong-questions` returns `502`.
- Response includes `"retryable": true`.
- The task is persisted as `failed` for inspection.

Checks:

```bash
tail -n 120 /home/ubuntu/.pm2/logs/xingrun-error.log
redis-cli -u "$XR_REDIS_URL" ping
cd "$APP_DIR"
.venv/bin/rq info --url "$XR_REDIS_URL" "$QUEUE"
```

Expected action: fix Redis/RQ connectivity first. After Redis and the worker are healthy, ask the parent to retry from the mini program; do not mark the old failed task as ready by hand.

## If Uploads Hit 413

Symptoms:
- Bridge or website returns `413`.
- Nginx access/error logs may show `client intended to send too large body`.

Checks:

```bash
grep -n "fileSize: 10 \\* 1024 \\* 1024" "$APP_DIR/miniprogram/backend/src/upload.ts"
sudo nginx -T 2>/dev/null | grep -n "client_max_body_size" || true
tail -n 120 /var/log/nginx/error.log
```

Expected action:
- If Nginx is below the bridge `10 MB` limit for upload routes, update Nginx in a controlled deploy.
- If bridge returns the 413, ask the parent to crop a smaller box or retake the image; the mini program should keep the draft for retry.
- Do not raise limits blindly without checking server memory and upload abuse risk.

## If PDF Refresh Fails

Symptoms:
- Task reaches `failed` after recognition.
- `maintainer_error_detail` mentions PDF, renderer, Chromium, or file write errors.
- Wrongbook record and original image should still be visible.

Checks:

```bash
tail -n 160 /home/ubuntu/.pm2/logs/xingrun-rq-worker-error.log
df -h "$APP_DIR" "$APP_DIR/data"
ls -lh "$APP_DIR/data/pdfs/wrong_question_libraries" | tail
```

Expected action: fix the renderer, disk, or permission issue first. The uploaded image-backed record should remain visible while the PDF is repaired.

### [MUTATING] Refresh A Student PDF After The Cause Is Fixed

```bash
curl -fsS -X POST \
  -H "X-Auth-Token: $STAFF_TOKEN" \
  "$FLASK_URL/api/wrong-question-student-libraries/$STUDENT_ID/refresh" | python3 -m json.tool
```

Expected healthy result: JSON contains `"ok": true` and `pdf_url` is `/api/wechat/student-libraries/<student_id>`.

## Local Proof

Before marking this runbook story complete locally, run:

```bash
scripts/ralph/production_upload_smoke_runbook_proof.sh
scripts/ralph/miniprogram_upload_stability_proof.sh
```

Expected healthy result: both scripts exit `0`.
