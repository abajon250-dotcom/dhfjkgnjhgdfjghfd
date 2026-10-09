import os
import asyncio
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton, \
    ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

import db
from config import CHANNEL_ID, ADMIN_IDS, CRYPTOBOT_TOKEN, XROCKET_TOKEN
from services.vk_service import (
    get_vk_account, check_vk_account,
    change_vk_name, change_vk_password, change_vk_avatar,
    get_vk_friends_txt, get_vk_security_notifications,
    get_vk_friends, send_vk_message
)
from services.payment_service import (
    create_cryptobot_invoice, create_xrocket_invoice
)

router = Router()


class AuthStates(StatesGroup):
    waiting_for_token = State()


class ProfileStates(StatesGroup):
    waiting_for_new_name = State()
    waiting_for_old_pass = State()
    waiting_for_new_pass = State()
    waiting_for_avatar = State()


class BroadcastState(StatesGroup):
    waiting_for_message = State()


class AdminBroadcastState(StatesGroup):
    waiting_for_message = State()


class AdminGrantState(StatesGroup):
    waiting_for_input = State()


class BulkState(StatesGroup):
    waiting = State()


def get_main_reply_keyboard(user_id: int):
    buttons = [
        [KeyboardButton(text="🔑 Добавить аккаунт"), KeyboardButton(text="📂 Мои аккаунты")],
        [KeyboardButton(text="📊 Аналитика и здоровье"), KeyboardButton(text="🚀 Запустить рассылку")],
        [KeyboardButton(text="💳 Подписка и Оплата"), KeyboardButton(text="👤 Профиль")]
    ]
    if ADMIN_IDS and user_id in ADMIN_IDS:
        buttons.append([KeyboardButton(text="👑 Админ-панель")])
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


async def is_subscribed(bot: Bot, user_id: int) -> bool:
    if not CHANNEL_ID:
        return True
    try:
        member = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        return member.status in ("member", "administrator", "creator")
    except Exception:
        return True


@router.message(F.text == "/start")
async def cmd_start(message: Message, state: FSMContext, bot: Bot):
    await state.clear()
    user_id = message.from_user.id
    db.add_or_update_user(user_id, message.from_user.username)

    if not await is_subscribed(bot, user_id):
        channel_link = f"https://t.me/{CHANNEL_ID.replace('@', '')}"
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📢 Подписаться на канал", url=channel_link)],
            [InlineKeyboardButton(text="✅ Я подписался", callback_data="check_sub")]
        ])
        return await message.answer("⚠️ Для использования бота обязательно подпишитесь на наш канал:", reply_markup=kb)

    await message.answer(
        "🛡 **Добро пожаловать в Aegis VK** — систему автоматизации и управления вашими аккаунтами ВКонтакте.\n\n"
        "Используйте кнопки под текстом для навигации:",
        reply_markup=get_main_reply_keyboard(user_id),
        parse_mode="Markdown"
    )


@router.callback_query(F.data == "check_sub")
async def check_sub(call: CallbackQuery, state: FSMContext, bot: Bot):
    if await is_subscribed(bot, call.from_user.id):
        await call.message.delete()
        await cmd_start(call.message, state, bot)
    else:
        await call.answer("❌ Вы еще не подписались на канал!", show_alert=True)


# Проверка подписки перед выполнением действий
async def check_sub_middleware(message: Message, bot: Bot) -> bool:
    if not await is_subscribed(bot, message.from_user.id):
        channel_link = f"https://t.me/{CHANNEL_ID.replace('@', '')}"
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📢 Подписаться", url=channel_link)],
            [InlineKeyboardButton(text="✅ Проверить подписку", callback_data="check_sub")]
        ])
        await message.answer("⚠️ Для выполнения этого действия подпишитесь на наш канал:", reply_markup=kb)
        return False
    return True


