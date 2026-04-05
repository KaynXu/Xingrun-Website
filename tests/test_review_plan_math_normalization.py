import unittest

from review_plan_templates.generate_review_pdfs import normalize_portable_text


class ReviewPlanMathNormalizationTestCase(unittest.TestCase):
    def test_normalize_portable_text_converts_inline_latex_formula(self):
        text = r"$(a^{2}+b^{2})(c^{2}+d^{2})\geq (ac + bd)^{2}$"

        self.assertEqual(
            normalize_portable_text(text),
            "(a²+b²)(c²+d²)≥(ac + bd)²",
        )

    def test_normalize_portable_text_keeps_surrounding_sentence(self):
        text = r"柯西不等式可写成 $(a^{2}+b^{2})(c^{2}+d^{2})\geq (ac + bd)^{2}$。"

        self.assertEqual(
            normalize_portable_text(text),
            "柯西不等式可写成 (a²+b²)(c²+d²)≥(ac + bd)²。",
        )


if __name__ == "__main__":
    unittest.main()
