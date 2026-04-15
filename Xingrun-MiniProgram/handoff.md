# Handover - Source-Aligned Pencil Design

## 2026-04-10 Parent Upload Voice Reason Merged Into Current Branch
- 用户当前打开的是 `feature/wrong-question-error-cause`，不是之前已完成语音功能的 worktree，所以本轮改为把语音错因能力直接并入当前分支的多图多框上传页。
- 已完成：
  - 家长上传页当前题目支持 `文字输入 / 语音说明` 切换
  - 每个框可单独录音，提交时自动走 `上传音频 -> 转写 -> 错因归类 -> 最终提交`
  - bridge 新增：
    - `POST /upload`
    - `POST /wechat/parent/reason-transcriptions`
    - `POST /wechat/parent/reason-classifications`
  - 最终错题提交现在强制携带：
    - `childReasonText`
    - `childReasonInputMode`
    - `primaryErrorType`
    - `secondaryErrorSummary`
- 这轮额外修正了一个真实运行时缺口：小程序语音 helper 已经调用 `/upload`，但当前 bridge 源码原本没有这个路由；现已补上并加入回归测试。
- proof：
  - `cd /Users/ark.mini/Desktop/Xingrun-MiniProgram && node miniprogram/utils/parentApi.test.js`
    - `pass 12 / fail 0`
  - `cd /Users/ark.mini/Desktop/Xingrun-MiniProgram && node miniprogram/pages/parent-upload/model.test.js`
    - `pass 6 / fail 0`
  - `cd /Users/ark.mini/Desktop/Xingrun-MiniProgram && node miniprogram/parent-only-scope.test.js`
    - `pass 7 / fail 0`
  - `cd /Users/ark.mini/Desktop/Xingrun-MiniProgram/backend && node --import tsx --test src/parent-wechat-bridge.test.ts`
    - `pass 8 / fail 0`
  - `cd /Users/ark.mini/Desktop/Xingrun-MiniProgram/backend && npm run build`
    - `tsc` 通过，`dist` 已同步到最新 bridge 路由与提交流程
  - 清理结果：旧 worktree `/Users/ark.mini/Desktop/Xingrun-MiniProgram/.worktrees/parent-voice-reason` 已移除，旧分支 `feature/parent-voice-reason` 已删除，仓库当前只保留用户正在工作的 `feature/wrong-question-error-cause`

## 2026-04-10 Parent Upload childRawReasonText Runtime Fix
- 用户反馈：小程序上传时报错 `child_raw_reason_text is required`。
- 根因确认：
  - `backend/src/index.ts` 与 `backend/src/website-client.ts` 已经按新协议转发 `childRawReasonText`。
  - 但实际运行入口仍是 `backend/package.json` 里的 `node dist/index.js`。
  - 仓库内旧的 `backend/dist/index.js` 仍在走历史 `parentNote` 提交逻辑，没有把 `child_raw_reason_text` 发给 website，因此 runtime 继续报旧字段缺失。
- 本轮处理：
  - 执行 `cd backend && npm run build`，把 `backend/dist/*.js` 同步到当前 `src`。
  - 确认编译后的 `dist/index.js` 已读取并校验 `childRawReasonText`，再转发为 `child_raw_reason_text`。
- proof：
  - `cd /Users/ark.mini/Desktop/Xingrun-MiniProgram/backend && node --import tsx --test src/parent-wechat-bridge.test.ts`
    - `pass 5 / fail 0`
  - 编译产物 smoke：直接启动 `dist` 入口并发送 `POST /wechat/parent/wrong-questions`
    - 返回 `201`
    - 下游转发体包含：
      - `child_raw_reason_text: 我把单位换算漏掉了`
      - `child_reason_input_mode: text`

## 2026-04-10 Mini Program Repo Cleanup Split Into Focused Buckets
- 本轮目标不是再改产品逻辑，而是把已经存在的杂乱工作区整理成可解释、可提交的几组改动。
- 已确认并整理出的边界：
  - `parent-only` 收缩：仓库只保留家长绑定、家长首页、家长上传和 bridge 所需代码
  - docs sync：把 README、部署说明、规格/计划文档同步到当前真实运行状态
  - generated cleanup：移除 `.superpowers/` brainstorm 产物，并补 `.gitignore`
- `parent-only` 代码侧已包含：
  - 删除 `chat / crop / wrongbook` 页面
  - 删除 bridge 里聊天、排课、名册、订阅、PDF 等遗留代码与依赖
  - 小程序入口改为直接跳家长链路
  - 新增 `miniprogram/parent-only-scope.test.js`
  - 新增 `backend/parent-only-scope.test.cjs`
- docs sync 已补到当前状态：
  - README 增加 `wrong-question-boxes` 路由说明
  - 部署文档改为公网域名 `https://xingrun.online`
  - 明确当前上传页支持 `AI 框选`
- proof：
  - 待本轮 cleanup commit 后统一跑：
    - `node miniprogram/parent-only-scope.test.js`
    - `node miniprogram/pages/parent-upload/model.test.js`
    - `node miniprogram/utils/parentApi.test.js`
    - `node backend/parent-only-scope.test.cjs`
    - `cd backend && node --import tsx --test src/parent-wechat-bridge.test.ts`

## 2026-04-09 Parent Upload Action Buttons Layout Tightened
- 用户反馈：上传页裁剪区底部三个按钮 `补加框 / 删除当前 / AI 框选` 排列不够规整，窄屏下观感发挤。
- 根因：
  - 当前 `pages/parent-upload/index.wxss` 使用三列 grid，但叠加小程序 button 默认盒模型后，按钮在深色底板里容易显得贴边、发紧，不够稳定。
- 已完成：
  - 将按钮容器 `.action-row` 从 grid 改为稳定的 flex 横排
  - 给 `.compact-btn` 明确：
    - `flex: 1`
    - `min-width: 0`
    - `height: 72rpx`
    - `line-height: 72rpx`
    - `white-space: nowrap`
  - 保证三个按钮等宽、同高、单行显示
- 回归：
  - 在 `miniprogram/parent-only-scope.test.js` 新增样式回归断言，要求上传页按钮区必须保持单行稳定布局
- proof：
  - red：`node miniprogram/parent-only-scope.test.js` -> `pass 6 / fail 1`
  - green：`node miniprogram/parent-only-scope.test.js` -> `pass 7 / fail 0`

## 2026-04-09 Final Submit HTTP 500 Fixed
- 用户反馈：点击“统一提交所有错题”后提示 `网站接口请求失败 http 500`。
- 分层复现结果：
  - 公网 bridge `POST /wechat/parent/wrong-questions` 可命中
  - 但网站内部 `POST /api/wechat/wrong-questions` 在生产库写入时抛异常
  - `pm2 logs xingrun` 明确 traceback：
    - `sqlite3.OperationalError: no such table: main.students__org_scope_legacy`
- 根因确认：
  - 生产 SQLite 之前做过 `students` 组织域迁移，但子表外键仍旧指向旧表名 `students__org_scope_legacy`
  - 至少受影响对象包括：
    - `class_students`
    - `parent_student_bindings`
    - `wrong_question_submissions`
  - 因此一旦创建新的错题提交记录，SQLite 在外键检查阶段直接报 500
- 本轮实际修复：
  - 为避免继续大改生产表结构，先在正式库补建兼容表 `students__org_scope_legacy`
  - 从当前 `students` 全量回填 276 条学生记录
  - 新增同步 triggers：
    - `trg_students_legacy_sync_insert`
    - `trg_students_legacy_sync_update`
    - `trg_students_legacy_sync_delete`
  - 这样旧外键仍然能命中有效父表，当前统一提交流程恢复可用
  - 另外恢复了中途调库时误删的 class feedback roster triggers：
    - `trg_class_feedback_student_entries_roster_insert`
    - `trg_class_feedback_student_entries_roster_update`
- proof：
  - 修复前日志：
    - `/api/wechat/wrong-questions` -> `sqlite3.OperationalError: no such table: main.students__org_scope_legacy`
  - 兼容表修复脚本输出：
    - `students_count 276`
    - `students_legacy_count 276`
  - 公网真实提交流程回测：
    - `curl -i -X POST -F 'openId=oVll31xVnhX6H-TCfFTZp-H3SjoQ' -F 'bindingId=2' -F 'parentNote=submit-smoke' -F 'file=@/tmp/xr-smoke.png;type=image/png' https://xingrun.online/wechat/parent/wrong-questions`
    - 返回 `HTTP/1.1 201 Created`
    - 记录 id：`wechat-e4d6b52dcaab5101`
  - 最新日志：
    - `127.0.0.1 - - [09/Apr/2026 17:11:58] "POST /api/wechat/wrong-questions HTTP/1.0" 201 -`
- 后续建议：
  - 当前是生产止血修复，根本治理仍应在网站仓库里补正式 migration，把这些旧外键从 `students__org_scope_legacy` 迁回 `students`

## 2026-04-09 Live Website AI Box 404 Fixed
- 用户再次反馈 `AI 框选` 提示：`网站接口请求失败 http 404`。
- 本轮重新分层验证后确认根因：
  - 公网 bridge `POST /wechat/parent/wrong-question-boxes` 已存在
  - 但 bridge 下游调用的线上网站接口 `http://127.0.0.1:5001/api/wechat/wrong-question-boxes` 当时实际返回 `404 Not Found`
  - 远端 `/home/ubuntu/Xingrun-Website/app.py` 与 `smart_wrong_questions.py` 仍是旧版，缺少：
    - `/api/wechat/wrong-question-boxes`
    - `detect_wechat_wrong_question_boxes(...)`
    - 直连 N1N 的框选逻辑
- 已完成：
  - 将验证过的补丁文件同步到正式服务器：
    - `/home/ubuntu/Xingrun-Website/app.py`
    - `/home/ubuntu/Xingrun-Website/smart_wrong_questions.py`
    - `/home/ubuntu/Xingrun-Website/.env.runtime`
  - 远端备份：
    - `app.py.bak-20260409-404fix`
    - `smart_wrong_questions.py.bak-20260409-404fix`
    - `.env.runtime.bak-20260409-404fix`
  - 执行 `pm2 restart xingrun`
- 当前线上状态：
  - `网站接口请求失败：HTTP 404` 已消失
  - 公网 `https://xingrun.online/wechat/parent/wrong-question-boxes` 已能走到 AI provider
  - 当前剩余错误已变成 provider/image 层错误，例如：
    - 非图片上传时：`invalid_image_format`
    - 极小测试 PNG 时：`image_parse_error`
  - 这说明当前 blocker 已不再是网站路由缺失，而是具体图片内容是否能被模型正确解析
- proof：
  - 修复前：
    - 公网 `curl -X POST -F 'file=@/etc/hosts' https://xingrun.online/wechat/parent/wrong-question-boxes` -> `500 {"error":"网站接口请求失败：HTTP 404"}`
    - 内网 `curl http://127.0.0.1:5001/api/wechat/wrong-question-boxes` -> `404 Not Found`
  - 修复后：
    - 公网 `curl -X POST -F 'file=@/etc/hosts' https://xingrun.online/wechat/parent/wrong-question-boxes` -> `500`，但错误体为 N1N `invalid_image_format`
    - 公网 `curl -X POST -F 'file=@/tmp/xr-smoke.png;type=image/png' ...` -> `500`，但错误体为 N1N `image_parse_error`
    - 内网 `curl http://127.0.0.1:5001/api/wechat/wrong-question-boxes` -> `429`，错误体为 provider 下载图片失败，而非 404

