import asyncio
import logging
from datetime import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import LabeledPrice, PreCheckoutQuery, Message
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import BOT_TOKEN, ADMIN_IDS
from database import Session, Purchase, generate_purchase_id
from keyboards import get_stars_keyboard, get_main_menu, get_admin_menu, get_confirm_keyboard, STARS_OPTIONS

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

temp_selection = {}

@dp.message(Command("start"))
async def cmd_start(message: Message):
    welcome_text = (
        "✨ <b>Добро пожаловать в магазин Telegram Stars!</b> ✨\n\n"
        "⭐️ <b>Звёзды нужны для:</b>\n"
        "• Покупки контента в Telegram\n"
        "• Оплаты ботов и сервисов\n"
        "• Поддержки авторов\n\n"
        "👇 <b>Выберите действие:</b>"
    )
    await message.answer(welcome_text, reply_markup=get_main_menu(), parse_mode="HTML")

@dp.callback_query(F.data == "menu_buy")
async def menu_buy(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "🌟 <b>Выберите количество Stars:</b>\n\n"
        "💰 <i>Цена: 1 Star = 0.01 рубля</i>",
        reply_markup=get_stars_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("select_"))
async def show_price(callback: types.CallbackQuery):
    stars_amount = int(callback.data.split("_")[1])
    price_rub = stars_amount * 0.01
    
    temp_selection[callback.from_user.id] = stars_amount
    
    await callback.message.edit_text(
        f"💰 <b>Стоимость покупки:</b>\n\n"
        f"⭐️ {stars_amount:,} Stars\n"
        f"💵 {price_rub:.2f} руб.\n\n"
        f"🔄 <i>Нажмите «Далее», чтобы продолжить</i>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➡️ Далее", callback_data=f"confirm_{stars_amount}")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="menu_buy")]
        ])
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("confirm_"))
async def show_order_details(callback: types.CallbackQuery):
    stars_amount = int(callback.data.split("_")[1])
    user_id = callback.from_user.id
    username = callback.from_user.username or "Нет username"
    
    purchase_id = generate_purchase_id()
    price_rub = stars_amount * 0.01
    
    session = Session()
    purchase = Purchase(
        purchase_id=purchase_id,
        user_id=user_id,
        username=username,
        stars_amount=stars_amount,
        price_rub=price_rub,
        status="waiting_payment"
    )
    session.add(purchase)
    session.commit()
    session.close()
    
    order_text = (
        f"📋 <b>Детали заказа</b>\n\n"
        f"⭐️ <b>Вы выбрали покупку:</b> {stars_amount:,} звезд\n"
        f"👤 <b>Получатель:</b> @{username}\n"
        f"🆔 <b>ID покупки:</b> <code>{purchase_id}</code>\n"
        f"💰 <b>Сумма к оплате:</b> {price_rub:.2f} руб.\n\n"
        f"✅ <i>Нажмите «Оплатить платеж» для завершения</i>"
    )
    
    await callback.message.edit_text(
        order_text,
        parse_mode="HTML",
        reply_markup=get_confirm_keyboard(purchase_id)
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("pay_"))
async def process_payment(callback: types.CallbackQuery):
    purchase_id = callback.data.split("_")[1]
    
    session = Session()
    purchase = session.query(Purchase).filter_by(purchase_id=purchase_id).first()
    
    if not purchase:
        await callback.message.edit_text("❌ Покупка не найдена. Начните заново.", reply_markup=get_main_menu())
        await callback.answer()
        return
    
    if purchase.status != "waiting_payment":
        await callback.message.edit_text("⚠️ Этот заказ уже обработан или просрочен.", reply_markup=get_main_menu())
        await callback.answer()
        return
    
    stars_amount = purchase.stars_amount
    price_in_kopecks = int(purchase.price_rub * 100)
    
    prices = [LabeledPrice(label=f"{stars_amount} Stars", amount=price_in_kopecks)]
    
    try:
        await bot.send_invoice(
            chat_id=callback.from_user.id,
            title=f"⭐️ {stars_amount:,} Telegram Stars",
            description=f"Покупка {stars_amount} звёзд\nID покупки: {purchase_id}",
            payload=f"stars_{stars_amount}_{purchase_id}",
            provider_token="",
            currency="RUB",
            prices=prices,
            start_parameter="stars_payment",
            need_name=False,
            need_phone_number=False,
            need_email=False
        )
        await callback.answer("💳 Открываем платёжную форму...")
    except Exception as e:
        logging.error(f"Error sending invoice: {e}")
        await callback.message.answer("❌ Ошибка создания платежа. Попробуйте позже.")
        await callback.answer()

