# Credit System Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add organization-shared credits with Xiaohongshu order redemption, owner-facing credit visibility, and AI usage charging across the existing Flask + React product.

**Architecture:** Keep SQLite as the source of truth, add explicit organization credit and AI usage ledgers, and centralize accounting logic in a new backend service module instead of scattering balance math across Flask routes. Keep the first Xiaohongshu redemption flow fixed-page based: owner logs in, submits order number plus phone suffix, the backend validates the order through a dedicated adapter, then credits the owner’s organization and exposes the result in a new owner-only credit center page.

**Tech Stack:** Flask, SQLite, Python `unittest`, OpenAI-compatible SDK usage metadata, React 19, TypeScript, Vite, `tsx --test`

---

## File Structure

- Create: `credit_manager.py`
  - Central service layer for pricing rules, ledger writes, organization balance reads, redemption, member usage summaries, and AI charge application.
- Create: `xhs_open_platform.py`
  - Xiaohongshu order validation adapter that returns a normalized paid-order payload for redemption.
- Modify: `lesson_manager.py`
  - Add new SQLite tables plus low-level row/query helpers for credit accounts, credit ledger, order redemptions, and AI usage rows.
- Modify: `config_runtime.py`
  - Add runtime keys for Xiaohongshu API credentials and base URL selection.
- Modify: `ai_processor.py`
  - Expose token usage metadata in a backward-compatible way so the backend can record real usage while still returning the existing feature payloads.
- Modify: `app.py`
  - Add credit center APIs, redemption API, manual adjustment API, and shared AI charging enforcement in existing AI endpoints.
- Create: `tests/test_credit_system.py`
  - Dedicated backend coverage for ledger behavior, redemption, owner-only access, duplicate prevention, member usage drill-down, and AI charging integration.
- Modify: `frontend/src/App.tsx`
  - Add owner-only `积分中心` page, new page state, overview/redeem/member-usage UI, and wiring to the new APIs.
- Modify: `frontend/src/workspace-navigation.test.ts`
  - Lock the new owner-only navigation item and page rendering into the workspace shell.
- Create: `frontend/src/credit-center.test.tsx`
  - Source assertions for the new credit center data loading, redemption form, and usage sections.

## Task 1: Add Credit Storage, Runtime Config, And The Shared Backend Service

**Files:**
- Create: `tests/test_credit_system.py`
- Create: `credit_manager.py`
- Modify: `lesson_manager.py`
- Modify: `config_runtime.py`

- [ ] **Step 1: Write failing backend service tests for account creation, manual crediting, debit application, and per-member usage aggregation**

```python
import gc
import tempfile
import unittest
from pathlib import Path

import config_runtime
import credit_manager
import lesson_manager


class CreditSystemServiceTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base = Path(self.temp_dir.name)
        lesson_manager.DB_PATH = self.base / "lessons.db"
        config_runtime.CFG_PATH = self.base / "config.json"
        config_runtime.write_file_config({})
        lesson_manager.init_db()
        self.owner, _ = lesson_manager.authenticate_user("Kayn", "xingrun2026")

    def tearDown(self):
        gc.collect()
        self.temp_dir.cleanup()

    def test_credit_account_is_created_and_tracks_manual_credit_then_debit(self):
        overview = credit_manager.get_credit_overview(self.owner["organization_id"])
        self.assertEqual(overview["credit_balance"], 0)

        credit_manager.apply_manual_adjustment(
            organization_id=self.owner["organization_id"],
            actor_user_id=self.owner["id"],
            amount=120,
            note="seed credits for test",
        )
        credit_manager.record_ai_charge(
            organization_id=self.owner["organization_id"],
            user_id=self.owner["id"],
            feature_key="consultation_ai_parse",
            provider="openai",
            model="gpt-4o",
            input_tokens=120,
            output_tokens=40,
            credit_cost_final=6,
            source_record_type="consultation_batch",
            source_record_id=7,
            request_id="req-credit-seed",
        )

        updated = credit_manager.get_credit_overview(self.owner["organization_id"])
        self.assertEqual(updated["credit_balance"], 114)
        self.assertEqual(updated["total_recharged"], 120)
        self.assertEqual(updated["total_consumed"], 6)

    def test_member_usage_summary_groups_by_user(self):
        member = lesson_manager.create_registration_request(
            username="member_credit",
            display_name="Credit Member",
            password="secret123",
            organization_name=self.owner["organization_name"],
        )
        approved = lesson_manager.approve_registration_request(member["id"], self.owner["id"])

        credit_manager.apply_manual_adjustment(
            organization_id=self.owner["organization_id"],
            actor_user_id=self.owner["id"],
            amount=100,
            note="seed balance",
        )
        credit_manager.record_ai_charge(
            organization_id=self.owner["organization_id"],
            user_id=approved["id"],
            feature_key="teacher_feedback_draft",
            provider="openai",
            model="gpt-4o",
            input_tokens=80,
            output_tokens=20,
            credit_cost_final=5,
            source_record_type="lesson",
            source_record_id=12,
            request_id="req-member-usage",
        )

        summary = credit_manager.list_member_usage_summary(self.owner["organization_id"])
        self.assertEqual(summary[0]["user_id"], approved["id"])
        self.assertEqual(summary[0]["credit_consumed"], 5)
        self.assertEqual(summary[0]["usage_count"], 1)
```