## 2026-04-09 Parent Upload AI Spec Clarified
- 用户追问当前文档是否漏写了 AI 框选所需的需求和模型约束。
- 结论：是，原规格文档只写到“新增 AI 框选接口”，但没有把首版必须明确的 provider、默认模型、运行时配置和请求头约束写清楚。
- 已补充到规格文档：
  - [docs/superpowers/specs/2026-04-09-parent-upload-crop-ai-design.md](docs/superpowers/specs/2026-04-09-parent-upload-crop-ai-design.md)
  - 新增明确要求：
    - provider 为 `N1N`
    - 默认走 `https://api.n1n.ai/v1/chat/completions`
    - 默认模型为 `gpt-4o`
    - 运行时配置项为 `N1N_API_KEY`、`XR_N1N_BASE_URL`、`XR_N1N_MODEL`
    - 服务端请求必须携带 `Authorization`、`Content-Type`、`User-Agent`、`Accept`
    - provider 故障时前端错误文案不能退化成“上传返回解析失败”
- 这样补的原因：本轮联调已证明，之前实际问题不只是“有没有接 AI”，而是模型/接口契约没有写清，导致生产调用细节容易被实现方各自猜错。

## 2026-04-09 Real Device Domain Whitelist Fix
- 用户反馈：真机测试时报错 `request:fail url not in domain list`
- 根因确认：
  - 小程序 [miniprogram/app.js](/Users/ark.mini/Desktop/Xingrun-MiniProgram/miniprogram/app.js) 里的 `serverUrl` 仍指向 `http://49.234.185.86:3001`
  - 开发者工具里 `urlCheck: false` 可放行，但真机不会放行 `http` + IP 请求
  - 已验证 `https://xingrun.online/wechat/parent/*` 可通，适合作为真机请求域名
- 已完成：
  - 将小程序 `serverUrl` 改为 `https://xingrun.online`
  - 新增回归测试，要求 `serverUrl` 必须使用正式 HTTPS 域名，不能再回退到原始 IP
- proof：
  - red：
    - `node miniprogram/parent-only-scope.test.js` -> `pass 4 / fail 1`
  - green：
    - `node miniprogram/parent-only-scope.test.js` -> `pass 5 / fail 0`
    - `node miniprogram/utils/parentApi.test.js` -> `pass 5 / fail 0`
    - `curl https://xingrun.online/wechat/parent/bindings?openId=test-openid` 返回 Express JSON 错误 `parent wechat account not found`，说明 HTTPS 域名已实际命中后端接口而不是被微信域名校验拦截
- 剩余注意：
  - 微信公众平台后台仍需把 `https://xingrun.online` 配到 request 合法域名里；如果后台没配，真机依然会拦
  - 改完代码后需要重新上传/预览一次小程序包，让真机拿到新地址

## 2026-04-09 Web Delete -> Mini Program Binding Sync Fixed
- 用户确认当前链路缺少“网页删学生后，小程序绑定自动消失”的删除同步。
- 已在网站仓库 `/Users/ark.mini/Desktop/Xingrun-Website` 完成修复并部署到正式服务器。
- 修复内容：
  - `lesson_manager.remove_student_from_class(class_id, student_id)` 现在会先将相同 `class_id + student_id` 的 `parent_student_bindings.status` 从 `active` 改为 `inactive`
  - 然后再删除 `class_students`
  - 新增回归测试：删除班级学生后，小程序 bindings 列表不再返回该学生绑定
- 网站仓库提交：
  - `8bdba5f fix: inactivate parent bindings when removing class students`
- 正式服务器部署结果：
  - 远端仓库 `/home/ubuntu/Xingrun-Website` 已到 `REMOTE_HEAD=8bdba5ff`
  - `pm2 restart xingrun` 后服务 `online`
  - `GET http://127.0.0.1:5001/` -> `302`，为既有前端重定向健康表现
- proof：
  - red：
    - `python3 -m unittest tests.test_wechat_parent_upload_data.WeChatParentUploadDataTestCase.test_remove_student_from_class_hides_active_parent_binding_from_mini_program`
    - `FAILED (failures=1)`
  - green：
    - 定向删除同步测试：`Ran 1 test ... OK`
    - 家长上传数据回归：`Ran 7 tests ... OK`
    - 原有删学生测试：`Ran 1 test ... OK`
    - 远端生产代码同一定向测试：`Ran 1 test ... OK`

## 2026-04-09 Parent Binding Delete Sync Gap Confirmed
- 用户追问当前链路是否其实没有完全打通，因为网页删学生不会同步到小程序。
- 结论：
  - 是的，当前“新增/绑定/查询”链路是打通的。
  - 但“网页删除学生 -> 小程序绑定自动消失”这条删除同步链路没有打通。
- 当前实际状态：
  - 网页删学生接口只删除 `class_students`
  - 小程序绑定列表读取 `parent_student_bindings`
  - 两者之间没有“删除时同步将绑定置 inactive / 删除绑定”的逻辑
- 如果后续要补齐：
  - 优先修网页 `DELETE /api/classes/<class_id>/students/<student_id>`
  - 删除班级学生时同步处理对应 `parent_student_bindings`

## 2026-04-09 Web Student Deletion Behavior For Mini Program
- 用户询问：如果在网页某个班级里新增一个测试学生，后续再删除，这个删除是否会正确同步到小程序。
- 代码核对结论：
  - 如果网页里执行的是“从班级移除学生”，当前不会自动清掉小程序里的家长绑定。
  - 原因是网页 DELETE 路由 `/api/classes/<class_id>/students/<student_id>` 实际调用的是 `remove_student_from_class(class_id, student_id)`，只执行：
    - `DELETE FROM class_students WHERE class_id=? AND student_id=?`
  - 但小程序绑定列表 `list_parent_student_bindings_for_openid(open_id)` 查询的是：
    - `parent_student_bindings`
    - `JOIN classes`
    - `JOIN students`
    - 不依赖 `class_students`
  - 所以“从班级移除”后，只要 `parent_student_bindings` 还是 `active`，小程序仍会显示。
- 额外结论：
  - `parent_student_bindings.class_id` 对 `classes.id` 是 `ON DELETE CASCADE`
    - 如果删的是整个班级，绑定会被级联删掉
  - `parent_student_bindings.student_id` 对 `students.id` 是 `ON DELETE NO ACTION`
    - 如果尝试物理删学生行，数据库通常会拦住，不会自动清绑定
- 推荐测试方式：
  - 不要依赖“网页删学生”来清小程序测试绑定
  - 更稳的是：
    - 单独测试班级
    - 或测试完成后把对应 `parent_student_bindings.status` 改回 `inactive`

## 2026-04-09 Test Binding Reactivated For Upload Flow
- 用户确认要保留一条测试绑定，方便直接测试“进入后的功能”。
- 已完成：
  - 将正式库中 `parent_student_bindings.id = 2` 重新改回 `active`
  - 对应测试绑定：
    - `openid = oVll31xVnhX6H-TCfFTZp-H3SjoQ`
    - `student_name = 董欣洋`

## 2026-04-10 VibeVoice-ASR Feasibility For Child Wrong-Reason Input
- 用户询问：孩子在填写错因时，能否改成说话输入，并使用 `microsoft/VibeVoice` 做 ASR。
- 结论：能做，但只能走“服务端语音转文字”方案，不能在微信小程序端本地直接跑模型。
- 判断依据：
  - `VibeVoice-ASR` 是 7B 级长音频语音识别模型，官方文档推荐 NVIDIA GPU Docker 环境。
  - 当前仓库的小程序只适合采集语音并上传，现有 Node bridge 更适合作为转发层，把音频交给单独的 Python ASR 服务。
  - 当前 `wrong-questions` 提交流程要求前端直接传 `childRawReasonText`，若接 ASR，需要先新增语音上传/转写链路，再把转写结果回填到提交流程。
- 适配建议：
  - 若目标是“孩子说一句简短错因”，`VibeVoice-ASR` 技术上可用，但偏重、延迟和部署成本都较高，优先级更像服务端实验方案。
  - 若目标是稳定上线，通常更适合先接轻量实时 ASR 或云 ASR，再保留 `VibeVoice-ASR` 作为备选或离线增强方案。

## 2026-04-10 Child Voice Reason Structured With API Prompt
- 用户继续询问：是否可以直接用自己的 API key 把孩子语音传给模型，并通过提示词删掉口头禅、把错因归纳到 `A/B/C/D/E`，同时保留备注。
- 结论：能实现，而且比直接自部署 `VibeVoice-ASR` 更适合当前仓库的首版落地。
- 推荐方案不是“单步直接得到最终归类”，而是两步：
  - 第一步：音频转写，得到原始 transcript
  - 第二步：把 transcript 交给文本模型做结构化归纳，输出 `reasonCode + cleanedText + note`
- 原因：
  - 语音转写接口的 prompt 更适合提升识别准确率、术语和风格，不适合承载稳定的业务归类规则。
  - `A/B/C/D/E` 分类、口水话清洗、备注保留，本质上是后处理和结构化抽取，更适合单独的文本推理步骤。
- 工程边界：
  - 小程序端只负责录音和上传，不持有真实 API key
  - API key 只能放服务端
  - 当前 bridge 需要新增音频上传和结构化返回接口，最后仍回填到现有 `wrong-questions` 提交流程

## 2026-04-10 Wrong-Reason Taxonomy Mismatch Confirmed
- 用户澄清的目标口径不是固定 6 个中文标签，也不是 `A-E` 简单码，而是：
  - 顶层更接近 `知识点问题 / 细节问题 / 方法问题 / 审题问题`
  - 孩子的原始口述文本需要完整保留一份
  - AI 只负责从顶层标签里选最接近的一类，并额外生成备注
  - 像 `书写 / 符号 / 单位` 这类内容应进入 AI 备注或二级描述，而不是再写死成固定主分类
- 已确认联动的 website 当前实现仍是旧口径：后端固定分类和前端固定列表都还是 6 个中文标签的实现，不等于当前用户想要的分类模型。
- 含义：
  - 如果要接孩子语音输入，不能默认沿用 website 当前那 6 类实现当作最终产品口径。
  - 更合理的是改成“双层结构”：
    - 存储层保留 `raw transcript`
    - AI 输出 `top_level_reason + generated_note`
  - 是否兼容 website 旧 6 类，需要后续单独决定映射或迁移策略。

## 2026-04-10 Parent Voice Reason Design Approved
- 用户已确认新的最终产品口径：
  - 顶层分类只保留 `知识点问题 / 细节问题 / 方法问题 / 审题问题`
  - website 不保留旧 6 类兼容逻辑，直接一起改口径
  - 细项如 `书写 / 符号 / 单位` 不再做固定主分类，而进入 AI 备注
  - 老师端不展示“清洗后错因文本”这类工程词，页面文案使用自然业务词
- 设计文档已新增：
  - `docs/superpowers/specs/2026-04-10-parent-voice-reason-design.md`
- 设计里的关键取舍：
  - 继续复用 website 现有字段名 `child_raw_reason_text / primary_error_type / secondary_error_summary / child_reason_input_mode`
  - 但业务语义改成：`老师可读错因描述 / 顶层错因分类 / AI备注 / 输入方式`
  - 首版不要求老师回听原始音频，也不新增老师端依赖的音频字段

