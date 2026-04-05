import unittest

import ai_processor


class AiProcessorPromptTestCase(unittest.TestCase):
    def test_plan_system_prompt_limits_formula_only_fill_ratio(self):
        self.assertIn("纯公式型填空题", ai_processor.PLAN_SYSTEM_PROMPT)
        self.assertIn("不得超过 30%", ai_processor.PLAN_SYSTEM_PROMPT)
        self.assertIn("至少 70% 的填空题", ai_processor.PLAN_SYSTEM_PROMPT)


if __name__ == "__main__":
    unittest.main()