- [ ] **Step 2: Run the backend service tests to verify they fail because the new tables and service module do not exist yet**

Run: `cd /Users/ark.mini/Desktop/Xingrun-Review/Xingrun-Summary && /Users/ark.mini/Desktop/Xingrun-Review/.venv/bin/python -m unittest tests.test_credit_system.CreditSystemServiceTestCase -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'credit_manager'` or missing attribute / missing table errors.

- [ ] **Step 3: Add runtime config keys, SQLite schema, and the shared service helpers**

```python
# config_runtime.py
FILE_CONFIG_DEFAULTS = {
    "provider": "openai",
    "xhs_base_url": "https://ark.xiaohongshu.com",
}

ENV_CONTROLLED_KEYS = {
    "openai_api_key",
    "deepseek_api_key",
    "mimo_api_key",
    "n1n_api_key",
    "xhs_app_id",
    "xhs_app_secret",
}
```

```python
# lesson_manager.py inside init_db()
conn.execute(
    """
    CREATE TABLE IF NOT EXISTS organization_credit_accounts (
        organization_id INTEGER PRIMARY KEY REFERENCES organizations(id) ON DELETE CASCADE,
        credit_balance INTEGER NOT NULL DEFAULT 0,
        total_recharged INTEGER NOT NULL DEFAULT 0,
        total_consumed INTEGER NOT NULL DEFAULT 0,
        updated_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
    )
    """
)
conn.execute(
    """
    CREATE TABLE IF NOT EXISTS organization_credit_ledger (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        organization_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
        direction TEXT NOT NULL CHECK(direction IN ('credit','debit')),
        amount INTEGER NOT NULL,
        balance_after INTEGER NOT NULL,
        source_type TEXT NOT NULL,
        source_id TEXT,
        note TEXT NOT NULL DEFAULT '',
        operator_user_id INTEGER REFERENCES users(id),
        created_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
    )
    """
)
conn.execute(
    """
    CREATE TABLE IF NOT EXISTS xhs_order_redemptions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        platform TEXT NOT NULL DEFAULT 'xiaohongshu',
        platform_order_id TEXT NOT NULL,
        product_id TEXT NOT NULL,
        sku_id TEXT NOT NULL DEFAULT '',
        product_name TEXT NOT NULL,
        paid_amount INTEGER NOT NULL,
        currency TEXT NOT NULL DEFAULT 'CNY',
        buyer_masked_phone TEXT NOT NULL DEFAULT '',
        order_status TEXT NOT NULL,
        redeem_status TEXT NOT NULL DEFAULT 'pending',
        credit_amount INTEGER NOT NULL,
        redeemed_organization_id INTEGER REFERENCES organizations(id),
        redeemed_by_user_id INTEGER REFERENCES users(id),
        redeemed_at TEXT,
        raw_order_payload TEXT NOT NULL DEFAULT '{}',
        created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
        updated_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
        UNIQUE(platform, platform_order_id)
    )
    """
)
conn.execute(
    """
    CREATE TABLE IF NOT EXISTS ai_usage_ledger (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        organization_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        feature_key TEXT NOT NULL,
        provider TEXT NOT NULL,
        model TEXT NOT NULL,
        input_tokens INTEGER NOT NULL DEFAULT 0,
        output_tokens INTEGER NOT NULL DEFAULT 0,
        total_tokens INTEGER NOT NULL DEFAULT 0,
        token_cost_raw REAL NOT NULL DEFAULT 0,
        credit_cost_final INTEGER NOT NULL,
        source_record_type TEXT NOT NULL,
        source_record_id TEXT NOT NULL,
        request_id TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
    )
    """
)
```