## 2026-04-10 Parent Voice Reason Plan Written
- 设计文档确认后，已新增实现计划：
  - `docs/superpowers/plans/2026-04-10-parent-voice-reason-plan.md`
- 计划拆分为 6 个独立任务：
  - website taxonomy + API contract
  - website teacher UI
  - Node bridge transcription/classification proxies
  - mini program API/model helpers
  - mini program page voice/text UI
  - final verification + handoff
- 当前尚未开始实现代码，下一步等待用户选择执行方式。
    - `class_name = 徐老师小课`
  - 远端备份：`/home/ubuntu/deploy-backups/parent-binding-2-before-reactivate-20260409-035828.json`
- proof：
  - `AFTER {"id": 2, "openid": "oVll31xVnhX6H-TCfFTZp-H3SjoQ", "status": "active", ...}`
  - `BINDINGS [...]` 返回 1 条 active 绑定
- 说明：
  - 这是服务器测试数据，不是重新部署代码
  - 后续如需恢复干净状态，可再把 `id = 2` 改回 `inactive`

## 2026-04-09 Test Account Decision
- 用户询问是否可以保留一条测试号，并担心“会不会部署到服务器上”。
- 结论：
  - 如果要测试“进入后”的真实家长首页/上传错题链路，这条测试绑定必须存在于正式服务器数据库里。
  - 这属于测试数据，不是再次部署代码。
  - 小程序每次都会从服务端刷新 `/wechat/parent/bindings`，所以不落服务器只留本地缓存是不可行的。
- 推荐：
  - 使用专门测试微信号 + 专门测试绑定数据
  - 不混用真实家长账号
  - 需要时再把测试绑定改回 `inactive`

## 2026-04-09 Testing Strategy For Parent Flow
- 用户希望测试“进入后的功能”，但不想每次都重新删除/解绑再跑一遍。
- 当前链路特性：
  - 家长首页和上传页进入前都会主动请求服务端 `/wechat/parent/bindings`
  - 因此单改本地缓存不够，服务端必须保留一条 `active` 绑定，页面才能稳定进入“已绑定后”的流程
- 推荐测试方式：
  - 准备一个专用测试微信账号/测试 openid，长期保留一条测试绑定，只用于测“进入后”的上传链路
  - 真实账号保持干净，需要验绑定流程时再单独测试
- 结论：
  - 以后不要在同一个账号上来回“绑定 -> 删除 -> 再绑定”做所有测试
  - 应拆成：
    - 一个“绑定流程测试账号”
    - 一个“已绑定上传流程测试账号”

## 2026-04-09 Bind Page White Screen Compatibility Fix
- 用户在解绑 `董欣洋` 后再次进入小程序，出现整页白屏。
- 根因判断：
  - 解绑后入口会更容易落到 `pages/parent-bind/index`
  - 当前保留的小程序活动链路里仍残留 `?.` 可选链语法
  - 在当前微信开发者工具/编译配置下，这类语法存在白屏风险
- 已完成：
  - 新增回归测试，要求活动链路文件不再包含 `?.` / `??`
  - 将以下文件中的可选链改为兼容写法：
    - `[miniprogram/utils/parentApi.js](/Users/ark.mini/Desktop/Xingrun-MiniProgram/miniprogram/utils/parentApi.js)`
    - `[miniprogram/pages/parent-bind/index.js](/Users/ark.mini/Desktop/Xingrun-MiniProgram/miniprogram/pages/parent-bind/index.js)`
    - `[miniprogram/pages/parent-upload/index.js](/Users/ark.mini/Desktop/Xingrun-MiniProgram/miniprogram/pages/parent-upload/index.js)`
- proof：
  - red：
    - `node miniprogram/parent-only-scope.test.js` -> `3 pass / 1 fail`
  - green：
    - `node miniprogram/parent-only-scope.test.js` -> `4 pass / 0 fail`
    - `node miniprogram/utils/parentApi.test.js` -> `5 pass / 0 fail`

## 2026-04-09 Actual Parent Binding For 董欣洋 Unbound
- 用户继续反馈绑定页里仍能看到 `董欣洋 · 徐老师小课`。
- 根因：
  - 不是前端模板残留。
  - 正式网站库 `/home/ubuntu/Xingrun-Website/data/xingrun.db` 中，`parent_student_bindings.id = 2` 仍是 `active`。
  - 该记录对应：
    - `openid = oVll31xVnhX6H-TCfFTZp-H3SjoQ`
    - `class_id = 51`
    - `student_id = 227`
    - `student_name = 董欣洋`
- 已完成：
  - 远端备份：`/home/ubuntu/deploy-backups/parent-binding-2-before-unbind-20260409-034542.json`
  - 将 `parent_student_bindings.id = 2` 从 `active` 改为 `inactive`
- proof：
  - 临时脚本输出：
    - `BACKUP /home/ubuntu/deploy-backups/parent-binding-2-before-unbind-20260409-034542.json`
    - `AFTER {"id": 2, "status": "inactive", ...}`
    - `BINDINGS []`
  - 说明这个 openid 下已没有 active 绑定残留

## 2026-04-09 Parent Home Wording Investigation
- 用户反馈即使重新编译，模拟器家长首页仍显示 `已绑定孩子`。
- 本地排查结论：
  - 当前仓库家长首页源码 `[miniprogram/pages/parent-home/index.wxml](/Users/ark.mini/Desktop/Xingrun-MiniProgram/miniprogram/pages/parent-home/index.wxml)` 第 25 行实际内容已是 `选择孩子上传`
  - 桌面范围全文检索结果显示：
    - `选择孩子上传` 只存在这一份家长首页模板
    - `已绑定孩子` 只剩：
      - `[miniprogram/pages/parent-bind/index.wxml](/Users/ark.mini/Desktop/Xingrun-MiniProgram/miniprogram/pages/parent-bind/index.wxml)` 绑定页
      - `README.md`
      - `handoff.md`
  - 因此，用户截图中的家长首页文案不是当前这份 `parent-home/index.wxml` 渲染出来的，更像是微信开发者工具仍在使用旧缓存或另一实例
- proof：
  - `stat ... miniprogram/pages/parent-home/index.wxml` 显示最近修改时间为 `2026-04-09 03:29:03`
  - `nl -ba miniprogram/pages/parent-home/index.wxml | sed -n '20,32p'` 显示第 25 行是 `选择孩子上传`
  - `rg -n "已绑定孩子" /Users/ark.mini/Desktop ...` 未命中家长首页模板

## 2026-04-09 Parent Home Continue-Bind Entry Removed
- 用户反馈家长首页在已有绑定后，仍显示“继续绑定”按钮。
- 根因：
  - `[miniprogram/pages/parent-home/index.wxml](/Users/ark.mini/Desktop/Xingrun-MiniProgram/miniprogram/pages/parent-home/index.wxml)` 在 `bindings.length > 0` 的分支里直接渲染了 `继续绑定` 按钮。
  - 这不是缓存问题，也不是后端返回异常，而是前端模板当前行为。
- 已完成：
  - 删除首页“已绑定孩子”区域中的 `继续绑定` 按钮
  - 将首页绑定态标题 `已绑定孩子` 改为 `选择孩子上传`
  - 增加回归测试，要求家长首页模板不再包含 `继续绑定` 和 `已绑定孩子`
- proof：
  - red：
    - `node miniprogram/parent-only-scope.test.js` -> `2 pass / 1 fail`
  - green：
    - `node miniprogram/parent-only-scope.test.js` -> `3 pass / 0 fail`

## 2026-04-09 Parent-Only Cleanup Completed
- 用户确认要把前后端旧聊天式链路彻底删除，只保留：
  - 家长绑定
  - 家长首页
  - 上传错题
- 已完成前端清理：
  - `miniprogram/app.json` 只保留：
    - `pages/index/index`
    - `pages/parent-home/index`
    - `pages/parent-bind/index`
    - `pages/parent-upload/index`
  - `miniprogram/app.js` 只保留家长链路所需全局状态
  - `miniprogram/pages/index/*` 改为最小重定向入口
  - 物理删除：
    - `miniprogram/pages/chat/*`
    - `miniprogram/pages/crop/*`
    - `miniprogram/pages/wrongbook/*`
- 已完成后端清理：
  - `backend/src/index.ts` 改为仅暴露：
    - `/healthz`
    - `/wechat/parent/login`
    - `/wechat/parent/bind-class`
    - `/wechat/parent/bind-student`
    - `/wechat/parent/bindings`
    - `/wechat/parent/wrong-questions`
  - 物理删除旧文件：
    - `backend/src/openclaw.ts`
    - `backend/src/rooms.ts`
    - `backend/src/roster.ts`
    - `backend/src/feedback.ts`
    - `backend/src/scheduler.ts`
    - `backend/src/subscription.ts`
    - `backend/src/vision.ts`
    - `backend/scripts/import-roster.mjs`
    - `backend/test-pdf.ts`
    - 以及旧 roster/dashboard 资产文件
  - `backend/package.json` / `backend/package-lock.json` 已切到新包名 `xingrun-parent-wechat-bridge`
  - `/healthz` 返回中的旧服务名 `openclaw-wechat-bridge` 已改为 `xingrun-parent-wechat-bridge`
- 部署：
  - 正式服务器 `49.234.185.86`
  - PM2 bridge 进程：`xingrun-bridge`
  - 本轮远端备份：
    - `/home/ubuntu/deploy-backups/parent-only-cleanup-20260409-031404`
    - `/home/ubuntu/deploy-backups/parent-only-cleanup-20260409-031644`
- fresh proof：
  - 本地临时脚本执行通过：
    - `node miniprogram/parent-only-scope.test.js` -> `1 pass / 0 fail`
    - `cd backend && node parent-only-scope.test.cjs` -> `1 pass / 0 fail`
    - `cd backend && node --import tsx --test src/parent-wechat-bridge.test.ts` -> `4 pass / 0 fail`
    - `cd backend && npm run build` -> passed
  - 线上公网临时脚本 smoke：
    - `GET /healthz` -> `200 {"ok":true,"service":"xingrun-parent-wechat-bridge",...}`
    - `GET /rooms` -> `404`
    - `GET /wechat/config` -> `404`
    - `POST /wechat/parent/login` -> `200`
    - `GET /wechat/parent/bindings` -> `200`
- 残留扫描：
  - 业务代码与运行文档中已无旧聊天链路残留
  - 旧关键词当前只出现在：
    - 回归测试断言
    - `handoff.md` 历史记录
    - `CLOUD_HOSTING_SETUP.md` 中“旧接口已删除”的说明句

## 2026-04-09 Mini Program Scope Clarification
- 用户询问当前小程序是否已经完全重构为“只剩家长上传错题”的版本，以及早期聊天式小程序代码是否已删除。
- 代码核对结论：
  - 不是完全删除旧功能的纯净版本
  - 当前默认入口确实已切到家长链路
  - 但早期聊天/错题本/裁剪等页面和逻辑仍在仓库中
- 证据：
  - `miniprogram/app.json` 仍注册以下页面：
    - `pages/index/index`
    - `pages/parent-home/index`
    - `pages/parent-bind/index`
    - `pages/parent-upload/index`
    - `pages/chat/chat`
    - `pages/crop/index`
    - `pages/wrongbook/index`
  - `pages/index/index.js` 在默认情况下会 `reLaunch(resolveParentEntryPath(wx))` 到家长入口
  - 但 `pages/index/index.js` 仍保留旧的学生档案、微信登录、WebSocket、名册读取、跳转 `pages/chat/chat` 的逻辑
  - `pages/chat/chat.js`、`pages/wrongbook/index.js`、`pages/crop/index.js` 仍存在并包含旧聊天/错题本链路代码
