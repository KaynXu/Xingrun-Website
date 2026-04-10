# AI Edu Landing Page Design

Date: 2026-03-27
Project: Xingrun-Summary frontend landing page refresh
Status: Approved in conversation, pending implementation

## Context

The current landing page presents the product as a teacher-facing after-class review system. That framing no longer matches the intended brand direction.

The desired public positioning is:

- Xingrun as an AI education solution provider
- Primary audience: B-end teams such as schools, education companies, and teaching organizations
- Real current product anchor: the after-class review system is the only implemented product today
- Planned solution map to express on the landing page:
  - Review system
  - Intelligent mistake notebook
  - International curriculum question bank and auto paper generation
  - Lesson plan and handout generation

The user wants the landing page updated to reflect this broader positioning while preserving the current visual language:

- black background
- blue glow / high-tech accents
- restrained futuristic aesthetic
- large rounded layout blocks
- minimal changes outside the landing page

## Goals

- Reposition the landing page from a single-purpose teacher tool to an AI education solutions brand
- Keep the page credible by anchoring messaging in one implemented flagship product
- Present the other modules as a solution map and expansion direction rather than falsely implying full delivery
- Preserve the existing visual style and page rhythm where possible
- Limit code changes to the landing page and directly related text/icon content

## Non-Goals

- Do not redesign the internal workspace, login flow, sidebar, or operational pages
- Do not rename implemented workspace IA just to match aspirational homepage wording
- Do not introduce unrelated new sections or heavy layout changes that make the site feel like a different product
- Do not claim that all solution modules are already fully shipped

## Approved Positioning

The approved direction is:

`Flagship product + solution map`

Interpretation:

- The homepage should present Xingrun as an AI education solutions provider
- The homepage should clearly imply there is already one working product foundation
- The homepage should show additional modules as a broader solution capability and roadmap
- The tone should feel B2B, not solo-teacher utility software

## Content Strategy

### Brand Identity

Landing page brand name changes from:

- `星润课后复习系统`

to:

- `星润 AI 教育解决方案`

This change applies to the landing page navbar and footer branding. It does not require renaming internal workspace labels in this phase.

### Messaging Principle

The page should communicate:

- we already have one working core product
- we are building toward a broader AI education delivery stack

The copy should avoid two extremes:

- sounding like a single narrow review tool
- sounding like a fully mature multi-product suite that already exists end-to-end

Recommended voice pattern:

- use confident solution language
- keep claims concrete
- describe non-implemented modules as capabilities, directions, or expansion areas

## Page Architecture

Keep the existing three-part landing flow:

1. Hero
2. Core solution modules
3. Delivery process

Keep the existing footer, but update its brand language.

## Section-by-Section Design

### 1. Navbar

Keep the current fixed transparent navbar structure.

Update nav copy to:

- `核心方案`
- `落地流程`
- `关于星润`

Keep the login CTA on the right.

### 2. Hero Section

Preserve:

- full-screen hero
- video background
- strong central typography
- black / blue / glow atmosphere

Shift content from teacher productivity framing to B-end solution framing.

Recommended hero eyebrow:

- `AI EDU SOLUTION FOR TEAMS`

Recommended headline:

- `为学校与教育机构打造`
- `可落地的 AI 教学方案`

This is the preferred direction because it is stronger for B-end teams and more grounded than an English-first concept headline.

Recommended supporting copy:

- `以课后复习系统为落地起点，延展智能错题本、国际课程题库与自动组卷、教案讲义生成等核心模块，帮助教学团队建立更高效的内容生产与交付链路。`

CTA strategy:

- primary CTA: `进入工作台`
- secondary CTA: `查看方案版图`

The secondary CTA should no longer suggest an unavailable polished video demo if that does not exist.

### 3. Core Solution Modules Section

Keep the current bento-like layout rhythm:

- one large flagship card
- two smaller cards
- one medium horizontal card

This preserves the existing composition while upgrading the meaning of the cards from features to solution modules.

Section heading:

- `重构 AI 教学交付`

Section subheading:

- `从单点工具走向可扩展的教育解决方案版图。`

#### Module Card 1: Flagship Product

Title:

- `课后复习系统`

Body:

- `从课堂录音、笔记到结构化复习资料与题目生成，已经形成可落地的教学交付闭环。`

Suggested tags:

- `课堂分析`
- `复习资料生成`
- `教学交付`

Status role:

- this is the implemented flagship product

#### Module Card 2: Intelligent Mistake Notebook

Title:

- `智能错题本`

Body:

- `沉淀学生高频错误与知识薄弱点，形成可持续追踪的个性化复习资产。`

Status role:

- present as a solution capability / expansion module

#### Module Card 3: International Curriculum Question Bank / Auto Paper Generation

Title:

- `国际课程题库 / 自动组卷`

Body:

- `面向 AP、A-Level、IB 等国际课程场景，支持题目整理、标签化管理与自动组卷。`

Status role:

- present as a solution capability / expansion module

#### Module Card 4: Lesson Plan and Handout Generation

Title:

- `教案与讲义生成`

Body:

- `将课程目标、知识结构与教学素材快速转化为讲义、课堂提纲和教研交付内容。`

Status role:

- present as a solution capability / expansion module

### 4. Delivery Process Section

Keep the current three-step structure and timeline-like composition.

Update heading to:

- `三步搭建 AI 教学交付链路`

Steps:

1. `教学素材接入`
   - `接入课堂录音、笔记、题目与课程资料。`
2. `AI 模块处理`
   - `按复习、错题、组卷、讲义等场景完成结构化生成。`
3. `面向团队交付`
   - `输出给教师、教研与教学运营团队，形成标准化内容资产。`

This section should feel operational and B2B rather than oriented around a solo teacher workflow.

### 5. Footer

Keep the structure.

Update footer brand name to:

- `星润 AI 教育解决方案`

Add / replace the short brand statement with:

- `面向学校、机构与教学团队，构建从内容生成到教学交付的 AI 能力底座。`

Keep legal links as-is unless implementation constraints suggest otherwise.

## Icon and Visual Mapping

The visual system should stay restrained and consistent with the existing page.

Recommended icon mapping:

- `课后复习系统`: `FileText` or `BookOpen`
- `智能错题本`: `CircleAlert`, `ClipboardList`, or equivalent close Lucide choice already available / easy to add
- `国际课程题库 / 自动组卷`: `Database`, `Library`, or `Layers`
- `教案与讲义生成`: `ScrollText`, `FileOutput`, or `PenTool`

Guidelines:

- icons should improve scanning, not decorate for their own sake
- preserve current card shape, spacing, and glow hierarchy
- prefer changing semantics over changing layout

## Implementation Scope

Allowed implementation changes:

- landing page navbar branding and nav labels
- hero copy and CTA labels
- feature/module section titles, descriptions, labels, icons
- process section heading and step copy
- footer brand wording and short description

Avoid in this phase:

- workspace renaming
- dashboard changes
- settings / quiz / lesson flow changes
- unrelated visual refactors

## Content Guardrails

To keep the page aspirational but credible:

- use direct language for the implemented review system
- use broader solution language for the planned modules
- avoid UI copy that explicitly states all modules are already available inside the product today

Good examples of acceptable framing:

- `核心模块`
- `方案版图`
- `能力扩展`
- `面向...场景`

Avoid:

- `全面上线`
- `现已全部支持`
- `完整产品矩阵已交付`

## Verification Notes for Implementation

When implementation starts, verify:

- landing page still matches the current black / blue brand style
- the page still feels cohesive with the existing product
- all changes are restricted to landing-page-related components
- buttons still lead to valid destinations
- no copy on the page accidentally overclaims implementation status

## Summary

This refresh should transform the homepage from a narrow teacher review tool narrative into a B-end AI education solutions narrative, while staying honest about product maturity.

The final intended impression is:

- Xingrun has one real flagship product
- Xingrun is building toward a broader AI education delivery stack
- Xingrun is a serious, design-conscious, solution-oriented brand for education teams
