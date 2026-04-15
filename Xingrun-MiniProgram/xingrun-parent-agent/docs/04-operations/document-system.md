# Document System

## 目标

把项目文档写成可协作、可追踪、可交接的系统，而不是越写越散。

## 文档层级

### 1. Stable Docs

长期稳定，更新频率低。

- `project-brief.md`
- `core-modules.md`

### 2. Working Docs

会随试点推进变化，但仍然是当前事实。

- `a-level-business-pilot.md`
- 后续的 `user-personas.md`
- 后续的 `success-metrics.md`

### 3. Templates

只放可复用格式，不写具体个案结论。

- `preview-task-template.md`
- `exam-review-template.md`
- `weekly-parent-report-template.md`

### 4. References

只做来源映射和原始材料入口，不作为当前结论文件。

## Markdown 使用规则

- 每个文件开头先写用途
- 每个文件第一屏就给结论或结构
- 真实试点进展不要回写进 `project-brief.md`
- 新想法先写进 working doc，确认后再升级进 stable doc
- 文件超过一个主题就拆，不要硬撑长文

## 推荐新增顺序

1. `docs/02-product/user-personas.md`
2. `docs/02-product/success-metrics.md`
3. `docs/04-operations/parent-followup-playbook.md`
4. `docs/03-pilot/business-week-01.md`