```python
# credit_manager.py
CREDIT_PRICING_RULES = {
    "consultation_ai_parse": {"base_credits": 3, "extra_token_threshold": 4000, "extra_credits": 2},
    "teacher_feedback_draft": {"base_credits": 2, "extra_token_threshold": 0, "extra_credits": 0},
    "lesson_plan_generate": {"base_credits": 8, "extra_token_threshold": 5000, "extra_credits": 2},
    "audio_transcription": {"base_credits": 4, "extra_token_threshold": 0, "extra_credits": 0},
    "monthly_plan_generate": {"base_credits": 10, "extra_token_threshold": 6000, "extra_credits": 2},
}


def get_credit_overview(organization_id: int) -> dict:
    account = lesson_manager.ensure_credit_account(organization_id)
    return {
        "organization_id": organization_id,
        "credit_balance": account["credit_balance"],
        "total_recharged": account["total_recharged"],
        "total_consumed": account["total_consumed"],
        "updated_at": account["updated_at"],
    }


def apply_manual_adjustment(*, organization_id: int, actor_user_id: int, amount: int, note: str) -> dict:
    source_type = "manual_adjustment"
    direction = "credit" if amount >= 0 else "debit"
    return lesson_manager.insert_credit_ledger_entry(
        organization_id=organization_id,
        direction=direction,
        amount=abs(amount),
        source_type=source_type,
        source_id="manual",
        note=note,
        operator_user_id=actor_user_id,
    )


def record_ai_charge(*, organization_id: int, user_id: int, feature_key: str, provider: str, model: str, input_tokens: int, output_tokens: int, credit_cost_final: int, source_record_type: str, source_record_id: int | str, request_id: str) -> dict:
    usage_row = lesson_manager.insert_ai_usage_row(
        organization_id=organization_id,
        user_id=user_id,
        feature_key=feature_key,
        provider=provider,
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        credit_cost_final=credit_cost_final,
        source_record_type=source_record_type,
        source_record_id=str(source_record_id),
        request_id=request_id,
    )
    lesson_manager.insert_credit_ledger_entry(
        organization_id=organization_id,
        direction="debit",
        amount=credit_cost_final,
        source_type="ai_usage",
        source_id=str(usage_row["id"]),
        note=feature_key,
        operator_user_id=user_id,
    )
    return usage_row
```

- [ ] **Step 4: Run the backend service tests to verify the storage and aggregation foundation passes**

Run: `cd /Users/ark.mini/Desktop/Xingrun-Review/Xingrun-Summary && /Users/ark.mini/Desktop/Xingrun-Review/.venv/bin/python -m unittest tests.test_credit_system.CreditSystemServiceTestCase -v`

Expected: PASS for the new credit service tests, with green assertions for balance, totals, and grouped member usage.

- [ ] **Step 5: Commit the storage and service foundation**

```bash
cd /Users/ark.mini/Desktop/Xingrun-Review/Xingrun-Summary
git add tests/test_credit_system.py credit_manager.py lesson_manager.py config_runtime.py
git commit -m "feat: add credit ledger storage and service layer"
```

## Task 2: Add Xiaohongshu Redemption And Owner Credit Center APIs

**Files:**
- Modify: `tests/test_credit_system.py`
- Create: `xhs_open_platform.py`
- Modify: `credit_manager.py`
- Modify: `app.py`

- [ ] **Step 1: Write failing API tests for owner redemption, duplicate prevention, owner-only access, and credit center reads**

```python
from unittest.mock import patch
import app as app_module


class CreditSystemApiTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base = Path(self.temp_dir.name)
        lesson_manager.DB_PATH = self.base / "lessons.db"
        config_runtime.CFG_PATH = self.base / "config.json"
        config_runtime.write_file_config({})
        lesson_manager.init_db()
        self.client = app_module.app.test_client()
        login = self.client.post("/api/login", json={"username": "Kayn", "password": "xingrun2026"})
        self.owner_token = login.get_json()["token"]

    def auth_headers(self, token: str) -> dict[str, str]:
        return {"X-Auth-Token": token}

    @patch("app.fetch_xhs_order_for_redemption")
    def test_owner_can_redeem_paid_xhs_order_once(self, mock_fetch):
        mock_fetch.return_value = {
            "platform_order_id": "XHS-1001",
            "product_id": "sku-credit-300",
            "sku_id": "sku-credit-300",
            "product_name": "300积分包",
            "paid_amount": 9900,
            "currency": "CNY",
            "buyer_masked_phone": "13800001234",
            "order_status": "paid",
            "credit_amount": 300,
            "raw_order_payload": {"status": "paid"},
        }

        redeem = self.client.post(
            "/api/credits/redeem/xhs",
            headers=self.auth_headers(self.owner_token),
            json={"platform_order_id": "XHS-1001", "phone_suffix": "1234"},
        )
        self.assertEqual(redeem.status_code, 200)
        self.assertEqual(redeem.get_json()["overview"]["credit_balance"], 300)

        duplicate = self.client.post(
            "/api/credits/redeem/xhs",
            headers=self.auth_headers(self.owner_token),
            json={"platform_order_id": "XHS-1001", "phone_suffix": "1234"},
        )
        self.assertEqual(duplicate.status_code, 409)

    @patch("app.fetch_xhs_order_for_redemption")
    def test_credit_center_read_apis_return_overview_ledger_and_member_summary(self, mock_fetch):
        mock_fetch.return_value = {
            "platform_order_id": "XHS-2002",
            "product_id": "sku-credit-100",
            "sku_id": "sku-credit-100",
            "product_name": "100积分包",
            "paid_amount": 3900,
            "currency": "CNY",
            "buyer_masked_phone": "13600005678",
            "order_status": "paid",
            "credit_amount": 100,
            "raw_order_payload": {"status": "paid"},
        }
        self.client.post(
            "/api/credits/redeem/xhs",
            headers=self.auth_headers(self.owner_token),
            json={"platform_order_id": "XHS-2002", "phone_suffix": "5678"},
        )

        overview = self.client.get("/api/credits/overview", headers=self.auth_headers(self.owner_token))
        ledger = self.client.get("/api/credits/ledger", headers=self.auth_headers(self.owner_token))
        members = self.client.get("/api/credits/member-usage", headers=self.auth_headers(self.owner_token))
        member_details = self.client.get("/api/credits/member-usage/1", headers=self.auth_headers(self.owner_token))

        self.assertEqual(overview.status_code, 200)
        self.assertEqual(ledger.status_code, 200)
        self.assertEqual(members.status_code, 200)
        self.assertEqual(member_details.status_code, 200)
        self.assertEqual(overview.get_json()["credit_balance"], 100)
        self.assertEqual(ledger.get_json()["items"][0]["source_type"], "xhs_order_redeem")
```

