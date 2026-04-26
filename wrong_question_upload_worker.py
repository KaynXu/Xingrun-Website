from pathlib import Path

import ai_processor
import pdf_engine
from lesson_manager import (
    attach_student_library_pdf_path,
    create_wechat_wrong_question_submission,
    delete_wechat_wrong_question_submission,
    get_wechat_wrong_question_upload_task,
    list_student_wrong_question_library_records,
    set_student_wrong_question_library_pdf_path,
    update_wechat_wrong_question_upload_task,
)


BASE_DIR = Path(__file__).parent.resolve()
PDF_DIR = BASE_DIR / "data" / "pdfs"


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


def process_wechat_wrong_question_upload_task(task_id: int) -> dict:
    task = get_wechat_wrong_question_upload_task(int(task_id))
    if not task:
        raise LookupError("wrong question upload task not found")

    update_wechat_wrong_question_upload_task(task["id"], status="processing")
    created_record_id = ""
    try:
        reason_text = str(task.get("child_raw_reason_text") or "").strip()
        if task.get("child_reason_input_mode") == "voice" and task.get("child_reason_audio_url"):
            transcription = ai_processor.transcribe_child_reason_audio(task["child_reason_audio_url"])
            reason_text = str(transcription.get("transcript_text") or "").strip()
        if not reason_text:
            raise ValueError("child reason text is required")

        recognition = ai_processor.recognize_wrong_question_image(task["image_url"])
        classification = ai_processor.classify_wrong_question_reason(
            reason_text,
            question_text=str(recognition.get("question_text") or ""),
        )
        display_text = str(classification.get("display_text") or reason_text).strip()

        record = create_wechat_wrong_question_submission(
            binding_id=int(task["binding_id"]),
            image_url=str(task["image_url"] or ""),
            child_raw_reason_text=display_text,
            child_reason_input_mode=str(task["child_reason_input_mode"] or "text"),
            primary_error_type=str(classification.get("primary_error_type") or ""),
            secondary_error_summary=str(classification.get("secondary_error_summary") or ""),
            recognition_status="recognized",
            is_geometry=bool(recognition.get("is_geometry")),
            question_text=str(recognition.get("question_text") or ""),
            question_text_source="ai",
        )
        created_record_id = str(record.get("id") or "")
        pdf_path = _refresh_student_wrong_question_library_cache(int(task["student_id"]))
        record = attach_student_library_pdf_path(record["id"], pdf_path) or record
        return update_wechat_wrong_question_upload_task(
            task["id"],
            status="ready",
            record_id=str(record.get("id") or ""),
            error_message="",
        ) or {}
    except Exception as exc:
        if created_record_id:
            delete_wechat_wrong_question_submission(created_record_id)
        return update_wechat_wrong_question_upload_task(
            task["id"],
            status="failed",
            record_id="",
            error_message=str(exc),
        ) or {}
