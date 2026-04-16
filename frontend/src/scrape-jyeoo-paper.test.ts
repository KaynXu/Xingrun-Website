import test from 'node:test';
import assert from 'node:assert/strict';

import {
  mathJyeHtmlToLatex,
  parseJyeooExamHtml,
} from '../scripts/scrapeJyeooPaper.mjs';

test('mathJyeHtmlToLatex converts fractions and vectors from MathJye markup', () => {
  const latex = mathJyeHtmlToLatex(
    '<div class="MathJye" mathtag="math"><div class="mrow"><div class="mfrac"><div class="fracZi"><div class="math-letter">1</div></div><div class="fracLine"><div class="mnormal"></div></div><div class="fracMu"><div class="math-letter">4</div></div></div><div class="mover"><div class="over overflowH"><div class="stretchArrow stretchArrowR stretchArrowNormal"></div></div><div class="base"><div class="baseCont"><div class="math-letter math-letter-i">AB</div></div></div></div></div></div>',
  );

  assert.equal(latex, '\\frac{1}{4}\\overrightarrow{AB}');
});

test('parseJyeooExamHtml extracts question records, image urls, and latex segments', () => {
  const html = `
    <!doctype html>
    <html lang="zh-CN">
      <head>
        <title>示例试卷 - 菁优网</title>
      </head>
      <body>
        <h3 class="ques-type fbold">一、选择题</h3>
        <ul class="ques-list list-box">
          <li class="QUES_LI">
            <section class="quesborder" s="math2">
              <div class="pt1">
                <h2>
                  <img alt="" src="/quiz/images/svg/demo.png" style="vertical-align:middle;FLOAT:right;" />
                  <span class="qseq">19．</span>
                  如图所示，<div class="MathJye" mathtag="math"><div class="mrow"><div class="mover"><div class="over overflowH"><div class="stretchArrow stretchArrowR stretchArrowNormal"></div></div><div class="base"><div class="baseCont"><div class="math-letter math-letter-i">AB</div></div></div></div><div class="mo">=</div><div class="math-letter">4</div></div></div>。
                </h2>
              </div>
              <div class="pt2">
                <table class="ques quesborder">
                  <tr>
                    <td class="selectoption"><label>A．3</label></td>
                    <td class="selectoption"><label>B．4</label></td>
                  </tr>
                </table>
              </div>
            </section>
          </li>
        </ul>
      </body>
    </html>
  `;
  const result = parseJyeooExamHtml(html, 'https://www.jyeoo.com/pp/demo');

  assert.equal(result.paper_title, '示例试卷');
  assert.equal(result.question_count, 1);
  assert.equal(result.questions[0]?.question_no, 19);
  assert.equal(result.questions[0]?.question_type, '一、选择题');
  assert.deepEqual(result.questions[0]?.image_urls, ['https://www.jyeoo.com/quiz/images/svg/demo.png']);
  assert.equal(result.questions[0]?.options[0]?.label, 'A');
  assert.equal(result.questions[0]?.options[0]?.text_plain, '3');
  assert.equal(result.questions[0]?.latex_segments[0]?.latex, '\\overrightarrow{AB} = 4');
  assert.match(result.questions[0]?.text_plain ?? '', /如图所示/);
});
