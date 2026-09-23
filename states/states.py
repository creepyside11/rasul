from aiogram.fsm.state import State, StatesGroup

class AddAccountStates(StatesGroup):
    waiting_for_phone = State()
    waiting_for_code = State()
    waiting_for_2fa = State()

class BroadcastStates(StatesGroup):
    choose_account = State()
    choose_chats_count = State()
    enter_delay = State()
    enter_msg_per_chat = State()
    choose_send_type = State()
    enter_message = State()