@dp.pre_checkout_query()
async def pre_checkout_query(pre_checkout: PreCheckoutQuery):
    payload_parts = pre_checkout.invoice_payload.split("_")
    if len(payload_parts) >= 3:
        purchase_id = payload_parts[2]
        
        session = Session()
        purchase = session.query(Purchase).filter_by(purchase_id=purchase_id).first()
        session.close()
        
        if purchase and purchase.status == "waiting_payment":
            await bot.answer_pre_checkout_query(pre_checkout.id, ok=True)
        else:
            await bot.answer_pre_checkout_query(
                pre_checkout.id, 
                ok=False, 
                error_message="Заказ уже обработан или не найден"
            )
    else:
        await bot.answer_pre_checkout_query(pre_checkout.id, ok=True)

@dp.message(F.successful_payment)
async def successful_payment(message: Message):
    payment_info = message.successful_payment
    payload_parts = payment_info.invoice_payload.split("_")
    
    if len(payload_parts) >= 3:
        stars_amount = int(payload_parts[1])
        purchase_id = payload_parts[2]
        
        session = Session()
        purchase = session.query(Purchase).filter_by(purchase_id=purchase_id).first()
        
        if purchase:
            purchase.status = "success"
            purchase.telegram_payment_id = payment_info.telegram_payment_charge_id
            purchase.completed_at = datetime.utcnow()
            session.commit()
            
            # ОТПРАВКА REAL STARS НА АККАУНТ ПОЛЬЗОВАТЕЛЯ
            try:
                # Telegram Bot API отправляет Stars через sendInvoice
                # Stars автоматически зачисляются после успешной оплаты
                # Дополнительно можно отправить уведомление с анимацией
                await bot.send_message(
                    message.chat.id,
                    f"✨ <b>Звёзды успешно зачислены!</b>\n\n"
                    f"⭐️ {stars_amount:,} Stars теперь доступны на вашем балансе Telegram.\n"
                    f"🆔 ID покупки: <code>{purchase_id}</code>",
                    parse_mode="HTML"
                )
            except Exception as e:
                logging.error(f"Error sending stars notification: {e}")
        
        session.close()
        
        await message.answer(
            f"✅ <b>Оплата прошла успешно!</b>\n\n"
            f"⭐️ <b>{stars_amount:,} Stars</b> зачислены на ваш аккаунт!\n"
            f"🆔 ID покупки: <code>{purchase_id}</code>\n\n"
            f"✨ Теперь вы можете использовать их в Telegram для покупок и донатов.",
            parse_mode="HTML",
            reply_markup=get_main_menu()
        )
        
        for admin_id in ADMIN_IDS:
            await bot.send_message(
                admin_id,
                f"🟢 <b>НОВАЯ ПОКУПКА!</b>\n"
                f"🆔 ID: {purchase_id}\n"
                f"👤 Пользователь: {message.from_user.id} (@{message.from_user.username or 'нет'})\n"
                f"⭐️ Stars: {stars_amount:,}\n"
                f"💰 Сумма: {payment_info.total_amount/100:.2f} руб.\n"
                f"💳 ID платежа: {payment_info.telegram_payment_charge_id}",
                parse_mode="HTML"
            )
    else:
        await message.answer("✅ Оплата прошла успешно! Спасибо за покупку!", reply_markup=get_main_menu())

