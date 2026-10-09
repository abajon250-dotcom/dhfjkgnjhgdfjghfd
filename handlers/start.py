import os
from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

from states.auth import AuthStates
from keyboards.reply import get_main_keyboard, get_cancel_keyboard
from database import (
    add_user, 
    get_user_subscription, 
    save_vk_account, 
    get_user_vk_accounts
)
from services.vk_service import check_vk_account
from services.payment_service import create_cryptobot_invoice, create_xrocket_invoice

router = Router()

ADMIN_IDS = [int(i.strip()) for i in os.getenv("ADMIN_IDS", "").split(",") if i.strip()]

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

@router.message(F.text == "🔑 Добавить VK аккаунт")
async def add_account_start(message: Message, state: FSMContext):
    sub = get_user_subscription(message.from_user.id)
    if not sub["active"]:
        await message.answer("❌ Для добавления аккаунтов необходима активная подписка! Купите ее в разделе «💎 Купить подписку».")
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
        await message.answer(
            f"❌ **Ошибка проверки токена:**\n`{err}`\n\nПопробуйте отправить другой токен или нажмите «❌ Отмена».",
            parse_mode="Markdown"
        )

@router.message(F.text == "💎 Купить подписку")
async def buy_subscription_handler(message: Message):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🤖 Оплатить через CryptoBot (USDT)", callback_data="pay_cryptobot")],
        [InlineKeyboardButton(text="🚀 Оплатить через XRocket (USDT)", callback_data="pay_xrocket")]
    ])
    await message.answer("💎 **Выберите способ оплаты подписки (30 дней):**", reply_markup=keyboard, parse_mode="Markdown")

@router.callback_query(F.data.startswith("pay_"))
async def process_payment(callback: CallbackQuery):
    action = callback.data.split("_")[1]
    amount = 5.0
    
    cryptobot_token = os.getenv("CRYPTOBOT_TOKEN", "")
    xrocket_token = os.getenv("XROCKET_TOKEN", "")
    
    if action == "cryptobot":
        res = await create_cryptobot_invoice(amount, cryptobot_token)
    elif action == "xrocket":
        res = await create_xrocket_invoice(amount, xrocket_token)
    else:
        await callback.answer("Неизвестный способ оплаты", show_alert=True)
        return
        
    if res.get("success"):
        pay_url = res["pay_url"]
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔗 Перейти к оплате", url=pay_url)]
        ])
        await callback.message.edit_text("💳 **Счет на оплату создан!**\nНажмите кнопку ниже для совершения платежа:", reply_markup=keyboard, parse_mode="Markdown")
    else:
        err = res.get("error", "Ошибка создания счета")
        await callback.answer(f"❌ Ошибка: {err}", show_alert=True)
    
    await callback.answer()
