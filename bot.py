import telebot
from telebot import types
import config
import database
import os
import schedule
import time
import logging
import pandas as pd  
from threading import Thread
from cachetools import TTLCache

# Налаштування логування
logging.basicConfig(filename="bot.log", 
                    level=logging.INFO, 
                    format="%(asctime)s - %(levelname)s - %(message)s", 
                    encoding='utf-8')  

# Ініціалізація бота
bot = telebot.TeleBot(config.TOKEN)

# Створення таблиць у базі даних
database.create_tables()

# Папка для зберігання файлів
UPLOAD_FOLDER = config.UPLOAD_FOLDER
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# Кешування користувачів для швидшого доступу
user_cache = TTLCache(maxsize=1000, ttl=600)  

@bot.message_handler(commands=['start'])
def start_registration(message):
    user_id = message.from_user.id

    if user_id in user_cache or database.is_user_registered(user_id):
        user_cache[user_id] = True  
        send_main_menu(message.chat.id)
        logging.info(f"Користувач {user_id} вже зареєстрований, відправлено головне меню")
    else:
        markup = types.InlineKeyboardMarkup()
        button = types.InlineKeyboardButton('🆕 Зареєструватися', callback_data='register')
        markup.add(button)
        bot.send_message(message.chat.id, "👤 **Натисніть кнопку для реєстрації**", reply_markup=markup, parse_mode='Markdown')
        logging.info(f"Користувач {user_id} отримав пропозицію реєстрації")

def send_active_requests_reminder():
    active_requests = database.get_all_active_requests()
    if active_requests:
        messages = []
        for req in active_requests:
            messages.append(
                f"📌 **Запит №{req['request_number']}**\n"
                f"👤 **Користувач:** {req['name']} (Телефон: {req['phone']})\n"
                f"💰 **Сума:** {req['amount']} {req['currency']}\n"
                f"🖋 **Коментар:** {req['comment']}\n"
                f"📎 **Файл:** {'Прикріплено' if req['file_path'] else 'Файл не додано.'}\n"
                f"📅 **Статус:** {req['status']}"
            )
        bot.send_message(config.ADMIN_CHAT_ID, "🔔 **Нагадування про активні заявки**:\n\n" + "\n\n".join(messages), parse_mode='Markdown')
        logging.info("Надіслано нагадування про активні заявки адміністратору")
    else:
        bot.send_message(config.ADMIN_CHAT_ID, "🔔 **Нагадування**: На даний момент немає активних заявок.", parse_mode='Markdown')
        logging.info("Надіслано повідомлення адміністратору: немає активних заявок")

def schedule_reminders():
    schedule.every().day.at("11:00").do(send_active_requests_reminder)
    schedule.every().day.at("12:00").do(send_active_requests_reminder)
    schedule.every().day.at("13:00").do(send_active_requests_reminder)
    schedule.every().day.at("14:00").do(send_active_requests_reminder)
    schedule.every().day.at("15:00").do(send_active_requests_reminder)
    schedule.every().day.at("16:00").do(send_active_requests_reminder)
    schedule.every().day.at("17:00").do(send_active_requests_reminder)
    schedule.every().day.at("17:30").do(send_active_requests_reminder)

    while True:
        schedule.run_pending()
        time.sleep(1)

def run_scheduler():
    scheduler_thread = Thread(target=schedule_reminders)
    scheduler_thread.start()
    logging.info("Запущено планувальник для відправки нагадувань")

@bot.callback_query_handler(func=lambda call: call.data == 'register')
def process_registration(call):
    user_id = call.from_user.id

    if user_id in user_cache or database.is_user_registered(user_id):
        user_cache[user_id] = True
        bot.send_message(call.message.chat.id, "✅ **Ви вже авторизовані!**", parse_mode='Markdown')
        logging.info(f"Користувач {user_id} вже авторизований")
    else:
        bot.send_message(call.from_user.id, "✏️ **Введіть своє ім'я та прізвище:**", parse_mode='Markdown')
        bot.register_next_step_handler(call.message, get_name)
        logging.info(f"Користувач {user_id} почав реєстрацію")

