from __future__ import annotations

import io
import json
import os
from pathlib import Path
import sys
import uuid
import urllib.error
import urllib.parse
import urllib.request
from urllib.parse import urlparse

import ai_processor
import pdf_engine
from lesson_manager import (
    attach_student_library_pdf_path,
    create_wrong_question_asset,
    create_wrong_question_ingestion_run,
    create_wechat_wrong_question_submission,
    get_wechat_wrong_question_upload_task,
    get_wrong_question_ingestion_run,
    list_student_wrong_question_library_records,
    set_student_wrong_question_library_pdf_path,
    update_wrong_question_ingestion_run,
    update_wechat_wrong_question_upload_task,
)


BASE_DIR = Path(__file__).parent.resolve()
PDF_DIR = BASE_DIR / "data" / "pdfs"
ERASED_IMAGE_DIR = BASE_DIR / "data" / "wrong_question_erased"
DEFAULT_ERROR_CORRECTION_BACKEND = Path("/Users/xiaodi/Desktop/error_correction/backend")


def _iter_exception_chain(exc: BaseException):
    current: BaseException | None = exc
    seen: set[int] = set()
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        yield current
        current = current.__cause__ or current.__context__


def _is_retryable_upload_error(exc: BaseException) -> bool:
    retryable_names = {
        "APIConnectionError",
        "APITimeoutError",
        "ConnectError",
        "ConnectTimeout",
        "ReadError",
        "ReadTimeout",
        "TimeoutException",
    }
    for item in _iter_exception_chain(exc):
        if isinstance(item, (ConnectionError, TimeoutError)):
            return True
        if item.__class__.__name__ in retryable_names:
            return True
    return False


def _student_wrong_question_library_path(student_id: int) -> Path:
    library_dir = PDF_DIR / "wrong_question_libraries"
    library_dir.mkdir(parents=True, exist_ok=True)
    return library_dir / f"student-{student_id}.pdf"


def _rebuild_student_wrong_question_library(student_id: int) -> str:
    records = list_student_wrong_question_library_records(student_id)
    if not records:
        raise ValueError("student wrong question library has no records")
    output_path = _student_wrong_question_library_path(student_id)
    return pdf_engine.generate_student_wrong_question_library_pdf(
        student_name=str(records[0].get("student_name") or ""),
        class_name=str(records[0].get("class_display_name") or ""),
        records=records,
        output_path=str(output_path),
    )


def _refresh_student_wrong_question_library_cache(student_id: int) -> str:
    records = list_student_wrong_question_library_records(student_id)
    output_path = _student_wrong_question_library_path(student_id)
    if not records:
        output_path.unlink(missing_ok=True)
        set_student_wrong_question_library_pdf_path(student_id, "")
        return ""

    pdf_path = str(_rebuild_student_wrong_question_library(student_id) or "").strip()
    set_student_wrong_question_library_pdf_path(student_id, pdf_path)
    return pdf_path


def _guess_upload_filename(file_url: str) -> str:
    path = urlparse(str(file_url or "").strip()).path
    filename = Path(path).name.strip()
    return filename


def _load_run_metadata(run: dict | None) -> dict:
    if not isinstance(run, dict):
        return {}
    raw = str(run.get("metadata_json") or "").strip()
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _update_ingestion_run_with_metadata(
    run_id: str,
    *,
    status: str,
    current_step: str = "",
    error_message: str = "",
    **extra_metadata,
) -> dict | None:
    existing = get_wrong_question_ingestion_run(run_id)
    metadata = _load_run_metadata(existing)
    metadata.update({key: value for key, value in extra_metadata.items() if value is not None})
    return update_wrong_question_ingestion_run(
        run_id,
        status=status,
        current_step=current_step,
        error_message=error_message,
        metadata_json=metadata,
    )


def _fetch_upload_image_bytes(image_url: str) -> bytes:
    normalized_image_url = str(image_url or "").strip()
    if not normalized_image_url:
        raise ValueError("image_url is required for erasure")
    parsed_url = urllib.parse.urlparse(normalized_image_url)
    if parsed_url.scheme in {"", "file"}:
        local_path = Path(urllib.request.url2pathname(parsed_url.path if parsed_url.scheme == "file" else normalized_image_url))
        return local_path.read_bytes()
    with urllib.request.urlopen(normalized_image_url, timeout=10) as response:
        return response.read()


def _erase_wrong_question_image_bytes(image_bytes: bytes) -> bytes:
    backend_path = Path(os.environ.get("XR_ERROR_CORRECTION_BACKEND_PATH") or DEFAULT_ERROR_CORRECTION_BACKEND)
    if not backend_path.exists():
        raise FileNotFoundError(f"error_correction backend not found: {backend_path}")
    sys.path.insert(0, str(backend_path))
    try:
        from models.inference import InferenceEngine

        result_image = InferenceEngine().run(image_bytes)
    finally:
        try:
            sys.path.remove(str(backend_path))
        except ValueError:
            pass
    output = io.BytesIO()
    result_image.save(output, format="PNG")
    return output.getvalue()


