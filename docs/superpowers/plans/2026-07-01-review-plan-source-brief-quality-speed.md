# Review Plan Source Brief Quality Speed Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a structured source-brief layer to review-plan generation so raw transcripts become evidence-backed teaching inputs, teacher requirements affect planning early, regeneration reuses a stable source artifact, and slow LLM review/revision paths are bounded.

**Architecture:** Persist a version-scoped source artifact containing raw source snapshot, cleaned source text, structured source brief, evidence map, and source hash. Insert a source brief node before parent planning, route teacher requirements through source analysis, parent planning, writer, revision, and observability, then use a local-first quality policy with stage-specific LLM timeouts. Regeneration reuses the selected/current version source artifact by default and creates a new version without overwriting previous PDFs.

**Tech Stack:** Python 3, Flask, SQLite, Pydantic, unittest, OpenAI-compatible SDK, Langfuse, Vite, React, TypeScript, node:test, PDF extraction smoke tests.

## Global Constraints

- Source audit: `docs/superpowers/audits/2026-07-01-review-plan-generation-workflow-audit.md`.
- Before implementation, fetch remote metadata, confirm local `develop` matches `origin/develop`, and create the implementation branch from `develop`.
- Do not develop directly on `master` or `develop`.
- Do not commit runtime data files, local DBs, uploads, generated PDFs, zip packages, screenshots, `data/`, `tmp/`, or one-off audio files.
- Regeneration must create a new version and must not overwrite the previous ready PDF.
- Teacher requirements may influence planning and writing, but cannot override factuality, schema, PDF safety, generation options, or quality gate rules.
- Langfuse traces must not include full classroom text, full prompts, raw transcripts, source brief cleaned text, or complete generated PDFs.
- Frontend copy must stay terse. Use compact labels and controls, not explanatory paragraphs.
- Legacy rows with no source artifact must still generate by falling back to `lessons.summary`.
- The first implementation must use existing dependencies. Do not add LangChain, LangGraph, or a new background queue in this PR.

---

## Source Audit

- `docs/superpowers/audits/2026-07-01-review-plan-generation-workflow-audit.md`

## File Structure

- Create `review_plan_workflow/source_brief.py`
  - Owns source text cleaning, evidence slicing, deterministic fallback extraction, source hashes, and source brief Pydantic models.

- Create `review_plan_workflow/nodes/source_brief_builder.py`
  - Workflow node that builds a source brief from `ReviewPlanInput`, `NormalizedBrief`, and generation options.
  - Uses deterministic extraction in this PR to avoid adding another slow LLM stage.
  - Leaves source-brief LLM enrichment out of scope until deterministic metrics prove where it is needed.

- Modify `review_plan_workflow/schemas.py`
  - Add `SourceEvidence`, `SourceKnowledgePoint`, `SourceMethodChain`, `SourceMistake`, `SourceExampleStem`, `SourceTeacherEmphasis`, and `ReviewPlanSourceBrief`.
  - Add `source_brief: Optional[ReviewPlanSourceBrief]` to `SourceSummary`.

- Modify `review_plan_workflow/nodes/__init__.py`
  - Export `source_brief_builder_node`.

- Modify `review_plan_workflow/service.py`
  - Run source brief builder before `source_analyzer_node`.
  - Pass source brief into source analyzer, parent planner, prompt bundle, writer, quality policy, and run storage.

- Modify `review_plan_workflow/nodes/source_analyzer.py`
  - Use source brief title candidates, knowledge points, and evidence map instead of marker-only extraction.

- Modify `review_plan_workflow/nodes/parent_planner.py`
  - Include `user_requirements` and source brief in parent planner payload.

- Modify `review_plan_workflow/nodes/prompt_bundle_builder.py`
  - Include source brief summary and teacher requirements in prompt variables.

- Modify `review_plan_workflow/nodes/plan_generator.py`
  - Prefer source brief and selected evidence snippets over full raw transcript.
  - Keep a legacy raw-summary fallback for rows without source brief.

- Modify `review_plan_workflow/nodes/revision.py`
  - Include source brief summary and teacher requirements in revision payload.

- Create `review_plan_workflow/quality_policy.py`
  - Owns local-first reviewer and revision decisions.
  - Makes LLM reviewer conditional.
  - Caps revision attempts and effective timeout.

- Modify `review_plan_workflow/llm/client.py`
  - Add stage-specific timeout support.
  - Use `client.with_options(timeout=request_timeout, max_retries=0)` when available for review-plan calls.

- Modify `lesson_manager.py`
  - Add `source_text`, `cleaned_source_text`, `source_text_hash`, and `source_brief_json` to `review_plan_versions`.
  - Hydrate these fields on version rows.
  - Add helper to persist source artifacts.

- Modify `app.py`
  - Store source snapshots when creating versions.
  - Use version source artifact during generation.
  - Make regeneration reuse current version source artifact by default.
  - Keep audio transcription raw text as source snapshot, then let source brief builder clean it.

- Modify `review_plan_workflow/observability.py`
  - Add source brief metrics and hashes to traces.
  - Assert no raw source or cleaned text leaks.

- Modify frontend files only where regeneration semantics need to be visible:
  - `frontend/src/features/review-generation/ReviewPlanRegenerateDialog.tsx`
  - `frontend/src/features/review-generation/ReviewGenerationPage.tsx`
  - `frontend/src/features/review-generation/ReviewPlanDetailView.tsx`
  - `frontend/src/features/review-generation/reviewPlanVersions.ts`

- Modify tests:
  - Create `tests/test_review_plan_source_brief.py`
  - Modify `tests/test_review_plan_workflow.py`
  - Modify `tests/test_review_plan_async_api.py`
  - Modify `tests/test_review_plan_version_store.py`
  - Modify `tests/test_review_plan_observability.py`
  - Modify `tests/test_review_plan_evals.py`
  - Modify `frontend/src/review-generation-async.test.tsx`

- Modify `handoff.md`
  - Record implementation result, proof commands, and deploy status.

## Target Data Contracts

`review_plan_workflow/source_brief.py` must expose these names:

```python
SOURCE_BRIEF_SCHEMA_VERSION = "2026-07-01"

def source_text_hash(text: str) -> str:
    """Return sha256:<hex> for trace-safe source identity."""

def clean_source_text(text: str) -> str:
    """Normalize raw classroom text without changing math meaning."""

def build_deterministic_source_brief(
    *,
    raw_text: str,
    subject: str = "",
    topic: str = "",
    weak_points: str = "",
    user_requirements: str = "",
) -> ReviewPlanSourceBrief:
    """Build a best-effort structured source brief without an LLM."""
```

`ReviewPlanSourceBrief` must provide:

```python
class ReviewPlanSourceBrief(BaseModel):
    schema_version: str = SOURCE_BRIEF_SCHEMA_VERSION
    source_text_hash: str = ""
    cleaned_text: str = ""
    lesson_title_candidates: list[str] = Field(default_factory=list)
    knowledge_points: list[SourceKnowledgePoint] = Field(default_factory=list)
    method_chains: list[SourceMethodChain] = Field(default_factory=list)
    common_mistakes: list[SourceMistake] = Field(default_factory=list)
    example_stems: list[SourceExampleStem] = Field(default_factory=list)
    teacher_emphasis: list[SourceTeacherEmphasis] = Field(default_factory=list)
    excluded_noise: list[str] = Field(default_factory=list)
    missing_fields: list[str] = Field(default_factory=list)
    evidence_map: list[SourceEvidence] = Field(default_factory=list)
    confidence: float = 0.0
```

`lesson_manager.py` must expose:

```python
def update_review_plan_version_source_artifact(
    version_id: int,
    *,
    source_text: str,
    cleaned_source_text: str,
    source_text_hash: str,
    source_brief: object,
) -> None:
    """Persist source artifact fields for one review_plan_versions row."""
```

`review_plan_workflow/quality_policy.py` must expose:

```python
def should_run_llm_quality_review(
    *,
    local_quality: QualityReview,
    source_brief: ReviewPlanSourceBrief | None,
) -> bool:
    """Return True when LLM review adds value beyond deterministic checks."""

def max_revision_attempts_for_quality(
    *,
    quality: QualityReview,
    source_brief: ReviewPlanSourceBrief | None,
) -> int:
    """Return 0 or 1 for production revision attempts."""
```

## Task 0: Branch Freshness And Audit Baseline

**Files:**
- Read: `AGENTS.md`
- Read: `handoff.md`
- Read: `docs/superpowers/audits/2026-07-01-review-plan-generation-workflow-audit.md`

**Interfaces:**
- Consumes: existing `develop` branch and audit findings.
- Produces: implementation branch ready for Task 1.

- [ ] **Step 1: Confirm remote freshness**

Run:

```bash
git fetch origin --prune
git switch develop
git pull --ff-only origin develop
git rev-list --left-right --count develop...origin/develop
```

Expected:

```text
0	0
```

- [ ] **Step 2: Create implementation branch**

Run:

```bash
git switch -c codex/review-plan-source-brief-quality-speed
```

Expected:

```text
Switched to a new branch 'codex/review-plan-source-brief-quality-speed'
```

- [ ] **Step 3: Re-read the audit**

