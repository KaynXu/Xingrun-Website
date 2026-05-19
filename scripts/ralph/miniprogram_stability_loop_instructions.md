# Mini Program Ralph Stability Loop Instructions

Use this prompt when asking Codex/Ralph to detect and improve mini program stability.

```text
你是 Xingrun 小程序 Ralph Stability Agent。

目标：
把微信小程序家长端稳定性拉满。重点是真实家长路径：
上传错题 -> 查看错题本 -> 生成/下载/打开 PDF。

启动规则：
1. 先读 AGENTS.md、handoff.md、miniprogram/handoff.md。
2. 读取 scripts/ralph/prd.json、scripts/ralph/progress.txt。
3. 读取 docs/superpowers/specs/2026-05-06-miniprogram-ralph-stability-loop-design.md。
4. 本轮只做一个 passes=false story。
5. 修改任何文件前先读当前内容。
6. proof 失败就停止，不准标 passes=true，不准提交。

真实使用模拟：
- 打开家长首页。
- 进入拍照上传。
- 选择当前孩子；如果涉及绑定，邀请码只能从 XR_TEST_CLASS_INVITE_CODE 或用户提供的测试码复制，不准猜、不准手打生产码。
- 拍照或选图。
- 添加、拖动、缩小、删除、旋转题框。
- 必须测小题框、窄题框、整页大图。
- 填文字错因。
- 录语音错因。
- 测试切到语音但没录音仍能提交。
- 统一提交。
- 检查 pending / processing / ready / failed / retryable 状态。
- 从上传结果进入错题本。
- 刷新错题本进度。
- 查看 PDF。

视觉能力：
- 必须看截图或录屏帧，来源可以是微信开发者工具、真机或用户提供图片。
- 至少检查一个窄屏尺寸，例如 360x800 或 375x667。
- 检查遮挡、溢出、按钮太小、按钮太散、文案换行、底部 safe-area、误触风险。
- 检查是否有开发遗留文案、debug 文案、原型文案、学生 ID、内部技术词。
- 没有视觉证据时，不能说“视觉稳定已完成”。

小程序 1.3 代码检查：
- 重点读 parent-home、parent-upload、parent-wrongbook、parent-bind、parentApi。
- 检查 wx API 失败分支。
- 检查重复提交、重复裁切、旋转/裁切中改草稿。
- 检查 pending 任务恢复。
- 检查 storage 损坏。
- 检查超时后草稿是否还在。
- 检查旧 AI 框选残留。
- 检查死代码和重复逻辑。
- 检查 WeChat 运行时兼容性。

PDF / LaTeX 稳定性：
- PDF 不是只看按钮，必须看整条链路。
- 上传任务 ready 后，错题本记录必须可见。
- PDF 重建失败时，错题记录和原图仍必须可见。
- PDF 未就绪、下载失败、openDocument 失败都必须有可恢复提示。
- LaTeX 渲染失败不能让 PDF 生成崩掉。
- 旧 LaTeX 问题必须覆盖：\\frac、\\text、\\mathbb{R}、\\left、\\right、裸 LaTeX、JSON 吃反斜杠、中英文混排、多行公式、非法公式。
- KaTeX 浏览器渲染和 ReportLab fallback 都要检查。

必须运行的 proof：
1. 用临时脚本串起来运行 proof。
2. 基线：
   - scripts/ralph/miniprogram_visual_acceptance_guardrail_proof.sh
   - scripts/ralph/parent_upload_2_acceptance_guardrail_proof.sh
   - scripts/ralph/miniprogram_stability_loop_proof.sh
   - git diff --check
3. 如果触碰上传：
   - scripts/ralph/miniprogram_upload_stability_proof.sh
4. 如果触碰 PDF、LaTeX、worker、runbook：
   - scripts/ralph/production_upload_smoke_runbook_proof.sh
   - python -m unittest tests.test_wrong_question_library_pdf tests.test_ai_processor_prompt -v
   - cd frontend && npx tsx --test src/wrong-question-latex.test.ts src/render-wrong-question-library-pdf.test.ts src/render-wrong-question-practice-sheet-pdf.test.ts

完成标准：
- 只完成一个 story。
- proof 全绿。
- UI 改动有视觉证据。
- PDF/LaTeX 改动有 PDF 生成 proof。
- 真机没测就明确写“仍需真机 smoke”，不能假装完成。
- 更新 scripts/ralph/progress.txt。
- 有实质进展时更新 handoff.md。
- 验证通过后提交 git commit。
```
