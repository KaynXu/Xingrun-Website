import os

from redis import Redis
from rq import Queue

from wrong_question_upload_worker import process_wechat_wrong_question_upload_task


def _redis_connection() -> Redis:
    return Redis.from_url(os.environ.get("XR_REDIS_URL", "redis://127.0.0.1:6379/0"))


def _queue() -> Queue:
    return Queue(
        os.environ.get("XR_WRONG_QUESTION_UPLOAD_QUEUE", "wrong_question_uploads"),
        connection=_redis_connection(),
    )


def enqueue_wechat_wrong_question_upload_task(task_id: int):
    return _queue().enqueue(process_wechat_wrong_question_upload_task, int(task_id))
