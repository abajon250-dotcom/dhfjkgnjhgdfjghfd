from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

from config import ADMIN_IDS, CRYPTOBOT_TOKEN, XROCKET_TOKEN
from states.auth import AuthStates
from keyboards.reply import get_main_keyboard, get_cancel_keyboard
from database import (
    add_user,
    get_user_subscription,
    save_vk_account,
    get_user_vk_accounts,
    get_stats
)
from services.vk_service import check_vk_account
from services.payment_service import create_cryptobot_invoice, create_xrocket_invoice

router = Router()


@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    add_user(message.from_user.id)
    sub = get_user_subscription(message.from_user.id)

    is_admin = message.from_user.id in ADMIN_IDS

    text = (
        f"🤖 **Добро пожаловать в Aegis VK!**\n\n"
        f"💎 Статус подписки: {sub['expire_str']}\n\n"
        f"Используйте кнопки меню ниже для работы с ботом:"
    )
    await message.answer(text, reply_markup=get_main_keyboard(is_admin), parse_mode="Markdown")


@router.message(F.text == "❌ Отмена")
async def cancel_handler(message: Message, state: FSMContext):
    await state.clear()
    is_admin = message.from_user.id in ADMIN_IDS
    await message.answer("❌ Действие отменено.", reply_markup=get_main_keyboard(is_admin))


@router.message(F.text == "👤 Профиль")
async def profile_handler(message: Message):
    sub = get_user_subscription(message.from_user.id)
    accounts = get_user_vk_accounts(message.from_user.id)

    text = (
        f"👤 **Ваш профиль:**\n"
        f"🆔 ID: `{message.from_user.id}`\n"
        f"💎 Подписка: {sub['expire_str']}\n"
        f"🔗 Подключено VK аккаунтов: **{len(accounts)}**"
    )
    await message.answer(text, parse_mode="Markdown")


@router.message(F.text == "📋 Мои аккаунты")
async def my_accounts_handler(message: Message):
    accounts = get_user_vk_accounts(message.from_user.id)
    if not accounts:
        await message.answer("❌ У вас пока нет подключенных VK аккаунтов. Нажмите «🔑 Добавить VK аккаунт».")
        return

    text = "📋 **Ваши подключенные аккаунты VK:**\n\n"
    for idx, acc in enumerate(accounts, 1):
        text += f"{idx}. **{acc['name']}** (Друзей: {acc['friends']})\n"

    await message.answer(text, parse_mode="Markdown")


@router.message(F.text == "🛠 Админ-панель")
async def admin_panel_handler(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("❌ У вас нет доступа к этой панели.")
        return

    users_count, accounts_count = get_stats()
    text = (
        f"🛠 **Панель администратора Aegis VK**\n\n"
        f"👥 Всего пользователей в базе: **{users_count}**\n"
        f"🔗 Всего подключено VK аккаунтов: **{accounts_count}**\n"
        f"👑 Статус: Вы авторизованы как владелец (вечная подписка активна)."
    )
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Обновить статистику", callback_data="admin_refresh_stats")]
    ])
    await message.answer(text, reply_markup=keyboard, parse_mode="Markdown")