# --- ТЕКСТОВЫЕ КНОПКИ ---
@router.message(F.text == "🔑 Добавить аккаунт")
async def btn_add_account(message: Message, bot: Bot):
    if not await check_sub_middleware(message, bot): return
    if not db.is_sub_active(message.from_user.id):
        return await message.answer("❌ Необходима активная подписка!")
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔑 Ввести один токен", callback_data="auth_single_token")],
        [InlineKeyboardButton(text="📥 Загрузить пачкой (.txt)", callback_data="vk_add_bulk")]
    ])
    await message.answer("Выберите способ добавления аккаунта:", reply_markup=kb)


@router.message(F.text == "📂 Мои аккаунты")
async def btn_my_accounts(message: Message, bot: Bot):
    if not await check_sub_middleware(message, bot): return
    accs = db.get_user_vk_accounts(message.from_user.id)
    if not accs:
        return await message.answer("📂 У вас нет добавленных аккаунтов.")

    text = f"📂 **Ваши аккаунты ({len(accs)} шт.):**\n\n"
    for i, a in enumerate(accs, 1):
        status = "🟢" if a["is_valid"] else "🔴"
        text += f"{i}. {status} **{a['name']}** | Друзей: {a['friends']}\n"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚙️ Управление первым аккаунтом", callback_data="manage_first_acc")],
        [InlineKeyboardButton(text="❌ Удалить все аккаунты", callback_data="clear_accs")]
    ])
    await message.answer(text, reply_markup=kb, parse_mode="Markdown")


@router.message(F.text == "📊 Аналитика и здоровье")
async def btn_health(message: Message, bot: Bot):
    if not await check_sub_middleware(message, bot): return
    accs = db.get_user_vk_accounts(message.from_user.id)
    if not accs:
        return await message.answer("У вас нет привязанных аккаунтов.")

    valid_count = 0
    total_friends = 0
    for a in accs:
        res = await get_vk_account(a["token"])
        if res.get("valid"):
            valid_count += 1
            total_friends += res.get("friends", 0)

    await message.answer(
        f"📊 **Аналитика и здоровье аккаунтов:**\n\n"
        f"• Всего аккаунтов: {len(accs)}\n"
        f"• Активных (валидных): {valid_count}\n"
        f"• Суммарно друзей: {total_friends}\n"
        f"• Общий статус: {'🟢 Всё работает стабильно' if valid_count > 0 else '🔴 Требуется внимание'}",
        parse_mode="Markdown"
    )


@router.message(F.text == "🚀 Запустить рассылку")
async def btn_broadcast(message: Message, state: FSMContext, bot: Bot):
    if not await check_sub_middleware(message, bot): return
    if not db.is_sub_active(message.from_user.id):
        return await message.answer("❌ Нужна активная подписка!")
    accs = db.get_user_vk_accounts(message.from_user.id)
    if not accs:
        return await message.answer("⚠️ Сначала добавьте аккаунты!")

    await state.set_state(BroadcastState.waiting_for_message)
    await message.answer("💬 Отправьте текст сообщения для рассылки по друзьям со всех ваших аккаунтов:")


@router.message(F.text == "💳 Подписка и Оплата")
async def btn_pay(message: Message, bot: Bot):
    if not await check_sub_middleware(message, bot): return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💎 CryptoBot (USDT — $3.5)", callback_data="pay_crypto_1")],
        [InlineKeyboardButton(text="🚀 XRocket (TON — $3.5)", callback_data="pay_xrocket_1")]
    ])
    await message.answer("💳 Выберите способ оплаты (1 день подписки):", reply_markup=kb)


@router.message(F.text == "👤 Профиль")
async def btn_profile(message: Message, bot: Bot):
    if not await check_sub_middleware(message, bot): return
    user_id = message.from_user.id
    active = db.is_sub_active(user_id)
    accs = db.get_user_vk_accounts(user_id)
    await message.answer(
        f"👤 **Ваш профиль:**\n\n"
        f"🆔 ID: <code>{user_id}</code>\n"
        f"⏳ Подписка: {'🟢 Активна (Постоянная владельцу)' if (ADMIN_IDS and user_id in ADMIN_IDS) else ('🟢 Активна' if active else '🔴 Неактивна')}\n"
        f"🔑 Привязано аккаунтов VK: {len(accs)}",
        parse_mode="HTML"
    )


