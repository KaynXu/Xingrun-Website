# Review Generation Information Architecture Design

## Goal

Rename and restructure the current lesson intake area so the product reflects its actual job: turning teacher classroom transcription content into review documents.

## Why This Change

The current split between `添加课程` and `课程列表` describes generic lesson CRUD, but the real workflow is narrower and more valuable:

- teachers upload or paste classroom transcription content
- the system generates a review document
- staff later return to the generated output to view, download, or delete it

The UI should therefore present one business module instead of two unrelated tabs.

## Product Decision

### Module Name

Use `复习生成` as the left sidebar module name.

Reasoning:

- it describes the module as a generation workflow, not generic data entry
- it matches the value users care about most
- it can contain both creation and history without sounding awkward

### Primary Action Name

Use `新建复习文档` as the main CTA.

Reasoning:

- it clearly states the output users will create
- it is more precise than `新建复习` or `添加课程`

### Form Section Title

Use `生成复习文档` as the expanded form area title.

Reasoning:

- the title describes the current task inside the page
- it separates page action from module-level navigation

### History Section Title

Use `历史文档` as the list area title.

Reasoning:

- it is concise and product-oriented
- it works for the current PDF-focused result set

## Information Architecture

### Navigation Structure

Replace the two current lesson navigation entries with a single module:

- `工作台`
- `复习生成`
- `咨询记录`
- `课程日历`
- `班级管理`
- `账号审批`
- `系统设置`

The old `添加课程` and `课程列表` left-sidebar items should be removed.

### Default Entry State

When the user enters `复习生成`, the default page state should show `历史文档` first.

Reasoning:

- the module feels like a stable workspace rather than a one-off form
- users can immediately orient themselves around existing output
- the main create action remains prominent without forcing a large form on first load

## Interaction Design

### Primary Flow

The confirmed flow is:

1. user enters `复习生成`
2. user sees `历史文档`
3. user clicks `新建复习文档`
4. the page expands an inline form section at the top of the same page
5. the form section title reads `生成复习文档`
6. after successful submission, the form collapses and `历史文档` refreshes

### Form Presentation

Use inline expansion inside the same page instead of a drawer or full-screen route.

Reasoning:

- this is the lowest-risk implementation path in the current shell
- users keep the history context visible
- success recovery is straightforward because the page returns naturally to the list view

### Success Behavior

After a successful generation:

- show a clear success message
- collapse the expanded form region
- refresh `历史文档`
- place the newest generated document where the user can immediately find it

### Empty State

When no generated documents exist yet, the page should show an empty state that points users to the confirmed action:

- `还没有复习文档，点击「新建复习文档」开始生成`

## Content Mapping

The current lesson-related labels should be remapped as follows:

- module/tab: `添加课程` + `课程列表` -> `复习生成`
- page primary action: `添加新课程` -> `新建复习文档`
- form heading: `添加新课程` -> `生成复习文档`
- list heading: `课程列表` -> `历史文档`

This change is an information architecture and product-language correction. It does not change the underlying review-document generation workflow.

## Scope Boundaries

Included in this design:

- sidebar/module naming changes for the lesson generation area
- page-level naming changes for entry, form, and history sections
- merging the current two-entry navigation model into one module
- defaulting the page to history-first with inline form expansion

Not included in this design:

- backend API contract changes
- review generation algorithm changes
- PDF format changes
- deeper redesign of lesson metadata fields
- cross-module navigation changes outside this lesson/review area

## Testing Implications

Implementation should verify at minimum:

- the old sidebar entries are removed and replaced by `复习生成`
- the header title for the page reads `复习生成`
- the default state renders `历史文档`
- the main CTA reads `新建复习文档`
- clicking the CTA expands an inline area titled `生成复习文档`
- successful submission collapses the form and refreshes the history list

## Acceptance Criteria

- users no longer see separate `添加课程` and `课程列表` tabs
- users see a single `复习生成` module
- entering the module lands on `历史文档`
- the main create action is labeled `新建复习文档`
- the expanded create area is labeled `生成复习文档`
- the interaction remains within one page and does not open a separate route or overlay
- the naming now matches the actual business workflow of generating review documents from classroom transcription content