def _try_create_erased_wrong_question_asset(ingestion_run_id: str, image_url: str) -> None:
    normalized_run_id = str(ingestion_run_id or "").strip()
    if not normalized_run_id:
        return
    try:
        source_bytes = _fetch_upload_image_bytes(image_url)
        erased_bytes = _erase_wrong_question_image_bytes(source_bytes)
        if not erased_bytes:
            raise RuntimeError("erasure returned empty image")
        ERASED_IMAGE_DIR.mkdir(parents=True, exist_ok=True)
        erased_path = ERASED_IMAGE_DIR / f"erased-{normalized_run_id}-{uuid.uuid4().hex[:8]}.png"
        erased_path.write_bytes(erased_bytes)
        asset = create_wrong_question_asset(
            ingestion_run_id=normalized_run_id,
            asset_role="erased_question_image",
            storage_path=str(erased_path),
            file_url=str(erased_path),
            mime_type="image/png",
            metadata_json={
                "source": "error_correction_ensexam",
                "original_image_url": str(image_url or "").strip(),
            },
        )
        _update_ingestion_run_with_metadata(
            normalized_run_id,
            status="processing",
            current_step="erased",
            erasure_status="succeeded",
            erased_image_asset_id=int(asset.get("id") or 0),
        )
    except Exception as exc:
        _update_ingestion_run_with_metadata(
            normalized_run_id,
            status="processing",
            current_step="erasure_unavailable",
            erasure_status="failed",
            erasure_error=str(exc),
        )


def _ensure_upload_task_ingestion_run(task: dict) -> dict:
    existing_run_id = str(task.get("ingestion_run_id") or "").strip()
    existing_run = get_wrong_question_ingestion_run(existing_run_id) if existing_run_id else None
    if existing_run:
        return existing_run

    run = create_wrong_question_ingestion_run(
        organization_id=int(task.get("organization_id") or 0),
        source="wechat_mp",
        class_id=int(task.get("class_id") or 0),
        student_id=int(task.get("student_id") or 0),
        teacher_user_id=int(task.get("teacher_user_id") or 0),
        parent_wechat_account_id=int(task.get("parent_wechat_account_id") or 0),
        status="processing",
        current_step="queued_for_recognition",
        original_filename=_guess_upload_filename(str(task.get("image_url") or "")),
        metadata_json={
            "wechat_upload_task_id": int(task.get("id") or 0),
            "topic_category": str(task.get("topic_category") or ""),
            "child_reason_input_mode": str(task.get("child_reason_input_mode") or "text"),
        },
    )
    create_wrong_question_asset(
        ingestion_run_id=run["id"],
        asset_role="original_upload",
        file_url=str(task.get("image_url") or ""),
        metadata_json={"source": "wechat_mp"},
    )
    child_reason_audio_url = str(task.get("child_reason_audio_url") or "").strip()
    if child_reason_audio_url:
        create_wrong_question_asset(
            ingestion_run_id=run["id"],
            asset_role="reason_audio",
            file_url=child_reason_audio_url,
            metadata_json={"source": "wechat_mp"},
        )
    update_wechat_wrong_question_upload_task(
        int(task["id"]),
        status=str(task.get("status") or "pending"),
        ingestion_run_id=run["id"],
        record_id=str(task.get("record_id") or ""),
        error_message=str(task.get("error_message") or ""),
        retryable=bool(task.get("retryable")),
    )
    return run


