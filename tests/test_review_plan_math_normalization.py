import unittest

from review_plan_templates.generate_review_pdfs import localize_paragraph_text, normalize_portable_text


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

    def test_normalize_portable_text_supports_block_dollar_and_double_escaped_commands(self):
        text = r"$$\\frac{a^2+b^2}{c^2+d^2}$$"

        self.assertEqual(
            normalize_portable_text(text),
            "(a²+b²)/(c²+d²)",
        )

    def test_normalize_portable_text_supports_double_escaped_bracket_math(self):
        text = r"\\[x^2+y^2\\geq 1\\]"

        self.assertEqual(
            normalize_portable_text(text),
            "x²+y²≥1",
        )

    def test_normalize_portable_text_repairs_json_consumed_latex_commands(self):
        text = (
            "The function $f$ is continuous at $x = 3$.\n"
            "$$f(3) = 1 + \text{lim}_{x \to 3^-} f(x) + \frac{1}{2}$$\n"
            "(C) $f(3) \neq \text{lim}_{x \to 3} f(x)$"
        )

        normalized = normalize_portable_text(text)

        self.assertNotIn("\t", normalized)
        self.assertNotIn("ext{", normalized)
        self.assertIn("lim(x → 3⁻)", normalized)
        self.assertIn("f(3)≠lim(x → 3)", normalized)

    def test_normalize_portable_text_keeps_math_subscripts_pdf_font_safe(self):
        self.assertEqual(normalize_portable_text(r"$\log_2 x$"), "log_2 x")
        self.assertEqual(normalize_portable_text(r"$a_n$"), "a_n")
        self.assertEqual(normalize_portable_text(r"$x_{12}$"), "x_12")

    def test_normalize_portable_text_normalizes_bare_latex_fragments_like_wrong_question_text(self):
        text = (
            "已知函数 f(x)=(x-1)e^{-ax}（a \\in \\mathbbR），e=2.71828\\ldots，"
            "且 a<m<a\\frac{a+e}{ae}-1。"
        )

        normalized = normalize_portable_text(text)

        self.assertNotIn("\\in", normalized)
        self.assertNotIn("\\mathbb", normalized)
        self.assertNotIn("\\ldots", normalized)
        self.assertNotIn("\\frac", normalized)
        self.assertIn("e⁻ᵃˣ", normalized)
        self.assertIn("∈", normalized)
        self.assertIn("ℝ", normalized)
        self.assertIn("2.71828...", normalized)
        self.assertIn("(a+e)/(ae)", normalized)

    def test_normalize_portable_text_keeps_underlined_latex_placeholders_printable(self):
        text = (
            r"$\frac{a^2}{x}+\frac{b^2}{y} "
            r"\ge \frac{(\underline{\hspace{1cm}})^2}{x+y}$"
        )

        normalized = normalize_portable_text(text)

        self.assertNotIn("frac(", normalized)
        self.assertNotIn("underlinehspace", normalized)
        self.assertIn("(a²)/(x)+(b²)/(y)≥", normalized)
        self.assertIn("______", normalized)
        self.assertIn("(x+y)", normalized)

    def test_normalize_portable_text_renders_cases_as_printable_conditions(self):
        text = r"$\begin{cases} 2x+1 > x+3 \\ 2x+1 > -5 \\ x+3 > -5 \end{cases}$"

        normalized = normalize_portable_text(text)

        self.assertNotIn("begincases", normalized)
        self.assertNotIn("endcases", normalized)
        self.assertIn("2x+1>x+3", normalized)
        self.assertIn("2x+1>-5", normalized)
        self.assertIn("x+3>-5", normalized)

    def test_localize_paragraph_text_does_not_strip_math_after_semicolon(self):
        text = r"B. $\begin{cases} 2x+1 > x+3 \\ 2x+1 > -5 \\ x+3 > -5 \end{cases}$"

        localized = localize_paragraph_text(text, True)

        self.assertIn("2x+1&gt;x+3", localized)
        self.assertIn("2x+1&gt;-5", localized)
        self.assertIn("x+3&gt;-5", localized)


if __name__ == "__main__":
    unittest.main()