- [ ] **Step 2: Run the new API tests to confirm they fail because the redemption adapter and routes do not exist yet**

Run: `cd /Users/ark.mini/Desktop/Xingrun-Review/Xingrun-Summary && /Users/ark.mini/Desktop/Xingrun-Review/.venv/bin/python -m unittest tests.test_credit_system.CreditSystemApiTestCase -v`

Expected: FAIL with missing `fetch_xhs_order_for_redemption` import and missing `/api/credits/*` routes.

- [ ] **Step 3: Implement the Xiaohongshu adapter, redemption service, and owner APIs**

```python
# xhs_open_platform.py
from config_runtime import get_runtime_config


def fetch_xhs_order_for_redemption(*, platform_order_id: str, phone_suffix: str) -> dict:
    cfg = get_runtime_config()
    app_id = (cfg.get("xhs_app_id") or os.environ.get("XHS_APP_ID", "")).strip()
    app_secret = (cfg.get("xhs_app_secret") or os.environ.get("XHS_APP_SECRET", "")).strip()
    if not app_id or not app_secret:
        raise RuntimeError("小红书订单校验凭证未配置")
    payload = _fetch_order_detail_from_xhs(platform_order_id=platform_order_id, app_id=app_id, app_secret=app_secret, base_url=cfg.get("xhs_base_url", "https://ark.xiaohongshu.com"))
    normalized = _normalize_xhs_paid_order(payload)
    if not normalized["buyer_masked_phone"].endswith(phone_suffix):
        raise ValueError("订单校验信息不匹配")
    return normalized
```

```python
# credit_manager.py
def redeem_xhs_order(*, organization_id: int, actor_user_id: int, platform_order_id: str, phone_suffix: str, order_payload: dict) -> dict:
    existing = lesson_manager.get_xhs_redemption_by_order_id(platform_order_id)
    if existing and existing["redeem_status"] == "redeemed":
        raise ValueError("order already redeemed")
    redemption = lesson_manager.upsert_xhs_redemption(
        platform_order_id=platform_order_id,
        product_id=order_payload["product_id"],
        sku_id=order_payload["sku_id"],
        product_name=order_payload["product_name"],
        paid_amount=order_payload["paid_amount"],
        currency=order_payload["currency"],
        buyer_masked_phone=order_payload["buyer_masked_phone"],
        order_status=order_payload["order_status"],
        credit_amount=order_payload["credit_amount"],
        redeem_status="redeemed",
        redeemed_organization_id=organization_id,
        redeemed_by_user_id=actor_user_id,
        raw_order_payload=order_payload["raw_order_payload"],
    )
    lesson_manager.insert_credit_ledger_entry(
        organization_id=organization_id,
        direction="credit",
        amount=order_payload["credit_amount"],
        source_type="xhs_order_redeem",
        source_id=str(redemption["id"]),
        note=platform_order_id,
        operator_user_id=actor_user_id,
    )
    return {
        "redemption": redemption,
        "overview": get_credit_overview(organization_id),
    }
```

```python
# app.py
from credit_manager import get_credit_overview, list_credit_ledger, list_member_usage_summary, redeem_xhs_order
from xhs_open_platform import fetch_xhs_order_for_redemption


@app.route("/api/credits/overview", methods=["GET"])
def api_credit_overview():
    user, error = _require_owner()
    if error:
        return error
    return jsonify(get_credit_overview(user["organization_id"]))


@app.route("/api/credits/ledger", methods=["GET"])
def api_credit_ledger():
    user, error = _require_owner()
    if error:
        return error
    return jsonify({"items": list_credit_ledger(user["organization_id"])})


@app.route("/api/credits/member-usage", methods=["GET"])
def api_credit_member_usage():
    user, error = _require_owner()
    if error:
        return error
    return jsonify({"items": list_member_usage_summary(user["organization_id"])})


@app.route("/api/credits/member-usage/<int:user_id>", methods=["GET"])
def api_credit_member_usage_detail(user_id: int):
    user, error = _require_owner()
    if error:
        return error
    return jsonify({"items": list_member_usage_detail(user["organization_id"], user_id)})


@app.route("/api/credits/redeem/xhs", methods=["POST"])
def api_credit_redeem_xhs():
    user, error = _require_owner()
    if error:
        return error
    data = request.get_json(silent=True) or {}
    platform_order_id = str(data.get("platform_order_id", "")).strip()
    phone_suffix = str(data.get("phone_suffix", "")).strip()
    if not platform_order_id or len(phone_suffix) != 4:
        return jsonify({"error": "platform_order_id and 4-digit phone_suffix are required"}), 400
    try:
        order_payload = fetch_xhs_order_for_redemption(platform_order_id=platform_order_id, phone_suffix=phone_suffix)
        result = redeem_xhs_order(
            organization_id=user["organization_id"],
            actor_user_id=user["id"],
            platform_order_id=platform_order_id,
            phone_suffix=phone_suffix,
            order_payload=order_payload,
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 409
    except RuntimeError as exc:
        return jsonify({"error": str(exc)}), 502
    return jsonify(result)
```

