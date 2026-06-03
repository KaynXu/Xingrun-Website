import test from 'node:test';
import assert from 'node:assert/strict';

import {
  buildDocumentMarkup,
  resolveChromiumLaunchOptions,
} from '../scripts/renderWrongQuestionPracticeSheetPdf.mjs';

test('buildDocumentMarkup renders one merged writing card without extra preview labels', async () => {
  const markup = await buildDocumentMarkup({
    studentName: 'Alice',
    className: '六年级 1 班',
    teacherName: '平台管理员',
    title: 'Alice 错题练习',
    items: [
      {
        question_order: 1,
        wrong_question_record_id: 'wechat-1',
        is_geometry: false,
        question_text_snapshot: '计算 \\(x^2 + 1\\) 并化简：\\[\\frac{x^2+1}{2}\\]。',
        child_reason_text_snapshot: '我把乘法放到了最后',
        ai_hint: '',
        reason_blank_prompt: '小标题：为什么会漏掉关键知识点？\n这题我没做好，是因为我漏掉了 ______、没有想清 ______，相关知识点其实是 ______。',
        improvement_summary_prompt: '小标题：接下来怎么补这块知识点？\n接下来我准备先补 ______，再练 ______，做题前还要提醒自己 ______。',
      },
    ],
  });

  assert.doesNotMatch(markup, /AI 提示/);
  assert.doesNotMatch(markup, /公式预览/);
  assert.doesNotMatch(markup, /预览正常/);
  assert.doesNotMatch(markup, /小标题/);
  assert.match(markup, /这题我没做好，是因为我漏掉了/);
  assert.match(markup, /接下来我准备先补/);
  assert.match(markup, /blank-gap/);
  assert.equal((markup.match(/class="writing-card"/g) || []).length, 1);
  assert.match(markup, /redo-work-area/);
  assert.match(markup, /redo-line/);
  assert.match(markup, /原题 \/ 原图/);
  assert.match(markup, /挖空复盘/);
  assert.match(markup, /订正区/);
  assert.match(markup, /重做这题/);
  assert.doesNotMatch(markup, /可选/);
  assert.match(markup, /katex/);
  assert.doesNotMatch(markup, /\\frac/);
  assert.match(markup, /xr-latex-preview/);
});

test('buildDocumentMarkup prefers structured content for method hints, review blocks, and confirmation copy', async () => {
  const markup = await buildDocumentMarkup({
    studentName: 'Alice',
    className: '六年级 1 班',
    teacherName: '平台管理员',
    title: 'Alice 错题练习',
    items: [
      {
        question_order: 2,
        wrong_question_record_id: 'wechat-structured',
        is_geometry: false,
        question_text_snapshot: '甲乙相向而行，求相遇时间。',
        structured_content: {
          mistake_focus: '速度和时间对应关系写反',
          review_goal: '先标相遇总路程再列式',
          method_hint_lines: ['先把总路程和速度和对应起来。', '再检查时间是不是同一段。'],
          blank_review_blocks: [
            {
              title: '相遇关系补全',
              lines: ['先补出总路程和 ______ 的对应关系。'],
            },
          ],
          teacher_feedback: '可继续追问单位。',
          confirmation_reasons: ['needs_unit_check', 'teacher_review_required'],
        },
        reason_blank_prompt: '旧提示\n这题我错在 ______。',
        improvement_summary_prompt: '旧提醒\n下次我会先 ______。',
      },
    ],
  });

  assert.match(markup, /方法提醒/);
  assert.match(markup, /先把总路程和速度和对应起来。/);
  assert.match(markup, /错因定位：速度和时间对应关系写反/);
  assert.match(markup, /本次目标：先标相遇总路程再列式/);
  assert.match(markup, /相遇关系补全/);
  assert.match(markup, /老师提示/);
  assert.match(markup, /可继续追问单位。/);
  assert.match(markup, /需老师确认/);
  assert.match(markup, /needs_unit_check/);
  assert.doesNotMatch(markup, /旧提示/);
});