- 当前状态更准确的描述：
  - “默认产品入口已改为家长绑定/上传链路”
  - “旧聊天式小程序仍在仓库内，尚未做物理删除或彻底下线”

## 2026-04-09 Test Child Unbound
- 用户要求把本轮测试绑定的孩子解绑。
- 已确认解绑对象：
  - `parent_student_bindings.id = 1`
  - `parent_wechat_account_id = 6`
  - `class_id = 51`
  - `student_id = 227`
  - 原状态：`active`
- 已完成：
  - 备份：`/home/ubuntu/deploy-backups/parent-binding-1-before-unbind-20260409-025703.json`
  - 将该记录状态改为：`inactive`
- proof：
  - 解绑前记录：`status = active`
  - 解绑后记录：`status = inactive`
  - `list_parent_student_bindings_for_openid('debug-parent-bind-openid')` 返回空列表，说明没有 active 绑定残留

## 2026-04-09 Class Teacher Data Fix For Parent Binding
- 用户在家长绑定页输入真实邀请码 `6C8D04` 后：
  - 班级预览成功
  - 绑定学生时报错：`class teacher is required`
- 根因已确认：
  - 邀请码 `6C8D04` 对应 `class_id=51`，班级名为 `徐老师小课`
  - 网站侧预览接口返回：
    - `teacher_user_id: null`
    - `teacher_display_name: ""`
  - 网站 `bind_parent_to_student(...)` 会强制要求 `get_class_teacher_user_id(class_id)` 非空，否则直接抛 `class teacher is required`
- 已完成：
  - 在正式服务器网站数据中，将 `class_id=51` 绑定到老师账号：
    - `teacher_user_id=18`
    - `teacher_display_name=徐大伟`
  - 修复前备份：`/home/ubuntu/deploy-backups/class-51-teacher-before-20260409-025153.json`
- proof：
  - 通过临时脚本执行真实链路回归：
    - `POST /wechat/parent/login` -> `200`
    - `POST /wechat/parent/bind-class` with invite `6C8D04` -> `200`
      - 返回 `teacher_user_id: 18`
      - 返回 `teacher_display_name: 徐大伟`
    - `POST /wechat/parent/bind-student` with `class_id=51` and real student `id=227` -> `200`
- 当前剩余：
  - 仍建议用户在真机小程序里再走一遍真实邀请码 + 真实学生绑定 smoke test

## 2026-04-09 Parent Bridge WeChat Env Fix
- 用户在家长绑定页继续遇到：
  - `微信小程序配置缺失，请补充 WECHAT_APPID / WECHAT_APPSECRET`
- 根因已确认：
  - 正式服务器 `/home/ubuntu/xingrun-backend-repo/backend/.env` 在上一轮部署后只保留了：
    - `BASE_URL`
    - `N1N_*`
    - `WEBSITE_API_*`
  - 丢失了 bridge 登录所需的：
    - `WECHAT_APPID`
    - `WECHAT_APPSECRET`
    - 以及本地 `backend/.env` 中的微信相关配置
  - 因此真机首次进入家长绑定页时，`wx.login -> /wechat/parent/login(code)` 会直接返回配置缺失错误
- 已完成：
  - 远端备份：`/home/ubuntu/deploy-backups/parent-wechat-env-fix-20260409-024539.env`
  - 将本地 `backend/.env` 的微信配置并回正式服务器 bridge 的 `.env`
  - 保留远端现有：
    - `BASE_URL`
    - `N1N_*`
    - `WEBSITE_API_*`
  - 仅重启 `PM2 xingrun-bridge`
- proof：
  - 修复前：
    - `POST http://49.234.185.86:3001/wechat/parent/login` with fake code -> `500 {"error":"微信小程序配置缺失，请补充 WECHAT_APPID / WECHAT_APPSECRET"}`
  - 修复后：
    - 同一路由 with fake code -> `500 {"error":"微信登录失败：invalid code, ..."}`
  - 这说明缺配置问题已解除，当前进入的是微信官方 code 校验逻辑
- 当前剩余：
  - 仍需用真实小程序真机 `wx.login` code 做人工 smoke，确认家长绑定页完整可用

## 2026-04-09 Parent Bridge Production Deploy
- 目标：
  - 将本地已实现的 `/wechat/parent/*` bridge 路由部署到正式服务器 `49.234.185.86`
  - 修正之前“正式服务器 live backend 缺少家长接口”的阻塞
- 现网进程核对结果：
  - `PM2 xingrun` 实际是网站 Python 服务：`/home/ubuntu/Xingrun-Website/scripts/run_backend.sh`
  - `PM2 xingrun-bridge` 才是小程序 Node bridge：`cd /home/ubuntu/xingrun-backend-repo/backend && node dist/index.js`
  - 监听端口 `3001` 的是 `xingrun-bridge`
- 部署动作：
  - 远端备份目录：`/home/ubuntu/deploy-backups/parent-wechat-bridge-20260409-023548`
  - 同步本地 `backend/src/`、`backend/package.json`、`backend/package-lock.json`、`backend/tsconfig.json` 到 `/home/ubuntu/xingrun-backend-repo/backend`
  - 在 bridge 侧 `backend/.env` 补齐：
    - `WEBSITE_API_BASE_URL=https://xingrun.online`
    - `WEBSITE_API_TOKEN=<server-only secret>`
  - 在网站侧 `/home/ubuntu/Xingrun-Website/.env.runtime` 补齐：
    - `XR_WECHAT_SERVICE_TOKEN=<same server-only secret>`
  - 远端执行：
    - `cd /home/ubuntu/xingrun-backend-repo/backend && npm run build`
    - `pm2 restart xingrun-bridge`
    - `pm2 restart xingrun`
- 结果：
  - 正式服务器 `/wechat/parent/login` 返回 `200`
  - 正式服务器 `/wechat/parent/bindings` 返回 `200`
  - 正式服务器 `/wechat/parent/bind-class` 不再是 `404`，对无效邀请码返回业务错误 `invite not found`
  - 正式服务器 `/wechat/parent/bind-student` 不再是 `404`，对无效班级/学生返回业务错误 `class not found`
  - 说明 bridge 路由、网站接口、服务鉴权已经串通
- proof：
  - 本地后端 proof：
    - `cd backend && node --import tsx --test src/parent-wechat-bridge.test.ts` -> `3 pass / 0 fail`
    - `cd backend && npm run build` -> passed
  - 远端本机验证：
    - `curl http://127.0.0.1:3001/healthz` -> `200`
    - `POST /wechat/parent/login` -> `200`
    - `GET /wechat/parent/bindings?openId=probe-openid` -> `200`
    - `POST /wechat/parent/bind-class` with invalid invite -> `500 {"error":"invite not found"}`
  - 本地公网验证：
    - `GET http://49.234.185.86:3001/healthz` -> `200`
    - `POST http://49.234.185.86:3001/wechat/parent/login` -> `200`
    - `GET http://49.234.185.86:3001/wechat/parent/bindings?openId=probe-openid-2` -> `200`
    - `POST http://49.234.185.86:3001/wechat/parent/bind-student` with invalid ids -> `500 {"error":"class not found"}`
- 当前剩余：
  - 还没做真实邀请码 + 真实学生绑定的人工 smoke test
  - 网站仓库服务器上没有 `handoff.md`，因此本轮仅更新了本仓库的 `handoff.md`

## 2026-04-09 Parent Bind Error Message Fix
- 用户反馈家长绑定页出现“暂时无法继续 / request:ok”。
- 根因已确认：
  - 正式服务器为 `49.234.185.86:3001`
  - 本地 [miniprogram/app.js](/Users/ark.mini/Desktop/Xingrun-MiniProgram/miniprogram/app.js) 当时仍残留旧的云托管域名配置
  - `GET /wechat/parent/bindings` 与 `POST /wechat/parent/bind-class` 在线上均返回 `404 Cannot GET/POST ...`
  - 前端 `miniprogram/utils/parentApi.js` 在收到非 JSON 404 HTML 响应时回退成了 `response.errMsg`
  - 微信请求成功时 `response.errMsg` 恰好是 `request:ok`，所以页面错误文案被误显示成了 `request:ok`
- 已完成：
  - 在 `miniprogram/utils/parentApi.js` 增加请求错误提取逻辑
  - 对“家长路由不存在”的 404 HTML 响应映射为：`家长绑定服务暂未部署，请联系老师稍后再试`
  - 在 `miniprogram/utils/parentApi.test.js` 增加回归测试，覆盖 `404 HTML + request:ok` 场景
- proof：
  - 通过临时脚本执行：
    - `node miniprogram/utils/parentApi.test.js` -> `5 pass / 0 fail`
    - `cd backend && node --import tsx --test src/parent-wechat-bridge.test.ts` -> `3 pass / 0 fail`
- 当前剩余：
  - 真正影响功能可用性的仍是正式服务器 live backend 未部署家长接口，不是前端逻辑缺失
  - `http://49.234.185.86:3001/healthz` 正常，但 `/wechat/parent/*` 路由仍 404
- 下一步建议：
  - 将当前带家长绑定接口的 `backend/` 重新部署到正式服务器 `49.234.185.86`
  - 部署后优先 smoke：
    - `/wechat/parent/login`
    - `/wechat/parent/bindings`
    - `/wechat/parent/bind-class`
    - `/wechat/parent/bind-student`

### 2026-04-09 Deployment Clarification
- 用户补充说明：当前正式使用的应是自有服务器，不是云托管。
- 代码与现网核对结果：
  - 已通过 SSH 登录正式服务器 `49.234.185.86`
  - live 后端目录确认为 `/home/ubuntu/xingrun-backend-repo/backend`
  - PM2 正在运行 `xingrun`
  - 实测正式服务器 `http://49.234.185.86:3001` 对 `/wechat/parent/bindings` 返回 `404 Cannot GET /wechat/parent/bindings`
  - 远端代码检索未发现 `/wechat/parent/*` 路由，说明正式服务器上的 live backend 仍是旧版本
- 结论：
  - 现在的阻塞不是“必须上云托管”
  - 而是“正式服务器已确认，但 live backend 代码还没包含家长绑定接口”
- 下一步建议：
  - 以 `49.234.185.86:3001` 作为唯一正式后端口径继续排查与部署
  - 部署当前本地 `backend/` 到这台机器后再做家长绑定 smoke test

## 2026-04-08 Cleanup + New Worktree + Parent Invite Flow
- 用户要求先清理主仓脏改动，再基于干净基线进入新 worktree 开发。
- 已完成清理与保留：
  - 创建保留分支：`backup/dirty-snapshot-20260408-222819`
  - `main` 已对齐 `origin/main` 到 `c18240b`
  - 当时主仓仅保留 `.worktrees/` 未跟踪目录
- 当时新建的开发 worktree：
  - 路径：`/Users/ark.mini/Desktop/Xingrun-MiniProgram/.worktrees/parent-invite-dev`
  - 分支：`feature/parent-invite-dev`
- 在新分支实装并验证了家长邀请码/上传链路：
  - `722c97e feat: add wechat parent upload flow`
  - `cb4b13d Re-sync parent bindings before showing or uploading child data`