- [ ] **Step 4: Run the API tests to verify redemption and owner reads now pass**

Run: `cd /Users/ark.mini/Desktop/Xingrun-Review/Xingrun-Summary && /Users/ark.mini/Desktop/Xingrun-Review/.venv/bin/python -m unittest tests.test_credit_system.CreditSystemApiTestCase -v`

Expected: PASS for owner redemption, duplicate blocking, and overview / ledger / member usage reads, including the per-member drill-down endpoint.

- [ ] **Step 5: Commit the redemption and credit center API layer**

```bash
cd /Users/ark.mini/Desktop/Xingrun-Review/Xingrun-Summary
git add tests/test_credit_system.py xhs_open_platform.py credit_manager.py app.py
git commit -m "feat: add xiaohongshu credit redemption APIs"
```

## Task 3: Enforce Shared Credit Charging In Existing AI Endpoints

**Files:**
- Modify: `tests/test_credit_system.py`
- Modify: `ai_processor.py`
- Modify: `credit_manager.py`
- Modify: `app.py`

- [ ] **Step 1: Write failing backend integration tests for insufficient balance blocking and successful AI usage ledger writes**

```python
from unittest.mock import patch


    @patch("app.parse_consultation_batch_text")
    def test_consultation_ai_parse_blocks_when_balance_is_insufficient(self, mock_parse):
        mock_parse.return_value = {"items": [], "warnings": []}

        response = self.client.post(
            "/api/consultations/ai-parse",
            headers=self.auth_headers(self.owner_token),
            json={"raw_text": "张妈妈，五年级数学"},
        )

        self.assertEqual(response.status_code, 402)
        self.assertIn("积分不足", response.get_json()["error"])

    @patch("app.generate_teacher_feedback_draft")
    def test_teacher_feedback_draft_records_ai_usage_and_deducts_balance(self, mock_feedback):
        credit_manager.apply_manual_adjustment(
            organization_id=1,
            actor_user_id=1,
            amount=30,
            note="seed draft credits",
        )
        mock_feedback.return_value = ("反馈草稿", {"provider": "openai", "model": "gpt-4o", "input_tokens": 220, "output_tokens": 80})

        lesson_id = lesson_manager.save_lesson(
            date_str="2026-04-02",
            subject="数学",
            grade="五年级",
            topic="分数应用题",
            summary="课堂总结",
            weak_points="计算",
            plan={"days": [], "questions": []},
            pdf_path="",
            class_id=None,
        )

        response = self.client.post(
            f"/api/lessons/{lesson_id}/feedback/draft",
            headers=self.auth_headers(self.owner_token),
            json={"students": [{"student_name": "王同学", "performance": "认真"}], "custom_templates": []},
        )

        self.assertEqual(response.status_code, 200)
        overview = self.client.get("/api/credits/overview", headers=self.auth_headers(self.owner_token)).get_json()
        ledger = self.client.get("/api/credits/ledger", headers=self.auth_headers(self.owner_token)).get_json()["items"]
        self.assertEqual(overview["credit_balance"], 28)
        self.assertEqual(ledger[0]["source_type"], "ai_usage")
```

- [ ] **Step 2: Run the AI charging tests and verify they fail because the routes do not yet enforce balance checks or capture usage metadata**

Run: `cd /Users/ark.mini/Desktop/Xingrun-Review/Xingrun-Summary && /Users/ark.mini/Desktop/Xingrun-Review/.venv/bin/python -m unittest tests.test_credit_system.CreditSystemApiTestCase.test_consultation_ai_parse_blocks_when_balance_is_insufficient tests.test_credit_system.CreditSystemApiTestCase.test_teacher_feedback_draft_records_ai_usage_and_deducts_balance -v`

Expected: FAIL because the current routes return `200` without checking balance and do not write credit ledger rows.

- [ ] **Step 3: Make AI helpers return usage metadata and add one shared charge wrapper in the Flask layer**

```python
# ai_processor.py
def _usage_dict(response) -> dict:
    usage = getattr(response, "usage", None)
    return {
        "provider": _load_config().get("provider", "openai"),
        "model": getattr(response, "model", "") or _get_chat_model(),
        "input_tokens": int(getattr(usage, "prompt_tokens", 0) or 0),
        "output_tokens": int(getattr(usage, "completion_tokens", 0) or 0),
    }


def parse_consultation_batch_text(raw_text: str, *, include_usage: bool = False):
    response = client.chat.completions.create(...)
    payload = json.loads(response.choices[0].message.content)
    if include_usage:
        return payload, _usage_dict(response)
    return payload


def generate_teacher_feedback_draft(*, lesson: dict, students: list[dict], custom_templates: list[dict], include_usage: bool = False):
    response = client.chat.completions.create(...)
    merged_text = response.choices[0].message.content.strip()
    if include_usage:
        return merged_text, _usage_dict(response)
    return merged_text
```

