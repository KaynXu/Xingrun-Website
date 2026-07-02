import unittest

from reportlab.graphics.shapes import Drawing
from reportlab.platypus import Image as ReportLabImage
from reportlab.platypus import Flowable

from review_plan_templates.generate_review_pdfs import (
    _mathjax_renderer_available,
    build_styles,
    localize_paragraph_text,
    normalize_portable_text,
    normalize_portable_text_preserving_latex,
    register_fonts,
    render_latex_formula_flowable,
    rich_text_flowables,
)


def _flowable_width(flowable):
    return getattr(flowable, "drawWidth", getattr(flowable, "width", 0))


def _flowable_height(flowable):
    return getattr(flowable, "drawHeight", getattr(flowable, "height", 0))


def _is_formula_flowable(flowable):
    return isinstance(flowable, (Drawing, ReportLabImage))


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

    def test_normalize_portable_text_normalizes_bare_geometry_tokens(self):
        text = "在triangle ABC中，angle BAC=120^circ，triangle ADC cong triangle EDB。"

        normalized = normalize_portable_text(text)

        self.assertEqual(normalized, "在△ABC中，∠BAC=120°，△ADC ≌ △EDB。")
        self.assertNotIn("triangle", normalized)
        self.assertNotIn("angle", normalized)
        self.assertNotIn("^circ", normalized)
        self.assertNotIn("cong", normalized)

    def test_normalize_portable_text_normalizes_bare_greek_trig_fragments(self):
        question = "已知alpha和beta为锐角，且tanalpha=(1)/(2)，tanbeta=(1)/(3)，则alpha+beta等于？"

        normalized_question = normalize_portable_text_preserving_latex(question)
        normalized_answer = normalize_portable_text_preserving_latex("alpha+beta=45°")

        self.assertEqual(normalized_question, "已知α和β为锐角，且tanα=1/2，tanβ=1/3，则α+β等于？")
        self.assertEqual(normalized_answer, "α+β=45°")
        self.assertNotIn("tanalpha", normalized_question)
        self.assertNotIn("tanbeta", normalized_question)
        self.assertNotIn("(1)/(2)", normalized_question)
        self.assertEqual(normalize_portable_text("alphabet"), "alphabet")

    def test_render_latex_formula_flowable_renders_fraction_as_image(self):
        flowable = render_latex_formula_flowable(
            r"\frac{a^2}{x}+\frac{b^2}{y}\ge \frac{(a+b)^2}{x+y}",
            max_width=120,
        )

        self.assertIsInstance(flowable, Flowable)
        self.assertLessEqual(_flowable_width(flowable), 120)
        self.assertGreater(_flowable_height(flowable), 0)

    def test_render_latex_formula_flowable_uses_mathjax_when_available(self):
        if not _mathjax_renderer_available():
            self.skipTest("MathJax frontend dependencies are not installed")

        flowable = render_latex_formula_flowable(
            r"\begin{aligned} \tan\alpha&=\frac{1}{2}\\ \alpha+\beta&=45^\circ \end{aligned}",
            max_width=180,
        )

        self.assertIsInstance(flowable, Drawing)
        self.assertLessEqual(_flowable_width(flowable), 180)
        self.assertGreater(_flowable_height(flowable), 0)

    def test_render_latex_formula_flowable_respects_requested_font_size(self):
        latex = r"\frac{a^2}{x}+\frac{b^2}{y}\ge \frac{(a+b)^2}{x+y}"

        body_formula = render_latex_formula_flowable(latex, max_width=180, font_size=10.3)
        small_formula = render_latex_formula_flowable(latex, max_width=180, font_size=8.6)

        self.assertIsInstance(body_formula, Flowable)
        self.assertIsInstance(small_formula, Flowable)
        self.assertLess(_flowable_height(small_formula), _flowable_height(body_formula))
        self.assertLess(_flowable_width(small_formula), _flowable_width(body_formula))

    def test_rich_text_flowables_embeds_standalone_fraction_formula_image(self):
        register_fonts()
        styles = build_styles()

        flowables = rich_text_flowables(
            r"$\frac{a^2}{x}+\frac{b^2}{y}\ge \frac{(a+b)^2}{x+y}$",
            styles["body"],
            True,
        )

        self.assertTrue(any(_is_formula_flowable(flowable) for flowable in flowables))

    def test_rich_text_flowables_keeps_inline_fraction_formula_compact(self):
        register_fonts()
        styles = build_styles()

        flowables = rich_text_flowables(
            r"全方和不等式：$\frac{a^2}{x}+\frac{b^2}{y}\ge \frac{(a+b)^2}{x+y}$ 的结构识别",
            styles["body"],
            True,
        )

        self.assertEqual(len(flowables), 1)
        self.assertFalse(any(_is_formula_flowable(flowable) for flowable in flowables))
        self.assertIn("全方和不等式", flowables[0].getPlainText())

    def test_rich_text_flowables_formula_size_follows_paragraph_style(self):
        register_fonts()
        styles = build_styles()
        text = r"$\frac{a^2}{x}+\frac{b^2}{y}\ge \frac{(a+b)^2}{x+y}$"

        body_images = [
            flowable
            for flowable in rich_text_flowables(text, styles["body"], True)
            if _is_formula_flowable(flowable)
        ]
        small_images = [
            flowable
            for flowable in rich_text_flowables(text, styles["small"], True)
            if _is_formula_flowable(flowable)
        ]

        self.assertTrue(body_images)
        self.assertTrue(small_images)
        self.assertLess(_flowable_height(small_images[0]), _flowable_height(body_images[0]))

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

    def test_normalize_portable_text_cleans_escaped_blank_underscores(self):
        normalized = normalize_portable_text(r"写出比例 5: \_\_\_\_:\_\_\_\_。")

        self.assertEqual(normalized, "写出比例 5:____:____。")
        self.assertNotIn("\\_", normalized)

    def test_normalize_portable_text_collapses_option_formula_newline(self):
        normalized = normalize_portable_text("A.\n\\\\sqrt{3}")

        self.assertEqual(normalized, "A. √(3)")
        self.assertNotIn("\n", normalized)
        self.assertNotIn("\\√", normalized)

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