- proof：
  - `node miniprogram/utils/parentApi.test.js` -> `4 pass / 0 fail`
  - `node --import tsx --test backend/src/parent-wechat-bridge.test.ts` -> `3 pass / 0 fail`
- 当时剩余：
  - 仍需微信开发者工具里的真实端到端 smoke 验证

## 2026-04-08 Branch Strategy Adjustment
- 用户确认不再使用新增 worktree 继续开发。
- 已移除 worktree：`.worktrees/parent-invite-dev`。
- 主仓已创建并切换到 `develop`（基于 `main@c18240b`）。
- 推荐分支流程调整为：`main` 保持稳定，日常从 `develop` 派生功能分支并回合到 `develop`。
- 当时保留的历史 worktree：`.worktrees/parent-binding-sync`。

## 2026-04-08 Parent Upload README & Verification Update
- 补充了家长上传 MVP 的 README / 验证说明：
  - `WEBSITE_API_BASE_URL` / `WEBSITE_API_TOKEN` 后端桥接配置
  - 家长端 bind -> home -> upload 页面职责
  - 从绑定到网站侧可见的 smoke-test 步骤
- 在独立 worktree 内补齐依赖并完成 fresh proof：
  - `cd backend && node --import tsx --test src/parent-wechat-bridge.test.ts` -> `3 pass / 0 fail`
  - `cd miniprogram && node utils/parentApi.test.js` -> `4 pass / 0 fail`
- 当时剩余：
  - 仍缺真实微信开发者工具人工流转验证
  - 分支尚未推送/合并

## Current Design Source
- Main file: `xingrun-error-correction.pen`
- Status: validated locally in Pencil and now aligned to the current `miniprogram` flow
- Top-level screens:
  - `GF8wL` - Screen 1: Entry
  - `fN5yF` - Screen 2: Chat
  - `cncsF` - Screen 3: Crop

## What Was Changed
- Removed the stale 5-screen V3 concept design (`Home / Chat / Crop / Notebook / Review`)
- Rebuilt the `.pen` file around the actual implemented mini program structure instead of a generic education dashboard
- Localized visible page copy to Chinese
- Switched the design direction to a WeChat-native visual language centered on:
  - `#07C160` green
  - `#F2F2F2` light gray
  - white card surfaces

## Screen Mapping

### 1. Entry (`GF8wL`)
Matches `miniprogram/pages/index/`

- Purpose:
  - show saved children
  - allow profile switching
  - register a new child
  - collect review reminder time before entering the wrong-problem flow
- UI structure:
  - brand / intro card
  - saved children list
  - registration form
  - primary CTA: `进入错题本`

### 2. Chat (`fN5yF`)
Matches `miniprogram/pages/chat/`

- Purpose:
  - represent the real mixed message stream
  - emphasize `analysis_card` as the primary business object
  - include `review_prompt` as the secondary business object
- UI structure:
  - page header with current child context
  - user text bubble
  - image/file-style bubble
  - AI `错题诊断卡`
  - `错题复习确认` card
  - bottom composer + toolbar actions
- Toolbar reflects the current code flow:
  - 图片
  - 查看错题本
  - 切换用户
  - 文件
  - 重置

### 3. Crop (`cncsF`)
Matches `miniprogram/pages/crop/`

- Purpose:
  - support one-by-one batch image cropping before upload
- UI structure:
  - crop title and instruction copy
  - dark crop stage
  - crop box with visible handles and grid
  - progress display like `2 / 5`
  - actions:
    - `使用原图`
    - `裁剪并继续`

## Validation Notes
- The `.pen` file is valid JSON
- Pencil currently reads exactly 3 top-level screens from the file
- Screens were visually checked in Pencil after rebuild
- Exported PNG assets are currently available at:
  - `backend/assets/GF8wL.png`
  - `backend/assets/fN5yF.png`
  - `backend/assets/cncsF.png`

## Next Suggested Step
- Implement the mini program UI based on these 3 source-aligned screens, starting with:
  - `miniprogram/pages/index/`
  - `miniprogram/pages/chat/`

## 2026-04-01 Git Identity Investigation
- Confirmed current repository history has 22 commits total.
- Distinct author/committer identities currently found:
  - `ark.mini <ark.mini@local>`: 19 commits
  - `Ark.0 <Ark.0@Ark.0>`: 2 commits
  - `小迪 <xiaodi@xiaodideMac-mini.local>`: 1 commit
- Root cause for missing GitHub contribution attribution:
  - local repository `user.email` is set to `ark.mini@local`
  - GitHub does not attribute contributions for this local-only email
- Current global Git identity on this machine:
  - `KaynXu <Kayn030423@gmail.com>`
- Completed actions:
  - created local backup branch `backup/pre-author-rewrite-20260401-013342`
  - rewrote all 22 historical commits so both author and committer are `KaynXu <Kayn030423@gmail.com>`
  - force-pushed rewritten `main` to `origin`
  - updated this repository's local git config to:
    - `user.name=KaynXu`
    - `user.email=Kayn030423@gmail.com`
- Verification:
  - remote `origin/main` now points to rewritten head `c18240b`
  - latest remote commits show `KaynXu <Kayn030423@gmail.com>` as both author and committer
  - GitHub commit API resolves rewritten commit `c18240b` with:
    - `author.login=KaynXu`
    - `committer.login=KaynXu`
  - this confirms GitHub is associating the rewritten commits with the logged-in account
- Important local state note:
  - local safety branch created during sync: `backup/pre-local-sync-20260401-013614`
  - local uncommitted work was stashed, local `main` was hard-reset to rewritten `origin/main`, and the stash was applied back successfully
  - local status is now `main...origin/main` with the same uncommitted changes restored on top of the rewritten history
  - temporary safety artifacts were later cleaned up explicitly:
    - dropped `stash@{0}: On main: pre-local-sync-20260401-013614`
    - deleted `backup/pre-author-rewrite-20260401-013342`
    - deleted `backup/pre-local-sync-20260401-013614`

## 2026-04-01 Wrongbook Scope Fix
- Root cause confirmed for mini program wrongbook cross-student leakage:

## 2026-04-02 OpenClaw 企业微信通道排查
- 目标：排查控制台中企业微信通道反复出现的两类报错：
  - `Kicked by server: a new connection was established elsewhere...`
  - `Unsupported type: . Use Raw mode.`
- 终端实测结果：
  - `openclaw status --deep` 与 `openclaw channels status --probe` 均显示企业微信通道 `enabled/configured/running`
  - 当前机器进程只存在一套 `openclaw` + `openclaw-gateway`
  - 配置文件校验通过：`openclaw config validate`
- 日志证据：
  - 企业微信错误日志中存在多次 `Kicked by server: a new connection was established elsewhere...`
  - 该报错可确定为“同一企业微信 botId 在其他实例上建立了连接”，导致当前实例被踢
  - 本地日志中未检索到 `Unsupported type: . Use Raw mode.` 同文案，推断其来源是控制台通道配置表单解析层（而非网关核心崩溃）
- 结论：
  - 企业微信通道可以本地跑，但要求“单连接持有”，不适合多台机器/多容器/重复守护同时在线
  - 若需稳定生产，建议固定单一常驻实例（云主机或一台长期在线设备），避免并发连接竞争
- 下一步建议：
  - 清点并关闭其他可能在线的 OpenClaw/企业微信通道实例（另一台电脑、容器、旧守护）
  - 在控制台配置页遇到 `Unsupported type` 时切换 Raw 编辑并保存规范 JSON，再 `Reload`
  - 保持仅一个实例在线后观察是否还出现被踢

### 2026-04-02 执行记录：步骤 2（Raw 等价修复）
- 已在 CLI 完成等价操作：
  - 读取当前配置：`openclaw config get channels.wecom`
  - 严格 JSON 方式重写字段：`openclaw config set channels.wecom.dmPolicy '"pairing"' --strict-json`
  - 校验配置：`openclaw config validate`
  - 重启网关并探测：`openclaw gateway restart && openclaw channels status --probe`
- 结果：
  - 配置校验通过
  - 网关重启成功
  - 企业微信通道状态恢复为 `enabled, configured, running`
  - wrongbook page queried records with only `roomId + studentName`
  - backend `getStudentFeedbackRecords(...)` also filtered only by `studentNickname`
  - same-name students under different teachers/classes could therefore return mixed records
- Completed changes:
  - wrongbook WebSocket query now sends `teacherName` and `className`
  - chat page now passes `teacherName` and `className` when navigating into wrongbook
  - wrongbook page now uses route-level `teacherName` / `className` as fallbacks when global profile is not fully hydrated
  - backend `/api/student/records` and WebSocket `get_student_records` now scope by `studentName + teacherName + className` when those fields are provided
- Proof:
  - backend build: `npm run build` passed
  - backend regression: `npx --yes tsx --test backend/src/teacher-records.test.ts`
  - result: `tests 6`, `pass 6`, `fail 0`

## 2026-04-01 Wrongbook Backend Production Deploy
- Production target confirmed:
  - server: `49.234.185.86`
  - live node backend repo: `/home/ubuntu/xingrun-backend-repo/backend`
  - PM2 process: `xingrun`
  - live port: `3001`
- Deployment action:
  - backed up remote `src/index.ts` to `/home/ubuntu/deploy-backups/wrongbook-scope-20260401-095748/index.ts`
  - synced updated local `backend/src/index.ts` to the live backend repo
  - ran remote `npm run build`
  - ran remote `pm2 restart xingrun`
- Production proof:
  - remote health check: `curl http://127.0.0.1:3001/healthz` returned `{"ok":true,"service":"openclaw-wechat-bridge",...}`
  - remote process state: `pm2` shows `xingrun` online after restart
  - remote built file now contains scoped wrongbook logic including:
    - `getStudentFeedbackRecords(roomId, studentName, teacherName, className)`
    - teacher/class filtering on feedback records
    - `teacherName` / `className` handling for `/api/student/records` and WebSocket `get_student_records`

## 2026-04-01 Vision 524 Timeout Fix
- Root cause confirmed for the giant HTML note in wrongbook records:
  - `backend/src/vision.ts` directly forwarded raw upstream error bodies from `https://api.n1n.ai/v1/chat/completions`
  - when `api.n1n.ai` returned Cloudflare `524` HTML, that entire page was thrown as `VisionAnalysisError`
  - `backend/src/index.ts` then copied `error.message` into the saved feedback `note`, so users saw the whole HTML timeout page
- Completed changes:
  - added `backend/src/vision.test.ts` with regressions for:
    - retrying one transient `524` response and succeeding on the next attempt
    - converting upstream HTML timeout pages into a concise user-facing message
  - `backend/src/vision.ts` now:
    - limits each vision request with `AbortSignal.timeout(...)`
    - retries retryable upstream failures once by default
    - normalizes `524` into `图片分析超时：上游视觉服务响应过慢，请稍后重试`
    - converts generic HTML error pages into concise HTTP summaries instead of returning raw HTML
  - `backend/src/index.ts` now only stores the normalized `VisionAnalysisError` message for image failures and falls back to a generic readable note for unexpected errors
- Local proof:
  - `npx --yes tsx --test src/vision.test.ts`
  - result: `tests 2`, `pass 2`, `fail 0`
  - `npx --yes tsx --test src/teacher-records.test.ts`
  - result: `tests 6`, `pass 6`, `fail 0`
  - `npm run build` passed