```python
# credit_manager.py
def ensure_feature_credits_available(*, organization_id: int, feature_key: str) -> None:
    overview = get_credit_overview(organization_id)
    minimum = CREDIT_PRICING_RULES[feature_key]["base_credits"]
    if overview["credit_balance"] < minimum:
        raise ValueError("机构积分不足，请先充值后再使用 AI 功能")


def finalize_ai_charge(*, organization_id: int, user_id: int, feature_key: str, usage: dict, source_record_type: str, source_record_id: int | str, request_id: str) -> dict:
    total_tokens = int(usage.get("input_tokens", 0)) + int(usage.get("output_tokens", 0))
    pricing = CREDIT_PRICING_RULES[feature_key]
    credits = pricing["base_credits"] + (pricing["extra_credits"] if pricing["extra_token_threshold"] and total_tokens > pricing["extra_token_threshold"] else 0)
    return record_ai_charge(
        organization_id=organization_id,
        user_id=user_id,
        feature_key=feature_key,
        provider=str(usage.get("provider", "")),
        model=str(usage.get("model", "")),
        input_tokens=int(usage.get("input_tokens", 0)),
        output_tokens=int(usage.get("output_tokens", 0)),
        credit_cost_final=credits,
        source_record_type=source_record_type,
        source_record_id=source_record_id,
        request_id=request_id,
    )
```

```python
# app.py
def _charge_ai_feature(*, user: dict, feature_key: str, source_record_type: str, source_record_id: int | str, usage: dict) -> None:
    finalize_ai_charge(
        organization_id=user["organization_id"],
        user_id=user["id"],
        feature_key=feature_key,
        usage=usage,
        source_record_type=source_record_type,
        source_record_id=source_record_id,
        request_id=str(uuid.uuid4()),
    )


@app.route("/api/consultations/ai-parse", methods=["POST"])
def api_consultation_ai_parse():
    user, error = _require_staff()
    if error:
        return error
    try:
        ensure_feature_credits_available(organization_id=user["organization_id"], feature_key="consultation_ai_parse")
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 402
    parsed, usage = parse_consultation_batch_text(cleaned_text, include_usage=True)
    normalized = normalize_consultation_batch_parse_result(parsed)
    _charge_ai_feature(user=user, feature_key="consultation_ai_parse", source_record_type="consultation_batch", source_record_id=raw_text[:32], usage=usage)
    return jsonify(normalized)
```

- [ ] **Step 4: Run targeted backend tests plus the existing AI-route suites to verify charging does not regress route behavior**

Run: `cd /Users/ark.mini/Desktop/Xingrun-Review/Xingrun-Summary && /Users/ark.mini/Desktop/Xingrun-Review/.venv/bin/python -m unittest tests.test_credit_system tests.test_consultation_flow tests.test_teacher_feedback_api -v`

Expected: PASS with new credit blocking / charging assertions and no regressions in consultation parse or teacher feedback route behavior.

- [ ] **Step 5: Commit the AI charging integration**

```bash
cd /Users/ark.mini/Desktop/Xingrun-Review/Xingrun-Summary
git add tests/test_credit_system.py ai_processor.py credit_manager.py app.py
git commit -m "feat: charge organization credits for ai usage"
```

## Task 4: Add The Owner Credit Center In The React Workspace

**Files:**
- Modify: `frontend/src/workspace-navigation.test.ts`
- Create: `frontend/src/credit-center.test.tsx`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Write failing frontend source tests for the owner-only navigation item, overview fetches, redemption form, and member usage sections**

