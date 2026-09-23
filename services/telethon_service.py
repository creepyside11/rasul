import os
import asyncio
import json
import random
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.tl.types import Channel, Chat
from telethon.errors import SessionPasswordNeededError, FloodWaitError
from config import config

# Хранилище временных клиентов в процессе авторизации:
# phone: { "client": TelegramClient, "phone_code_hash": str }
pending_auths = {}

# Хранилище активных задач рассылки для их мгновенной остановки:
# task_id: asyncio.Task
active_tasks = {}

def get_client_by_session(session_str: str) -> TelegramClient:
    return TelegramClient(StringSession(session_str), config.api_id, config.api_hash)

async def start_auth(phone: str):
    session = StringSession()
    client = TelegramClient(session, config.api_id, config.api_hash)
    await client.connect()
    res = await client.send_code_request(phone)
    pending_auths[phone] = {
        "client": client,
        "phone_code_hash": res.phone_code_hash,
        "session": session
    }
    return res.phone_code_hash

async def submit_code(phone: str, code: str):
    if phone not in pending_auths:
        raise ValueError("Сессия авторизации не найдена. Начните сначала.")
    data = pending_auths[phone]
    client: TelegramClient = data["client"]
    try:
        await client.sign_in(phone=phone, code=code, phone_code_hash=data["phone_code_hash"])
        session_str = client.session.save()
        await client.disconnect()
        del pending_auths[phone]
        return {"status": "ok", "session": session_str}
    except SessionPasswordNeededError:
        return {"status": "2fa_needed"}

async def submit_2fa_password(phone: str, password: str):
    if phone not in pending_auths:
        raise ValueError("Сессия авторизации не найдена.")
    data = pending_auths[phone]
    client: TelegramClient = data["client"]
    await client.sign_in(password=password)
    session_str = client.session.save()
    await client.disconnect()
    del pending_auths[phone]
    return session_str

async def get_account_chats(session_str: str, limit: int = 100):
    client = get_client_by_session(session_str)
    await client.connect()
    chats = []
    try:
        async for dialog in client.iter_dialogs():
            if dialog.is_group or dialog.is_channel:
                chats.append({
                    "id": dialog.id,
                    "title": dialog.name or "Без названия"
                })
            if len(chats) >= limit:
                break
    finally:
        await client.disconnect()
    return chats

async def run_broadcast_worker(
    task_id: int,
    session_str: str,
    chats: list,
    delay: float,
    msg_per_chat: int,
    send_type: str,
    text_content: str | None,
    photo_path: str | None,
    on_finish_callback=None
):
    client = get_client_by_session(session_str)
    await client.connect()

    async def send_to_one_chat(chat_id: int):
        for _ in range(msg_per_chat):
            try:
                if photo_path and os.path.exists(photo_path):
                    await client.send_file(
                        chat_id,
                        file=photo_path,
                        caption=text_content or "",
                        parse_mode="html"
                    )
                else:
                    await client.send_message(
                        chat_id,
                        message=text_content or "",
                        parse_mode="html"
                    )
            except FloodWaitError as e:
                await asyncio.sleep(e.seconds + 1)
            except Exception as err:
                print(f"[Broadcast Error] Chat {chat_id}: {err}")
            
            if delay > 0:
                await asyncio.sleep(delay)

    try:
        if send_type == "random":
            # Рандомный выбор чата по 1 сообщению за цикл
            # Общее количество отправок в каждый чат = msg_per_chat
            remaining = {c["id"]: msg_per_chat for c in chats}
            while any(v > 0 for v in remaining.values()):
                available = [cid for cid, count in remaining.items() if count > 0]
                if not available:
                    break
                target_chat_id = random.choice(available)
                try:
                    if photo_path and os.path.exists(photo_path):
                        await client.send_file(
                            target_chat_id,
                            file=photo_path,
                            caption=text_content or "",
                            parse_mode="html"
                        )
                    else:
                        await client.send_message(
                            target_chat_id,
                            message=text_content or "",
                            parse_mode="html"
                        )
                except FloodWaitError as e:
                    await asyncio.sleep(e.seconds + 1)
                except Exception as err:
                    print(f"[Broadcast Random Error] {target_chat_id}: {err}")
                
                remaining[target_chat_id] -= 1
                if delay > 0:
                    await asyncio.sleep(delay)

        elif send_type == "simultaneous":
            # Одновременная отправка во все чаты параллельно (каждый со своей задержкой)
            tasks = [asyncio.create_task(send_to_one_chat(c["id"])) for c in chats]
            await asyncio.gather(*tasks, return_exceptions=True)
            
    except asyncio.CancelledError:
        print(f"[Task {task_id}] Cancelled by user.")
    finally:
        await client.disconnect()
        if photo_path and os.path.exists(photo_path):
            try:
                os.remove(photo_path)
            except Exception:
                pass
        if task_id in active_tasks:
            del active_tasks[task_id]
        if on_finish_callback:
            await on_finish_callback(task_id)
