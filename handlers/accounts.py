from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from sqlalchemy import select, delete

from database.db import async_session
from database.models import Account
from states.states import AddAccountStates
from keyboards.keyboards import get_accounts_menu, get_cancel_kb
from services.telethon_service import start_auth, submit_code, submit_2fa_password

router = Router()

@router.message(F.text == "📱 Менеджер аккаунтов")
async def accounts_manager_menu(message: Message):
    await message.answer("📱 <b>Менеджер аккаунтов</b>\nВыберите действие:", reply_markup=get_accounts_menu(), parse_mode="html")

@router.callback_query(F.data == "list_accounts")
async def list_accounts_handler(call: CallbackQuery):
    async with async_session() as session:
        result = await session.execute(select(Account))
        accounts = result.scalars().all()
    
    if not accounts:
        await call.message.edit_text("ℹ️ У вас еще нет добавленных аккаунтов.", reply_markup=get_accounts_menu())
        return

    text = "📋 <b>Список подключенных аккаунтов:</b>\n\n"
    keyboard = []
    for acc in accounts:
        status_emoji = "🟢" if acc.is_active else "🔴"
        text += f"{status_emoji} ID: {acc.id} | Тел: <code>{acc.phone}</code>\n"
        keyboard.append([InlineKeyboardButton(text=f"🗑 Удалить {acc.phone}", callback_data=f"del_acc_{acc.id}")])
    
    keyboard.append([InlineKeyboardButton(text="➕ Добавить еще", callback_data="add_account")])
    keyboard.append([InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_accounts")])

    await call.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard), parse_mode="html")

@router.callback_query(F.data.startswith("del_acc_"))
async def delete_account_handler(call: CallbackQuery):
    acc_id = int(call.data.replace("del_acc_", ""))
    async with async_session() as session:
        await session.execute(delete(Account).where(Account.id == acc_id))
        await session.commit()
    await call.answer("Аккаунт успешно удален!", show_alert=True)
    await list_accounts_handler(call)

@router.callback_query(F.data == "back_to_accounts")
async def back_to_accounts_handler(call: CallbackQuery):
    await call.message.edit_text("📱 <b>Менеджер аккаунтов</b>\nВыберите действие:", reply_markup=get_accounts_menu(), parse_mode="html")

@router.callback_query(F.data == "add_account")
async def start_add_account(call: CallbackQuery, state: FSMContext):
    await state.set_state(AddAccountStates.waiting_for_phone)
    await call.message.edit_text(
        "📲 Введите номер телефона аккаунта в международном формате:\nПример: <code>+79991234567</code>",
        reply_markup=get_cancel_kb(),
        parse_mode="html"
    )

@router.message(AddAccountStates.waiting_for_phone)
async def process_phone(message: Message, state: FSMContext):
    phone = message.text.strip().replace(" ", "")
    status_msg = await message.answer("⏳ Отправляем код подтверждения в Telegram...")
    try:
        await start_auth(phone)
        await state.update_data(phone=phone)
        await state.set_state(AddAccountStates.waiting_for_code)
        await status_msg.edit_text(
            f"✅ Код подтверждения отправлен на номер <code>{phone}</code>!\n\n"
            "💬 Введите полученный код из Telegram.\n"
            "<i>(Если код содержит цифры, разделенные пробелом/дефисом, вводите только цифры)</i>",
            reply_markup=get_cancel_kb(),
            parse_mode="html"
        )
    except Exception as e:
        await status_msg.edit_text(f"❌ Ошибка отправки кода: {e}\nПопробуйте снова через меню аккаунтов.")
        await state.clear()

@router.message(AddAccountStates.waiting_for_code)
async def process_code(message: Message, state: FSMContext):
    code = message.text.strip().replace(" ", "").replace("-", "")
    data = await state.get_data()
    phone = data.get("phone")

    status_msg = await message.answer("⏳ Авторизуемся...")
    try:
        res = await submit_code(phone, code)
        if res.get("status") == "2fa_needed":
            await state.set_state(AddAccountStates.waiting_for_2fa)
            await status_msg.edit_text(
                "🔐 На аккаунте включен <b>облачный пароль (2FA)</b>.\nВведите пароль двухфакторной аутентификации:",
                reply_markup=get_cancel_kb(),
                parse_mode="html"
            )
            return

        session_str = res["session"]
        async with async_session() as session:
            new_acc = Account(phone=phone, session_string=session_str)
            session.add(new_acc)
            await session.commit()

        await state.clear()
        await status_msg.edit_text(f"🎉 Аккаунт <code>{phone}</code> успешно добавлен!", parse_mode="html")
    except Exception as e:
        await status_msg.edit_text(f"❌ Ошибка при входе: {e}\nПопробуйте снова.")
        await state.clear()

@router.message(AddAccountStates.waiting_for_2fa)
async def process_2fa(message: Message, state: FSMContext):
    password = message.text.strip()
    data = await state.get_data()
    phone = data.get("phone")

    status_msg = await message.answer("⏳ Проверяем пароль 2FA...")
    try:
        session_str = await submit_2fa_password(phone, password)
        async with async_session() as session:
            new_acc = Account(phone=phone, session_string=session_str)
            session.add(new_acc)
            await session.commit()

        await state.clear()
        await status_msg.edit_text(f"🎉 Аккаунт <code>{phone}</code> с 2FA успешно добавлен!", parse_mode="html")
    except Exception as e:
        await status_msg.edit_text(f"❌ Ошибка пароля 2FA: {e}\nПопробуйте снова.")
        await state.clear()

@router.callback_query(F.data == "cancel_action")
async def cancel_handler(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.edit_text("🚫 Действие отменено.")