Run:

```bash
sed -n '1,260p' docs/superpowers/audits/2026-07-01-review-plan-generation-workflow-audit.md
```

Expected: the audit names all five problem areas: source preprocessing, output quality, speed, teacher prompt integration, and regeneration consistency.

## Task 1: Source Brief Models And Deterministic Extraction

**Files:**
- Create: `review_plan_workflow/source_brief.py`
- Create: `tests/test_review_plan_source_brief.py`
- Modify: `review_plan_workflow/schemas.py`

**Interfaces:**
- Produces: `source_text_hash(text: str) -> str`
- Produces: `clean_source_text(text: str) -> str`
- Produces: `build_deterministic_source_brief(*, raw_text: str, subject: str = "", topic: str = "", weak_points: str = "", user_requirements: str = "") -> ReviewPlanSourceBrief`
- Produces: `ReviewPlanSourceBrief` and nested source evidence models.
- Consumes later: source brief node, source analyzer, parent planner, writer, observability, version storage.

- [ ] **Step 1: Write failing source brief tests**

Create `tests/test_review_plan_source_brief.py`:

```python
import unittest

from review_plan_workflow.source_brief import (
    build_deterministic_source_brief,
    clean_source_text,
    source_text_hash,
)


class ReviewPlanSourceBriefTestCase(unittest.TestCase):
    def test_source_text_hash_is_stable_and_redactable(self):
        first = source_text_hash("动点与立体几何综合")
        second = source_text_hash("动点与立体几何综合")
        other = source_text_hash("一次函数")

        self.assertEqual(first, second)
        self.assertTrue(first.startswith("sha256:"))
        self.assertEqual(len(first), len("sha256:") + 64)
        self.assertNotEqual(first, other)
        self.assertNotIn("动点", first)

    def test_clean_source_text_removes_common_asr_noise_without_destroying_math(self):
        cleaned = clean_source_text(
            "嗯嗯 今天我们讲 动点 与 立体几何。\r\n"
            "然后然后 PA=PB，angle ABC = 60 ^circ。\n\n"
            "好吧好吧 先看固定量，再判断轨迹。"
        )

        self.assertIn("动点 与 立体几何", cleaned)
        self.assertIn("PA=PB", cleaned)
        self.assertIn("angle ABC = 60 ^circ", cleaned)
        self.assertIn("先看固定量，再判断轨迹", cleaned)
        self.assertNotIn("\r", cleaned)
        self.assertNotIn("嗯嗯", cleaned)
        self.assertNotIn("然后然后", cleaned)
        self.assertNotIn("好吧好吧", cleaned)

    def test_deterministic_brief_extracts_topic_knowledge_methods_and_evidence(self):
        brief = build_deterministic_source_brief(
            raw_text=(
                "本节课主题：动点与立体几何综合\n"
                "老师强调：先看固定量，再判断轨迹。\n"
                "例题：动点 P 到定点 O 的距离恒为 r，轨迹是什么？\n"
                "易错：把空间球面误看成平面圆。\n"
                "方法：固定量 -> 轨迹对象 -> 边界条件。"
            ),
            subject="数学",
            topic="",
            weak_points="轨迹判断",
            user_requirements="少一点题量，多做诊断",
        )

        self.assertEqual(brief.schema_version, "2026-07-01")
        self.assertEqual(brief.lesson_title_candidates[0], "动点与立体几何综合")
        self.assertTrue(any(item.name == "轨迹判断" for item in brief.knowledge_points))
        self.assertTrue(any("固定量" in " ".join(item.steps) for item in brief.method_chains))
        self.assertTrue(any("球面" in item.name for item in brief.common_mistakes))
        self.assertTrue(any("动点 P" in item.stem for item in brief.example_stems))
        self.assertTrue(any("先看固定量" in item.quote for item in brief.teacher_emphasis))
        self.assertTrue(brief.evidence_map)
        self.assertGreaterEqual(brief.confidence, 0.7)

    def test_deterministic_brief_marks_missing_topic_when_no_topic_signal_exists(self):
        brief = build_deterministic_source_brief(
            raw_text="今天讲了很多题，学生容易把条件看漏。",
            subject="数学",
            topic="",
            weak_points="",
            user_requirements="",
        )

        self.assertIn("topic", brief.missing_fields)
        self.assertLess(brief.confidence, 0.7)
        self.assertTrue(brief.evidence_map)
```

- [ ] **Step 2: Run source brief tests and confirm failure**

Run:

```bash
python3 -m unittest tests.test_review_plan_source_brief -v
```

Expected: failure because `review_plan_workflow.source_brief` does not exist.

- [ ] **Step 3: Add source brief models to schemas**

Modify `review_plan_workflow/schemas.py` by adding these classes after `SubjectRoute` and before `SourceSummary`:

```python
class SourceEvidence(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    source: str = "summary_text"
    quote: str
    offset_start: int = 0
    offset_end: int = 0
    kind: str = "text"


class SourceKnowledgePoint(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str
    evidence_ids: list[str] = Field(default_factory=list)
    confidence: float = 0.0


class SourceMethodChain(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str
    steps: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)


class SourceMistake(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str
    evidence_ids: list[str] = Field(default_factory=list)


class SourceExampleStem(BaseModel):
    model_config = ConfigDict(extra="allow")

    stem: str
    evidence_ids: list[str] = Field(default_factory=list)


class SourceTeacherEmphasis(BaseModel):
    model_config = ConfigDict(extra="allow")

    quote: str
    evidence_ids: list[str] = Field(default_factory=list)


class ReviewPlanSourceBrief(BaseModel):
    model_config = ConfigDict(extra="allow")

    schema_version: str = "2026-07-01"
    source_text_hash: str = ""
    cleaned_text: str = ""
    lesson_title_candidates: list[str] = Field(default_factory=list)
    knowledge_points: list[SourceKnowledgePoint] = Field(default_factory=list)
    method_chains: list[SourceMethodChain] = Field(default_factory=list)
    common_mistakes: list[SourceMistake] = Field(default_factory=list)
    example_stems: list[SourceExampleStem] = Field(default_factory=list)
    teacher_emphasis: list[SourceTeacherEmphasis] = Field(default_factory=list)
    excluded_noise: list[str] = Field(default_factory=list)
    missing_fields: list[str] = Field(default_factory=list)
    evidence_map: list[SourceEvidence] = Field(default_factory=list)
    confidence: float = 0.0
```

Then modify `SourceSummary` to include:

```python
    source_brief: Optional[ReviewPlanSourceBrief] = None
```

- [ ] **Step 4: Create deterministic source brief implementation**

Create `review_plan_workflow/source_brief.py`:

```python
from __future__ import annotations

import hashlib
import re

from review_plan_workflow.schemas import (
    ReviewPlanSourceBrief,
    SourceEvidence,
    SourceExampleStem,
    SourceKnowledgePoint,
    SourceMethodChain,
    SourceMistake,
    SourceTeacherEmphasis,
)


SOURCE_BRIEF_SCHEMA_VERSION = "2026-07-01"
_NOISE_PATTERNS = (
    "嗯嗯",
    "呃呃",
    "然后然后",
    "好吧好吧",
    "对吧对吧",
)
_TITLE_MARKERS = ("本节课主题：", "主题：", "topic:")
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[。！？!?；;])\s+|\n+")
_METHOD_SPLIT_RE = re.compile(r"\s*(?:->|→|、|，|,|；|;)\s*")


def source_text_hash(text: str) -> str:
    digest = hashlib.sha256((text or "").encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def clean_source_text(text: str) -> str:
    cleaned = str(text or "").replace("\r\n", "\n").replace("\r", "\n")
    for pattern in _NOISE_PATTERNS:
        cleaned = cleaned.replace(pattern, "")
    lines = [" ".join(line.split()) for line in cleaned.splitlines()]
    return "\n".join(line for line in lines if line).strip()


def _sentences(text: str) -> list[str]:
    return [item.strip() for item in _SENTENCE_SPLIT_RE.split(text) if item.strip()]


def _evidence_id(index: int) -> str:
    return f"ev-{index:03d}"


def _make_evidence(cleaned: str, sentence: str, index: int, *, kind: str = "text") -> SourceEvidence:
    start = cleaned.find(sentence)
    if start < 0:
        start = 0
    return SourceEvidence(
        id=_evidence_id(index),
        source="summary_text",
        quote=sentence[:180],
        offset_start=start,
        offset_end=start + len(sentence),
        kind=kind,
    )


def _title_candidates(cleaned: str, explicit_topic: str) -> list[str]:
    titles: list[str] = []
    if explicit_topic.strip():
        titles.append(explicit_topic.strip())
    for marker in _TITLE_MARKERS:
        if marker in cleaned:
            candidate = cleaned.split(marker, 1)[1].splitlines()[0].strip(" ：:。；;")
            if candidate and candidate not in titles:
                titles.append(candidate)
            break
    return titles[:3]


def build_deterministic_source_brief(
    *,
    raw_text: str,
    subject: str = "",
    topic: str = "",
    weak_points: str = "",
    user_requirements: str = "",
) -> ReviewPlanSourceBrief:
    cleaned = clean_source_text(raw_text)
    sentences = _sentences(cleaned)
    evidence_items = [_make_evidence(cleaned, sentence, index + 1) for index, sentence in enumerate(sentences[:18])]
    evidence_ids = [item.id for item in evidence_items[:3]]
    title_candidates = _title_candidates(cleaned, topic)

    knowledge_points: list[SourceKnowledgePoint] = []
    if weak_points.strip():
        knowledge_points.append(SourceKnowledgePoint(name=weak_points.strip(), evidence_ids=evidence_ids, confidence=0.72))
    for sentence in sentences:
        if any(token in sentence for token in ("知识点", "方法", "定理", "公式", "轨迹", "函数", "方程", "几何")):
            name = sentence.strip("。；; ")
            if name and all(item.name != name for item in knowledge_points):
                knowledge_points.append(SourceKnowledgePoint(name=name[:60], evidence_ids=evidence_ids, confidence=0.68))
        if len(knowledge_points) >= 8:
            break

    method_chains: list[SourceMethodChain] = []
    for sentence in sentences:
        if "方法" in sentence or "先" in sentence or "步骤" in sentence or "->" in sentence or "→" in sentence:
            parts = [part for part in _METHOD_SPLIT_RE.split(sentence.strip("。；; ")) if part]
            if len(parts) >= 2:
                method_chains.append(SourceMethodChain(name=parts[0][:40], steps=parts[:6], evidence_ids=evidence_ids))
        if len(method_chains) >= 5:
            break

    mistakes: list[SourceMistake] = []
    for sentence in sentences:
        if any(token in sentence for token in ("易错", "错", "误看", "漏", "混淆", "卡")):
            mistakes.append(SourceMistake(name=sentence.strip("。；; ")[:80], evidence_ids=evidence_ids))
        if len(mistakes) >= 5:
            break

    examples: list[SourceExampleStem] = []
    for sentence in sentences:
        if any(token in sentence for token in ("例题", "题", "已知", "求", "证明", "动点")):
            examples.append(SourceExampleStem(stem=sentence.strip("。；; ")[:120], evidence_ids=evidence_ids))
        if len(examples) >= 6:
            break

    emphasis: list[SourceTeacherEmphasis] = []
    for sentence in sentences:
        if any(token in sentence for token in ("老师强调", "强调", "记住", "一定", "先")):
            emphasis.append(SourceTeacherEmphasis(quote=sentence.strip("。；; ")[:100], evidence_ids=evidence_ids))
        if len(emphasis) >= 5:
            break

    missing_fields = []
    if not title_candidates:
        missing_fields.append("topic")
    if not knowledge_points:
        missing_fields.append("knowledge_points")
    if not examples:
        missing_fields.append("example_stems")

    signal_count = len(title_candidates) + len(knowledge_points) + len(method_chains) + len(mistakes) + len(examples) + len(emphasis)
    confidence = min(0.9, 0.35 + signal_count * 0.08)
    if missing_fields:
        confidence = min(confidence, 0.65)

    return ReviewPlanSourceBrief(
        schema_version=SOURCE_BRIEF_SCHEMA_VERSION,
        source_text_hash=source_text_hash(raw_text),
        cleaned_text=cleaned,
        lesson_title_candidates=title_candidates,
        knowledge_points=knowledge_points,
        method_chains=method_chains,
        common_mistakes=mistakes,
        example_stems=examples,
        teacher_emphasis=emphasis,
        excluded_noise=[pattern for pattern in _NOISE_PATTERNS if pattern in str(raw_text or "")],
        missing_fields=missing_fields,
        evidence_map=evidence_items,
        confidence=round(confidence, 2),
    )
```

- [ ] **Step 5: Run source brief tests and confirm pass**

Run:

```bash
python3 -m unittest tests.test_review_plan_source_brief -v
```

Expected: all 4 tests pass.

- [ ] **Step 6: Commit Task 1**

Run:

```bash
git add review_plan_workflow/schemas.py review_plan_workflow/source_brief.py tests/test_review_plan_source_brief.py
git commit -m "feat: add review plan source brief model"
```

## Task 2: Version Source Artifact Storage

**Files:**
- Modify: `lesson_manager.py`
- Modify: `tests/test_review_plan_version_store.py`

**Interfaces:**
- Consumes: `ReviewPlanSourceBrief.model_dump()`
- Produces: hydrated version fields `source_text`, `cleaned_source_text`, `source_text_hash`, `source_brief`
- Produces: `update_review_plan_version_source_artifact(version_id: int, *, source_text: str, cleaned_source_text: str, source_text_hash: str, source_brief: object) -> None`

- [ ] **Step 1: Add failing version storage test**

Append this test method to `ReviewPlanVersionLifecycleTestCase` in `tests/test_review_plan_version_store.py`:

```python
    def test_review_plan_version_persists_source_artifact(self):
        lesson_id = lesson_manager.create_pending_lesson(
            date_str="2026-07-01",
            subject="数学",
            grade="六年级",
            topic="动点与立体几何综合",
            summary="原始课堂材料",
            weak_points="空间轨迹",
            created_by_user_id=7,
        )
        version = lesson_manager.create_review_plan_version(
            lesson_id=lesson_id,
            status="generating",
            created_by_user_id=7,
        )

        lesson_manager.update_review_plan_version_source_artifact(
            int(version["id"]),
            source_text="原始课堂材料",
            cleaned_source_text="清洗后课堂材料",
            source_text_hash="sha256:" + "a" * 64,
            source_brief={
                "schema_version": "2026-07-01",
                "source_text_hash": "sha256:" + "a" * 64,
                "cleaned_text": "清洗后课堂材料",
                "lesson_title_candidates": ["动点与立体几何综合"],
                "knowledge_points": [{"name": "空间轨迹", "evidence_ids": ["ev-001"], "confidence": 0.8}],
                "method_chains": [],
                "common_mistakes": [],
                "example_stems": [],
                "teacher_emphasis": [],
                "excluded_noise": [],
                "missing_fields": [],
                "evidence_map": [{"id": "ev-001", "source": "summary_text", "quote": "清洗后课堂材料", "offset_start": 0, "offset_end": 7, "kind": "text"}],
                "confidence": 0.8,
            },
        )

        hydrated = lesson_manager.get_review_plan_version_for_lesson(lesson_id, int(version["id"]))
        self.assertEqual(hydrated["source_text"], "原始课堂材料")
        self.assertEqual(hydrated["cleaned_source_text"], "清洗后课堂材料")
        self.assertEqual(hydrated["source_text_hash"], "sha256:" + "a" * 64)
        self.assertEqual(hydrated["source_brief"]["lesson_title_candidates"], ["动点与立体几何综合"])
        self.assertEqual(hydrated["source_brief"]["knowledge_points"][0]["name"], "空间轨迹")
```

- [ ] **Step 2: Run version storage test and confirm failure**

Run:

```bash
python3 -m unittest tests.test_review_plan_version_store.ReviewPlanVersionLifecycleTestCase.test_review_plan_version_persists_source_artifact -v
```

Expected: failure because `update_review_plan_version_source_artifact` and storage columns do not exist.

- [ ] **Step 3: Add version columns**

In `lesson_manager.py`, update the `review_plan_versions` table schema and migration helpers to include:

```python
source_text TEXT NOT NULL DEFAULT '',
cleaned_source_text TEXT NOT NULL DEFAULT '',
source_text_hash TEXT NOT NULL DEFAULT '',
source_brief_json TEXT NOT NULL DEFAULT '{}',
```

In `_ensure_review_plan_versions_schema(conn)`, add:

```python
    _ensure_column(conn, "review_plan_versions", "source_text", "TEXT NOT NULL DEFAULT ''")
    _ensure_column(conn, "review_plan_versions", "cleaned_source_text", "TEXT NOT NULL DEFAULT ''")
    _ensure_column(conn, "review_plan_versions", "source_text_hash", "TEXT NOT NULL DEFAULT ''")
    _ensure_column(conn, "review_plan_versions", "source_brief_json", "TEXT NOT NULL DEFAULT '{}'")
```

- [ ] **Step 4: Hydrate source artifact fields**

Add helper functions near the existing review-plan JSON helpers:

```python
def _dump_review_plan_source_brief(value: object | None) -> str:
    return _dump_review_plan_run_json(value, {})


def _load_review_plan_source_brief(value: object | None) -> dict:
    payload = _load_review_plan_run_json(value, {})
    return payload if isinstance(payload, dict) else {}
```

In the version hydration function that currently loads `same_lesson_materials` and `generation_options`, add:

```python
    version["source_text"] = str(version.get("source_text") or "")
    version["cleaned_source_text"] = str(version.get("cleaned_source_text") or "")
    version["source_text_hash"] = str(version.get("source_text_hash") or "")
    version["source_brief"] = _load_review_plan_source_brief(version.get("source_brief_json"))
```

- [ ] **Step 5: Add update helper**

Add this function near the existing review-plan version update helpers:

```python
def update_review_plan_version_source_artifact(
    version_id: int,
    *,
    source_text: str,
    cleaned_source_text: str,
    source_text_hash: str,
    source_brief: object,
) -> None:
    with get_conn() as conn:
        cur = conn.execute(
            """
            UPDATE review_plan_versions
            SET source_text=?,
                cleaned_source_text=?,
                source_text_hash=?,
                source_brief_json=?,
                updated_at=datetime('now','localtime')
            WHERE id=?
            """,
            (
                str(source_text or ""),
                str(cleaned_source_text or ""),
                str(source_text_hash or ""),
                _dump_review_plan_source_brief(source_brief),
                int(version_id),
            ),
        )
        conn.commit()
    if cur.rowcount == 0:
        raise LookupError("review plan version not found")
```

- [ ] **Step 6: Run version storage test and confirm pass**

Run:

```bash
python3 -m unittest tests.test_review_plan_version_store.ReviewPlanVersionLifecycleTestCase.test_review_plan_version_persists_source_artifact -v
```

Expected: the new test passes.

- [ ] **Step 7: Commit Task 2**

Run:

```bash
git add lesson_manager.py tests/test_review_plan_version_store.py
git commit -m "feat: persist review plan source artifacts"
```

## Task 3: Source Brief Workflow Node

**Files:**
- Create: `review_plan_workflow/nodes/source_brief_builder.py`
- Modify: `review_plan_workflow/nodes/__init__.py`
- Modify: `tests/test_review_plan_workflow.py`

**Interfaces:**
- Consumes: `ReviewPlanInput`, `NormalizedBrief`
- Produces: `ReviewPlanSourceBrief`
- Consumes later: service, source analyzer, planner, writer, observability

- [ ] **Step 1: Add failing workflow node test**

Add this test to `ReviewPlanWorkflowTestCase` in `tests/test_review_plan_workflow.py`:

```python
    def test_source_brief_builder_records_structured_source_before_writer(self):
        from review_plan_workflow.nodes.intake_normalizer import intake_normalizer_node
        from review_plan_workflow.nodes.source_brief_builder import source_brief_builder_node
        from review_plan_workflow.executor import run_workflow_node
        from review_plan_workflow.schemas import ReviewPlanInput
        from review_plan_workflow.state import WorkflowContext

        review_input = ReviewPlanInput(
            summary_text=(
                "本节课主题：动点与立体几何综合\n"
                "老师强调：先看固定量，再判断轨迹。\n"
                "例题：动点 P 到定点 O 的距离恒为 r，轨迹是什么？"
            ),
            subject="数学",
            grade="六年级",
            user_requirements="压缩成一天，少一点题量",
        )
        context = WorkflowContext(provider="deepseek", model="deepseek-v4-pro")
        normalized = run_workflow_node(intake_normalizer_node, review_input, context)
        brief = run_workflow_node(
            source_brief_builder_node,
            {"input": review_input, "normalized": normalized},
            context,
        )

        self.assertEqual(brief.lesson_title_candidates[0], "动点与立体几何综合")
        self.assertTrue(brief.evidence_map)
        self.assertIn("source_brief", context.node_outputs)
        self.assertEqual(context.node_outputs["source_brief"]["schema_version"], "2026-07-01")
        self.assertNotIn("压缩成一天，少一点题量", context.node_outputs["source_brief"]["cleaned_text"])
```

- [ ] **Step 2: Run node test and confirm failure**

Run:

```bash
python3 -m unittest tests.test_review_plan_workflow.ReviewPlanWorkflowTestCase.test_source_brief_builder_records_structured_source_before_writer -v
```

Expected: failure because `source_brief_builder_node` does not exist.

- [ ] **Step 3: Create source brief builder node**

Create `review_plan_workflow/nodes/source_brief_builder.py`:

```python
from __future__ import annotations

from typing import Any

from review_plan_workflow.executor import WorkflowNode
from review_plan_workflow.schemas import NormalizedBrief, ReviewPlanInput, ReviewPlanSourceBrief
from review_plan_workflow.source_brief import build_deterministic_source_brief
from review_plan_workflow.state import WorkflowContext


def _run(input_data: dict[str, Any], context: WorkflowContext) -> ReviewPlanSourceBrief:
    review_input: ReviewPlanInput = input_data["input"]
    normalized: NormalizedBrief = input_data["normalized"]
    raw_text = "\n\n".join(normalized.materials).strip() or review_input.summary_text
    brief = build_deterministic_source_brief(
        raw_text=raw_text,
        subject=review_input.subject,
        topic=review_input.topic,
        weak_points=review_input.weak_points,
        user_requirements=review_input.user_requirements,
    )
    context.node_outputs["source_brief"] = {
        **brief.model_dump(exclude={"cleaned_text"}),
        "cleaned_text_length": len(brief.cleaned_text),
    }
    if brief.missing_fields:
        context.add_warning(
            "source_brief_missing_fields",
            "结构化课堂材料缺少字段：" + "、".join(brief.missing_fields),
            "medium",
        )
    return brief


source_brief_builder_node: WorkflowNode[dict[str, Any], ReviewPlanSourceBrief] = WorkflowNode(
    name="source_brief_builder",
    run=_run,
)
```

- [ ] **Step 4: Export the node**

Modify `review_plan_workflow/nodes/__init__.py`:

```python
from .source_brief_builder import source_brief_builder_node
```

Add `"source_brief_builder_node"` to `__all__`.

- [ ] **Step 5: Run node test and confirm pass**

Run:

```bash
python3 -m unittest tests.test_review_plan_workflow.ReviewPlanWorkflowTestCase.test_source_brief_builder_records_structured_source_before_writer -v
```

Expected: the test passes and `context.node_outputs["source_brief"]` contains no full cleaned text.

- [ ] **Step 6: Commit Task 3**

Run:

```bash
git add review_plan_workflow/nodes/source_brief_builder.py review_plan_workflow/nodes/__init__.py tests/test_review_plan_workflow.py
git commit -m "feat: add review plan source brief node"
```

## Task 4: Integrate Source Brief Into Workflow And Storage

**Files:**
- Modify: `review_plan_workflow/service.py`
- Modify: `review_plan_workflow/nodes/source_analyzer.py`
- Modify: `review_plan_workflow/nodes/parent_planner.py`
- Modify: `review_plan_workflow/nodes/prompt_bundle_builder.py`
- Modify: `review_plan_workflow/nodes/plan_generator.py`
- Modify: `review_plan_workflow/nodes/revision.py`
- Modify: `app.py`
- Modify: `tests/test_review_plan_workflow.py`
- Modify: `tests/test_review_plan_async_api.py`

**Interfaces:**
- Consumes: `ReviewPlanSourceBrief`
- Produces: planner/writer payloads that include source brief and user requirements.
- Produces: generation job that reads and persists version source artifacts.

- [ ] **Step 1: Add failing service integration test**

Add this test to `ReviewPlanWorkflowTestCase`:

```python
    @patch("review_plan_workflow.nodes.llm_quality_reviewer.generate_review_plan_json")
    @patch("review_plan_workflow.nodes.plan_generator.generate_review_plan_json")
    @patch("review_plan_workflow.nodes.parent_planner.generate_review_plan_json")
    def test_service_passes_source_brief_and_user_requirements_to_planner_and_writer(
        self,
        mock_parent_plan,
        mock_generate_plan,
        mock_llm_review,
    ):
        mock_parent_plan.return_value = (
            {
                "strategy_summary": "按源材料聚焦空间轨迹",
                "student_diagnosis": ["空间轨迹判断不稳"],
                "knowledge_map": [{"name": "空间轨迹", "role": "核心", "evidence": "ev-001"}],
                "day_strategies": [{"day": 1, "objective": "压缩复习", "retrieval_focus": ["轨迹"], "question_design": ["填空"], "review_loop": ["自检"], "risk_controls": ["不虚构"]}],
                "writer_instructions": ["只用源材料证据"],
                "quality_risks": [],
                "success_criteria": ["题目可打印"],
                "assumptions": [],
                "confidence": 0.9,
            },
            {"provider": "deepseek", "model": "deepseek-v4-pro", "input_tokens": 1, "output_tokens": 2},
        )
        mock_generate_plan.return_value = (
            valid_single_lesson_plan(subject="数学", topic="动点与立体几何综合"),
            {"provider": "deepseek", "model": "deepseek-v4-pro", "input_tokens": 3, "output_tokens": 4},
        )
        mock_llm_review.return_value = (
            {"score": 96, "passed": True, "must_revise": False, "issues": [], "revision_instructions": []},
            {"provider": "deepseek", "model": "deepseek-v4-pro", "input_tokens": 5, "output_tokens": 6},
        )

        generate_single_lesson_review_plan(
            summary_text=(
                "本节课主题：动点与立体几何综合\n"
                "老师强调：先看固定量，再判断轨迹。\n"
                "例题：动点 P 到定点 O 的距离恒为 r，轨迹是什么？"
            ),
            subject="数学",
            grade="六年级",
            topic="",
            weak_points="空间轨迹",
            lesson_date="2026-07-01",
            generation_options={
                "schedule_mode": "compressed",
                "user_requirements": "压缩成一天，少一点题量，多做诊断",
            },
            provider="deepseek",
            model="deepseek-v4-pro",
        )

        parent_message = mock_parent_plan.call_args.kwargs["user_message"]
        writer_message = mock_generate_plan.call_args.kwargs["user_message"]
        self.assertIn("source_brief", parent_message)
        self.assertIn("压缩成一天，少一点题量，多做诊断", parent_message)
        self.assertIn("结构化课堂材料", writer_message)
        self.assertIn("动点与立体几何综合", writer_message)
        self.assertIn("压缩成一天，少一点题量，多做诊断", writer_message)
```