def get_name(message):
    user_id = message.from_user.id
    name = message.text
    bot.send_message(message.chat.id, "📱 **Введіть ваш номер телефону:**", parse_mode='Markdown')
    bot.register_next_step_handler(message, get_phone, name)
    logging.info(f"Користувач {user_id} ввів ім'я: {name}")

def get_phone(message, name):
    phone = message.text
    bot.send_message(message.chat.id, "🏙 **Введіть ваше місто:**", parse_mode='Markdown')
    bot.register_next_step_handler(message, get_city, name, phone)
    logging.info(f"Користувач {message.from_user.id} ввів телефон: {phone}")

def get_city(message, name, phone):
    city = message.text
    user_id = message.from_user.id

    database.add_user(user_id, name, phone, city)
    user_cache[user_id] = True  # Додаємо користувача до кешу

    bot.send_message(message.chat.id, "🎉 **Ви успішно зареєстровані!**", parse_mode='Markdown')
    logging.info(f"Користувач {user_id} зареєстрований. Місто: {city}, Телефон: {phone}")
    send_main_menu(message.chat.id)

def send_main_menu(chat_id):
    markup = types.InlineKeyboardMarkup()
    button_request = types.InlineKeyboardButton('📝 Зробити запит', callback_data='make_request')
    button_status = types.InlineKeyboardButton('🔍 Перевірити статус', callback_data='check_status')
    button_export = types.InlineKeyboardButton('📊 Експортувати запити', callback_data='export_requests')
    markup.add(button_request, button_status, button_export)
    bot.send_message(chat_id, "🔔 **Оберіть одну з опцій:**", reply_markup=markup, parse_mode='Markdown')
    logging.info(f"Користувачу {chat_id} надіслано головне меню")

@bot.callback_query_handler(func=lambda call: call.data == 'export_requests')
def export_requests(call):
    user_id = call.from_user.id
    if user_id in config.ADMIN_NAMES:
        # Экспортируем запросы в Excel
        file_path = database.export_requests_to_excel()
        with open(file_path, 'rb') as file:
            bot.send_document(user_id, file)
        logging.info(f"Адміністратор {user_id} експортував запити в Excel")
    else:
        bot.send_message(call.message.chat.id, "⛔️ Ви не маєте прав для експорту запитів.")
        logging.warning(f"Користувач {user_id} спробував експортувати запити без прав")

@bot.callback_query_handler(func=lambda call: call.data == 'make_request')
def choose_currency(call):
    markup = types.InlineKeyboardMarkup()
    button_usd = types.InlineKeyboardButton('💵 USD', callback_data='currency_usd')
    button_eur = types.InlineKeyboardButton('💶 EUR', callback_data='currency_eur')
    button_uah = types.InlineKeyboardButton('💴 UAH', callback_data='currency_uah')
    markup.add(button_usd, button_eur, button_uah)
    bot.send_message(call.message.chat.id, "💰 **Оберіть валюту:**", reply_markup=markup, parse_mode='Markdown')
    logging.info(f"Користувачу {call.message.chat.id} запропоновано вибір валюти")

@bot.callback_query_handler(func=lambda call: call.data.startswith('currency_'))
def process_currency(call):
    currency = call.data.split('_')[1].upper()
    bot.send_message(call.message.chat.id, f"🤑 **Ви обрали {currency}. Тепер введіть суму:**", parse_mode='Markdown')
    logging.info(f"Користувач {call.message.chat.id} обрав валюту: {currency}")
    bot.register_next_step_handler(call.message, process_amount, currency)

def process_amount(message, currency):
    amount = message.text
    if not amount.isdigit():
        bot.send_message(message.chat.id, "❗️ **Будь ласка, введіть коректне число для суми.**", parse_mode='Markdown')
        logging.warning(f"Користувач {message.from_user.id} ввів некоректну суму: {amount}")
        bot.register_next_step_handler(message, process_amount, currency)
        return

    bot.send_message(message.chat.id, "🖋 **Введіть коментар:**", parse_mode='Markdown')
    logging.info(f"Користувач {message.from_user.id} ввів суму: {amount} {currency}")
    bot.register_next_step_handler(message, process_comment, currency, amount)

