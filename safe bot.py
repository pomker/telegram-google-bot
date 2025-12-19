import asyncio
import os
import json
from datetime import datetime
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
import gspread

# ================== НАСТРОЙКИ ==================
# Telegram token берём из переменной окружения
BOT_TOKEN = os.environ["BOT_TOKEN"]

# Google credentials берём из переменной окружения
# В Render создаёшь GOOGLE_CREDENTIALS и вставляешь туда весь credentials.json одной строкой
creds_dict = json.loads(os.environ["GOOGLE_CREDENTIALS"])

# Имя Google Sheets (можно тоже через env, иначе дефолт)
SHEET_NAME = os.environ.get("SHEET_NAME", "Электронная версия фото")
# ===============================================

# ---------- Google Sheets ----------
client = gspread.service_account_from_dict(creds_dict)
sheet = client.open(SHEET_NAME).sheet1

# ---------- Telegram ----------
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# ---------- Состояние пользователей ----------
user_state = {}

# ---------- Клавиатура главного меню ----------
main_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📥 Старт"), KeyboardButton(text="✏️ Редактировать")]
    ],
    resize_keyboard=True
)

# ---------- Клавиатура для отправки номера ----------
phone_kb = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="📱 Отправить номер", request_contact=True)]],
    resize_keyboard=True
)

# ---------- Нормализация номера ----------
def normalize_phone(phone: str) -> str | None:
    phone = phone.strip().replace(" ", "").replace("-", "")
    if phone.startswith("+"):
        digits = phone[1:]
    else:
        digits = phone
    if not digits.isdigit():
        return None
    if len(digits) == 11 and digits.startswith(("8", "7")):
        return "+7" + digits[1:]
    if len(digits) == 10:
        return "+7" + digits
    return None

# ---------- Проверки ----------
def phone_exists(phone: str) -> bool:
    return phone in sheet.col_values(1)

def find_row_by_phone(phone: str) -> int | None:
    for idx, value in enumerate(sheet.col_values(1), start=1):
        if value == phone:
            return idx
    return None

def get_user_numbers(user_id: int) -> list[str]:
    numbers = []
    col_values = sheet.col_values(2)  # B: user_id
    phone_values = sheet.col_values(1)  # A: phone
    for uid, phone in zip(col_values, phone_values):
        if str(user_id) == uid:
            numbers.append(phone)
    return numbers

# ---------- START ----------
@dp.message(Command("start"))
async def start(message: types.Message):
    user_state.pop(message.from_user.id, None)
    await message.answer(
        "📷 Привет!\n\n"
        "1️⃣ Укажите номер телефона (тот же, что назвали фотографу):\n\n"
        "Пример: +79991234567\n\n"
        "2️⃣ После ввода номер будет сохранён\n\n"
        "3️⃣ Напоминаем, что электронная версия фотографий отправляется в течение двух дней после мероприятия. Ожидайте\n\n"
        "Если прошло более двух суток, а фотографии не были получены — напишите нам:\n+79264177796",
        reply_markup=phone_kb
    )
    user_state[message.from_user.id] = {"mode": "new_number"}

# ---------- ОБРАБОТКА КНОПОК И СООБЩЕНИЙ ----------
@dp.message()
async def main_handler(message: types.Message):
    user_id = message.from_user.id
    text = message.text
    state = user_state.get(user_id)

    # ===== Главное меню =====
    if text == "📥 Старт":
        await start(message)
        return

    if text == "✏️ Редактировать":
        numbers = get_user_numbers(user_id)
        if not numbers:
            await message.answer("❌ У вас пока нет сохранённых номеров.", reply_markup=main_kb)
            return

        # Формируем кнопки с номерами
        buttons = [[KeyboardButton(text=num)] for num in numbers]
        kb = ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True, one_time_keyboard=True)
        await message.answer(
            "✏️ Выберите номер для редактирования комментария:",
            reply_markup=kb
        )
        user_state[user_id] = {"mode": "edit_phone"}
        return

    # ===== ОБРАБОТКА НОВОГО НОМЕРА =====
    if state:
        mode = state.get("mode")

        if mode == "new_number":
            raw_phone = message.contact.phone_number if message.contact else text
            phone = normalize_phone(raw_phone)
            if not phone:
                await message.answer("❌ Неверный формат номера. Пример: +79991234567")
                return
            if phone_exists(phone):
                await message.answer(
                    "ℹ️ Этот номер уже сохранён. Чтобы изменить комментарий, используйте ✏️ Редактировать",
                    reply_markup=main_kb  # оставляем главное меню
                )
                user_state.pop(user_id, None)
                return
            sheet.append_row([
                phone,
                user_id,
                message.from_user.username or "",
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                ""
            ])
            user_state[user_id] = {"mode": "new_comment", "phone": phone}
            await message.answer(
                f"✅ Ваш номер принят и записан:\n{phone}\n\n"
                "✍️ Напишите комментарий: какие фото вам прислать",
                reply_markup=ReplyKeyboardRemove()
            )
            return

        if mode == "new_comment":
            phone = state["phone"]
            comment = text.strip()
            row = find_row_by_phone(phone)
            sheet.update_cell(row, 5, comment)
            user_state.pop(user_id)
            await message.answer(
                "✅ Ваш комментарий сохранён.\n📷 Спасибо! Мы учтём ваши пожелания.\n\n"
                "Если прошло более двух суток и фото не пришли — напишите нам:\n\n"
                "https://t.me/liza_monika_li",
                reply_markup=main_kb
            )
            return

        # ===== РЕДАКТИРОВАНИЕ =====
        if mode == "edit_phone":
            phone = normalize_phone(text)
            if not phone or not phone_exists(phone):
                await message.answer("❌ Номер не найден. Выберите правильный номер.")
                return
            row = find_row_by_phone(phone)
            old_comment = sheet.cell(row, 5).value or "—"
            user_state[user_id] = {"mode": "edit_comment", "phone": phone}
            await message.answer(
                f"📄 Текущий комментарий:\n{old_comment}\n✍️ Введите новый комментарий:",
                reply_markup=ReplyKeyboardRemove()
            )
            return

        if mode == "edit_comment":
            phone = state["phone"]
            new_comment = text.strip()
            row = find_row_by_phone(phone)
            sheet.update_cell(row, 5, new_comment)
            user_state.pop(user_id)
            await message.answer("✅ Комментарий обновлён.", reply_markup=main_kb)
            return

# ---------- ЗАПУСК ----------
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