def process_wechat_wrong_question_upload_task(task_id: int) -> dict:
    task = get_wechat_wrong_question_upload_task(int(task_id))
    if not task:
        raise LookupError("wrong question upload task not found")

    task = update_wechat_wrong_question_upload_task(task["id"], status="processing", retryable=False) or task
    ingestion_run = _ensure_upload_task_ingestion_run(task)
    ingestion_run_id = str(ingestion_run.get("id") or "")
    created_record_id = ""
    reason_text = str(task.get("child_raw_reason_text") or "").strip()
    display_text = ""
    recognition = {}
    try:
        _try_create_erased_wrong_question_asset(ingestion_run_id, str(task.get("image_url") or ""))

        if task.get("child_reason_input_mode") == "voice" and task.get("child_reason_audio_url"):
            transcription = ai_processor.transcribe_child_reason_audio(task["child_reason_audio_url"])
            reason_text = str(transcription.get("transcript_text") or "").strip()

        recognition = ai_processor.recognize_wrong_question_image(task["image_url"])
        if reason_text:
            classification = ai_processor.classify_wrong_question_reason(
                reason_text,
                question_text=str(recognition.get("question_text") or ""),
            )
        else:
            classification = {
                "display_text": "待补充｜孩子暂未填写错因",
                "primary_error_type": "待补充",
                "secondary_error_summary": "孩子暂未填写错因",
            }
        display_text = str(classification.get("display_text") or reason_text).strip()
        stored_reason_text = reason_text or display_text

        record = create_wechat_wrong_question_submission(
            binding_id=int(task["binding_id"]),
            image_url=str(task["image_url"] or ""),
            child_raw_reason_text=stored_reason_text,
            child_reason_transcript=reason_text,
            child_reason_input_mode=str(task["child_reason_input_mode"] or "text"),
            primary_error_type=str(classification.get("primary_error_type") or ""),
            secondary_error_summary=str(classification.get("secondary_error_summary") or ""),
            child_reason_core_issue=str(classification.get("core_issue") or display_text),
            child_reason_key_omission=str(classification.get("key_omission") or ""),
            child_reason_next_step=str(classification.get("next_step") or ""),
            topic_category=str(task.get("topic_category") or ""),
            recognition_status="recognized",
            ingestion_run_id=ingestion_run_id,
            is_geometry=bool(recognition.get("is_geometry")),
            image_rotation_degrees=int(recognition.get("image_rotation_degrees") or 0),
            question_text=str(recognition.get("question_text") or ""),
            question_text_source="ai",
            diagram_type=str(recognition.get("diagram_type") or ""),
            diagram_spec=recognition.get("diagram_spec") if isinstance(recognition.get("diagram_spec"), dict) else None,
        )
        created_record_id = str(record.get("id") or "")
        pdf_path = _refresh_student_wrong_question_library_cache(int(task["student_id"]))
        record = attach_student_library_pdf_path(record["id"], pdf_path) or record
        _update_ingestion_run_with_metadata(
            ingestion_run_id,
            status="archived",
            current_step="archived",
            record_id=str(record.get("id") or ""),
            recognition_status="recognized",
            is_geometry=bool(recognition.get("is_geometry")),
            image_rotation_degrees=int(recognition.get("image_rotation_degrees") or 0),
            question_text_present=bool(str(recognition.get("question_text") or "").strip()),
            student_library_pdf_path=pdf_path,
        )
        return update_wechat_wrong_question_upload_task(
            task["id"],
            status="ready",
            ingestion_run_id=ingestion_run_id,
            record_id=str(record.get("id") or ""),
            error_message="",
            retryable=False,
        ) or {}
    except Exception as exc:
        _update_ingestion_run_with_metadata(
            ingestion_run_id,
            status="failed",
            current_step="failed",
            error_message=str(exc),
            recognition_status="failed" if created_record_id else "processing_failed",
            record_id=created_record_id or "",
        )
        if not created_record_id and _is_retryable_upload_error(exc):
            return update_wechat_wrong_question_upload_task(
                task["id"],
                status="failed",
                ingestion_run_id=ingestion_run_id,
                record_id="",
                error_message=str(exc),
                retryable=True,
            ) or {}

        if not created_record_id:
            try:
                failed_record = create_wechat_wrong_question_submission(
                    binding_id=int(task["binding_id"]),
                    image_url=str(task["image_url"] or ""),
                    child_raw_reason_text=display_text or reason_text,
                    child_reason_transcript=reason_text,
                    child_reason_input_mode=str(task["child_reason_input_mode"] or "text"),
                    primary_error_type="待补充",
                    secondary_error_summary="题目识别失败，等待老师查看原图后补充。",
                    child_reason_core_issue=display_text or reason_text,
                    child_reason_key_omission="题目识别失败，暂时无法结合题目确认关键遗漏。",
                    child_reason_next_step="请老师先查看原图和孩子说明，再补充可执行的订正步骤。",
                    topic_category=str(task.get("topic_category") or ""),
                    recognition_status="failed",
                    ingestion_run_id=ingestion_run_id,
                    is_geometry=bool(recognition.get("is_geometry")) if isinstance(recognition, dict) else False,
                    image_rotation_degrees=int(recognition.get("image_rotation_degrees") or 0) if isinstance(recognition, dict) else 0,
                    question_text=str(recognition.get("question_text") or "") if isinstance(recognition, dict) else "",
                    question_text_source="ai",
                    diagram_type=str(recognition.get("diagram_type") or "") if isinstance(recognition, dict) else "",
                    diagram_spec=recognition.get("diagram_spec") if isinstance(recognition, dict) and isinstance(recognition.get("diagram_spec"), dict) else None,
                    recognition_error=str(exc),
                )
                created_record_id = str(failed_record.get("id") or "")
            except Exception:
                created_record_id = ""
        _update_ingestion_run_with_metadata(
            ingestion_run_id,
            status="failed",
            current_step="failed",
            error_message=str(exc),
            recognition_status="failed",
            record_id=created_record_id or "",
        )
        return update_wechat_wrong_question_upload_task(
            task["id"],
            status="failed",
            ingestion_run_id=ingestion_run_id,
            record_id=created_record_id,
            error_message=str(exc),
            retryable=False,
        ) or {}