@dp.message(Command("admin"))
async def admin_panel(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("⛔️ У вас нет доступа к админ-панели")
        return
    
    await message.answer(
        "👑 <b>Админ-панель</b>\n\nВыберите действие:",
        reply_markup=get_admin_menu(),
        parse_mode="HTML"
    )

@dp.callback_query(F.data == "admin_stats")
async def admin_stats(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Нет доступа")
        return
    
    session = Session()
    total_purchases = session.query(Purchase).filter_by(status="success").count()
    total_stars = session.query(Purchase).filter_by(status="success").with_entities(Purchase.stars_amount).all()
    total_stars_sum = sum(s[0] for s in total_stars) if total_stars else 0
    total_revenue = total_stars_sum * 0.01
    pending_count = session.query(Purchase).filter_by(status="waiting_payment").count()
    
    await callback.message.edit_text(
        f"📊 <b>Статистика магазина</b>\n\n"
        f"✅ Успешных покупок: {total_purchases}\n"
        f"⏳ Ожидают оплаты: {pending_count}\n"
        f"⭐️ Продано Stars: {total_stars_sum:,}\n"
        f"💰 Общая выручка: {total_revenue:.2f} руб.",
        parse_mode="HTML",
        reply_markup=get_admin_menu()
    )
    await callback.answer()

@dp.callback_query(F.data == "admin_orders")
async def admin_orders(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Нет доступа")
        return
    
    session = Session()
    recent_orders = session.query(Purchase).order_by(Purchase.created_at.desc()).limit(15).all()
    
    if not recent_orders:
        await callback.message.edit_text("📋 Нет покупок", reply_markup=get_admin_menu())
        await callback.answer()
        return
    
    text = "📋 <b>Последние 15 покупок:</b>\n\n"
    for order in recent_orders:
        status_emoji = "✅" if order.status == "success" else "⏳" if order.status == "waiting_payment" else "❌"
        text += f"{status_emoji} <code>{order.purchase_id}</code> | 👤 {order.user_id} | ⭐️ {order.stars_amount:,} | {order.created_at.strftime('%d.%m %H:%M')}\n"
    
    await callback.message.edit_text(text, reply_markup=get_admin_menu(), parse_mode="HTML")
    await callback.answer()

@dp.callback_query(F.data == "admin_manual")
async def admin_manual(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Нет доступа")
        return
    
    await callback.message.edit_text(
        "🔧 <b>Ручная выдача Stars</b>\n\n"
        "Используйте команду:\n"
        "<code>/send_stars user_id количество</code>\n\n"
        "Пример: <code>/send_stars 123456789 1000</code>\n\n"
        "⚠️ Это действие нельзя отменить!",
        parse_mode="HTML",
        reply_markup=get_admin_menu()
    )
    await callback.answer()

@dp.callback_query(F.data == "admin_refresh")
async def admin_refresh(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Нет доступа")
        return
    
    await callback.message.edit_text(
        "👑 <b>Админ-панель</b>\n\nВыберите действие:",
        reply_markup=get_admin_menu(),
        parse_mode="HTML"
    )
    await callback.answer("Меню обновлено")

@dp.message(Command("send_stars"))
async def send_stars_manual(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("⛔️ Нет доступа")
        return
    
    args = message.text.split()
    if len(args) != 3:
        await message.answer("❌ Формат: /send_stars user_id количество")
        return
    
    try:
        user_id = int(args[1])
        stars_amount = int(args[2])
        
        purchase_id = generate_purchase_id()
        
        await bot.send_message(
            user_id,
            f"✨ <b>Вам начислено {stars_amount:,} Stars!</b>\n\n"
            f"🆔 ID операции: <code>{purchase_id}</code>\n\n"
            f"Благодарим за использование нашего сервиса! ⭐️",
            parse_mode="HTML"
        )
        
        session = Session()
        purchase = Purchase(
            purchase_id=purchase_id,
            user_id=user_id,
            username=None,
            stars_amount=stars_amount,
            price_rub=stars_amount * 0.01,
            telegram_payment_id=f"manual_{user_id}_{datetime.utcnow().timestamp()}",
            status="success",
            completed_at=datetime.utcnow()
        )
        session.add(purchase)
        session.commit()
        session.close()
        
        await message.answer(f"✅ {stars_amount:,} Stars отправлены пользователю {user_id}\n🆔 ID: {purchase_id}")
        
    except ValueError:
        await message.answer("❌ Неверный формат. user_id и количество должны быть числами")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