@router.callback_query(F.data == "admin_refresh_stats")
async def admin_refresh_stats(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    users_count, accounts_count = get_stats()
    text = (
        f"🛠 **Панель администратора Aegis VK**\n\n"
        f"👥 Всего пользователей в базе: **{users_count}**\n"
        f"🔗 Всего подключено VK аккаунтов: **{accounts_count}**\n"
        f"👑 Статус: Вы авторизованы как владелец (вечная подписка активна)."
    )
    try:
        await callback.message.edit_text(text, reply_markup=callback.message.reply_markup, parse_mode="Markdown")
    except Exception:
        pass
    await callback.answer("✅ Статистика обновлена!")


@router.message(F.text == "🔑 Добавить VK аккаунт")
async def add_account_start(message: Message, state: FSMContext):
    sub = get_user_subscription(message.from_user.id)
    if not sub["active"]:
        await message.answer(
            "❌ Для добавления аккаунтов необходима активная подписка! Купите ее в разделе «💎 Купить подписку».")
        return

    await state.set_state(AuthStates.waiting_for_token)
    text = (
        "🔑 **Добавление VK аккаунта**\n\n"
        "Отправьте ваш Access Token от VK аккаунта.\n"
        "*(Убедитесь, что токен получен правильно)*"
    )
    await message.answer(text, reply_markup=get_cancel_keyboard(), parse_mode="Markdown")


@router.message(AuthStates.waiting_for_token)
async def got_token(message: Message, state: FSMContext):
    raw_token = message.text.strip()

    res = await check_vk_account(raw_token)
    is_admin = message.from_user.id in ADMIN_IDS

    if res.get("valid"):
        save_vk_account(message.from_user.id, res["token"], res["name"], res["friends"])
        await state.clear()
        await message.answer(
            f"✅ **Аккаунт успешно добавлен!**\n👤 Имя: {res['name']}\n👥 Друзей: {res['friends']}",
            reply_markup=get_main_keyboard(is_admin),
            parse_mode="Markdown"
        )
    else:
        err = res.get("error", "Неизвестная ошибка")
        if "ip address" in err.lower():
            err = "Токен привязан к другому IP-адресу сервера. Сгенерируйте токен прямо на облачном сервере."
        elif "authorization failed" in err.lower():
            err = "Ошибка авторизации: неверный или просроченный токен."

        if len(err) > 180:
            err = err[:180] + "..."

        await message.answer(
            f"❌ **Ошибка проверки токена:**\n`{err}`\n\nПопробуйте отправить другой токен или нажмите «❌ Отмена».",
            parse_mode="Markdown"
        )


@router.message(F.text == "💎 Купить подписку")
async def buy_subscription_handler(message: Message):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⏳ 1 день — 3 USDT", callback_data="select_days_1")],
        [InlineKeyboardButton(text="📅 7 дней — 7 USDT", callback_data="select_days_7")],
        [InlineKeyboardButton(text="💎 30 дней — 24 USDT", callback_data="select_days_30")]
    ])
    await message.answer("💎 **Выберите срок подписки:**", reply_markup=keyboard, parse_mode="Markdown")


@router.callback_query(F.data.startswith("select_days_"))
async def select_gateway_handler(callback: CallbackQuery):
    days = callback.data.split("_")[2]
    prices = {"1": 3.0, "7": 7.0, "30": 24.0}
    price = prices.get(days, 24.0)

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🤖 CryptoBot (USDT)", callback_data=f"pay_cryptobot_{days}_{price}")],
        [InlineKeyboardButton(text="🚀 XRocket (USDT)", callback_data=f"pay_xrocket_{days}_{price}")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_tariffs")]
    ])
    await callback.message.edit_text(
        f"💳 **Выбран тариф:** {days} дн. ({price} USDT)\nВыберите платежную систему:",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )
    await callback.answer()


@router.callback_query(F.data == "back_to_tariffs")
async def back_to_tariffs(callback: CallbackQuery):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⏳ 1 день — 3 USDT", callback_data="select_days_1")],
        [InlineKeyboardButton(text="📅 7 дней — 7 USDT", callback_data="select_days_7")],
        [InlineKeyboardButton(text="💎 30 дней — 24 USDT", callback_data="select_days_30")]
    ])
    await callback.message.edit_text("💎 **Выберите срок подписки:**", reply_markup=keyboard, parse_mode="Markdown")
    await callback.answer()


@router.callback_query(F.data.startswith("pay_"))
async def process_payment(callback: CallbackQuery):
    parts = callback.data.split("_")
    gateway = parts[1]
    days = int(parts[2])
    amount = float(parts[3])

    description = f"Подписка Aegis VK на {days} дн."

    if gateway == "cryptobot":
        res = await create_cryptobot_invoice(amount, description, CRYPTOBOT_TOKEN)
    elif gateway == "xrocket":
        username = callback.from_user.username if callback.from_user else None
        res = await create_xrocket_invoice(
            amount,
            description,
            XROCKET_TOKEN,
            user_id=callback.from_user.id,
            username=username,
        )
    else:
        await callback.answer("Неизвестный способ оплаты", show_alert=True)
        return

    if res.get("success"):
        pay_url = res["pay_url"]
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔗 Перейти к оплате", url=pay_url)]
        ])
        await callback.message.edit_text(
            f"💳 **Счет на оплату создан ({days} дн. / {amount} USDT)!**\nНажмите кнопку ниже для совершения платежа:",
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
        await callback.answer()
        return

    err = res.get("error", "Ошибка создания счета")
    if len(err) > 180:
        err = err[:180] + "..."
    await callback.answer(f"❌ {err}", show_alert=True)