def process_comment(message, currency, amount):
    comment = message.text

    markup = types.InlineKeyboardMarkup()
    skip_button = types.InlineKeyboardButton('⏭ Пропустити', callback_data=f'skip_file|{currency}|{amount}|{comment}')
    markup.add(skip_button)

    bot.send_message(message.chat.id, "📎 **Тепер можете прикріпити фото або PDF-файл. Якщо файл не потрібен, пропустіть цей крок.**", reply_markup=markup, parse_mode='Markdown')
    logging.info(f"Користувач {message.from_user.id} додав коментар: {comment}")
    bot.register_next_step_handler(message, process_file, currency, amount, comment)

@bot.callback_query_handler(func=lambda call: call.data.startswith('skip_file'))
def skip_file(call):
    try:
        _, currency, amount, comment = call.data.split('|')
        user_id = call.from_user.id

        request_id, request_number = database.add_request(user_id, currency, amount, comment, None)

        user_info = database.get_user_info(user_id)
        request_text = (f"🆕 **Запит №{request_number}** від {user_info['name']}, {user_info['city']} (📞 Телефон: {user_info['phone']}):\n"
                        f"💰 **Сума:** {amount} {currency}\n"
                        f"🖋 **Коментар:** {comment}\n"
                        f"📎 **Файл:** Файл не додано.")
        request_message = bot.send_message(config.ADMIN_CHAT_ID, request_text, parse_mode='Markdown')

        markup = types.InlineKeyboardMarkup()
        approve_button = types.InlineKeyboardButton('✅ Погодити', callback_data=f'approve_{request_id}')
        reject_button = types.InlineKeyboardButton('❌ Відхилити', callback_data=f'reject_{request_id}')
        markup.add(approve_button, reject_button)

        bot.edit_message_reply_markup(config.ADMIN_CHAT_ID, request_message.message_id, reply_markup=markup)
        bot.send_message(call.message.chat.id, f"📩 **Ваш запит №{request_number}: {amount} {currency}. Запит прийнятий на розгляд без файлу.**", parse_mode='Markdown')
        logging.info(f"Користувач {user_id} створив запит №{request_number} на суму {amount} {currency} без файлу")
    except Exception as e:
        bot.send_message(call.message.chat.id, "❗️ **Виникла помилка при пропуску файлу. Спробуйте ще раз.**")
        logging.error(f"Помилка при пропуску файлу для користувача {call.from_user.id}: {str(e)}")

def process_file(message, currency, amount, comment):
    try:
        file_path = None
        user_id = message.from_user.id

        if message.content_type == 'photo':
            file_info = bot.get_file(message.photo[-1].file_id)
            downloaded_file = bot.download_file(file_info.file_path)
            file_path = os.path.join(UPLOAD_FOLDER, file_info.file_unique_id + '.jpg')
            with open(file_path, 'wb') as new_file:
                new_file.write(downloaded_file)
        elif message.content_type == 'document' and message.document.mime_type == 'application/pdf':
            file_info = bot.get_file(message.document.file_id)
            downloaded_file = bot.download_file(file_info.file_path)
            file_path = os.path.join(UPLOAD_FOLDER, message.document.file_name)
            with open(file_path, 'wb') as new_file:
                new_file.write(downloaded_file)

        request_id, request_number = database.add_request(user_id, currency, amount, comment, file_path)

        user_info = database.get_user_info(user_id)
        request_text = (f"🆕 **Запит №{request_number}** від {user_info['name']}, {user_info['city']} (📞 Телефон: {user_info['phone']}):\n"
                        f"💰 **Сума:** {amount} {currency}\n"
                        f"🖋 **Коментар:** {comment}\n"
                        f"📎 **Файл:** {'Прикріплено' if file_path else 'Файл не додано.'}")
        request_message = bot.send_message(config.ADMIN_CHAT_ID, request_text, parse_mode='Markdown')

        markup = types.InlineKeyboardMarkup()
        approve_button = types.InlineKeyboardButton('✅ Погодити', callback_data=f'approve_{request_id}')
        reject_button = types.InlineKeyboardButton('❌ Відхилити', callback_data=f'reject_{request_id}')
        markup.add(approve_button, reject_button)

        bot.edit_message_reply_markup(config.ADMIN_CHAT_ID, request_message.message_id, reply_markup=markup)

        if file_path:
            with open(file_path, 'rb') as file_to_send:
                if message.content_type == 'photo':
                    bot.send_photo(config.ADMIN_CHAT_ID, photo=file_to_send)
                elif message.content_type == 'document':
                    bot.send_document(config.ADMIN_CHAT_ID, document=file_to_send)

        bot.send_message(message.chat.id, f"📩 **Ваш запит №{request_number}: {amount} {currency}. Запит прийнятий на розгляд.**", parse_mode='Markdown')
        logging.info(f"Користувач {user_id} створив запит №{request_number} на суму {amount} {currency} з файлом")
    except Exception as e:
        bot.send_message(message.chat.id, "❗️ **Виникла помилка під час обробки файлу. Спробуйте ще раз або пропустіть цей крок.**")
        logging.error(f"Помилка під час обробки файлу для користувача {message.from_user.id}: {str(e)}")

