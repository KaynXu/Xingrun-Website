import unittest

from class_commentary_graph_jobs import (
    _extract_with_validation_correction,
    _strict_candidates,
)

FEEDBACK = "小王今天计算稳定，需要注意单位。"

GOOD_PAYLOAD = {
    "schema_version": "student_learning_event.v1",
    "items": [
        {
            "knowledge_point_key": None,
            "unmapped_candidate": "计算稳定性",
            "observed_state": "secure",
            "reported_trend": "stable",
            "evidence_quote": "小王今天计算稳定",
            "teaching_methods": [],
            "next_steps": [],
            "teaching_method_causal_supported": False,
            "teaching_method_causal_evidence": [],
        }
    ],
}

BAD_PAYLOAD = {
    "schema_version": "student_learning_event.v1",
    "items": [
        {
            "knowledge_point_key": None,
            "unmapped_candidate": "计算稳定性",
            "observed_state": "secure",
            "reported_trend": "stable",
            "evidence_quote": "计算非常稳定",
            "teaching_methods": [],
            "next_steps": [],
            "teaching_method_causal_supported": False,
            "teaching_method_causal_evidence": [],
        }
    ],
}


class ValidationCorrectionTest(unittest.TestCase):
    def test_valid_payload_passes_without_correction(self):
        calls = []

        def extract(input, config):
            calls.append(input)
            return GOOD_PAYLOAD

        candidates, result, usage = _extract_with_validation_correction(
            extract,
            {"feedback_text": FEEDBACK, "subject_key": "math", "registry": []},
            {},
            feedback_text=FEEDBACK,
        )
        self.assertEqual(len(calls), 1)
        self.assertEqual(candidates[0]["evidence_quote"], "小王今天计算稳定")
        self.assertIn("evidence_start_offset", candidates[0])

    def test_validation_failure_triggers_one_correction_retry(self):
        calls = []

        def extract(input, config):
            calls.append(dict(input))
            if len(calls) == 1:
                return BAD_PAYLOAD
            return GOOD_PAYLOAD

        candidates, result, usage = _extract_with_validation_correction(
            extract,
            {"feedback_text": FEEDBACK, "subject_key": "math", "registry": []},
            {},
            feedback_text=FEEDBACK,
        )
        self.assertEqual(len(calls), 2)
        correction = calls[1].get("correction") or {}
        self.assertIn("quote", correction.get("validation_error") or "")
        self.assertEqual(correction.get("previous_output"), BAD_PAYLOAD)
        self.assertIn("instruction", correction)
        self.assertEqual(candidates[0]["evidence_quote"], "小王今天计算稳定")

    def test_second_failure_propagates(self):
        calls = []

        def extract(input, config):
            calls.append(input)
            return BAD_PAYLOAD

        with self.assertRaises(ValueError):
            _extract_with_validation_correction(
                extract,
                {"feedback_text": FEEDBACK, "subject_key": "math", "registry": []},
                {},
                feedback_text=FEEDBACK,
            )
        self.assertEqual(len(calls), 2)

    def test_strict_candidates_still_rejects_bad_quotes(self):
        with self.assertRaises(ValueError):
            _strict_candidates(BAD_PAYLOAD, feedback_text=FEEDBACK)


if __name__ == "__main__":
    unittest.main()
