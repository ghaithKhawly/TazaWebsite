"""
sheets.py – Google Sheets database layer for Taza bot.
Handles all CRUD, locking, and atomic reservation logic.
"""

import asyncio
import logging
import os
import random
import time
from datetime import datetime
from typing import Optional

import gspread
from gspread.utils import rowcol_to_a1
from google.oauth2.service_account import Credentials

logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

SHEET_SCHEMAS = {
    "users": [
        "user_id",
        "name",
        "phone",
        "default_area",
        "role",
        "created_at",
    ],
    "restaurants": [
        "restaurant_id",
        "name",
        "area",
        "pickup_address",
        "manager_chat_id",
        "is_active",
        "added_at",
    ],
    "bags": [
        "bag_id",
        "restaurant_id",
        "date",
        "type",
        "hint",
        "original_price",
        "discounted_price",
        "quantity",
        "remaining",
        "pickup_start",
        "pickup_end",
        "is_active",
        "photo_file_id",
        "created_at",
    ],
    "orders": [
        "order_id",
        "user_id",
        "bag_id",
        "restaurant_id",
        "order_code",
        "status",
        "customer_name",
        "customer_phone",
        "created_at",
        "updated_at",
    ],
    "config": ["key", "value"],
    "locks": ["bag_id", "locked", "locked_at"],
    "vendor_leads": [
        "lead_id",
        "user_id",
        "username",
        "shop_name",
        "category",
        "area",
        "pickup_address",
        "contact_name",
        "whatsapp",
        "closing_time",
        "surplus_notes",
        "interest_level",
        "main_concern",
        "status",
        "source",
        "created_at",
    ],
}

LOCK_TIMEOUT = 10  # seconds
LOCK_RETRY_DELAY = 0.3  # seconds
LOCK_MAX_RETRIES = 8