@bot.callback_query_handler(func=lambda call: call.data.startswith(('approve_', 'reject_')))
def process_approval(call):
    action, request_id = call.data.split('_')
    request_id = int(request_id)

    # Получаем ID администратора
    admin_id = call.from_user.id

    # Получаем имя администратора из словаря
    admin_name = config.ADMIN_NAMES.get(admin_id, f"Адміністратор {admin_id}")

    status = 'Погоджено' if action == 'approve' else 'Відхилено'
    database.update_request_status(request_id, status)

    request_info = database.get_request_info(request_id)
    user_id = request_info['user_id']
    request_number = request_info['request_number']

    bot.send_message(user_id, f"Ваш запит №{request_number} було {status.lower()}.")
    bot.edit_message_text(
        f"Запит №{request_number} від {request_info['name']} було {status.lower()}.",
        config.ADMIN_CHAT_ID,
        message_id=call.message.message_id
    )

    # Логирование действия с указанием администратора
    logging.info(f"Запит №{request_number} користувача {user_id} було {status.lower()} адміністратором {admin_name}")

@bot.message_handler(commands=['stats'])
def send_stats(message):
    if message.from_user.id in config.ADMIN_NAMES:
        total_requests = database.get_total_requests()
        approved_requests = database.get_approved_requests()
        rejected_requests = database.get_rejected_requests()
        amount_by_currency = database.get_total_amount_by_currency()  

        # Формируем строку с суммой по валютам
        currency_stats = ""
        for currency, total_amount in amount_by_currency.items():
            currency_stats += f"{currency}: {total_amount}\n"

        # Формируем итоговое сообщение
        bot.send_message(message.chat.id, f"📊 Статистика запитів:\n"
                                          f"Загалом запитів: {total_requests}\n"
                                          f"Погоджено: {approved_requests}\n"
                                          f"Відхилено: {rejected_requests}\n"
                                          f"Загальна сума запитів по валютам:\n{currency_stats}")
        logging.info(f"Адміністратор {message.from_user.id} запросив статистику")
    else:
        bot.send_message(message.chat.id, "⛔️ Ви не маєте прав для перегляду статистики.")
        logging.warning(f"Користувач {message.from_user.id} спробував отримати доступ до статистики без прав")

@bot.callback_query_handler(func=lambda call: call.data == 'check_status')
def check_status(call):
    user_id = call.from_user.id
    active_requests = database.get_active_requests(user_id)

    if active_requests:
        messages = []
        for req in active_requests:
            messages.append(f"Запит №{req['request_number']}: {req['amount']} {req['currency']}\nСтатус: {req['status']}")
        bot.send_message(call.message.chat.id, "\n\n".join(messages))
        logging.info(f"Користувачу {user_id} надіслано список активних запитів")
    else:
        bot.send_message(call.message.chat.id, "У вас немає активних запитів.")
        logging.info(f"Користувачу {user_id} надіслано повідомлення: немає активних запитів")

if __name__ == "__main__":
    run_scheduler()
    bot.polling(none_stop=True)