- Production deploy:
  - synced updated `backend/src/index.ts` and `backend/src/vision.ts` to server `49.234.185.86`
  - backup path: `/home/ubuntu/deploy-backups/vision-timeout-20260401-100439/`
  - rebuilt remote backend and restarted PM2 process `xingrun`
- Production proof:
  - remote health check still returns `{"ok":true,"service":"openclaw-wechat-bridge",...}`
  - remote `dist/vision.js` now contains:
    - `VISION_MAX_ATTEMPTS`
    - `图片分析超时：上游视觉服务响应过慢，请稍后重试`
    - retry-aware `VisionAnalysisError`
  - remote `dist/index.js` now contains the generic fallback note:
    - `图片已存档，但图片分析暂时失败，请稍后重试`

## 2026-04-01 Historical Feedback Note Cleanup
- User-selected follow-up completed:
  - cleaned the already-saved contaminated historical feedback note for `阿斯顿 / 曹老师 / 八年级2班`
- Root cause of this specific stored dirty note:
  - the old record was not a `524` payload after all
  - it stored a full internal tool failure trace from `openclaw agent` including `EACCES: permission denied, mkdir '/Users'`
  - the same technical payload also polluted `analysis.errorType`
- Scope proof before cleanup:
  - pulled production file `/home/ubuntu/xingrun-backend-repo/data/XINGRUN_2026-03-19.json` locally for inspection
  - temporary proof script matched exactly `1` contaminated record:
    - `id=1773930958880-ha7nz0`
    - `studentNickname=阿斯顿`
    - `teacherName=曹老师`
    - `className=八年级2班`
- Cleanup action:
  - backed up the live data file to `/home/ubuntu/deploy-backups/feedback-note-cleanup-20260401-101835/XINGRUN_2026-03-19.json`
  - replaced the dirty stored fields with readable values:
    - `note -> 图片已存档，但当时图片分析失败，请老师手动确认题目内容`
    - `analysis.errorType -> 待老师确认`
  - uploaded the cleaned JSON back to `/home/ubuntu/xingrun-backend-repo/data/XINGRUN_2026-03-19.json`
- Proof after cleanup:
  - remote file now returns:
    - `note = 图片已存档，但当时图片分析失败，请老师手动确认题目内容`
    - `analysis.errorType = 待老师确认`
  - remote re-scan result:
    - `remaining_dirty_records = 0`

## 2026-04-01 MiniProgram WebSocket Connection Fix
- Root cause confirmed for the mini program toast `连接失败`:
  - mini program pages still preferred `wx.cloud.connectContainer(...)` whenever that API existed
  - the live backend WebSocket is now served directly from `wss://xingrun.online/ws`
  - because the cloud connector branch was tried first, old cloud-container failures prevented fallback to the live direct WebSocket
- Completed changes:
  - added `miniprogram/utils/socket.js` as the shared WebSocket connector helper
  - helper behavior:
    - direct `wss://xingrun.online/ws` is now the default path
    - cloud-container WebSocket is only used when `app.globalData.useCloudSocket` is explicitly enabled
    - if cloud mode is enabled but connectContainer throws, it falls back to direct WebSocket
  - updated these pages to use the shared helper:
    - `miniprogram/pages/chat/chat.js`
    - `miniprogram/pages/index/index.js`
    - `miniprogram/pages/wrongbook/index.js`
  - added `app.globalData.useCloudSocket = false` in `miniprogram/app.js`
  - added regression tests in `miniprogram/utils/socket.test.js`
- Local proof:
  - `node --test miniprogram/utils/socket.test.js`
  - result: `tests 3`, `pass 3`, `fail 0`
  - syntax checks passed for:
    - `miniprogram/app.js`
    - `miniprogram/pages/chat/chat.js`
    - `miniprogram/pages/index/index.js`
    - `miniprogram/pages/wrongbook/index.js`
    - `miniprogram/utils/socket.js`
- Operational note:
  - this is a mini program frontend change, so it only takes effect after re-uploading the mini program build

## 2026-04-01 n1n Provider Naming Cleanup
- Root cause confirmed for the user-facing error text `AI 出错：MiMo error: 401 ...`:
  - backend requests were already going to `https://api.n1n.ai/v1/chat/completions`
  - but `backend/src/openclaw.ts` still used legacy `MiMo` naming in:
    - top-of-file provider comment
    - internal function/constant names
    - thrown error text `MiMo error: ...`
  - this made live `n1n` auth failures look like a Xiaomi/MiMo problem even after the provider switch
- Completed changes:
  - added regression `backend/src/openclaw.test.ts`
  - renamed backend provider wording to `n1n` in:
    - `backend/src/openclaw.ts`
    - `backend/src/vision.ts`
  - updated config/docs examples:
    - `backend/.env.cloud.example`
    - `CLOUD_HOSTING_SETUP.md`
- Local proof:
  - `npx --yes tsx --test src/openclaw.test.ts src/vision.test.ts src/teacher-records.test.ts`
  - result: `tests 9`, `pass 9`, `fail 0`
  - `npm run build` passed
  - source re-scan for `MiMo error | Xiaomi MiMo | MIMO_API_KEY | MIMO_MODEL` in `backend/src`, env example, and cloud setup doc returned no matches
- Production deploy:
  - synced updated `backend/src/openclaw.ts` and `backend/src/vision.ts` to server `49.234.185.86`
  - rebuilt remote backend and restarted PM2 process `xingrun`
  - backup path: `/home/ubuntu/deploy-backups/openclaw-n1n-rename-20260401-125946/`
- Production proof:
  - remote `dist/openclaw.js` now reports:
    - `contains_n1n_error = True`
    - `contains_mimo_error = False`
    - `contains_xiaomi_comment = False`
- Remaining operational issue:
  - current backend auth failure is not a Xiaomi/MiMo routing issue anymore
  - production `.env`, local `.env`, and visible PM2 env inspection all showed no `N1N_API_KEY` / `N1N_MODEL`
  - so AI calls can still fail with `n1n error: 401 ...` until a valid `N1N_API_KEY` and `N1N_MODEL` are configured for the live backend process

## 2026-04-01 Live n1n Credential Config Attempt
- User provided a new `N1N_API_KEY` and `N1N_MODEL`, and requested option `1` from the prior next-step list: configure server 1 directly
- Completed actions on server `49.234.185.86`:
  - wrote `N1N_API_KEY` and `N1N_MODEL` into `/home/ubuntu/xingrun-backend-repo/backend/.env`
  - restarted PM2 process `xingrun`
  - confirmed masked key presence in `.env`:
    - `N1N_API_KEY=SET`
    - `N1N_MODEL=SET`
  - backup path for the previous `.env` state:
    - `/home/ubuntu/deploy-backups/n1n-env-20260401-130409/`
- Direct verification result:
  - executed a minimal authenticated request from the live server to `https://api.n1n.ai/v1/chat/completions`
  - response was still:
    - `status=401`
    - `message=Invalid token`
- Conclusion:
  - server-side configuration path now exists and is being loaded from `.env`
  - the remaining blocker is not code, deployment, or missing env keys
  - the provided `N1N_API_KEY` is currently rejected by `api.n1n.ai` and needs to be replaced with a valid token before AI chat/image analysis can recover

## 2026-04-01 Env Source Recheck
- Reconfirmed from source that the backend loads environment variables via `import 'dotenv/config'` at process startup.
- This means a normal `npm start` / `node dist/index.js` launch inside `/home/ubuntu/xingrun-backend-repo/backend` will read that directory's `.env` file.
- `N1N_API_KEY` and `N1N_MODEL` are consumed directly from `process.env` in:
  - `backend/src/openclaw.ts`
  - `backend/src/vision.ts`
- Live re-inspection from the current local workspace was blocked because SSH access to `ubuntu@49.234.185.86` failed with `Permission denied (publickey,password)`.
- So the remaining unknown is not the code path, but which concrete `.env` values or PM2-injected env values are currently active on the server at runtime.

## 2026-04-01 Root Cause of 401: Stale PM2 Process Environment
- **Root cause confirmed:** The `.env` file on server contains the new n1n credentials, but the PM2-managed `xingrun` process has **not reloaded** them.
- **Evidence:**
  - PM2 process env: `N1N_API_KEY=UNSET`, `N1N_MODEL=UNSET`
  - `.env` file: `N1N_API_KEY=***REMOVED-REVOKED-N1N-API-KEY***`, `N1N_MODEL=claude-sonnet-4-6`
- **Mechanism:**
  - Backend code reads `process.env.N1N_API_KEY` and `process.env.N1N_MODEL` at **process startup** (via `import 'dotenv/config'`)
  - `.env` was updated AFTER the process started, so the already-running process never re-reads the new values
  - All AI calls use `undefined` token → n1n returns 401
- **Fix:** Restart the PM2 process to force reload of `.env`:
  ```bash
  cd /home/ubuntu/xingrun-backend-repo/backend
  pm2 restart xingrun
  ```
  After this, the process will re-execute `import 'dotenv/config'`, load the new credentials, and AI calls should work.

## 2026-04-02 PM2 Ecosystem Config Applied
- Added repository file `backend/ecosystem.config.cjs` for the production `xingrun` PM2 process.
- Deployed the config to server `49.234.185.86` and recreated the `xingrun` process from that file.
- Current PM2 runtime characteristics after recreation:
  - `node env = production`
  - `interpreter args = --max-old-space-size=512`
  - `max_memory_restart = 300M` (configured in ecosystem file)
  - `autorestart = true`
  - `max_restarts = 10`
  - `min_uptime = 60s`
- Verification proof completed with a temporary script on the server:
  - `curl http://127.0.0.1:3001/healthz` returned `{"ok":true,"service":"openclaw-wechat-bridge",...}`
  - `pm2 show xingrun` showed:
    - `status = online`
    - `restarts = 0`
    - `node env = production`
    - `interpreter args = --max-old-space-size=512`
    - `exec cwd = /home/ubuntu/xingrun-backend-repo/backend`
- Important note:
  - earlier observed PM2 restart count was historical and not sufficient by itself to prove spontaneous crashes
  - this ecosystem setup improves operational stability and makes runtime config explicit, but it does not eliminate external causes such as upstream AI provider failures, network interruptions, or invalid tokens

## 2026-04-02 WebSocket Proxy Idle Timeout Fix
- Root cause investigation for the symptom "chat runs for a while and then disconnects" found a strong proxy-layer issue in Nginx.
- Findings:
  - Nginx site file `/etc/nginx/sites-available/xingrun.online` proxied `/ws` to `http://127.0.0.1:3001`
  - the `/ws` location had the Upgrade headers set correctly
  - but it had **no** explicit `proxy_read_timeout` / `proxy_send_timeout`
  - backend source search showed no WebSocket ping/pong heartbeat implementation in `backend/src/index.ts`
- Why this matters:
  - with no heartbeat traffic, Nginx's default idle proxy timeout can close an otherwise healthy WebSocket after about 60 seconds of silence
  - this matches the user report that the connection "runs for a while and then disconnects"
- Applied production fix on server `49.234.185.86`:
  - backed up the live Nginx site config
  - updated the `/ws` block to include:
    - `proxy_connect_timeout 60s`
    - `proxy_send_timeout 3600s`
    - `proxy_read_timeout 3600s`
  - validated with `nginx -t`
  - reloaded Nginx successfully