```tsx
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

const source = readFileSync(resolve(process.cwd(), 'src/App.tsx'), 'utf8');

test('workspace navigation exposes a dedicated owner-only credit center page', () => {
  const sidebarBlock = source.match(/const menuItems = \[[\s\S]*?\n  \];/);
  assert.ok(sidebarBlock);
  assert.match(source, /type Page = 'dashboard' \| 'review-generation' \| 'consultation' \| 'calendar' \| 'smartWrongQuestions' \| 'classes' \| 'accounts' \| 'credits' \| 'settings';/);
  assert.match(sidebarBlock[0], /hasOwnerAccess\(currentUser\.role\)[\s\S]*\{ id: 'credits', icon: Database, label: '积分中心' \}/);
  assert.match(source, /activePage === 'credits'[\s\S]*<CreditCenterPage currentUser=\{currentUser\} \/>/);
});

test('credit center source loads overview, ledger, and member usage plus a redemption form', () => {
  const creditCenterBlock = source.match(/const CreditCenterPage = \(\{[\s\S]*?\n};/);
  assert.ok(creditCenterBlock);
  assert.match(creditCenterBlock[0], /apiFetch<CreditOverview>\('\/api\/credits\/overview'\)/);
  assert.match(creditCenterBlock[0], /apiFetch<\{ items: CreditLedgerItem\[] \}>\('\/api\/credits\/ledger'\)/);
  assert.match(creditCenterBlock[0], /apiFetch<\{ items: MemberCreditUsageItem\[] \}>\('\/api\/credits\/member-usage'\)/);
  assert.match(creditCenterBlock[0], /apiFetch<\{ items: MemberCreditUsageDetailItem\[] \}>\(`\/api\/credits\/member-usage\/\$\{selectedMemberId\}`\)/);
  assert.match(creditCenterBlock[0], /platformOrderId/);
  assert.match(creditCenterBlock[0], /phoneSuffix/);
  assert.match(creditCenterBlock[0], /兑换积分/);
  assert.match(creditCenterBlock[0], /成员消耗/);
  assert.match(creditCenterBlock[0], /机构流水/);
  assert.match(creditCenterBlock[0], /调用明细/);
});
```

- [ ] **Step 2: Run the frontend tests to confirm they fail because the page and API wiring do not exist yet**

Run: `cd /Users/ark.mini/Desktop/Xingrun-Review/Xingrun-Summary/frontend && npx tsx --test src/workspace-navigation.test.ts src/credit-center.test.tsx`

Expected: FAIL with missing `credits` page type, missing `CreditCenterPage`, and missing source assertions.

- [ ] **Step 3: Implement the new owner UI in `App.tsx` using the existing workspace patterns**

```tsx
// App.tsx
type Page = 'dashboard' | 'review-generation' | 'consultation' | 'calendar' | 'smartWrongQuestions' | 'classes' | 'accounts' | 'credits' | 'settings';

interface CreditOverview {
  organization_id: number;
  credit_balance: number;
  total_recharged: number;
  total_consumed: number;
  updated_at: string;
}

interface CreditLedgerItem {
  id: number;
  direction: 'credit' | 'debit';
  amount: number;
  source_type: string;
  note: string;
  created_at: string;
}

interface MemberCreditUsageItem {
  user_id: number;
  display_name: string;
  credit_consumed: number;
  usage_count: number;
  last_used_at: string | null;
}

interface MemberCreditUsageDetailItem {
  id: number;
  feature_key: string;
  credit_cost_final: number;
  total_tokens: number;
  created_at: string;
}

const menuItems = [
  { id: 'dashboard', icon: LayoutDashboard, label: '工作台' },
  { id: 'review-generation', icon: Library, label: '复习生成' },
  { id: 'consultation', icon: MessageSquare, label: '咨询记录' },
  ...(hasOwnerAccess(currentUser.role) ? [{ id: 'credits', icon: Database, label: '积分中心' }] : []),
  ...(hasOwnerAccess(currentUser.role) ? [{ id: 'accounts', icon: User, label: '账号审批' }] : []),
  { id: 'settings', icon: Settings, label: '系统设置' },
];
```

```tsx
const CreditCenterPage = ({ currentUser }: { currentUser: CurrentUser }) => {
  const [overview, setOverview] = useState<CreditOverview | null>(null);
  const [ledger, setLedger] = useState<CreditLedgerItem[]>([]);
  const [memberUsage, setMemberUsage] = useState<MemberCreditUsageItem[]>([]);
  const [selectedMemberId, setSelectedMemberId] = useState<number | null>(null);
  const [memberDetails, setMemberDetails] = useState<MemberCreditUsageDetailItem[]>([]);
  const [platformOrderId, setPlatformOrderId] = useState('');
  const [phoneSuffix, setPhoneSuffix] = useState('');
  const [redeemMessage, setRedeemMessage] = useState('');

  const loadCreditPage = async () => {
    const [overviewData, ledgerData, usageData] = await Promise.all([
      apiFetch<CreditOverview>('/api/credits/overview'),
      apiFetch<{ items: CreditLedgerItem[] }>('/api/credits/ledger'),
      apiFetch<{ items: MemberCreditUsageItem[] }>('/api/credits/member-usage'),
    ]);
    setOverview(overviewData);
    setLedger(ledgerData.items);
    setMemberUsage(usageData.items);
  };

  useEffect(() => {
    loadCreditPage().catch(() => undefined);
  }, []);

  useEffect(() => {
    if (!selectedMemberId) {
      setMemberDetails([]);
      return;
    }
    apiFetch<{ items: MemberCreditUsageDetailItem[] }>(`/api/credits/member-usage/${selectedMemberId}`)
      .then((payload) => setMemberDetails(payload.items))
      .catch(() => undefined);
  }, [selectedMemberId]);

  const handleRedeem = async (event: React.FormEvent) => {
    event.preventDefault();
    const payload = await apiFetch<{ overview: CreditOverview }>('/api/credits/redeem/xhs', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ platform_order_id: platformOrderId.trim(), phone_suffix: phoneSuffix.trim() }),
    });
    setOverview(payload.overview);
    setRedeemMessage('积分已充值到当前机构。');
    setPlatformOrderId('');
    setPhoneSuffix('');
    await loadCreditPage();
  };

  return (
    <section className={workspaceCardClass}>
      <h2 className={workspaceSectionTitleClass}>积分中心</h2>
      <p className="mt-2 text-sm text-slate-500 dark:text-slate-400">机构共享积分池会覆盖 {currentUser.organization_name} 的全部 AI 功能消耗。</p>
    </section>
  );
};
```