@router.message(F.text == "👑 Админ-панель")
async def btn_admin(message: Message):
    if not ADMIN_IDS or message.from_user.id not in ADMIN_IDS:
        return
    stats = db.get_stats()
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 Рассылка пользователям", callback_data="admin_broadcast")],
        [InlineKeyboardButton(text="🎁 Выдать подписку", callback_data="admin_grant_sub")]
    ])
    await message.answer(
        f"👑 **Админ-панель Aegis VK**\n\n"
        f"📊 Статистика:\n"
        f"• Всего пользователей: {stats['users']}\n"
        f"• Привязано аккаунтов VK: {stats['accounts']}\n"
        f"• 💰 Заработано с бота: **${stats['earnings']:.2f}**\n"
        f"• ✅ Успешных рассылок: {stats['success_bc']}\n"
        f"• ❌ Ошибок при рассылках: {stats['fail_bc']}",
        reply_markup=kb,
        parse_mode="Markdown"
    )


# --- ПЛАТЕЖИ (С записью заработка) ---
@router.callback_query(F.data.startswith("pay_crypto_"))
async def pay_crypto(callback: CallbackQuery):
    res = await create_cryptobot_invoice(3.5, CRYPTOBOT_TOKEN)
    if res.get("success"):
        db.add_earnings(3.5)  # Засчитываем в заработок
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔗 Оплатить счет", url=res["pay_url"])]])
        await callback.message.answer("💳 Ссылка на оплату в CryptoBot:", reply_markup=kb)
    else:
        await callback.answer(f"Ошибка: {res.get('error')}", show_alert=True)


@router.callback_query(F.data.startswith("pay_xrocket_"))
async def pay_xrocket(callback: CallbackQuery):
    res = await create_xrocket_invoice(3.5, XROCKET_TOKEN)
    if res.get("success"):
        db.add_earnings(3.5)  # Засчитываем в заработок
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔗 Оплатить счет", url=res["pay_url"])]])
        await callback.message.answer("🚀 Ссылка на оплату в XRocket:", reply_markup=kb)
    else:
        await callback.answer(f"Ошибка: {res.get('error')}", show_alert=True)


# --- ДОБАВЛЕНИЕ АККАУНТОВ ---
@router.callback_query(F.data == "auth_single_token")
async def auth_single(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("🔑 Отправьте ваш Access Token:")
    await state.set_state(AuthStates.waiting_for_token)
    await callback.answer()


@router.message(AuthStates.waiting_for_token)
async def got_token(message: Message, state: FSMContext):
    acc = await get_vk_account(message.text.strip())
    if acc.get("valid"):
        db.save_vk_account(message.from_user.id, message.text.strip(), acc["name"], acc["friends"])
        await state.clear()
        await message.answer(f"✅ Аккаунт добавлен!\n👤 {acc['name']}")
    else:
        await message.answer("❌ Неверный токен.")
        await state.clear()


@router.callback_query(F.data == "vk_add_bulk")
async def start_bulk(callback: CallbackQuery, state: FSMContext):
    await state.set_state(BulkState.waiting)
    await callback.message.answer("📥 Отправьте .txt файл или текст с токенами (каждый с новой строки):")
    await callback.answer()


@router.message(BulkState.waiting, F.document | F.text)
async def process_bulk(message: Message, state: FSMContext, bot: Bot):
    lines = []
    if message.document:
        file_info = await bot.get_file(message.document.file_id)
        file_io = await bot.download_file(file_info.file_path)
        try:
            content = file_io.read().decode('utf-8')
        except:
            content = file_io.read().decode('cp1251', errors='ignore')
        lines = content.splitlines()
    elif message.text:
        lines = message.text.splitlines()

    raw = [l.strip() for l in lines if l.strip()]
    status_msg = await message.answer(f"⏳ Проверяем аккаунты (0/{len(raw)})...")

    valid = 0
    for item in raw:
        res = await check_vk_account(item)
        if res.get("valid"):
            valid += 1
            db.save_vk_account(message.from_user.id, res["token"], res["name"], res["friends"])

    await state.clear()
    await status_msg.edit_text(f"✅ Загрузка завершена! Добавлено валидных: {valid}")


# --- УПРАВЛЕНИЕ АККАУНТОМ ---
@router.callback_query(F.data == "manage_first_acc")
async def manage_acc(callback: CallbackQuery):
    accs = db.get_user_vk_accounts(callback.from_user.id)
    if not accs:
        return await callback.answer("Нет аккаунтов", show_alert=True)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Изменить Имя/Фамилию", callback_data="ch_name")],
        [InlineKeyboardButton(text="🔒 Изменить пароль", callback_data="ch_pass")],
        [InlineKeyboardButton(text="🖼 Сменить аватарку", callback_data="ch_avatar")],
        [InlineKeyboardButton(text="👥 Выгрузить друзей (.txt)", callback_data="get_friends")],
        [InlineKeyboardButton(text="📥 Проверить уведомления", callback_data="check_notif")]
    ])
    await callback.message.answer(f"⚙️ Управление аккаунтом: **{accs[0]['name']}**", reply_markup=kb,
                                  parse_mode="Markdown")


