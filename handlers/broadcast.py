import os
import uuid
import json
import asyncio
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from sqlalchemy import select, update

from database.db import async_session
from database.models import Account, BroadcastTask
from states.states import BroadcastStates
from keyboards.keyboards import (
    get_functions_menu,
    get_send_type_kb,
    get_cancel_kb
)
from services.telethon_service import (
    get_account_chats,
    run_broadcast_worker,
    active_tasks
)

router = Router()

@router.message(F.text == "🚀 Функции")
async def functions_menu(message: Message):
    await message.answer("🚀 <b>Доступные функции:</b>", reply_markup=get_functions_menu(), parse_mode="html")

@router.callback_query(F.data == "start_broadcast")
async def start_broadcast_init(call: CallbackQuery, state: FSMContext):
    async with async_session() as session:
        result = await session.execute(select(Account).where(Account.is_active == True))
        accounts = result.scalars().all()

    if not accounts:
        await call.message.edit_text("❌ Нет доступных аккаунтов. Сначала добавьте аккаунт в <b>Менеджере аккаунтов</b>.", parse_mode="html")
        return

    keyboard = []
    for acc in accounts:
        keyboard.append([InlineKeyboardButton(text=f"📱 {acc.phone}", callback_data=f"sel_acc_{acc.id}")])
    keyboard.append([InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_action")])

    await state.set_state(BroadcastStates.choose_account)
    await call.message.edit_text("👤 Выберите аккаунт, с которого запускать рассылку:", reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard))

@router.callback_query(BroadcastStates.choose_account, F.data.startswith("sel_acc_"))
async def choose_account_handler(call: CallbackQuery, state: FSMContext):
    acc_id = int(call.data.replace("sel_acc_", ""))
    await state.update_data(account_id=acc_id)
    await state.set_state(BroadcastStates.choose_chats_count)
    await call.message.edit_text(
        "🔢 Введите количество чатов для рассылки (от <b>1</b> до <b>100</b>):\n<i>Бот выберет первые N доступных групп/каналов с этого аккаунта.</i>",
        reply_markup=get_cancel_kb(),
        parse_mode="html"
    )

@router.message(BroadcastStates.choose_chats_count)
async def process_chats_count(message: Message, state: FSMContext):
    text = message.text.strip()
    if not text.isdigit() or not (1 <= int(text) <= 100):
        await message.answer("⚠️ Введите число от 1 до 100!", reply_markup=get_cancel_kb())
        return

    count = int(text)
    await state.update_data(chats_count=count)
    await state.set_state(BroadcastStates.enter_delay)
    await message.answer(
        "⏱ Введите <b>задержку между сообщениями</b> (в секундах):\nНапример: <code>2</code> или <code>0.5</code>",
        reply_markup=get_cancel_kb(),
        parse_mode="html"
    )

@router.message(BroadcastStates.enter_delay)
async def process_delay(message: Message, state: FSMContext):
    try:
        delay = float(message.text.strip().replace(",", "."))
        if delay < 0:
            raise ValueError
    except ValueError:
        await message.answer("⚠️ Введите корректное положительное число секунд (например, 2 или 1.5):", reply_markup=get_cancel_kb())
        return

    await state.update_data(delay=delay)
    await state.set_state(BroadcastStates.enter_msg_per_chat)
    await message.answer(
        "✉️ Введите <b>количество сообщений в каждый чат</b>:\nНапример: <code>1</code> или <code>3</code>",
        reply_markup=get_cancel_kb(),
        parse_mode="html"
    )

@router.message(BroadcastStates.enter_msg_per_chat)
async def process_msg_per_chat(message: Message, state: FSMContext):
    text = message.text.strip()
    if not text.isdigit() or int(text) <= 0:
        await message.answer("⚠️ Введите целое положительное число (например, 1):", reply_markup=get_cancel_kb())
        return

    msg_count = int(text)
    await state.update_data(msg_per_chat=msg_count)
    await state.set_state(BroadcastStates.choose_send_type)
    await message.answer(
        "⚙️ Выберите <b>тип отправки</b>:\n\n"
        "🎲 <b>Рандомный (по 1)</b> — отправляет по одному сообщению в случайные чаты из списка по очереди.\n"
        "⚡ <b>Одновременный</b> — рассылает параллельно во все выбранные чаты сразу.",
        reply_markup=get_send_type_kb(),
        parse_mode="html"
    )

@router.callback_query(BroadcastStates.choose_send_type, F.data.startswith("type_"))
async def process_send_type(call: CallbackQuery, state: FSMContext):
    send_type = call.data.replace("type_", "") # "random" or "simultaneous"
    await state.update_data(send_type=send_type)
    await state.set_state(BroadcastStates.enter_message)
    await call.message.edit_text(
        "📝 Теперь отправьте само <b>сообщение</b> для рассылки:\n\n"
        "• Поддерживается <b>HTML-форматирование</b> (<b>жирный</b>, <i>курсив</i>, <a href='https://example.com'>ссылки</a>, <code>код</code>).\n"
        "• Можно отправить <b>текст с фото</b> или просто текст.\n\n"
        "<i>Отправьте сообщение прямо сейчас:</i>",
        reply_markup=get_cancel_kb(),
        parse_mode="html"
    )

@router.message(BroadcastStates.enter_message)
async def process_broadcast_message(message: Message, state: FSMContext):
    data = await state.get_data()
    acc_id = data["account_id"]
    chats_count = data["chats_count"]
    delay = data["delay"]
    msg_per_chat = data["msg_per_chat"]
    send_type = data["send_type"]

    photo_path = None
    text_content = ""

    if message.photo:
        photo = message.photo[-1]
        os.makedirs("downloads", exist_ok=True)
        photo_path = f"downloads/{uuid.uuid4()}.jpg"
        file = await message.bot.get_file(photo.file_id)
        await message.bot.download_file(file.file_path, photo_path)
        text_content = message.html_text or ""
    else:
        text_content = message.html_text or message.text or ""

    status_msg = await message.answer("🔍 Получаем чаты с выбранного аккаунта...")

    async with async_session() as session:
        result = await session.execute(select(Account).where(Account.id == acc_id))
        acc = result.scalar_one_or_none()

    if not acc:
        await status_msg.edit_text("❌ Аккаунт не найден в базе!")
        await state.clear()
        return

    try:
        chats = await get_account_chats(acc.session_string, limit=chats_count)
    except Exception as e:
        await status_msg.edit_text(f"❌ Ошибка получения чатов: {e}")
        await state.clear()
        return

    if not chats:
        await status_msg.edit_text("⚠️ На аккаунте не найдено доступных групп или каналов.")
        await state.clear()
        return

    # Сохраняем задачу в БД
    async with async_session() as session:
        task = BroadcastTask(
            account_id=acc_id,
            total_chats=len(chats),
            chats_data=json.dumps(chats, ensure_ascii=False),
            delay_seconds=delay,
            msg_per_chat=msg_per_chat,
            send_type=send_type,
            text_content=text_content,
            photo_path=photo_path,
            status="running"
        )
        session.add(task)
        await session.commit()
        task_id = task.id

    async def on_finish(tid):
        async with async_session() as s:
            await s.execute(update(BroadcastTask).where(BroadcastTask.id == tid).values(status="completed"))
            await s.commit()

    # Запускаем worker рассылки в фоне
    worker = asyncio.create_task(
        run_broadcast_worker(
            task_id=task_id,
            session_str=acc.session_string,
            chats=chats,
            delay=delay,
            msg_per_chat=msg_per_chat,
            send_type=send_type,
            text_content=text_content,
            photo_path=photo_path,
            on_finish_callback=on_finish
        )
    )
    active_tasks[task_id] = worker

    await state.clear()
    await status_msg.edit_text(
        f"🚀 <b>Рассылка #{task_id} успешно запущена!</b>\n\n"
        f"📌 Чатов: <b>{len(chats)}</b>\n"
        f"⏱ Задержка: <b>{delay} сек</b>\n"
        f"✉️ Сообщений в чат: <b>{msg_per_chat}</b>\n"
        f"⚙️ Тип: <b>{'🎲 Рандомный' if send_type == 'random' else '⚡ Одновременный'}</b>\n\n"
        "Вы всегда можете отслеживать или остановить её в меню <b>Мои рассылки</b>.",
        parse_mode="html"
    )

# --- МОИ РАССЫЛКИ ---
@router.message(F.text == "📊 Мои рассылки")
async def my_broadcasts(message: Message):
    async with async_session() as session:
        result = await session.execute(
            select(BroadcastTask).order_by(BroadcastTask.id.desc()).limit(10)
        )
        tasks = result.scalars().all()

    if not tasks:
        await message.answer("📊 У вас еще нет запущенных или завершенных рассылок.")
        return

    text = "📊 <b>Список последних рассылок:</b>\n\n"
    keyboard = []
    for t in tasks:
        is_running = t.id in active_tasks
        status_text = "🟢 Выполняется" if is_running else f"⚪ {t.status}"
        text += (
            f"🆔 <b>Рассылка #{t.id}</b>\n"
            f"Статус: {status_text}\n"
            f"Чатов: {t.total_chats} | Задержка: {t.delay_seconds}с | В чат: {t.msg_per_chat}\n\n"
        )
        if is_running:
            keyboard.append([InlineKeyboardButton(text=f"🛑 Остановить #{t.id}", callback_data=f"stop_task_{t.id}")])

    await message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard) if keyboard else None, parse_mode="html")

@router.callback_query(F.data.startswith("stop_task_"))
async def stop_broadcast_handler(call: CallbackQuery):
    task_id = int(call.data.replace("stop_task_", ""))
    if task_id in active_tasks:
        worker = active_tasks[task_id]
        worker.cancel()
        async with async_session() as session:
            await session.execute(update(BroadcastTask).where(BroadcastTask.id == task_id).values(status="stopped"))
            await session.commit()
        await call.answer(f"Рассылка #{task_id} остановлена!", show_alert=True)
    else:
        await call.answer("Рассылка уже завершена или остановлена.", show_alert=True)

    await call.message.edit_text("✅ Статус рассылок обновлен.")
