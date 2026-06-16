"""
scheduler.py – APScheduler async jobs.
Pickup reminders (30 min before window) + nightly restaurant summaries.
"""

import html
import logging
from datetime import datetime, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from telegram import Bot
from telegram.constants import ParseMode

from sheets import db

logger = logging.getLogger(__name__)


def e(text) -> str:
    return html.escape(str(text))


def b(text) -> str:
    return f"<b>{text}</b>"


def code(text) -> str:
    return f"<code>{text}</code>"


async def send_pickup_reminders(bot: Bot):
    """Send reminders to customers 30 minutes before their pickup window."""
    try:
        today_orders = await bot.get_event_loop().run_in_executor(
            None, db.get_today_orders
        )
        now = datetime.now()

        for order in today_orders:
            if order.get("status") != "reserved":
                continue

            bag = await bot.get_event_loop().run_in_executor(
                None, db.get_bag_by_id, order["bag_id"]
            )
            if not bag:
                continue

            try:
                pickup_start_str = bag.get("pickup_start", "")
                if not pickup_start_str:
                    continue
                pickup_time = datetime.strptime(
                    f"{now.date()} {pickup_start_str}", "%Y-%m-%d %H:%M"
                )
            except ValueError:
                continue

            delta = pickup_time - now
            # Send reminder if 28–32 minutes away (window to avoid double-send)
            if timedelta(minutes=28) <= delta <= timedelta(minutes=32):
                rest = await bot.get_event_loop().run_in_executor(
                    None, db.get_restaurant_by_id, bag["restaurant_id"]
                )
                rest_name = rest["name"] if rest else "المطعم"
                rest_address = rest.get("pickup_address", "") if rest else ""

                msg = (
                    f"⏰ {b('تذكير بالاستلام')}\n\n"
                    f"طلبك من {b(e(rest_name))} جاهز للاستلام بعد 30 دقيقة.\n"
                    f"رمز الطلب: {code(order['order_code'])}\n"
                    f"وقت الاستلام: {bag['pickup_start']}–{bag['pickup_end']}\n"
                    f"الموقع: {e(rest_address)}"
                )
                try:
                    await bot.send_message(
                        chat_id=order["user_id"],
                        text=msg,
                        parse_mode=ParseMode.HTML,
                    )
                    logger.info("Sent pickup reminder to user %s", order["user_id"])
                except Exception as e:
                    logger.warning("Could not send reminder to %s: %s", order["user_id"], e)

    except Exception as e:
        logger.error("Error in send_pickup_reminders: %s", e)


async def send_daily_summaries(bot: Bot):
    """Send nightly summary to each restaurant that had bags today."""
    try:
        restaurants = await bot.get_event_loop().run_in_executor(
            None, db.get_all_restaurants
        )

        for rest in restaurants:
            rid = rest["restaurant_id"]
            manager_id = rest.get("manager_chat_id")
            if not manager_id:
                continue

            bags = await bot.get_event_loop().run_in_executor(
                None, db.get_bags_for_restaurant, rid
            )
            if not bags:
                continue

            orders = await bot.get_event_loop().run_in_executor(
                None, db.get_orders_for_restaurant_today, rid
            )

            total_bags = sum(int(b.get("quantity", 0)) for b in bags)
            sold = len([o for o in orders if o["status"] in ("reserved", "picked_up")])
            revenue = sum(
                int(db.get_bag_by_id(o["bag_id"]).get("discounted_price", 0))
                for o in orders
                if o["status"] in ("reserved", "picked_up")
            )

            date_str = datetime.now().strftime("%Y-%m-%d")
            msg = (
                f"📊 {b(f'ملخص يوم {date_str}')}\n\n"
                f"إجمالي الأكياس: {b(str(total_bags))}\n"
                f"✅ المباعة: {b(str(sold))}\n"
                f"📦 المتبقية: {b(str(total_bags - sold))}\n"
                f"💰 الإيرادات المتوقعة: {b(f'{revenue:,} ل.س')}\n\n"
                f"شكراً لشراكتك مع {b('تازا')} 💚"
            )
            try:
                await bot.send_message(
                    chat_id=int(manager_id),
                    text=msg,
                    parse_mode=ParseMode.HTML,
                )
            except Exception as e:
                logger.warning("Could not send summary to restaurant %s: %s", rid, e)

    except Exception as e:
        logger.error("Error in send_daily_summaries: %s", e)


async def send_post_pickup_ratings(bot: Bot):
    """After pickup window ends, ask customers to rate their experience."""
    try:
        today_orders = await bot.get_event_loop().run_in_executor(
            None, db.get_today_orders
        )
        now = datetime.now()

        for order in today_orders:
            if order.get("status") != "reserved":
                continue

            bag = await bot.get_event_loop().run_in_executor(
                None, db.get_bag_by_id, order["bag_id"]
            )
            if not bag:
                continue

            try:
                pickup_end_str = bag.get("pickup_end", "")
                pickup_end = datetime.strptime(
                    f"{now.date()} {pickup_end_str}", "%Y-%m-%d %H:%M"
                )
            except ValueError:
                continue

            # Rate 5–10 minutes after pickup window ends
            delta = now - pickup_end
            if timedelta(minutes=5) <= delta <= timedelta(minutes=10):
                from telegram import InlineKeyboardButton, InlineKeyboardMarkup

                keyboard = InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton(
                                "👍 ممتاز", callback_data=f"rate_good_{order['order_id']}"
                            ),
                            InlineKeyboardButton(
                                "👎 سيء", callback_data=f"rate_bad_{order['order_id']}"
                            ),
                        ]
                    ]
                )
                try:
                    await bot.send_message(
                        chat_id=order["user_id"],
                        text=(
                            f"كيف كانت تجربتك مع طلب {code(order['order_code'])}؟ 😊\n"
                            "رأيك يهمنا ويساعدنا نتحسن."
                        ),
                        parse_mode=ParseMode.HTML,
                        reply_markup=keyboard,
                    )
                except Exception as e:
                    logger.warning("Could not send rating prompt to %s: %s", order["user_id"], e)

    except Exception as e:
        logger.error("Error in send_post_pickup_ratings: %s", e)


def setup_scheduler(bot: Bot) -> AsyncIOScheduler:
    """Create and start the async scheduler with all jobs."""
    scheduler = AsyncIOScheduler()

    # Pickup reminders: check every minute
    scheduler.add_job(
        send_pickup_reminders,
        "interval",
        minutes=1,
        args=[bot],
        id="pickup_reminders",
        max_instances=1,
    )

    # Post-pickup ratings: check every minute
    scheduler.add_job(
        send_post_pickup_ratings,
        "interval",
        minutes=1,
        args=[bot],
        id="post_pickup_ratings",
        max_instances=1,
    )

    # Daily summary at 23:00
    scheduler.add_job(
        send_daily_summaries,
        "cron",
        hour=23,
        minute=0,
        args=[bot],
        id="daily_summaries",
        max_instances=1,
    )

    scheduler.start()
    logger.info("Scheduler started.")
    return scheduler