@router.callback_query(F.data == "clear_accs")
async def clear_accs(callback: CallbackQuery):
    db.clear_user_vk_accounts(callback.from_user.id)
    await callback.message.answer("🗑 Все аккаунты удалены.")


@router.callback_query(F.data == "ch_name")
async def req_name(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("✍️ Введите Новое Имя и Фамилию через пробел:")
    await state.set_state(ProfileStates.waiting_for_new_name)
    await callback.answer()


@router.message(ProfileStates.waiting_for_new_name)
async def proc_name(message: Message, state: FSMContext):
    accs = db.get_user_vk_accounts(message.from_user.id)
    parts = message.text.strip().split(maxsplit=1)
    if len(parts) < 2:
        return await message.answer("⚠️ Укажите имя и фамилию.")
    res = await change_vk_name(accs[0]["token"], parts[0], parts[1])
    await message.answer("✅ Успешно изменено!" if res.get("success") else f"❌ Ошибка: {res.get('error')}")
    await state.clear()


@router.callback_query(F.data == "ch_pass")
async def req_opass(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("🔑 Введите СТАРЫЙ пароль:")
    await state.set_state(ProfileStates.waiting_for_old_pass)
    await callback.answer()


@router.message(ProfileStates.waiting_for_old_pass)
async def proc_opass(message: Message, state: FSMContext):
    await state.update_data(old_pass=message.text.strip())
    await message.answer("🔒 Введите НОВЫЙ пароль:")
    await state.set_state(ProfileStates.waiting_for_new_pass)


@router.message(ProfileStates.waiting_for_new_pass)
async def proc_npass(message: Message, state: FSMContext):
    data = await state.get_data()
    accs = db.get_user_vk_accounts(message.from_user.id)
    res = await change_vk_password(accs[0]["token"], data.get("old_pass"), message.text.strip())
    await message.answer("✅ Пароль успешно изменен!" if res.get("success") else f"❌ Ошибка: {res.get('error')}")
    await state.clear()


@router.callback_query(F.data == "ch_avatar")
async def req_av(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("🖼 Отправьте картинку для аватарки:")
    await state.set_state(ProfileStates.waiting_for_avatar)
    await callback.answer()


@router.message(ProfileStates.waiting_for_avatar, F.photo)
async def proc_av(message: Message, state: FSMContext, bot: Bot):
    accs = db.get_user_vk_accounts(message.from_user.id)
    photo = message.photo[-1]
    file_info = await bot.get_file(photo.file_id)
    filename = f"avatar_{message.from_user.id}.jpg"
    await bot.download(file_info.file_path, destination=filename)
    res = await change_vk_avatar(accs[0]["token"], filename)
    if os.path.exists(filename):
        os.remove(filename)
    await message.answer("✅ Аватарка обновлена!" if res.get("success") else f"❌ Ошибка: {res.get('error')}")
    await state.clear()


@router.callback_query(F.data == "get_friends")
async def exp_friends(callback: CallbackQuery):
    accs = db.get_user_vk_accounts(callback.from_user.id)
    filename = f"friends_{callback.from_user.id}.txt"
    res = await get_vk_friends_txt(accs[0]["token"], filename)
    if res.get("success"):
        await callback.message.answer_document(FSInputFile(filename), caption=f"📂 Друзей: {res['count']}")
        if os.path.exists(filename):
            os.remove(filename)
    else:
        await callback.message.answer(f"❌ Ошибка: {res.get('error')}")
    await callback.answer()


@router.callback_query(F.data == "check_notif")
async def chk_notif(callback: CallbackQuery):
    accs = db.get_user_vk_accounts(callback.from_user.id)
    res = await get_vk_security_notifications(accs[0]["token"])
    await callback.message.answer(f"🔔 Последние уведомления:\n\n{res.get('notifications', res.get('error'))}")
    await callback.answer()


# --- РАССЫЛКА ПО ДРУЗЬЯМ (С учетом статистики) ---
@router.message(BroadcastState.waiting_for_message, F.text)
async def run_broadcast(message: Message, state: FSMContext):
    text = message.text
    await state.clear()
    accs = db.get_user_vk_accounts(message.from_user.id)
    status_msg = await message.answer("🚀 Запуск рассылки...")

    success, errors = 0, 0
    for acc in accs:
        friends = await get_vk_friends(acc["token"])
        for f_id in friends:
            res = await send_vk_message(acc["token"], str(f_id), text)
            if res.get("success"):
                success += 1
            else:
                errors += 1
            await asyncio.sleep(1.5)

    db.add_broadcast_stats(success, errors)
    await status_msg.edit_text(f"✅ Рассылка завершена!\n📤 Успешно: {success}\n🔴 Ошибок: {errors}")


# --- АДМИНКА ---
@router.callback_query(F.data == "admin_broadcast")
async def admin_broadcast_req(callback: CallbackQuery, state: FSMContext):
    if not ADMIN_IDS or callback.from_user.id not in ADMIN_IDS:
        return
    await state.set_state(AdminBroadcastState.waiting_for_message)
    await callback.message.answer("💬 Введите текст рассылки для всех пользователей бота:")
    await callback.answer()


@router.message(AdminBroadcastState.waiting_for_message, F.text)
async def admin_broadcast_run(message: Message, bot: Bot, state: FSMContext):
    text = message.text
    await state.clear()
    users = db.get_all_users()
    status = await message.answer(f"🚀 Рассылка запущена (0/{len(users)})...")
    success, blocked = 0, 0
    for uid in users:
        try:
            await bot.send_message(uid, text)
            success += 1
            await asyncio.sleep(0.05)
        except:
            blocked += 1
    await status.edit_text(f"✅ Рассылка завершена!\n📤 Доставлено: {success}\n🔴 Заблокировали: {blocked}")


@router.callback_query(F.data == "admin_grant_sub")
async def admin_grant_req(callback: CallbackQuery, state: FSMContext):
    if not ADMIN_IDS or callback.from_user.id not in ADMIN_IDS:
        return
    await state.set_state(AdminGrantState.waiting_for_input)
    await callback.message.answer("🎁 Введите в формате: `user_id` `дни` (например: `123456789 30`):")
    await callback.answer()


@router.message(AdminGrantState.waiting_for_input, F.text)
async def admin_grant_run(message: Message, state: FSMContext):
    parts = message.text.strip().split()
    if len(parts) < 2 or not parts[0].isdigit() or not parts[1].isdigit():
        return await message.answer("⚠️ Неверный формат! Пример: `123456789 30`")
    target_id, days = int(parts[0]), int(parts[1])
    db.set_subscription(target_id, days)
    await state.clear()
    await message.answer(f"✅ Пользователю <code>{target_id}</code> добавлено дней: {days}.", parse_mode="HTML")