class SheetsDB:
    def __init__(self):
        self.gc: Optional[gspread.Client] = None
        self.spreadsheet: Optional[gspread.Spreadsheet] = None
        self._sheets: dict = {}

    def connect(self):
        """Initialize Google Sheets connection from env credentials."""
        import json

        creds_json = os.environ.get("GOOGLE_SHEETS_CREDENTIALS")
        if not creds_json:
            raise ValueError("GOOGLE_SHEETS_CREDENTIALS env var not set")
        creds_json = creds_json.strip()
        if (
            len(creds_json) >= 2
            and creds_json[0] == creds_json[-1]
            and creds_json[0] in ("'", '"')
        ):
            creds_json = creds_json[1:-1]

        creds_dict = json.loads(creds_json)
        creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
        self.gc = gspread.authorize(creds)

        spreadsheet_name = os.environ.get("SPREADSHEET_NAME", "Taza Bot DB")
        self.spreadsheet = self.gc.open(spreadsheet_name)
        self._load_sheets()
        logger.info("Connected to Google Sheets: %s", spreadsheet_name)

    def _load_sheets(self):
        """Cache worksheet references."""
        required = list(SHEET_SCHEMAS.keys())
        for name in required:
            try:
                self._sheets[name] = self.spreadsheet.worksheet(name)
            except gspread.WorksheetNotFound:
                logger.warning("Sheet '%s' not found – run init_sheets() first", name)

    def sheet(self, name: str) -> gspread.Worksheet:
        if name not in self._sheets:
            try:
                self._sheets[name] = self.spreadsheet.worksheet(name)
            except gspread.WorksheetNotFound:
                headers = SHEET_SCHEMAS.get(name)
                if not headers:
                    raise
                ws = self.spreadsheet.add_worksheet(
                    title=name, rows=1000, cols=len(headers)
                )
                ws.append_row(headers)
                self._sheets[name] = ws
                logger.info("Created missing sheet: %s", name)
        return self._sheets[name]

    # ─────────────────────────────────────────────
    # INIT: Create sheets if missing
    # ─────────────────────────────────────────────
    def init_sheets(self):
        """Create all required sheets with headers if they don't exist."""
        existing = [ws.title for ws in self.spreadsheet.worksheets()]

        for name, headers in SHEET_SCHEMAS.items():
            if name not in existing:
                ws = self.spreadsheet.add_worksheet(
                    title=name, rows=1000, cols=len(headers)
                )
                ws.append_row(headers)
                self._sheets[name] = ws
                logger.info("Created sheet: %s", name)
            else:
                self._sheets[name] = self.spreadsheet.worksheet(name)

        # Seed config defaults
        self._seed_config()

    def _seed_config(self):
        ws = self.sheet("config")
        rows = self._get_records("config")
        keys_present = {r["key"] for r in rows}
        defaults = {
            "next_order_code": "1",
            "admin_group_chat_id": os.environ.get("ADMIN_GROUP_CHAT_ID", ""),
        }
        for k, v in defaults.items():
            if k not in keys_present:
                ws.append_row([k, v])

    # ─────────────────────────────────────────────
    # HELPERS
    # ─────────────────────────────────────────────
    def _repair_headers(self, ws: gspread.Worksheet, headers: list):
        end_cell = rowcol_to_a1(1, len(headers))
        ws.update(f"A1:{end_cell}", [headers])

    def _ensure_schema(self, sheet_name: str):
        expected = SHEET_SCHEMAS.get(sheet_name)
        if not expected:
            return
        ws = self.sheet(sheet_name)
        headers = ws.row_values(1)

        needs_repair = False
        if not headers:
            needs_repair = True
        elif len(set(headers)) != len(headers):
            needs_repair = True
        elif headers[: len(expected)] != expected:
            needs_repair = True

        if needs_repair:
            self._repair_headers(ws, expected)

    def _get_records(self, sheet_name: str) -> list:
        ws = self.sheet(sheet_name)
        expected = SHEET_SCHEMAS.get(sheet_name)
        if expected:
            self._ensure_schema(sheet_name)
            try:
                return self._retry_api(ws.get_all_records, expected_headers=expected)
            except Exception as e:
                msg = str(e)
                if "header row" in msg or "expected_headers" in msg:
                    self._repair_headers(ws, expected)
                    return self._retry_api(
                        ws.get_all_records, expected_headers=expected
                    )
                raise
        return self._retry_api(ws.get_all_records)

    def _retry_api(self, fn, *args, retries=4, **kwargs):
        """Retry a gspread call with exponential backoff on quota errors."""
        for attempt in range(retries):
            try:
                return fn(*args, **kwargs)
            except gspread.exceptions.APIError as e:
                if e.response.status_code in (429, 503) and attempt < retries - 1:
                    wait = 2**attempt + random.uniform(0, 1)
                    logger.warning("Sheets API rate limit, retry in %.1fs", wait)
                    time.sleep(wait)
                else:
                    raise

    def _next_id(self, sheet_name: str, id_col: str) -> int:
        ws = self.sheet(sheet_name)
        records = self._get_records(sheet_name)
        if not records:
            return 1
        ids = [r[id_col] for r in records if str(r[id_col]).isdigit()]
        return max(int(i) for i in ids) + 1 if ids else 1

    def get_config(self, key: str) -> str:
        ws = self.sheet("config")
        records = self._get_records("config")
        for r in records:
            if r["key"] == key:
                return str(r["value"])
        return ""

    def set_config(self, key: str, value: str):
        ws = self.sheet("config")
        records = self._get_records("config")
        for idx, r in enumerate(records):
            if r["key"] == key:
                ws.update_cell(idx + 2, 2, value)
                return
        ws.append_row([key, value])

    # ─────────────────────────────────────────────
    # USERS
    # ─────────────────────────────────────────────
    def get_user(self, user_id: int) -> Optional[dict]:
        ws = self.sheet("users")
        records = self._get_records("users")
        for r in records:
            if str(r["user_id"]) == str(user_id):
                return r
        return None

    def upsert_user(self, user_id: int, **fields) -> dict:
        ws = self.sheet("users")
        records = self._get_records("users")
        headers = ws.row_values(1)

        for idx, r in enumerate(records):
            if str(r["user_id"]) == str(user_id):
                for k, v in fields.items():
                    if k in headers:
                        col = headers.index(k) + 1
                        ws.update_cell(idx + 2, col, v)
                r.update(fields)
                return r

        # New user
        new_user = {
            "user_id": user_id,
            "name": fields.get("name", ""),
            "phone": fields.get("phone", ""),
            "default_area": fields.get("default_area", ""),
            "role": fields.get("role", "customer"),
            "created_at": datetime.now().isoformat(),
        }
        row = [new_user.get(h, "") for h in headers]
        ws.append_row(row)
        return new_user

    def set_user_area(self, user_id: int, area: str):
        self.upsert_user(user_id, default_area=area)

    def get_all_users(self) -> list:
        return self._get_records("users")

    # ─────────────────────────────────────────────
    # RESTAURANTS
    # ─────────────────────────────────────────────
    def add_restaurant(
        self, name: str, area: str, pickup_address: str, manager_chat_id: int
    ) -> dict:
        ws = self.sheet("restaurants")
        rid = self._next_id("restaurants", "restaurant_id")
        row = [
            rid,
            name,
            area,
            pickup_address,
            manager_chat_id,
            True,
            datetime.now().isoformat(),
        ]
        ws.append_row(row)
        return {
            "restaurant_id": rid,
            "name": name,
            "area": area,
            "pickup_address": pickup_address,
            "manager_chat_id": manager_chat_id,
            "is_active": True,
        }

    def get_restaurant_by_manager(self, manager_chat_id: int) -> Optional[dict]:
        ws = self.sheet("restaurants")
        records = self._get_records("restaurants")
        for r in records:
            if str(r["manager_chat_id"]) == str(manager_chat_id) and r["is_active"]:
                return r
        return None

    def get_restaurant_by_id(self, restaurant_id: int) -> Optional[dict]:
        ws = self.sheet("restaurants")
        records = self._get_records("restaurants")
        for r in records:
            if str(r["restaurant_id"]) == str(restaurant_id):
                return r
        return None

    def get_all_restaurants(self) -> list:
        return [r for r in self._get_records("restaurants") if r["is_active"]]

    # ─────────────────────────────────────────────
    # VENDOR LEADS
    # ─────────────────────────────────────────────
    def add_vendor_lead(
        self,
        user_id: int,
        username: str,
        shop_name: str,
        category: str,
        area: str,
        pickup_address: str,
        contact_name: str,
        whatsapp: str,
        closing_time: str,
        surplus_notes: str,
        interest_level: str,
        main_concern: str,
        source: str = "telegram_bot",
    ) -> dict:
        ws = self.sheet("vendor_leads")
        lead_id = self._next_id("vendor_leads", "lead_id")
        now = datetime.now().isoformat()
        lead = {
            "lead_id": lead_id,
            "user_id": user_id,
            "username": username,
            "shop_name": shop_name,
            "category": category,
            "area": area,
            "pickup_address": pickup_address,
            "contact_name": contact_name,
            "whatsapp": whatsapp,
            "closing_time": closing_time,
            "surplus_notes": surplus_notes,
            "interest_level": interest_level,
            "main_concern": main_concern,
            "status": "new",
            "source": source,
            "created_at": now,
        }
        headers = ws.row_values(1)
        ws.append_row([lead.get(h, "") for h in headers])
        return lead

    def get_vendor_leads(self, limit: int = None) -> list:
        leads = self._get_records("vendor_leads")
        return leads[-limit:] if limit else leads

    # ─────────────────────────────────────────────
    # BAGS
    # ─────────────────────────────────────────────
    def add_bag(
        self,
        restaurant_id: int,
        bag_type: str,
        hint: str,
        original_price: int,
        discounted_price: int,
        quantity: int,
        pickup_start: str,
        pickup_end: str,
        photo_file_id: str = "",
    ) -> dict:
        ws = self.sheet("bags")
        bid = self._next_id("bags", "bag_id")
        today = datetime.now().strftime("%Y-%m-%d")
        row = [
            bid,
            restaurant_id,
            today,
            bag_type,
            hint,
            original_price,
            discounted_price,
            quantity,
            quantity,
            pickup_start,
            pickup_end,
            True,
            photo_file_id,
            datetime.now().isoformat(),
        ]
        ws.append_row(row)
        return {
            "bag_id": bid,
            "restaurant_id": restaurant_id,
            "date": today,
            "type": bag_type,
            "hint": hint,
            "original_price": original_price,
            "discounted_price": discounted_price,
            "quantity": quantity,
            "remaining": quantity,
            "pickup_start": pickup_start,
            "pickup_end": pickup_end,
            "is_active": True,
            "photo_file_id": photo_file_id,
        }

    def get_available_bags(self, area: str = None) -> list:
        """Return today's active bags with remaining > 0, optionally filtered by area."""
        ws = self.sheet("bags")
        records = self._get_records("bags")
        today = datetime.now().strftime("%Y-%m-%d")

        result = []
        for bag in records:
            if (
                bag["date"] == today
                and str(bag["is_active"]).lower() in ("true", "1", "yes")
                and int(bag.get("remaining", 0)) > 0
            ):
                if area:
                    rest = self.get_restaurant_by_id(bag["restaurant_id"])
                    if not rest or rest.get("area") != area:
                        continue
                result.append(bag)
        return result

    def get_bags_for_restaurant(self, restaurant_id: int) -> list:
        ws = self.sheet("bags")
        records = self._get_records("bags")
        today = datetime.now().strftime("%Y-%m-%d")
        return [
            b
            for b in records
            if str(b["restaurant_id"]) == str(restaurant_id) and b["date"] == today
        ]

    def get_bag_by_id(self, bag_id: int) -> Optional[dict]:
        ws = self.sheet("bags")
        records = self._get_records("bags")
        for b in records:
            if str(b["bag_id"]) == str(bag_id):
                return b
        return None

    def update_bag_field(self, bag_id: int, field: str, value):
        self._ensure_schema("bags")
        ws = self.sheet("bags")
        headers = ws.row_values(1)
        records = self._get_records("bags")
        for idx, b in enumerate(records):
            if str(b["bag_id"]) == str(bag_id):
                col = headers.index(field) + 1
                ws.update_cell(idx + 2, col, value)
                return

    def deactivate_bag(self, bag_id: int):
        self.update_bag_field(bag_id, "is_active", False)

    # ─────────────────────────────────────────────
    # ORDERS
    # ─────────────────────────────────────────────
    def _next_order_code(self) -> str:
        ws = self.sheet("config")
        records = self._get_records("config")
        for idx, r in enumerate(records):
            if r["key"] == "next_order_code":
                code_num = int(r["value"])
                ws.update_cell(idx + 2, 2, code_num + 1)
                return f"TAZA-{code_num:05d}"
        ws.append_row(["next_order_code", "2"])
        return "TAZA-00001"

    def create_order(
        self,
        user_id: int,
        bag_id: int,
        restaurant_id: int,
        customer_name: str,
        customer_phone: str,
    ) -> dict:
        ws = self.sheet("orders")
        oid = self._next_id("orders", "order_id")
        order_code = self._next_order_code()
        now = datetime.now().isoformat()
        row = [
            oid,
            user_id,
            bag_id,
            restaurant_id,
            order_code,
            "reserved",
            customer_name,
            customer_phone,
            now,
            now,
        ]
        ws.append_row(row)
        return {
            "order_id": oid,
            "user_id": user_id,
            "bag_id": bag_id,
            "restaurant_id": restaurant_id,
            "order_code": order_code,
            "status": "reserved",
            "customer_name": customer_name,
            "customer_phone": customer_phone,
            "created_at": now,
            "updated_at": now,
        }

    def update_order_status(self, order_id: int, status: str):
        self._ensure_schema("orders")
        ws = self.sheet("orders")
        headers = ws.row_values(1)
        records = self._get_records("orders")
        for idx, o in enumerate(records):
            if str(o["order_id"]) == str(order_id):
                status_col = headers.index("status") + 1
                updated_col = headers.index("updated_at") + 1
                ws.update_cell(idx + 2, status_col, status)
                ws.update_cell(idx + 2, updated_col, datetime.now().isoformat())
                return

    def get_order_by_code(self, order_code: str) -> Optional[dict]:
        ws = self.sheet("orders")
        records = self._get_records("orders")
        for o in records:
            if o["order_code"] == order_code:
                return o
        return None

    def get_order_by_id(self, order_id: int) -> Optional[dict]:
        ws = self.sheet("orders")
        records = self._get_records("orders")
        for o in records:
            if str(o["order_id"]) == str(order_id):
                return o
        return None

    def get_user_orders(self, user_id: int) -> list:
        ws = self.sheet("orders")
        records = self._get_records("orders")
        return [o for o in records if str(o["user_id"]) == str(user_id)]

    def get_today_orders(self) -> list:
        ws = self.sheet("orders")
        records = self._get_records("orders")
        today = datetime.now().strftime("%Y-%m-%d")
        return [o for o in records if o.get("created_at", "").startswith(today)]

    def get_orders_for_restaurant_today(self, restaurant_id: int) -> list:
        ws = self.sheet("orders")
        records = self._get_records("orders")
        today = datetime.now().strftime("%Y-%m-%d")
        return [
            o
            for o in records
            if str(o["restaurant_id"]) == str(restaurant_id)
            and o.get("created_at", "").startswith(today)
        ]

    # ─────────────────────────────────────────────
    # LOCKING (for atomic reservation)
    # ─────────────────────────────────────────────
    def _acquire_lock(self, bag_id: int) -> bool:
        """Try to acquire a lock for a bag. Returns True if acquired."""
        ws = self.sheet("locks")
        records = self._get_records("locks")

        now_ts = time.time()
        for idx, r in enumerate(records):
            if str(r.get("bag_id", "")) == str(bag_id):
                # Check if lock is stale (> LOCK_TIMEOUT seconds old)
                locked_at = float(r.get("locked_at", 0) or 0)
                locked_val = str(r.get("locked", "0")).lower()
                if (
                    locked_val in ("1", "true", "yes")
                    and (now_ts - locked_at) < LOCK_TIMEOUT
                ):
                    return False  # Lock held by someone else
                # Acquire (overwrite)
                ws.update(f"A{idx+2}:C{idx+2}", [[bag_id, 1, now_ts]])
                return True

        # No lock row exists – create one
        ws.append_row([bag_id, 1, now_ts])
        return True

    def _release_lock(self, bag_id: int):
        ws = self.sheet("locks")
        records = self._get_records("locks")
        for idx, r in enumerate(records):
            if str(r.get("bag_id", "")) == str(bag_id):
                ws.update(f"A{idx+2}:C{idx+2}", [[bag_id, 0, 0]])
                return

    async def atomic_reserve(
        self,
        bag_id: int,
        user_id: int,
        customer_name: str,
        customer_phone: str,
    ) -> tuple[bool, Optional[dict], str]:
        """
        Atomically reserve a bag.
        Returns (success, order_dict, message_ar)
        """
        loop = asyncio.get_event_loop()

        for attempt in range(LOCK_MAX_RETRIES):
            # Try to acquire lock in thread pool (blocking IO)
            acquired = await loop.run_in_executor(None, self._acquire_lock, bag_id)
            if not acquired:
                delay = LOCK_RETRY_DELAY + random.uniform(0, 0.2)
                await asyncio.sleep(delay)
                continue

            try:
                # Re-read bag inside lock
                bag = await loop.run_in_executor(None, self.get_bag_by_id, bag_id)
                if not bag:
                    return False, None, "الكيس غير موجود."

                remaining = int(bag.get("remaining", 0))
                if remaining <= 0:
                    return False, None, "عذراً، نفذت الكمية للتو."

                # Decrement remaining
                new_remaining = remaining - 1
                await loop.run_in_executor(
                    None, self.update_bag_field, bag_id, "remaining", new_remaining
                )
                if new_remaining == 0:
                    await loop.run_in_executor(
                        None, self.update_bag_field, bag_id, "is_active", False
                    )

                # Create order
                restaurant_id = bag["restaurant_id"]
                order = await loop.run_in_executor(
                    None,
                    self.create_order,
                    user_id,
                    bag_id,
                    restaurant_id,
                    customer_name,
                    customer_phone,
                )
                return True, order, "تم الحجز بنجاح!"

            finally:
                await loop.run_in_executor(None, self._release_lock, bag_id)

        return False, None, "النظام مشغول حالياً. حاول مجدداً بعد لحظة."

    async def cancel_reservation(self, order_id: int, bag_id: int) -> bool:
        """Cancel an order and restore bag quantity."""
        loop = asyncio.get_event_loop()
        for attempt in range(LOCK_MAX_RETRIES):
            acquired = await loop.run_in_executor(None, self._acquire_lock, bag_id)
            if not acquired:
                await asyncio.sleep(LOCK_RETRY_DELAY + random.uniform(0, 0.2))
                continue
            try:
                await loop.run_in_executor(
                    None, self.update_order_status, order_id, "cancelled"
                )
                bag = await loop.run_in_executor(None, self.get_bag_by_id, bag_id)
                if bag:
                    new_remaining = int(bag.get("remaining", 0)) + 1
                    await loop.run_in_executor(
                        None, self.update_bag_field, bag_id, "remaining", new_remaining
                    )
                    await loop.run_in_executor(
                        None, self.update_bag_field, bag_id, "is_active", True
                    )
                return True
            finally:
                await loop.run_in_executor(None, self._release_lock, bag_id)

        return False


# Global singleton
db = SheetsDB()