test('buildDocumentMarkup falls back to reflection spine when structured content is missing', async () => {
  const markup = await buildDocumentMarkup({
    studentName: 'Alice',
    className: '六年级 1 班',
    teacherName: '平台管理员',
    title: 'Alice 错题练习',
    items: [
      {
        question_order: 3,
        wrong_question_record_id: 'wechat-reflection',
        is_geometry: false,
        question_text_snapshot: '解方程 $\\frac{x-1}{2}=3$。',
        reason_blank_prompt: '先复盘这题错因\n我这题错在 ______，因为 ______。',
        improvement_summary_prompt: '再写下次提醒\n下次我会先 ______，再检查 ______。',
        question_structured_snapshot_json: {
          stem: '解方程 (x-1)/2=3',
          subject: '数学',
        },
        knowledge_tags_snapshot_json: ['一元一次方程', '去分母'],
        reflection_summary_snapshot_json: {
          schema_version: 'wrong_question_reflection_summary.v1',
          mode: 'archive_reflection',
          why_wrong: '我去分母时漏乘了右边常数',
          unknown_step: '不知道等式右边也要同乘 2',
          help_preference: '先提醒我要两边一起乘，再让我自己重做',
        },
      },
    ],
  });

  assert.match(markup, /错因定位：我去分母时漏乘了右边常数/);
  assert.match(markup, /本次目标：先提醒我要两边一起乘，再让我自己重做/);
  assert.match(markup, /知识点：一元一次方程 \/ 去分母/);
  assert.match(markup, /先回到 一元一次方程 \/ 去分母 这组知识点。/);
  assert.match(markup, /先补清：不知道等式右边也要同乘 2/);
});

test('buildDocumentMarkup normalizes literal newline escapes in question and prompt text', async () => {
  const markup = await buildDocumentMarkup({
    studentName: 'Alice',
    className: '六年级 1 班',
    teacherName: '平台管理员',
    title: 'Alice 错题练习',
    items: [
      {
        question_order: 4,
        wrong_question_record_id: 'wechat-2',
        is_geometry: false,
        question_text_snapshot: '已知函数 $f(x)=(x-1)e^x-ax$。\\n\\n(2) 若 $a > e$，证明 $f(x) \\neq 1$。',
        reason_blank_prompt: '先梳理错因\\n这道题涉及 ______ 知识点。',
        improvement_summary_prompt: '再写你的想法\\n接下来我准备先补 ______。',
      },
    ],
  });

  assert.doesNotMatch(markup, /\\n\\n\(2\)|\\n这道题|\\n接下来/);
  assert.match(markup, /\(2\) 若/);
  assert.match(markup, /这道题涉及/);
  assert.match(markup, /接下来我准备先补/);
});

test('buildDocumentMarkup splits compact multiple-choice options onto separate lines', async () => {
  const markup = await buildDocumentMarkup({
    studentName: 'Alice',
    className: '七年级 4 班',
    teacherName: '何老师',
    title: 'Alice 错题练习',
    items: [
      {
        question_order: 22,
        wrong_question_record_id: 'wechat-choice',
        is_geometry: false,
        question_text_snapshot: '22. 设 a=x-2023，b=x-2025，c=x-2024。若 a◇+b◇=16，则 c◇ 的值是（ ） A.6 B.7 C.8 D.9',
      },
    ],
  });

  assert.match(markup, /值是（ ）<br \/>A\. 6<br \/>B\. 7<br \/>C\. 8<br \/>D\. 9/);
});

test('buildDocumentMarkup keeps non-empty question blocks for bare latex and geometry practice records', async () => {
  const markup = await buildDocumentMarkup({
    studentName: 'Alice',
    className: '六年级 1 班',
    teacherName: '平台管理员',
    title: 'Alice 错题练习',
    items: [
      {
        question_order: 2,
        wrong_question_record_id: 'wechat-2',
        is_geometry: false,
        question_text_snapshot: '向量 ' + String.raw`\overrightarrow{AB}` + ' 长度为 ' + String.raw`\sqrt{16}` + '，且 $x^2+1>0$。',
      },
      {
        question_order: 3,
        wrong_question_record_id: 'wechat-3',
        is_geometry: true,
        image_data_url: 'data:image/png;base64,ZmFrZQ==',
      },
      {
        question_order: 4,
        wrong_question_record_id: 'wechat-4',
        is_geometry: true,
      },
    ],
  });

  assert.equal((markup.match(/class="question-latex-card"/g) || []).length, 1);
  assert.equal((markup.match(/class="geometry-card"/g) || []).length, 2);
  assert.match(markup, /向量 AB 长度为 √\(16\)/);
  assert.match(markup, /class="katex"/);
  assert.match(markup, /src="data:image\/png;base64,ZmFrZQ=="/);
  assert.match(markup, /图片暂时无法载入，已保留原图记录。/);
  assert.doesNotMatch(markup, /\\overrightarrow|undefined/);
});