- [ ] **Step 2: Run service integration test and confirm failure**

Run:

```bash
python3 -m unittest tests.test_review_plan_workflow.ReviewPlanWorkflowTestCase.test_service_passes_source_brief_and_user_requirements_to_planner_and_writer -v
```

Expected: failure because service does not run source brief node and parent planner does not include user requirements.

- [ ] **Step 3: Run source brief node in service**

In `review_plan_workflow/service.py`, import:

```python
from .nodes.source_brief_builder import source_brief_builder_node
```

After `normalized = run_workflow_node(intake_normalizer_node, review_input, context)`, insert:

```python
            source_brief = run_workflow_node(
                source_brief_builder_node,
                {"input": review_input, "normalized": normalized},
                context,
            )
```

Change source analyzer call to:

```python
            source = run_workflow_node(
                source_analyzer_node,
                {"normalized": normalized, "source_brief": source_brief},
                context,
            )
```

Update these exact service call sites:

```python
            scope = run_workflow_node(
                scope_planner_node,
                {
                    "input": review_input,
                    "normalized": normalized,
                    "route": route,
                    "source": source,
                    "source_brief": source_brief,
                },
                context,
            )
```

```python
            task_blueprint = run_workflow_node(
                task_blueprint_node,
                {
                    "normalized": normalized,
                    "route": route,
                    "source": source,
                    "source_brief": source_brief,
                    "scope": scope,
                    "time_allocation": time_allocation,
                },
                context,
            )
```

Change `_run_parent_planner_with_fallback` signature to include:

```python
    source_brief: ReviewPlanSourceBrief | None = None,
```

Call it with:

```python
                source_brief=source_brief,
```

Pass source brief into prompt bundle input:

```python
                    "source_brief": source_brief,
```

Pass source brief into plan generator input:

```python
                    "source_brief": source_brief,
```

Pass source brief into quality review:

```python
                source_brief=source_brief,
```

Pass source brief into revision:

```python
                source_brief=source_brief,
```

- [ ] **Step 4: Make source analyzer consume source brief**

Replace `source_analyzer.py` input handling with:

```python
def _run(input_data: dict[str, object] | NormalizedBrief, context: WorkflowContext) -> SourceSummary:
    if isinstance(input_data, dict):
        normalized = input_data["normalized"]
        source_brief = input_data.get("source_brief")
    else:
        normalized = input_data
        source_brief = None
    assert isinstance(normalized, NormalizedBrief)

    if source_brief is not None:
        topics = list(getattr(source_brief, "lesson_title_candidates", []) or [])
        evidence_map = [item.model_dump() for item in getattr(source_brief, "evidence_map", [])]
        risk_notes = []
        if getattr(source_brief, "missing_fields", []):
            risk_notes.append("结构化课堂材料缺少：" + "、".join(source_brief.missing_fields))
        return SourceSummary(
            source_type="structured_source_brief",
            confirmed_topics=topics,
            assumed_topics=[] if topics else ["根据结构化课堂材料低置信度推断主题"],
            evidence_map=evidence_map,
            risk_notes=risk_notes,
            confidence=float(getattr(source_brief, "confidence", 0.0) or 0.0),
            source_brief=source_brief,
        )
```

Keep the existing marker-based logic as the fallback branch for legacy callers.

- [ ] **Step 5: Add user requirements and source brief to parent planner**

In `parent_planner.py`, update the `payload["input"]` dict:

```python
            "schedule_mode": review_input.schedule_mode,
            "review_days": review_input.review_days,
            "user_requirements": review_input.user_requirements,
```

Add source brief to payload:

```python
        "source_brief": source.source_brief.model_dump(exclude={"cleaned_text"}) if source.source_brief else None,
```

- [ ] **Step 6: Add source brief to prompt bundle variables**

In `prompt_bundle_builder.py`, add:

```python
        "source_brief": source.source_brief.model_dump(exclude={"cleaned_text"}) if source.source_brief else None,
```

- [ ] **Step 7: Prefer source brief in writer message**

In `plan_generator.py`, replace the raw `"课堂总结：\n" + review_input.summary_text` section with:

```python
    source_brief = prompt_bundle.variables.get("source_brief")
    if source_brief:
        sections.append("结构化课堂材料：\n" + json.dumps(source_brief, ensure_ascii=False, indent=2))
        cleaned_preview = str((source_brief or {}).get("cleaned_text") or "")
        if cleaned_preview:
            sections.append("课堂材料摘录：\n" + cleaned_preview[:1600])
    else:
        sections.append("课堂总结：\n" + review_input.summary_text)
```

The implementation must not serialize full `cleaned_text` inside `prompt_bundle.variables`; use an explicit excerpt in the writer message only.

- [ ] **Step 8: Include source brief in revision payload**

In `revision.py`, add after teacher requirements:

```python
    source_brief = prompt_bundle.variables.get("source_brief")
    if source_brief:
        sections.append("结构化课堂材料：\n" + json.dumps(source_brief, ensure_ascii=False, indent=2))
```

- [ ] **Step 9: Persist source artifact in app worker**

In `app.py`, import:

```python
from review_plan_workflow.source_brief import build_deterministic_source_brief
```

In `_run_review_plan_generation_job`, after `raw_text = str(lesson.get("summary") or "")`, resolve version-owned source text:

```python
        version_source_text = str((version or {}).get("source_text") or "").strip()
        source_text_for_generation = version_source_text or raw_text
```

Before calling `generate_single_lesson_review_plan`, build and persist a deterministic source artifact when the version has none:

```python
        if version_id and not str((version or {}).get("source_text_hash") or "").strip():
            source_brief = build_deterministic_source_brief(
                raw_text=source_text_for_generation,
                subject=subject,
                topic=topic,
                weak_points=weak_points,
                user_requirements=str((generation_options or {}).get("user_requirements") or ""),
            )
            update_review_plan_version_source_artifact(
                version_id,
                source_text=source_text_for_generation,
                cleaned_source_text=source_brief.cleaned_text,
                source_text_hash=source_brief.source_text_hash,
                source_brief=source_brief.model_dump(),
            )
            version = get_review_plan_version_for_lesson(lesson_id, version_id)
```

Pass `source_text_for_generation` to service:

```python
                    summary_text=source_text_for_generation,
```

- [ ] **Step 10: Run service integration test and confirm pass**

Run:

```bash
python3 -m unittest tests.test_review_plan_workflow.ReviewPlanWorkflowTestCase.test_service_passes_source_brief_and_user_requirements_to_planner_and_writer -v
```

Expected: pass.

- [ ] **Step 11: Run focused workflow tests**

Run:

```bash
python3 -m unittest tests.test_review_plan_workflow -v
```

Expected: pass.

- [ ] **Step 12: Commit Task 4**

Run:

```bash
git add app.py review_plan_workflow/service.py review_plan_workflow/nodes/source_analyzer.py review_plan_workflow/nodes/parent_planner.py review_plan_workflow/nodes/prompt_bundle_builder.py review_plan_workflow/nodes/plan_generator.py review_plan_workflow/nodes/revision.py tests/test_review_plan_workflow.py
git commit -m "feat: route source brief through review plan workflow"
```

## Task 5: Regeneration Uses Stable Source Artifact

**Files:**
- Modify: `app.py`
- Modify: `lesson_manager.py`
- Modify: `tests/test_review_plan_async_api.py`
- Modify: `frontend/src/features/review-generation/ReviewPlanRegenerateDialog.tsx`
- Modify: `frontend/src/review-generation-async.test.tsx`

**Interfaces:**
- Consumes: current version source fields.
- Produces: new regenerate version with copied source artifact.
- Produces: terse frontend regeneration labels.

- [ ] **Step 1: Add failing API regeneration test**

Add this test to `ReviewPlanAsyncApiTestCase` in `tests/test_review_plan_async_api.py`:

```python
    @patch("app._start_review_plan_generation_thread")
    def test_regenerate_review_plan_reuses_current_version_source_artifact(self, mock_start_thread):
        user_id = lesson_manager.create_user(
            username="teacher-source",
            password_hash="hash",
            role="member",
            organization_id=1,
            display_name="华老师",
        )
        lesson_id = lesson_manager.create_pending_lesson(
            date_str="2026-07-01",
            subject="数学",
            grade="六年级",
            topic="动点与立体几何综合",
            summary="后来被编辑过的 lesson summary",
            weak_points="空间轨迹",
            created_by_user_id=user_id,
        )
        current = lesson_manager.create_review_plan_version(
            lesson_id=lesson_id,
            status="ready",
            created_by_user_id=user_id,
            generation_options={"schedule_mode": "standard"},
        )
        lesson_manager.update_review_plan_version_source_artifact(
            int(current["id"]),
            source_text="原始课堂源材料",
            cleaned_source_text="清洗后课堂源材料",
            source_text_hash="sha256:" + "b" * 64,
            source_brief={
                "schema_version": "2026-07-01",
                "source_text_hash": "sha256:" + "b" * 64,
                "cleaned_text": "清洗后课堂源材料",
                "lesson_title_candidates": ["动点与立体几何综合"],
                "knowledge_points": [],
                "method_chains": [],
                "common_mistakes": [],
                "example_stems": [],
                "teacher_emphasis": [],
                "excluded_noise": [],
                "missing_fields": [],
                "evidence_map": [],
                "confidence": 0.8,
            },
        )
        lesson_manager.set_current_review_plan_version(lesson_id, int(current["id"]))

        client = self.app.test_client()
        with client.session_transaction() as sess:
            sess["user_id"] = user_id

        response = client.post(
            f"/api/review-plans/{lesson_id}/regenerate",
            json={"generation_options": {"schedule_mode": "compressed", "user_requirements": "压缩一天"}},
        )

        self.assertEqual(response.status_code, 202)
        new_version_id = response.get_json()["version_id"]
        new_version = lesson_manager.get_review_plan_version_for_lesson(lesson_id, new_version_id)
        self.assertEqual(new_version["source_text"], "原始课堂源材料")
        self.assertEqual(new_version["cleaned_source_text"], "清洗后课堂源材料")
        self.assertEqual(new_version["source_text_hash"], "sha256:" + "b" * 64)
        self.assertEqual(new_version["source_brief"]["lesson_title_candidates"], ["动点与立体几何综合"])
        self.assertEqual(mock_start_thread.call_args.kwargs["generation_options"]["user_requirements"], "压缩一天")
```

- [ ] **Step 2: Run regeneration test and confirm failure**

Run:

```bash
python3 -m unittest tests.test_review_plan_async_api.ReviewPlanAsyncApiTestCase.test_regenerate_review_plan_reuses_current_version_source_artifact -v
```

Expected: failure because regenerate does not copy source artifact fields.

- [ ] **Step 3: Copy source artifact when creating regenerate version**

In `app.py` inside `api_lesson_regenerate`, after `current_version = get_current_review_plan_version(lesson_id)`, derive source fields:

```python
    source_text = str((current_version or {}).get("source_text") or raw_text).strip()
    cleaned_source_text = str((current_version or {}).get("cleaned_source_text") or "").strip()
    source_text_hash_value = str((current_version or {}).get("source_text_hash") or "").strip()
    source_brief = (current_version or {}).get("source_brief") or {}
```

After the regenerate route creates the new version row, persist copied source artifact if the current version has one:

```python
        if source_text_hash_value or source_brief:
            update_review_plan_version_source_artifact(
                int(version["id"]),
                source_text=source_text,
                cleaned_source_text=cleaned_source_text,
                source_text_hash=source_text_hash_value,
                source_brief=source_brief,
            )
            version = get_review_plan_version_for_lesson(lesson_id, int(version["id"])) or version
```

Keep the existing `_start_review_plan_generation_thread` call shape and make sure its `same_lesson_materials` and `generation_options` arguments still come from the freshly hydrated `version`.

- [ ] **Step 4: Add terse frontend source reuse label**

In `ReviewPlanRegenerateDialog.tsx`, add a compact row under the title:

```tsx
            <div className="mt-3 inline-flex items-center rounded-md bg-slate-100 px-2 py-1 text-xs font-medium text-slate-600 dark:bg-white/10 dark:text-slate-300">
              复用原课堂材料
            </div>
```

Do not add explanatory paragraphs.

- [ ] **Step 5: Add frontend source assertion**

In `frontend/src/review-generation-async.test.tsx`, add a source assertion test:

```ts
test('regenerate dialog keeps source reuse copy terse', () => {
  const source = readFileSync(new URL('./features/review-generation/ReviewPlanRegenerateDialog.tsx', import.meta.url), 'utf8');
  assert.match(source, /复用原课堂材料/);
  assert.doesNotMatch(source, /重新上传|重新转录|原始逐字稿会/);
});
```

- [ ] **Step 6: Run API and frontend tests**

Run:

```bash
python3 -m unittest tests.test_review_plan_async_api.ReviewPlanAsyncApiTestCase.test_regenerate_review_plan_reuses_current_version_source_artifact -v
cd frontend && npx tsx --test src/review-generation-async.test.tsx
```

Expected: both pass.

- [ ] **Step 7: Commit Task 5**

Run:

```bash
git add app.py frontend/src/features/review-generation/ReviewPlanRegenerateDialog.tsx frontend/src/review-generation-async.test.tsx tests/test_review_plan_async_api.py
git commit -m "feat: reuse review plan source artifact on regenerate"
```

## Task 6: Local-First Quality Policy And Bounded LLM Calls

**Files:**
- Create: `review_plan_workflow/quality_policy.py`
- Modify: `review_plan_workflow/service.py`
- Modify: `review_plan_workflow/llm/client.py`
- Modify: `tests/test_review_plan_workflow.py`

**Interfaces:**
- Produces: `should_run_llm_quality_review(*, local_quality: QualityReview, source_brief: ReviewPlanSourceBrief | None) -> bool`
- Produces: `max_revision_attempts_for_quality(*, quality: QualityReview, source_brief: ReviewPlanSourceBrief | None) -> int`
- Produces: `generate_review_plan_json(*, system_prompt: str, user_message: str, provider: str = "", model: str = "", reasoning_effort: str = "", temperature: float | None = None, stage: str = "generate_json", timeout_seconds: float | None = None, max_retries: int = 0) -> tuple[dict[str, Any], dict[str, Any]]`

- [ ] **Step 1: Add failing quality policy tests**

Add these tests to `ReviewPlanWorkflowTestCase`:

```python
    def test_quality_policy_skips_llm_reviewer_for_high_confidence_local_pass(self):
        from review_plan_workflow.quality_policy import should_run_llm_quality_review
        from review_plan_workflow.schemas import QualityReview, ReviewPlanSourceBrief

        local_quality = QualityReview(score=96, passed=True, must_revise=False, issues=[], revision_instructions=[])
        source_brief = ReviewPlanSourceBrief(
            source_text_hash="sha256:" + "c" * 64,
            cleaned_text="课堂材料",
            lesson_title_candidates=["一次函数"],
            confidence=0.86,
        )

        self.assertFalse(should_run_llm_quality_review(local_quality=local_quality, source_brief=source_brief))

    def test_quality_policy_runs_llm_reviewer_when_source_confidence_is_low(self):
        from review_plan_workflow.quality_policy import should_run_llm_quality_review
        from review_plan_workflow.schemas import QualityReview, ReviewPlanSourceBrief

        local_quality = QualityReview(score=92, passed=True, must_revise=False, issues=[], revision_instructions=[])
        source_brief = ReviewPlanSourceBrief(confidence=0.5, missing_fields=["topic"])

        self.assertTrue(should_run_llm_quality_review(local_quality=local_quality, source_brief=source_brief))

    def test_quality_policy_caps_revision_attempts_to_one(self):
        from review_plan_workflow.quality_policy import max_revision_attempts_for_quality
        from review_plan_workflow.schemas import QualityIssue, QualityReview, ReviewPlanSourceBrief

        quality = QualityReview(
            score=40,
            passed=False,
            must_revise=True,
            issues=[QualityIssue(severity="high", category="pdf_readiness", description="题量不足")],
            revision_instructions=["补足题目"],
        )
        source_brief = ReviewPlanSourceBrief(confidence=0.82)

        self.assertEqual(max_revision_attempts_for_quality(quality=quality, source_brief=source_brief), 1)
```

- [ ] **Step 2: Run quality policy tests and confirm failure**

Run:

```bash
python3 -m unittest \
  tests.test_review_plan_workflow.ReviewPlanWorkflowTestCase.test_quality_policy_skips_llm_reviewer_for_high_confidence_local_pass \
  tests.test_review_plan_workflow.ReviewPlanWorkflowTestCase.test_quality_policy_runs_llm_reviewer_when_source_confidence_is_low \
  tests.test_review_plan_workflow.ReviewPlanWorkflowTestCase.test_quality_policy_caps_revision_attempts_to_one -v
```

Expected: failure because `quality_policy.py` does not exist.

- [ ] **Step 3: Create quality policy**

Create `review_plan_workflow/quality_policy.py`:

```python
from __future__ import annotations

from review_plan_workflow.schemas import QualityReview, ReviewPlanSourceBrief


def _has_high_issue(quality: QualityReview) -> bool:
    return any(issue.severity == "high" for issue in quality.issues)


def should_run_llm_quality_review(
    *,
    local_quality: QualityReview,
    source_brief: ReviewPlanSourceBrief | None,
) -> bool:
    if not local_quality.passed or local_quality.must_revise or _has_high_issue(local_quality):
        return True
    if local_quality.score < 92:
        return True
    if source_brief is None:
        return True
    if source_brief.confidence < 0.75:
        return True
    if source_brief.missing_fields:
        return True
    return False


def max_revision_attempts_for_quality(
    *,
    quality: QualityReview,
    source_brief: ReviewPlanSourceBrief | None,
) -> int:
    if quality.passed and not quality.must_revise and not _has_high_issue(quality):
        return 0
    if not quality.revision_instructions and not quality.issues:
        return 0
    return 1
```

