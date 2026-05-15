# WeChat Wrong Question Image Orientation Design

## Current Problem

Parents may upload a wrong-question photo whose readable page direction is sideways. The mini program already has a manual rotate tool, but uploaded tasks can still reach the backend with the original sideways orientation. For geometry records, the PDF keeps the original image, so the student wrong-question library can also show the page sideways.

## Goal

Let the AI recognition step decide the correct reading orientation for each uploaded wrong-question image, then use that decision when storing the record and rendering geometry images in the student wrong-question library PDF.

## Approach

The vision recognition JSON will add `image_rotation_degrees`, limited to `0`, `90`, `180`, or `270`. The value means the clockwise rotation needed to make the original uploaded image readable. The prompt will explicitly tell the model to first orient the image by printed text and page layout before extracting the question or marking it as geometry.

`ai_processor._normalize_wrong_question_recognition_result()` will normalize invalid or missing values to `0`, so old model responses remain compatible. `wrong_question_upload_worker.process_wechat_wrong_question_upload_task()` will pass the normalized value into `create_wechat_wrong_question_submission()`.

`lesson_manager` will persist the rotation on `wrong_question_submissions` as an integer column. Student wrong-question library record queries will expose the value as `image_rotation_degrees`.

`pdf_engine` will rotate fetched geometry images by the stored clockwise degrees before embedding them in the browser-rendered PDF payload and the ReportLab fallback image card. Non-geometry PDF entries remain text-only.

## Testing

Add focused unit coverage for:

- recognition normalization keeps valid `image_rotation_degrees` and falls back to `0` for invalid values.
- upload worker stores the AI rotation value on the created wrong-question record.
- PDF image fetching returns rotated image bytes when `image_rotation_degrees` is present.

Final proof should run through a temporary script and include the targeted backend tests, Python compile, and `git diff --check`.

## Out Of Scope

- No mini program UI changes.
- No manual teacher rotation UI.
- No migration of existing sideways records.
- No change to non-geometry question extraction beyond the prompt requiring correct reading orientation first.