- [ ] **Step 4: Run the frontend tests plus lint/build verification for the new page**

Run: `cd /Users/ark.mini/Desktop/Xingrun-Review/Xingrun-Summary/frontend && npx tsx --test src/workspace-navigation.test.ts src/credit-center.test.tsx && npm run lint && npm run build`

Expected: PASS for the new source tests, TypeScript check, and Vite build.

- [ ] **Step 5: Commit the owner credit center UI**

```bash
cd /Users/ark.mini/Desktop/Xingrun-Review/Xingrun-Summary
git add frontend/src/App.tsx frontend/src/workspace-navigation.test.ts frontend/src/credit-center.test.tsx
git commit -m "feat: add owner credit center workspace"
```

## Task 5: Add Manual Reversal Support And Run Final Cross-Stack Verification

**Files:**
- Modify: `tests/test_credit_system.py`
- Modify: `credit_manager.py`
- Modify: `app.py`

- [ ] **Step 1: Write a failing backend test for manual negative adjustment after a refunded redeemed order**

```python
    @patch("app.fetch_xhs_order_for_redemption")
    def test_super_owner_can_reverse_redeemed_order_with_negative_adjustment(self, mock_fetch):
        mock_fetch.return_value = {
            "platform_order_id": "XHS-3003",
            "product_id": "sku-credit-100",
            "sku_id": "sku-credit-100",
            "product_name": "100积分包",
            "paid_amount": 3900,
            "currency": "CNY",
            "buyer_masked_phone": "13600005678",
            "order_status": "paid",
            "credit_amount": 100,
            "raw_order_payload": {"status": "paid"},
        }
        self.client.post(
            "/api/credits/redeem/xhs",
            headers=self.auth_headers(self.owner_token),
            json={"platform_order_id": "XHS-3003", "phone_suffix": "5678"},
        )

        response = self.client.post(
            "/api/admin/credits/adjustments",
            headers=self.auth_headers(self.owner_token),
            json={"organization_id": 1, "amount": -40, "note": "refund partial reversal"},
        )

        self.assertEqual(response.status_code, 200)
        overview = self.client.get("/api/credits/overview", headers=self.auth_headers(self.owner_token)).get_json()
        self.assertEqual(overview["credit_balance"], 60)
```

- [ ] **Step 2: Run the refund-adjustment test and confirm it fails because the manual adjustment API is not present**

Run: `cd /Users/ark.mini/Desktop/Xingrun-Review/Xingrun-Summary && /Users/ark.mini/Desktop/Xingrun-Review/.venv/bin/python -m unittest tests.test_credit_system.CreditSystemApiTestCase.test_super_owner_can_reverse_redeemed_order_with_negative_adjustment -v`

Expected: FAIL with missing `/api/admin/credits/adjustments`.

- [ ] **Step 3: Add the manual adjustment endpoint and keep reversal history immutable**

```python
# app.py
@app.route("/api/admin/credits/adjustments", methods=["POST"])
def api_admin_credit_adjustments():
    user, error = _require_owner()
    if error:
        return error
    data = request.get_json(silent=True) or {}
    amount = int(data.get("amount", 0))
    organization_id = int(data.get("organization_id", 0) or 0)
    note = str(data.get("note", "")).strip()
    if not organization_id or amount == 0 or not note:
        return jsonify({"error": "organization_id, amount and note are required"}), 400
    result = apply_manual_adjustment(
        organization_id=organization_id,
        actor_user_id=user["id"],
        amount=amount,
        note=note,
    )
    return jsonify({"entry": result, "overview": get_credit_overview(organization_id)})
```

- [ ] **Step 4: Run the final backend and frontend verification suites**

Run: `cd /Users/ark.mini/Desktop/Xingrun-Review/Xingrun-Summary && /Users/ark.mini/Desktop/Xingrun-Review/.venv/bin/python -m unittest tests.test_credit_system tests.test_account_flow tests.test_consultation_flow tests.test_teacher_feedback_api -v && cd frontend && npx tsx --test src/workspace-navigation.test.ts src/credit-center.test.tsx src/account-card.test.tsx && npm run lint && npm run build`

Expected: PASS across backend credit coverage, account/auth regressions, existing AI-route suites, frontend source tests, TypeScript lint, and production build.

- [ ] **Step 5: Commit the final reconciliation support and verification pass**

```bash
cd /Users/ark.mini/Desktop/Xingrun-Review/Xingrun-Summary
git add tests/test_credit_system.py credit_manager.py app.py
git commit -m "feat: add credit reversal support and finalize verification"
```