- [ ] **Step 4: Add stage timeout support to LLM client**

In `review_plan_workflow/llm/client.py`, change signature:

```python
def generate_review_plan_json(
    *,
    system_prompt: str,
    user_message: str,
    provider: str = "",
    model: str = "",
    reasoning_effort: str = "",
    temperature: float | None = None,
    stage: str = "generate_json",
    timeout_seconds: float | None = None,
    max_retries: int = 0,
) -> tuple[dict[str, Any], dict[str, Any]]:
```

Then replace timeout handling:

```python
    request_timeout = REVIEW_PLAN_LLM_TIMEOUT_SECONDS if timeout_seconds is None else float(timeout_seconds)
    request_kwargs: dict[str, Any] = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        "temperature": request_temperature,
        "response_format": {"type": "json_object"},
        "timeout": request_timeout,
    }
```

Before `response = client.chat.completions.create(**request_kwargs)`, add:

```python
            active_client = client
            with_options = getattr(client, "with_options", None)
            if callable(with_options):
                active_client = with_options(timeout=request_timeout, max_retries=max(0, int(max_retries)))
            response = active_client.chat.completions.create(**request_kwargs)
```

Remove the old direct `client.chat.completions.create(**request_kwargs)` line.

- [ ] **Step 5: Apply quality policy in service**

In `service.py`, import:

```python
from .quality_policy import max_revision_attempts_for_quality, should_run_llm_quality_review
```

Change `_review_with_llm_quality_gate` to accept `source_brief`. If `should_run_llm_quality_review(local_quality=local_quality, source_brief=source_brief)` returns `False`, record:

```python
    context.node_outputs[node_key] = {
        "mode": "skipped",
        "reason": "local_quality_passed_with_high_source_confidence",
        "score": local_quality.score,
    }
    return local_quality, {}
```

Change `_maybe_revise_plan` so the loop count comes from `max_revision_attempts_for_quality(quality=quality, source_brief=source_brief)` instead of a hard-coded two attempts.

When calling LLM reviewer, pass:

```python
        timeout_seconds=90.0,
        max_retries=0,
```

When calling revision, pass:

```python
        timeout_seconds=90.0,
        max_retries=0,
```

When calling parent planner, pass:

```python
        timeout_seconds=120.0,
        max_retries=0,
```

Keep writer timeout at `180.0`.

- [ ] **Step 6: Update existing timeout test**

In `tests/test_review_plan_workflow.py`, update `test_generate_review_plan_json_sets_timeout` so it asserts:

```python
        self.assertEqual(create_kwargs["timeout"], 42.0)
```

Call `generate_review_plan_json` with `timeout_seconds=42.0` and `max_retries=0`.

If the fake client has `with_options`, assert `max_retries=0` was passed.

- [ ] **Step 7: Run quality and timeout tests**

Run:

```bash
python3 -m unittest tests.test_review_plan_workflow -v
```

Expected: pass.

- [ ] **Step 8: Commit Task 6**

Run:

```bash
git add review_plan_workflow/quality_policy.py review_plan_workflow/service.py review_plan_workflow/llm/client.py tests/test_review_plan_workflow.py
git commit -m "feat: bound review plan quality LLM path"
```

## Task 7: Observability Without Source Leakage

**Files:**
- Modify: `review_plan_workflow/observability.py`
- Modify: `tests/test_review_plan_observability.py`

**Interfaces:**
- Consumes: source brief fields.
- Produces: trace-safe source summary with hash, counts, confidence, and missing fields.

- [ ] **Step 1: Add failing observability test**

Add this test to `ReviewPlanObservabilityTestCase`:

```python
    @patch("review_plan_workflow.nodes.plan_generator.generate_review_plan_json")
    def test_langfuse_trace_includes_source_metrics_without_source_text(self, mock_generate_plan):
        fake_client = FakeLangfuseClient()
        plan = valid_single_lesson_plan(subject="数学", topic="动点与立体几何综合")
        mock_generate_plan.return_value = (
            plan,
            {"provider": "deepseek", "model": "deepseek-v4-pro", "input_tokens": 10, "output_tokens": 20},
        )

        with patch.dict(os.environ, self.langfuse_env(), clear=True), patch.dict(
            sys.modules,
            {"langfuse": fake_langfuse_module(fake_client)},
        ):
            generate_single_lesson_review_plan(
                summary_text=(
                    "本节课主题：动点与立体几何综合\n"
                    "老师强调：先看固定量，再判断轨迹。\n"
                    "这段完整课堂材料不要进入 Langfuse。"
                ),
                subject="数学",
                grade="六年级",
                lesson_date="2026-07-01",
                provider="deepseek",
                model="deepseek-v4-pro",
            )

        telemetry_blob = json.dumps(
            {
                "started": fake_client.started,
                "updates": [observation.updates for observation in fake_client.observations],
                "current_updates": fake_client.current_updates,
            },
            ensure_ascii=False,
        )
        self.assertIn("source_brief", telemetry_blob)
        self.assertIn("source_text_hash", telemetry_blob)
        self.assertIn("knowledge_points_count", telemetry_blob)
        self.assertIn("confidence", telemetry_blob)
        self.assertNotIn("这段完整课堂材料不要进入 Langfuse", telemetry_blob)
        self.assertNotIn("先看固定量，再判断轨迹", telemetry_blob)
```

- [ ] **Step 2: Run observability test and confirm failure**

Run:

```bash
python3 -m unittest tests.test_review_plan_observability.ReviewPlanObservabilityTestCase.test_langfuse_trace_includes_source_metrics_without_source_text -v
```

Expected: failure because source brief metrics are not summarized.

- [ ] **Step 3: Add trace-safe source brief summary**

In `observability.py`, add:

```python
def summarize_source_brief(value: object) -> dict[str, Any]:
    data = value if isinstance(value, dict) else {}
    return {
        "schema_version": str(data.get("schema_version") or ""),
        "source_text_hash": str(data.get("source_text_hash") or ""),
        "title_candidates_count": len(data.get("lesson_title_candidates") or []),
        "knowledge_points_count": len(data.get("knowledge_points") or []),
        "method_chains_count": len(data.get("method_chains") or []),
        "common_mistakes_count": len(data.get("common_mistakes") or []),
        "example_stems_count": len(data.get("example_stems") or []),
        "teacher_emphasis_count": len(data.get("teacher_emphasis") or []),
        "missing_fields": list(data.get("missing_fields") or [])[:10],
        "confidence": float(data.get("confidence") or 0.0),
    }
```

Where node outputs are summarized, if key is `source_brief`, use:

```python
        return summarize_source_brief(data)
```

Do not include `cleaned_text`, `evidence_map.quote`, raw prompt, or full user message.

- [ ] **Step 4: Run observability tests**

Run:

```bash
python3 -m unittest tests.test_review_plan_observability -v
```

Expected: pass.

- [ ] **Step 5: Commit Task 7**

Run:

```bash
git add review_plan_workflow/observability.py tests/test_review_plan_observability.py
git commit -m "feat: trace review plan source brief metrics"
```

## Task 8: Eval Fixtures For Real Failures

**Files:**
- Create: `review_plan_workflow/evals/fixtures/math/dynamic-geometry-source-brief.json`
- Create: `review_plan_workflow/evals/fixtures/math/text-only-low-density-review-plan.json`
- Modify: `tests/test_review_plan_evals.py`
- Modify: `tests/review_plan_test_utils.py`

**Interfaces:**
- Consumes: eval fixture runner.
- Produces: regression coverage for lesson 80 and lesson 81 failure classes.

- [ ] **Step 1: Add dynamic geometry fixture**

Create `review_plan_workflow/evals/fixtures/math/dynamic-geometry-source-brief.json`:

```json
{
  "name": "dynamic-geometry-source-brief",
  "subject": "数学",
  "grade": "六年级",
  "topic": "动点与立体几何综合",
  "summary_text": "本节课主题：动点与立体几何综合\n老师强调：先看固定量，再判断轨迹。\n例题：动点 P 到定点 O 的距离恒为 r，轨迹是什么？\n易错：把空间球面误看成平面圆。\n方法：固定量 -> 轨迹对象 -> 边界条件。",
  "weak_points": "空间轨迹判断",
  "generation_options": {
    "schedule_mode": "standard",
    "review_days": [1, 2, 7, 14, 30],
    "user_requirements": "选择题不要全是执行清单，要有真实数学判断。"
  },
  "assertions": [
    {"name": "fixed_single_lesson_review_days", "daysExactly": [1, 2, 7, 14, 30]},
    {"name": "topic_contains", "contains": "动点"},
    {"name": "minimum_printable_items_per_day", "minimum": 3},
    {"name": "choices_have_complete_options", "minimumChoices": 1},
    {"name": "no_generic_checklist_choices"}
  ]
}
```

- [ ] **Step 2: Add text-only low-density fixture**

Create `review_plan_workflow/evals/fixtures/math/text-only-low-density-review-plan.json`:

```json
{
  "name": "text-only-low-density-review-plan",
  "subject": "数学",
  "grade": "六年级",
  "topic": "",
  "summary_text": "课堂讲了等式判断、取倒数需要分母不为0、平方相等和绝对值相等的边界、两数相等或互为相反数、应用题中理想购买数量的语义转化。学生容易把若则关系倒过来，也容易把贵20元的方向列反。",
  "weak_points": "等式推导边界和审题列式",
  "generation_options": {
    "schedule_mode": "standard",
    "review_days": [1, 2, 7, 14, 30],
    "user_requirements": "执行清单不能全做选择题。"
  },
  "assertions": [
    {"name": "fixed_single_lesson_review_days", "daysExactly": [1, 2, 7, 14, 30]},
    {"name": "topic_not_empty"},
    {"name": "full_review_topics_minimum", "minimum": 5},
    {"name": "minimum_printable_items_per_day", "minimum": 3},
    {"name": "no_duplicate_printable_tasks"}
  ]
}
```

- [ ] **Step 3: Add eval assertions**

In `tests/test_review_plan_evals.py`, add assertion handlers:

```python
def _assert_topic_not_empty(plan: dict, assertion: dict) -> None:
    topic = str((plan.get("lesson_info") or {}).get("topic") or "").strip()
    assert topic and topic != "课后"


def _assert_full_review_topics_minimum(plan: dict, assertion: dict) -> None:
    assert len(plan.get("full_review_topics") or []) >= int(assertion["minimum"])


def _assert_minimum_printable_items_per_day(plan: dict, assertion: dict) -> None:
    minimum = int(assertion["minimum"])
    for day in plan.get("days") or []:
        count = len(day.get("items") or []) + len(day.get("blanks") or []) + len(day.get("choices") or [])
        assert count >= minimum


def _assert_no_duplicate_printable_tasks(plan: dict, assertion: dict) -> None:
    for day in plan.get("days") or []:
        texts = []
        for key in ("items", "blanks", "choices"):
            for item in day.get(key) or []:
                texts.append(str(item.get("text") or item.get("question") or "").strip())
        normalized = [text for text in texts if text]
        assert len(normalized) == len(set(normalized))


def _assert_no_generic_checklist_choices(plan: dict, assertion: dict) -> None:
    banned = ("先看固定量", "检查边界", "完成复盘", "执行清单")
    for day in plan.get("days") or []:
        for choice in day.get("choices") or []:
            question = str(choice.get("question") or "")
            assert not all(token in question for token in banned[:2])
```

Register the new assertion names in the existing assertion dispatch map.

- [ ] **Step 4: Run eval tests and confirm pass**

Run:

```bash
python3 -m unittest tests.test_review_plan_evals -v
```

Expected: pass.

- [ ] **Step 5: Commit Task 8**

Run:

```bash
git add review_plan_workflow/evals/fixtures/math/dynamic-geometry-source-brief.json review_plan_workflow/evals/fixtures/math/text-only-low-density-review-plan.json tests/test_review_plan_evals.py tests/review_plan_test_utils.py
git commit -m "test: add review plan source quality evals"
```

## Task 9: End-To-End Proof, Handoff, And Merge To Develop

**Files:**
- Modify: `handoff.md`

**Interfaces:**
- Consumes: all tasks above.
- Produces: verified branch merged into `develop`.

- [ ] **Step 1: Run backend focused proof**

Run:

```bash
python3 -m py_compile \
  app.py \
  lesson_manager.py \
  review_plan_workflow/schemas.py \
  review_plan_workflow/source_brief.py \
  review_plan_workflow/service.py \
  review_plan_workflow/quality_policy.py \
  review_plan_workflow/llm/client.py \
  review_plan_workflow/nodes/source_brief_builder.py \
  review_plan_workflow/nodes/source_analyzer.py \
  review_plan_workflow/nodes/parent_planner.py \
  review_plan_workflow/nodes/prompt_bundle_builder.py \
  review_plan_workflow/nodes/plan_generator.py \
  review_plan_workflow/nodes/revision.py
python3 -m unittest \
  tests.test_review_plan_source_brief \
  tests.test_review_plan_version_store \
  tests.test_review_plan_workflow \
  tests.test_review_plan_async_api \
  tests.test_review_plan_observability \
  tests.test_review_plan_evals \
  tests.test_single_lesson_pdf_unification -v
```

Expected: py_compile succeeds and all listed unittest modules pass.

- [ ] **Step 2: Run frontend focused proof**

Run:

```bash
cd frontend
npx tsx --test src/review-generation-async.test.tsx src/reviewGenerationAsync.test.ts
npm run build
```

Expected: focused frontend tests pass and Vite build succeeds.

- [ ] **Step 3: Run source leak scan**

Run:

```bash
rg -n "这段完整课堂材料不要进入 Langfuse|课堂总结文本-不要进入Langfuse|清洗后课堂源材料" review_plan_workflow tests app.py lesson_manager.py frontend/src
```

Expected: matches only in tests that intentionally assert no leakage.

- [ ] **Step 4: Run diff hygiene**

Run:

```bash
git diff --check
git status --short
```

Expected: no whitespace errors. `git status --short` shows only intended tracked changes before the final commit.

- [ ] **Step 5: Update handoff**

Append this entry to `handoff.md`:

```markdown
## 2026-07-01 review plan source brief quality/speed
- Added version-scoped review-plan source artifacts: raw source snapshot, cleaned source text, source hash, and structured source brief.
- Routed source brief and teacher requirements through source analysis, parent planning, writer, revision, and privacy-safe observability.
- Changed regeneration to reuse the current version source artifact by default while still creating a new version.
- Added local-first quality policy and bounded LLM timeouts to avoid 10-20 minute slow paths.
- Added regression coverage for dynamic geometry, text-only low-density output, checklist-like choices, source artifact storage, regeneration consistency, and Langfuse source-metric privacy.
- Proof passed:
  - `python3 -m py_compile app.py lesson_manager.py review_plan_workflow/schemas.py review_plan_workflow/source_brief.py review_plan_workflow/service.py review_plan_workflow/quality_policy.py review_plan_workflow/llm/client.py review_plan_workflow/nodes/source_brief_builder.py review_plan_workflow/nodes/source_analyzer.py review_plan_workflow/nodes/parent_planner.py review_plan_workflow/nodes/prompt_bundle_builder.py review_plan_workflow/nodes/plan_generator.py review_plan_workflow/nodes/revision.py`
  - `python3 -m unittest tests.test_review_plan_source_brief tests.test_review_plan_version_store tests.test_review_plan_workflow tests.test_review_plan_async_api tests.test_review_plan_observability tests.test_review_plan_evals tests.test_single_lesson_pdf_unification -v`
  - `cd frontend && npx tsx --test src/review-generation-async.test.tsx src/reviewGenerationAsync.test.ts`
  - `cd frontend && npm run build`
  - `git diff --check`
```

- [ ] **Step 6: Commit final handoff**

Run:

```bash
git add handoff.md
git commit -m "docs: record review plan source brief implementation"
```

- [ ] **Step 7: Merge branch back into develop**

Run:

```bash
git fetch origin --prune
git switch develop
git pull --ff-only origin develop
git merge --no-ff codex/review-plan-source-brief-quality-speed
git status --short --branch
```

Expected: merge succeeds on `develop`. Only unrelated runtime untracked files remain.

- [ ] **Step 8: Push develop**

Run:

```bash
git push origin develop
```

Expected: remote `develop` includes the source-brief implementation commits.

## NOT In Scope

- Do not merge `develop` into `master`.
- Do not replace the current Flask background thread model with Celery/RQ.
- Do not add LangChain or LangGraph in this PR.
- Do not redesign the review-generation page layout.
- Do not change PDF visual styling except where tests need source-quality proof.
- Do not store full classroom text in Langfuse.

## Parallelization Strategy

Sequential implementation is recommended for Tasks 1-7 because they touch the same workflow contracts and tests build on the previous task.

After Task 7 lands, Task 8 eval fixtures and Task 5 frontend copy can be split into separate worktrees if needed:

- Lane A: backend source brief, storage, workflow, quality policy, observability.
- Lane B: eval fixtures and assertion helpers after Lane A exposes source brief.
- Lane C: frontend regenerate label after Task 5 API contract is clear.

Merge order: Lane A first, then Lane B and Lane C.

## Self-Review

Spec coverage:

- Source preprocessing: Tasks 1, 3, 4.
- Output quality: Tasks 4, 6, 8.
- Speed: Task 6.
- Teacher prompt integration: Tasks 3, 4, 7.
- New generation vs regeneration consistency: Tasks 2, 5.
- Langfuse and production monitoring: Task 7.
- Frontend regeneration semantics: Task 5.

Placeholder scan:

- No task uses open-ended deferred-work language.
- Each code task includes concrete tests, code snippets, commands, and expected results.

Type consistency:

- `ReviewPlanSourceBrief` is defined in Task 1 and consumed by Tasks 3, 4, 6, and 7.
- `update_review_plan_version_source_artifact` is defined in Task 2 and consumed by Tasks 4 and 5.
- `should_run_llm_quality_review` and `max_revision_attempts_for_quality` are defined in Task 6 and consumed by service code in the same task.