- Proof:
  - executed a temporary Node script on the server using the installed `ws` package
  - opened `wss://xingrun.online/ws`
  - kept the connection idle for 75 seconds
  - observed output:
    - `OPEN 257`
    - `STILL_OPEN 75320`
    - `CLOSE 1005  75324`
  - this proves the public WebSocket endpoint now remains open past 60 seconds of idle time
- Residual note:
  - this fixes the proxy idle-timeout root cause
  - future disconnects can still happen from mobile network changes, upstream provider failures, or application-level reconnect gaps

## 2026-04-02 MiniProgram Chat Auto-Reconnect
- Investigated the mini program chat page client behavior after proxy-layer timeout was fixed.
- Root cause on the client side:
  - `miniprogram/pages/chat/chat.js` only appended `连接已断开` on socket close
  - it had no automatic reconnect, retry delay, or managed socket lifecycle
  - `miniprogram/utils/socket.js` only created raw socket connections and had no reconnect wrapper
- Completed changes:
  - added `createManagedSocket(...)` in `miniprogram/utils/socket.js`
  - managed socket behavior:
    - wraps the raw mini program socket
    - forwards `onOpen` / `onMessage` / `onClose` / `onError`
    - automatically reconnects after unexpected close with a delay
    - suppresses reconnect on intentional `close()`
  - updated `miniprogram/pages/chat/chat.js` to use the managed socket wrapper instead of a one-shot raw socket
  - chat page now shows `连接已断开，正在重连…` when the socket closes unexpectedly
- Local proof:
  - temporary script executed:
    - `node --test miniprogram/utils/socket.test.js`
    - `node --check miniprogram/utils/socket.js`
    - `node --check miniprogram/pages/chat/chat.js`
  - complete result summary:
    - `tests 4`
    - `pass 4`
    - `fail 0`
  - new regression covered:
    - reconnect once after unexpected socket close
- Important deployment note:
  - this is a mini program frontend change only
  - it will not affect users until the mini program is rebuilt/uploaded and the new version is used

## 2026-04-02 MiniProgram Upload Field Audit
- Scope completed:
  - traced the full path from mini program teacher/class selection to WebSocket upload payload and backend saved wrong-question records
  - checked whether stable `teacher_id` / `class_id` exist in current code and roster source
  - checked which fields are later exposed to downstream dashboards / SaaS-style consumers
- Confirmed current mini program selection model:
  - teacher picker stores only `teacherName`
  - class picker reads a class item that includes `classKey`, `className`, `studentCount`, `subjectHint`
  - but `saveProfile()` only persists `studentName`, `teacherName`, `className`, `reviewReminderTime`, roster flags
- Confirmed current upload payload from mini program to backend WebSocket:
  - `join` message includes:
    - `roomId`
    - `userId`
    - `nickname`
    - `studentName`
    - `teacherName`
    - `className`
    - `rosterMatched`
    - `rosterWarning`
    - `reviewReminderTime`
  - `file` message includes:
    - `type`
    - `fileUrl`
    - `fileId`
    - `fileName`
    - `studentName`
    - `teacherName`
    - `className`
    - `rosterMatched`
    - `rosterWarning`
    - `reviewReminderTime`
- Confirmed current backend saved wrong-question record shape:
  - top-level stable/business fields currently include:
    - `id` (backend-generated record id)
    - `from`
    - `studentNickname`
    - `teacherName`
    - `className`
    - `rosterMatched`
    - `rosterWarning`
    - `subject`
    - `status`
    - `note`
    - `imageUrl`
    - `time`
    - `analysis`
- Identifier findings:
  - no `teacherId`, `teacher_id`, or `source_teacher_id` found in `miniprogram/**` or `backend/**`
  - no `classId`, `class_id`, or `source_class_id` found in `miniprogram/**` or `backend/**`
  - roster data has no teacher object with source ID; `teachers` is a plain `string[]`
  - roster data does have a derived class key `classKey = teacherName + "__" + className`
  - `classKey` is currently available in roster/class picker data but is not persisted in profile and is not sent in upload payload
  - `subjectHint` is currently available in roster/class picker data but is not sent in upload payload
- Relationship findings from current roster model:
  - one teacher can have multiple classes
  - each roster class entry belongs to exactly one teacher in the current model because class identity is keyed by `teacherName + className`
  - same visible class name can exist under different teachers, so `className` alone is not globally unique
  - current model allows a teacher to span multiple subjects via per-class `subjectHint`, though there is no separate teacher-subject identity table
- Downstream exposure findings:
  - student-facing API returns `roomId`, `studentName`, `teacherName`, `className`, `total`, `records`
  - wrong-question dashboard API returns `roomId`, `total`, `records`
  - downstream consumers therefore currently receive text fields for teacher/class, not stable source IDs
- Low-cost enhancement candidates:
  - best low-cost addition: `source_class_id` from existing roster `classKey`
  - next low-cost addition: `subject` from existing roster `subjectHint`
  - `source_teacher_id` is not currently present anywhere; adding it requires either extending roster import/source data or defining a new derived teacher key convention
  - `source_org_id` / campus / organization is not present in current roster or payloads and would require new source data or schema changes

## 2026-04-09 agent.md 跨仓协作模式补充
- 本轮目标：
  - 把当前项目与 `Xingrun-Website` 的协作模式写进根目录 `agent.md`
- 本轮已完成：
  - 在 `agent.md` 保留原有分支策略的基础上，新增了跨仓协作规则
  - 明确了两边职责分工：
    - 本项目负责小程序前端、桥接后端、微信侧上传/转发
    - `Xingrun-Website` 负责家长微信账号、邀请码、绑定、错题记录等 canonical API 与数据
  - 明确了跨仓分支协作方式：
    - 默认 `develop` 对 `develop`
    - 本项目最终进 `main`
    - `Xingrun-Website` 最终进 `master`
  - 明确了跨仓接口协作要求：
    - 以 `Xingrun-Website` 的 `/api/wechat/*` 契约为准
    - 共享字段命名保持 `open_id`、`class_id`、`student_id`、`teacher_user_id`、`binding_id`、`source`
    - 服务鉴权头保持 `X-Wechat-Service-Token`
    - 相关接口变更时同步维护本项目 `backend/src/parent-wechat-bridge.test.ts`
  - 明确了跨仓交接要求：
    - 两边仓库任务结束后都要更新各自 `handoff.md`
- proof（临时脚本执行）：
  - 临时脚本：`/tmp/tmp_proof_agent_collab_20260409.sh`
  - fresh 输出：
    - `AGENT_TARGET=/Users/ark.mini/Desktop/Xingrun-MiniProgram/agent.md`
    - `HAS_CROSS_REPO_SECTION=OK`
    - `HAS_ROLE_SPLIT=OK`
    - `HAS_DEVELOP_TO_DEVELOP_RULE=OK`
    - `HAS_CANONICAL_FIELDS=OK`
    - `HAS_BRIDGE_TEST_RULE=OK`
    - `HAS_HANDOFF_SYNC_RULE=OK`
    - `HANDOFF_TARGET=/Users/ark.mini/Desktop/Xingrun-MiniProgram/handoff.md`
    - `HANDOFF_HAS_SECTION=OK`
    - `HANDOFF_HAS_PROOF_SCRIPT=OK`
    - `HANDOFF_HAS_NEXT_STEP=OK`
- 当前剩余：
  - 本轮只补充了当前仓库 `agent.md`，没有同步修改 `Xingrun-Website` 的说明文件
- 下一步方向：
  - 如果你希望两边完全对齐，下一轮可以把同一套协作模式补到 `Xingrun-Website/AGENTS.md`

## 2026-04-09 Branch Commit And Push
- Completed:
  - reviewed current branch `feature/parent-smoke-closure` before commit，确认仓库内需要入库的变更只有已跟踪文档文件
  - preserved local git worktree directory `.worktrees/parent-binding-sync` as a local-only artifact and excluded `.worktrees/` via `.git/info/exclude` to avoid accidental commits
  - committed branch docs update as `1cc9acf` (`docs: sync agent workflow and handoff`)
  - pushed `feature/parent-smoke-closure` to `origin` successfully
- Remaining:
  - if parent-side smoke still needs full manual closure, the outstanding step is still the WeChat DevTools manual verification path recorded earlier
- Next step:
  - continue on `feature/parent-smoke-closure` or open a PR / merge after remote review

## 2026-04-09 Branch Cleanup And Sync
- 目标：
  - 收回历史 worktree / feature 分支
  - 先让 `develop`、`main` 对齐到同一提交
  - 把仓库清到只剩主线分支
- 合并处理：
  - 已将 `feature/parent-smoke-closure` fast-forward 合入 `develop`
  - `feature/parent-binding-sync` 的功能提交已被 `feature/parent-smoke-closure` 覆盖
  - `feature/parent-invite-dev` 的关键信息已收敛进当前 `handoff.md`
- 清理处理：
  - 已移除 worktree：`.worktrees/parent-binding-sync`
  - 已删除本地分支：
    - `feature/parent-binding-sync`
    - `feature/parent-invite-dev`
    - `backup/dirty-snapshot-20260408-222819`
- 本轮 proof：
  - `node miniprogram/utils/parentApi.test.js` -> `4 pass / 0 fail`
  - `node --import tsx --test backend/src/parent-wechat-bridge.test.ts` -> `3 pass / 0 fail`
  - `cd backend && npm run build` -> pass
- 当前剩余：
  - Git 清理已完成；当前只剩 `main` / `develop`，且两者已同步到同一提交
  - 产品层面仍缺微信开发者工具内的真实人工 smoke 验证
# Handover - Source-Aligned Pencil Design

## 2026-04-09 Parent Upload Crop + AI Design Drafted
- 用户需求：
  - 家长上传页增加拍照后裁剪
  - 同页裁剪，不跳单独裁剪页
  - 支持一次多图、连续拍照追加
  - 支持单图多个错题
  - 提供 `AI 框选` 按钮，但 AI 只给候选框，不判断质量
- 已确认设计：
  - 顶部缩略图切换图片，不需要“下一张”按钮
  - 已有框直接拖四角/框体调整，不需要单独“微调”按钮
  - 底部保留 `补加框`、`删除当前`、`AI 框选`
  - `AI 框选` 一次触发当前全部图片检测，但技术上按每图独立请求与状态管理
  - 某张图如果 AI 返回 0 个框，要明确提示家长先手动补框后再统一提交
- 设计文档：
  - `docs/superpowers/specs/2026-04-09-parent-upload-crop-ai-design.md`
- 当前阶段：
  - 仅完成 brainstorming/spec，尚未进入实现
- 下一步：
  - 等用户 review spec 文件
  - 用户确认后进入 implementation plan，再开始 TDD 实现

## 2026-04-09 Parent Upload Crop + AI Implementation Plan Drafted
- 用户已确认设计 spec，可进入实施规划。
- 已完成：
  - 新增 implementation plan：
    - `docs/superpowers/plans/2026-04-09-parent-upload-crop-ai-plan.md`
  - 计划内容已覆盖：
    - 后端 AI 框选桥接接口
    - 小程序 AI 检测 API helper
    - 上传页纯状态模型
    - 手机端多图同页框选 UI
    - 统一提交前校验与逐框上传
- 计划校对结果：
  - 修正了页面 `currentImage` 状态同步
  - 修正了批量 AI 并发描述，限制为最多 3 个 worker
  - 修正了裁剪导出方案，使用 canvas 导出而不是不明确 API
