import ast
import asyncio
import importlib.util
import json
import os
import sys
import time
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def load_module(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


os.environ.setdefault("BOT_TOKEN", "123456:TEST")

bot = load_module("taza_bot", "bot.py")
sheets = load_module("taza_sheets_for_tests", "sheets.py")


class MvpHelperTests(unittest.TestCase):
    def test_normalize_order_code(self):
        self.assertEqual(bot.normalize_order_code("42"), "TAZA-00042")
        self.assertEqual(bot.normalize_order_code(" taza-00042 "), "TAZA-00042")
        self.assertEqual(bot.normalize_order_code("bad"), "BAD")

    def test_pickup_window_validation(self):
        self.assertTrue(bot.pickup_window_is_valid("20:00", "21:00"))
        self.assertFalse(bot.pickup_window_is_valid("21:00", "20:00"))
        self.assertFalse(bot.pickup_window_is_valid("bad", "21:00"))

    def test_sheets_truthy_values(self):
        self.assertTrue(sheets._truthy(True))
        self.assertTrue(sheets._truthy("TRUE"))
        self.assertTrue(sheets._truthy("1"))
        self.assertFalse(sheets._truthy("FALSE"))
        self.assertFalse(sheets._truthy(""))

    def test_bot_has_no_duplicate_top_level_definitions(self):
        tree = ast.parse((ROOT / "bot.py").read_text(encoding="utf-8"))
        seen = {}
        duplicates = {}
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                if node.name in seen:
                    duplicates.setdefault(node.name, [seen[node.name]]).append(
                        node.lineno
                    )
                else:
                    seen[node.name] = node.lineno
        self.assertEqual(duplicates, {})

    def test_vendor_claim_payload_and_expiration(self):
        self.assertEqual(
            bot.parse_vendor_claim_payload("vendor_claim_12_abC-123_xyz"),
            (12, "abC-123_xyz"),
        )
        self.assertIsNone(bot.parse_vendor_claim_payload("vendor_claim_bad"))
        recent = {"created_at": datetime.now().isoformat()}
        expired = {
            "created_at": (datetime.now() - timedelta(days=8)).isoformat()
        }
        self.assertFalse(bot.vendor_claim_is_expired(recent))
        self.assertTrue(bot.vendor_claim_is_expired(expired))

    def test_unclaimed_lead_cannot_be_reviewed(self):
        self.assertTrue(
            bot.vendor_lead_review_error(
                {"status": "pending_telegram", "user_id": 0}
            )
        )
        self.assertTrue(
            bot.vendor_lead_review_error({"status": "new", "user_id": ""})
        )
        self.assertEqual(
            bot.vendor_lead_review_error({"status": "new", "user_id": 123}),
            "",
        )

    def test_vendor_lead_claim_is_idempotent(self):
        database = sheets.SheetsDB()
        pending = {
            "lead_id": 4,
            "status": "pending_telegram",
            "claim_token": "secret",
            "user_id": 0,
        }
        database.get_vendor_lead_by_id = lambda _lead_id: dict(pending)
        database.update_vendor_lead = lambda lead_id, **fields: {
            **pending,
            **fields,
        }
        result, claimed = database.claim_vendor_lead(4, "secret", 99, "owner")
        self.assertEqual(result, "claimed")
        self.assertEqual(claimed["user_id"], 99)
        self.assertEqual(claimed["status"], "new")
        self.assertEqual(claimed["claim_token"], "")

        database.get_vendor_lead_by_id = lambda _lead_id: {
            **claimed,
            "claim_token": "",
        }
        repeated, _ = database.claim_vendor_lead(4, "secret", 99, "owner")
        other_user, _ = database.claim_vendor_lead(4, "secret", 100, "other")
        self.assertEqual(repeated, "already_claimed")
        self.assertEqual(other_user, "claimed_by_other")


class FakeBot:
    username = "taza_test_bot"

    async def send_message(self, *args, **kwargs):
        return None


class FakeRequest:
    def __init__(self, payload, remote="198.51.100.20"):
        self._payload = payload
        self.remote = remote
        self.headers = {}
        self.app = {"bot": FakeBot()}

    async def json(self):
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


VALID_VENDOR_PAYLOAD = {
    "shop_name": "مخبز الاختبار",
    "category": "مخبز ومخبوزات",
    "area": "دمشق – المزة",
    "pickup_address": "المزة، شارع الاختبار",
    "contact_name": "أحمد",
    "whatsapp": "0933123456",
    "closing_time": "22:00",
    "surplus_notes": "مخبوزات",
    "company_website": "",
}


class VendorLeadApiTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        bot._vendor_lead_requests.clear()

    async def test_valid_vendor_lead_submission(self):
        lead = {
            "lead_id": 7,
            "status": "pending_telegram",
            **VALID_VENDOR_PAYLOAD,
        }
        with patch.object(bot.db, "add_vendor_lead", return_value=lead), patch.object(
            bot, "notify_vendor_lead", new=AsyncMock()
        ):
            response = await bot.api_vendor_lead(FakeRequest(VALID_VENDOR_PAYLOAD))
        body = json.loads(response.text)
        self.assertEqual(response.status, 201)
        self.assertTrue(body["success"])
        self.assertEqual(body["lead_id"], 7)
        self.assertEqual(body["status"], "pending_telegram")
        self.assertIn("vendor_claim_7_", body["telegram_url"])

    async def test_invalid_vendor_lead_submission(self):
        payload = {**VALID_VENDOR_PAYLOAD, "whatsapp": "123"}
        response = await bot.api_vendor_lead(FakeRequest(payload))
        self.assertEqual(response.status, 400)
        self.assertFalse(json.loads(response.text)["success"])

    async def test_honeypot_is_silently_discarded(self):
        payload = {**VALID_VENDOR_PAYLOAD, "company_website": "spam.example"}
        with patch.object(bot.db, "add_vendor_lead") as add_lead:
            response = await bot.api_vendor_lead(FakeRequest(payload))
        self.assertEqual(response.status, 201)
        self.assertTrue(json.loads(response.text)["success"])
        add_lead.assert_not_called()

    async def test_rate_limit_returns_retry_after(self):
        bot._vendor_lead_requests["198.51.100.20"] = [
            time.monotonic()
        ] * bot.VENDOR_LEAD_RATE_LIMIT
        response = await bot.api_vendor_lead(FakeRequest(VALID_VENDOR_PAYLOAD))
        self.assertEqual(response.status, 429)
        self.assertEqual(
            response.headers["Retry-After"], str(bot.VENDOR_LEAD_RATE_WINDOW)
        )

    async def test_sheets_failure_returns_service_unavailable(self):
        with patch.object(
            bot.db, "add_vendor_lead", side_effect=RuntimeError("offline")
        ):
            response = await bot.api_vendor_lead(FakeRequest(VALID_VENDOR_PAYLOAD))
        self.assertEqual(response.status, 503)
        self.assertFalse(json.loads(response.text)["success"])


class InMemoryReservationDB(sheets.SheetsDB):
    def __init__(self):
        super().__init__()
        self.bag = {
            "bag_id": 1,
            "restaurant_id": 2,
            "remaining": 1,
            "is_active": True,
        }
        self.orders = []

    def _acquire_lock(self, bag_id):
        return True

    def _release_lock(self, bag_id):
        return None

    def get_bag_by_id(self, bag_id):
        return dict(self.bag)

    def update_bag_field(self, bag_id, field, value):
        self.bag[field] = value

    def create_order(
        self,
        user_id,
        bag_id,
        restaurant_id,
        customer_name,
        customer_phone,
    ):
        order = {
            "order_id": len(self.orders) + 1,
            "user_id": user_id,
            "bag_id": bag_id,
            "restaurant_id": restaurant_id,
            "status": "reserved",
        }
        self.orders.append(order)
        return order


class ReservationConcurrencyTests(unittest.IsolatedAsyncioTestCase):
    async def test_only_one_reservation_wins_the_last_bag(self):
        database = InMemoryReservationDB()
        results = await asyncio.gather(
            database.atomic_reserve(1, 10, "أحمد", "0933000000"),
            database.atomic_reserve(1, 11, "سارة", "0944000000"),
        )
        successes = [result for result in results if result[0]]
        self.assertEqual(len(successes), 1)
        self.assertEqual(database.bag["remaining"], 0)
        self.assertEqual(len(database.orders), 1)


if __name__ == "__main__":
    unittest.main()
