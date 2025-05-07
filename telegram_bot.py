import logging
import asyncio
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from config import BOT_API_TOKEN

# Логирование
logging.basicConfig(level=logging.INFO)

# Токен бота
bot = Bot(token=BOT_API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# Параметры SMTP-сервера
SMTP_SERVER = "smtp.mail.ru"
SMTP_PORT = 465
EMAIL_SENDER = "npk-poly@mail.ru"
EMAIL_LOGIN = "npk-poly@mail.ru"
EMAIL_PASSWORD = "mTQdt6Vx6MGxRmCuUm2h"

# Получатель заявки
EMAIL_RECIPIENT = "npk@polymetal.ru"

# Состояния
class Form(StatesGroup):
    email = State()
    has_topic = State()
    entered_topic = State()
    knows_mentor = State()
    mentor = State()

# Фиктивная база данных для хранения данных пользователя
user_data = {}

# Клавиатура для команд
main_menu = types.ReplyKeyboardMarkup(
    keyboard=[[types.KeyboardButton(text="Начать")]], resize_keyboard=True
)

apply_menu = types.ReplyKeyboardMarkup(
    keyboard=[[types.KeyboardButton(text="Подать заявку")]], resize_keyboard=True
)

# Стартовая команда
@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "Добро пожаловать в бота для подачи заявок!",
        reply_markup=main_menu
    )

# Обработка нажатия на кнопку "Начать"
@dp.message(lambda message: message.text == "Начать")
async def start_application(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "Нажми 'Подать заявку', чтобы начать процесс подачи заявки.",
        reply_markup=apply_menu
    )

# Обработка нажатия на кнопку "Подать заявку"
@dp.message(lambda message: message.text == "Подать заявку")
async def cmd_apply(message: types.Message, state: FSMContext):
    await message.answer(
        "Введи свой рабочий email. Он должен заканчиваться на один из следующих доменов:\n"
        "- @polymetal.ru\n"
        "- @solidcore-resources.kz\n"
        "- @pme.spb.ru"
    )
    await state.set_state(Form.email)

# Обработка email
@dp.message(StateFilter(Form.email))
async def process_email(message: types.Message, state: FSMContext):
    email = message.text
    valid_domains = ["@polymetal.ru", "@solidcore-resources.kz", "@pme.spb.ru"]

    if not any(email.endswith(domain) for domain in valid_domains):
        await message.answer("Неверный формат email. Попробуй еще раз.")
        return

    user_data[message.from_user.id] = {'email': email}
    await message.answer("Email подтвержден!\nУ тебя есть тема для участия в НПК? (ответь — да или нет)")
    await state.set_state(Form.has_topic)

# Проверка наличия темы
@dp.message(StateFilter(Form.has_topic))
async def ask_for_topic(message: types.Message, state: FSMContext):
    answer = message.text.strip().lower()

    if answer == "да":
        await message.answer("Введи свою тему для участия в НПК:")
        await state.set_state(Form.entered_topic)
    elif answer == "нет":
        user_data[message.from_user.id]['topic'] = "Тема не выбрана"
        await message.answer("Так бывает. Ты можешь посмотреть Ярмарку тем на корпоративном портале.")
        await message.answer("Ты уже знаешь, кто будет твоим наставником? (ответь да или нет)")
        await state.set_state(Form.knows_mentor)
    else:
        await message.answer("Пожалуйста, ответь 'да' или 'нет'.")

# Обработка введенной темы вручную
@dp.message(StateFilter(Form.entered_topic))
async def process_entered_topic(message: types.Message, state: FSMContext):
    topic = message.text.strip()
    user_data[message.from_user.id]['topic'] = topic
    await message.answer(f"Тема '{topic}' подтверждена.\nТы уже знаешь, кто будет твоим наставником? (ответь да или нет)")
    await state.set_state(Form.knows_mentor)

# Проверка, знает ли пользователь наставника
@dp.message(StateFilter(Form.knows_mentor))
async def knows_mentor(message: types.Message, state: FSMContext):
    answer = message.text.strip().lower()

    if answer == "да":
        await message.answer("Напиши имя предполагаемого наставника:")
        await state.set_state(Form.mentor)
    elif answer == "нет":
        user_data[message.from_user.id]['mentor'] = "Наставник не выбран"
        await message.answer("Не переживай, мы поможем тебе найти наставника чуть позднее.")
        await show_final_message(message, state)
    else:
        await message.answer("Пожалуйста, ответь 'да' или 'нет'.")

# Обработка ввода наставника
@dp.message(StateFilter(Form.mentor))
async def process_mentor(message: types.Message, state: FSMContext):
    user_data[message.from_user.id]['mentor'] = message.text
    await show_final_message(message, state)

# Показ итогового сообщения и отправка email
async def show_final_message(message: types.Message, state: FSMContext):
    user_data_state = await state.get_data()
    email = user_data[message.from_user.id]['email']
    topic = user_data[message.from_user.id]['topic']
    mentor = user_data[message.from_user.id].get('mentor', 'Наставник не выбран')

    # Формируем текст заявки
    email_body = f"""
    Новая заявка на участие в НПК:
    Email: {email}
    Тема: {topic}
    Наставник: {mentor}
    """

    # Сначала показываем пользователю итоговую заявку
    await message.answer(
        "Спасибо за вашу заявку!\n"
        "Ваши данные:\n"
        f"Email: {email}\n"
        f"Тема: {topic}\n"
        f"Наставник: {mentor}\n"
        "Заявка принята на рассмотрение!"
    )

    # Затем отправляем email
    await send_email(email_body)
    await state.clear()

# Отправка email с помощью SMTP
async def send_email(body: str):
    try:
        msg = MIMEMultipart()
        msg["From"] = EMAIL_SENDER
        msg["To"] = EMAIL_RECIPIENT
        msg["Subject"] = "@@@ Заявка на НПК"

        # Добавляем тело письма
        msg.attach(MIMEText(body, "plain"))

        # Подключаемся к SMTP-серверу с SSL
        with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as server:
            logging.info("Подключение к SMTP-серверу через SSL успешно.")
            server.login(EMAIL_LOGIN, EMAIL_PASSWORD)
            server.send_message(msg)
            logging.info("Email успешно отправлен.")
    except Exception as e:
        logging.error(f"Ошибка при отправке email: {e}")

# Глобальный обработчик для неожиданных сообщений
@dp.message()
async def handle_unrecognized_message(message: types.Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state is None:  # Если бот не ожидает никакого конкретного состояния
        await message.answer(
            "Команда не распознана. Нажмите 'Начать', чтобы вернуться в главное меню.",
            reply_markup=main_menu
        )
    else:
        logging.info(f"Неожиданное сообщение '{message.text}' в состоянии '{current_state}'")

# Основной цикл работы бота
if __name__ == "__main__":
    asyncio.run(dp.start_polling(bot))