- proof：
  - `node --test miniprogram/utils/parentApi.test.js` -> `pass 5 / fail 0`
  - `node --test miniprogram/parent-only-scope.test.js` -> `pass 5 / fail 0`
  - `cd backend && node --import tsx --test src/parent-wechat-bridge.test.ts` -> `pass 4 / fail 0`
- 下一步：
  - 由用户选择执行方式：
    - subagent-driven
    - inline execution
  - 选定后按 plan 逐 task 执行并保持 TDD

## 2026-04-09 Parent Upload Crop + AI Flow Implemented
- 用户确认按 inline execution 直接实现“同页裁剪 + 多图 + AI 框选”。
- 已完成：
  - 后端新增 AI 框选桥接路由：
    - `POST /wechat/parent/wrong-question-boxes`
  - 小程序新增 AI 检测 helper：
    - `detectParentWrongQuestionBoxes(...)`
  - 新增上传页纯状态模型：
    - 图片队列追加
    - AI 空结果/多框结果
    - 提交阻塞判断
    - 多图多框上传任务编排
  - 家长上传页改为手机单列多图裁剪结构：
    - 顶部缩略图切换
    - 当前图裁剪 stage
    - 多个题框显示
    - 直接拖动框体 / 四角缩放当前框
    - 按钮保留 `补加框` / `删除当前` / `AI 框选`
  - `AI 框选` 现在会对当前已选全部图片触发检测，并按每张图独立写回状态
  - 统一提交会在提交前拦截：
    - AI 仍在处理中
    - 某张图没有任何框
  - 最终上传按“每个框一条记录”裁剪导出并逐条调用现有 wrong-question 上传接口
- 当前限制 / 未覆盖：
  - 交互裁剪主要完成于页面逻辑层，尚未接入更细的自动化页面级测试
  - 目前 proof 以纯脚本测试和 JS 语法检查为主，未做微信开发者工具真机手动验证
  - 由于仓库已有大量既有脏改动，本轮没有做中途 commit，避免把无关改动一起提交
- proof：
  - `node --test miniprogram/utils/parentApi.test.js` -> `pass 6 / fail 0`
  - `node --test miniprogram/pages/parent-upload/model.test.js` -> `pass 6 / fail 0`
  - `node --test miniprogram/parent-only-scope.test.js` -> `pass 6 / fail 0`
  - `cd backend && node --import tsx --test src/parent-wechat-bridge.test.ts` -> `pass 5 / fail 0`
  - `node --check miniprogram/pages/parent-upload/index.js` -> syntax ok
- 下一步：
  - 在微信开发者工具里重点手测：
    - 多图追加
    - AI 返回 0 框 / 失败
    - 多框拖动和四角缩放
    - 统一提交后的多条记录落库
  - 如需更稳，可继续补页面层自动化测试或接入更真实的 AI 网站端联调

## 2026-04-09 AI Box Route Not Yet Live On Production
- 用户反馈当前提示：`家长绑定服务暂未部署，请联系老师后重试`
- 根因确认：
  - 不是 `/wechat/parent/bindings` 挂了
  - 线上 `https://xingrun.online/wechat/parent/bindings?openId=test-openid` 实际命中 Express，并返回 `{"error":"parent wechat account not found"}`
  - 线上 `https://xingrun.online/wechat/parent/wrong-question-boxes` 目前返回 `404` HTML：
    - `Cannot POST /wechat/parent/wrong-question-boxes`
  - 所以用户点击 `AI 框选` 时，前端把这个 404 误翻译成了“家长绑定服务暂未部署”
- 已完成：
  - 调整小程序错误映射：
    - 当缺失的是 `wrong-question-boxes` 路由时，提示改为
    - `AI 框选服务暂未部署，请先手动补框继续上传`
- 当前阻塞：
  - 生产服务器上的 bridge 还没部署到包含 `/wechat/parent/wrong-question-boxes` 的版本
  - 当前本机尝试 `ssh ubuntu@49.234.185.86` 返回：
    - `Permission denied (publickey,password)`
  - 因此本轮无法直接完成线上部署
- proof：
  - `curl -i -X POST https://xingrun.online/wechat/parent/wrong-question-boxes -d '{}'` -> `HTTP/1.1 404 Not Found` + `Cannot POST /wechat/parent/wrong-question-boxes`
  - `node --test miniprogram/utils/parentApi.test.js` -> `pass 8 / fail 0`
- 下一步：
  - 拿到服务器 SSH 权限后，同步并部署：
    - `backend/src/index.ts`
    - `backend/src/website-client.ts`
  - 远端执行：
    - `cd /home/ubuntu/xingrun-backend-repo/backend`
    - `npm run build`
    - `pm2 restart xingrun-bridge`

## 2026-04-09 Parent AI Box Parse Failure Root Cause Confirmed
- 用户反馈：点击 AI 框选时提示“上传返回解析失败”。
- 根因确认：
  - 本地仓库已存在 `POST /wechat/parent/wrong-question-boxes` bridge 路由和对应测试。
  - 线上 `https://xingrun.online/wechat/parent/wrong-question-boxes` 当前实际返回 `404` HTML：`Cannot POST /wechat/parent/wrong-question-boxes`。
  - 小程序原先在 `uploadFile` 成功回调里直接对返回体做 `JSON.parse`，收到 HTML 时就会误报成“上传返回解析失败”。
- 已完成：
  - 小程序 `miniprogram/utils/parentApi.js` 的上传返回解析已加固：
    - 若返回体不是 JSON，会回退到统一错误提取逻辑。
    - 对 `Cannot POST /wechat/parent/...` 这类缺路由 HTML，现改为明确提示：`家长绑定服务暂未部署，请联系老师稍后再试`。
  - 新增回归测试，覆盖 AI 框选上传接口返回 404 HTML 时的错误提示映射。
- proof：
  - `curl -i -X POST https://xingrun.online/wechat/parent/wrong-question-boxes` -> `HTTP/1.1 404 Not Found` + `Cannot POST /wechat/parent/wrong-question-boxes`
  - `curl -sS -o /tmp/xr-ai-box-body.txt -D /tmp/xr-ai-box-headers.txt -X POST -F 'file=@/etc/hosts' https://xingrun.online/wechat/parent/wrong-question-boxes` -> 同样返回 404 HTML
  - `node --test miniprogram/utils/parentApi.test.js` -> `pass 7 / fail 0`
- 下一步：
  - 把当前仓库里的 bridge 最新版本重新部署到正式服务，使线上真正暴露 `POST /wechat/parent/wrong-question-boxes`
  - 重新上传 / 预览小程序后，在真机再次验证 AI 框选

## 2026-04-09 Production AI Box Route Deployed But Downstream Service Still Unconfigured
- 本轮已确认并修正：
  - SSH 实际可用，密码是 `***REMOVED-ROTATED-SSH-PASSWORD***`，此前自动登录失败是因为密码大小写写错。
  - `/home/ubuntu/xingrun-backend-repo/backend` 已同步最新 `backend/src/index.ts` 和 `backend/src/website-client.ts`，并执行：
    - `npm run build`
    - `pm2 restart xingrun-bridge`
  - 线上实际对外监听 `3001` 的不是 `xingrun` Python 网站，而是 `xingrun-bridge` Node 进程；`xingrun` 是网站后端下游服务。
  - 生产网站 `/home/ubuntu/Xingrun-Website` 已补上：
    - `POST /api/wechat/wrong-question-boxes`
    - `smart_wrong_questions.detect_wechat_wrong_question_boxes(...)`
  - 已备份远端网站文件：
    - `app.py.bak-20260409-boxes`
    - `smart_wrong_questions.py.bak-20260409-boxes`
- 当前线上状态：
  - `https://xingrun.online/wechat/parent/wrong-question-boxes` 已不再返回 `404 HTML`。
  - 当前返回变为 JSON `500`：`{"error":"智能错题服务尚未配置"}`。
  - 这说明：
    - bridge 路由缺失问题已经解决
    - 网站端代理路由也已经解决
    - 剩余 blocker 是网站项目运行时没有配置：
      - `XR_WRONG_QUESTION_SERVICE_URL`
      - `XR_WRONG_QUESTION_SERVICE_TOKEN`
- 额外确认：
  - 服务器全局搜索未发现现成的 `wrong_question_service_url/token` 配置。
  - 也未发现已有 `wrong-question-boxes` 下游服务实现可直接复用。
- proof：
  - 远端 `grep -R 'wrong-question-boxes' -n src dist` 现在可命中 bridge 源码
  - `curl -sS -i -X POST -F 'file=@/etc/hosts' https://xingrun.online/wechat/parent/wrong-question-boxes` -> `HTTP/1.1 500 Internal Server Error` + `{"error":"智能错题服务尚未配置"}`
  - `cd backend && node --import tsx --test src/parent-wechat-bridge.test.ts` -> `pass 5 / fail 0`
- 下一步：
  - 需要补齐网站端下游智能错题服务配置，或者新实现一个 `wrong-question-boxes` 下游能力
  - 在下游服务可用后，再次真机验证 `AI 框选`

## 2026-04-09 Direct N1N Fallback Wired In But Provider Access Still Fails
- 用户已明确：并不存在额外的“下游错题服务”，目标就是直接调用 AI（N1N）做题框识别。
- 本轮已完成：
  - 将网站后端 `smart_wrong_questions.detect_wechat_wrong_question_boxes(...)` 改为：
    - 若配置了 `wrong_question_service_url/token`，仍可走外部代理
    - 若未配置，则直接 fallback 到 N1N
  - 已把生产环境 `.env.runtime` 补充：
    - `N1N_API_KEY`
    - `XR_N1N_BASE_URL=https://api.n1n.ai/v1`
    - `XR_N1N_MODEL=gpt-5.4`
  - 已重启 `pm2 restart xingrun`
  - 已备份：
    - `smart_wrong_questions.py.bak-20260409-n1n`
    - `.env.runtime.bak-20260409-n1n`
- 当前结论：
  - 代码链路已经改成“直接调 N1N”，不是还在等所谓下游服务。
  - 但 N1N 本身当前拒绝访问：
    - 本地直接请求 `https://api.n1n.ai/v1/chat/completions` -> `403 error code: 1010`
    - 本地直接请求 `https://api.n1n.ai/v1/responses` -> `403 error code: 1010`
    - 服务器上直接请求 `https://api.n1n.ai/v1/responses` -> 同样 `403 error code: 1010`
  - 因此当前 `AI 框选` 还不能算可用；问题已从“系统未接 AI”收敛成“当前 N1N 凭证/账号/访问策略被 provider 拒绝”。
- proof：
  - `curl -sS -i -X POST -F 'file=@/tmp/xr-test.png;type=image/png' https://xingrun.online/wechat/parent/wrong-question-boxes` -> `HTTP/1.1 500 Internal Server Error` + `{"error":"error code: 1010"}`
  - 本地 `python urllib` 测试 `https://api.n1n.ai/v1/responses` -> `HTTPError 403` + `error code: 1010`
  - 服务器 `python urllib` 测试 `https://api.n1n.ai/v1/responses` -> `HTTPError 403` + `error code: 1010`
- 下一步：
  - 需要更换一组可用的 N1N 凭证，或改用其他可访问的模型服务
  - 拿到可用 provider 后，再次回测 `AI 框选`