test('buildDocumentMarkup renders generated diagram practice items with question text', async () => {
  const markup = await buildDocumentMarkup({
    studentName: 'Alice',
    className: '六年级 1 班',
    teacherName: '平台管理员',
    title: 'Alice 错题练习',
    items: [
      {
        question_order: 3,
        wrong_question_record_id: 'wechat-3',
        is_geometry: true,
        question_text_snapshot: '如图，函数 $y=x^2$ 经过原点。',
        diagram_type: 'function_plot',
        image_data_url: 'data:image/svg+xml;base64,PHN2Zz48L3N2Zz4=',
      },
    ],
  });

  assert.match(markup, /函数/);
  assert.match(markup, /class="katex"/);
  assert.match(markup, /生成图像/);
  assert.match(markup, /src="data:image\/svg\+xml;base64,PHN2Zz48L3N2Zz4="/);
  assert.doesNotMatch(markup, /图片暂时无法载入/);
});

test('buildDocumentMarkup renders scheduled answer math through latex preview', async () => {
  const markup = await buildDocumentMarkup({
    studentName: 'Alice',
    className: '六年级 1 班',
    teacherName: '平台管理员',
    title: 'Alice 一周错题练习',
    schedule: [
      {
        dayIndex: 1,
        date: '2026-05-20',
        items: [
          {
            practiceItemId: 'variant-1',
            itemType: 'variant',
            question_order: 1,
            is_geometry: false,
            question_text_snapshot: '解方程 $x+1=3$。',
          },
        ],
      },
    ],
    answerItems: [
      {
        practiceItemId: 'variant-1',
        answer: '$x=2$',
        keySteps: ['两边同时减去 $1$'],
        pitfallReminder: '移项后要变号。',
      },
    ],
  });

  const answerSection = markup.slice(markup.indexOf('答案与关键步骤'));
  assert.match(answerSection, /class="katex"/);
  assert.doesNotMatch(answerSection, /\$x=2\$/);
});

test('buildDocumentMarkup keeps scheduled practice pages in the final four-area order', async () => {
  const markup = await buildDocumentMarkup({
    studentName: 'Alice',
    className: '六年级 1 班',
    teacherName: '平台管理员',
    title: 'Alice 一周错题练习',
    schedule: [
      {
        dayIndex: 1,
        date: '2026-05-20',
        items: [
          {
            practiceItemId: 'real-1',
            itemType: 'real',
            question_order: 1,
            is_geometry: false,
            question_text_snapshot: '解方程 $x+1=3$。',
            reason_blank_prompt: '先复盘这题错因\n我这题错在 ______，重做前要先检查 ______。',
            improvement_summary_prompt: '再写下次提醒\n下次看到同类题，先 ______ 再列式。',
          },
        ],
      },
    ],
    answerItems: [],
  });

  const sourceIndex = markup.indexOf('原题 / 原图');
  const questionIndex = markup.indexOf('解方程');
  const reviewIndex = markup.indexOf('挖空复盘');
  const reasonIndex = markup.indexOf('我这题错在');
  const correctionIndex = markup.indexOf('订正区');
  const redoIndex = markup.indexOf('重做原题');

  assert.ok(sourceIndex > -1);
  assert.ok(questionIndex > sourceIndex);
  assert.ok(reviewIndex > -1);
  assert.ok(reasonIndex > reviewIndex);
  assert.ok(correctionIndex > reasonIndex);
  assert.ok(redoIndex > correctionIndex);
  assert.match(markup, /blank-gap/);
});

test('buildDocumentMarkup renders latex inside scheduled error-review blanks', async () => {
  const markup = await buildDocumentMarkup({
    studentName: 'Alice',
    className: '六年级 1 班',
    teacherName: '平台管理员',
    title: 'Alice 一周错题练习',
    schedule: [
      {
        dayIndex: 2,
        date: '2026-05-21',
        items: [
          {
            practiceItemId: 'real-2',
            itemType: 'real',
            question_order: 2,
            is_geometry: false,
            question_text_snapshot: '求第三个内角。',
            reason_blank_prompt: '先复盘错因\n第三个角要用 $180^\\circ$ 减去两个已知角，而不是直接写 ______。',
            improvement_summary_prompt: '下次提醒\n列式时先写 $180^\\circ-40^\\circ-65^\\circ$，再计算。',
          },
        ],
      },
    ],
    answerItems: [],
  });

  const reviewSection = markup.slice(markup.indexOf('挖空复盘'), markup.indexOf('订正区'));
  assert.match(reviewSection, /class="katex"/);
  assert.doesNotMatch(reviewSection, /\$180\^\\circ/);
  assert.match(reviewSection, /blank-gap/);
});

test('resolveChromiumLaunchOptions adds hardened chromium flags on linux', async () => {
  const launchOptions = await resolveChromiumLaunchOptions({
    env: {},
    platform: 'linux',
    pathExists: async (candidate) => candidate === '/snap/bin/chromium',
  });

  assert.deepEqual(launchOptions, {
    executablePath: '/snap/bin/chromium',
    args: ['--disable-dev-shm-usage', '--no-sandbox', '--disable-setuid-sandbox'],
  });
});
