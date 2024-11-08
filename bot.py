import telebot
from telebot import types
import config
import database
import os
import logging
from cachetools import TTLCache
from threading import Thread
import schedule
import time

logging.basicConfig(filename="bot.log", 
                    level=logging.INFO, 
                    format="%(asctime)s - %(levelname)s - %(message)s", 
                    encoding='utf-8')

bot = telebot.TeleBot(config.TOKEN)
database.create_tables()

UPLOAD_FOLDER = config.UPLOAD_FOLDER
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

user_cache = TTLCache(maxsize=1000, ttl=600)

@bot.message_handler(commands=['start'])
def start_registration(message):
    user_id = message.from_user.id
    if user_id in user_cache or database.is_user_registered(user_id):
        user_cache[user_id] = True  
        send_main_menu(message.chat.id)
        logging.info(f"Користувач {user_id} вже зареєстрований, надіслано головне меню")
    else:
        markup = types.InlineKeyboardMarkup()
        button = types.InlineKeyboardButton('🆕 Зареєструватися', callback_data='register')
        markup.add(button)
        bot.send_message(message.chat.id, "👤 **Натисніть кнопку для реєстрації**", reply_markup=markup, parse_mode='Markdown')
        logging.info(f"Користувач {user_id} отримав пропозицію для реєстрації")

def send_active_requests_reminder():
    active_requests = database.get_all_active_requests()
    if active_requests:
        messages = [
            f"📌 **Запит №{req['request_number']}**\n"
            f"👤 **Користувач:** {req['name']} (Телефон: {req['phone']})\n"
            f"💰 **Сума:** {req['amount']}\n"
            f"🖋 **Коментар:** {req['comment']}\n"
            f"📎 **Файл:** {'Прикріплено' if req['file_path'] else 'Файл не додано.'}\n"
            f"📅 **Статус:** {req['status']}"
            for req in active_requests
        ]
        bot.send_message(config.ADMIN_CHAT_ID, "🔔 **Нагадування про активні заявки**:\n\n" + "\n\n".join(messages), parse_mode='Markdown')
        logging.info("Надіслано нагадування про активні заявки адміністратору")

def schedule_reminders():
    weekdays = ["monday", "tuesday", "wednesday", "thursday", "friday"]
    for day in weekdays:
        for hour in range(10, 17):
            getattr(schedule.every(), day).at(f"{hour}:00").do(send_active_requests_reminder)
    while True:
        schedule.run_pending()
        time.sleep(1)

def run_scheduler():
    scheduler_thread = Thread(target=schedule_reminders)
    scheduler_thread.start()
    logging.info("Запущено планувальник для відправки нагадувань")

@bot.callback_query_handler(func=lambda call: call.data == 'make_request')
def handle_make_request(call):
    user_id = call.from_user.id
    bot.send_message(call.message.chat.id, "💰 **Введіть суму вашого запиту:**", parse_mode='Markdown')
    bot.register_next_step_handler(call.message, process_amount)
    logging.info(f"Користувач {user_id} натиснув кнопку 'Зробити запит'")

@bot.callback_query_handler(func=lambda call: call.data == 'register')
def process_registration(call):
    user_id = call.from_user.id
    if user_id in user_cache or database.is_user_registered(user_id):
        user_cache[user_id] = True
        bot.send_message(call.message.chat.id, "✅ **Ви вже авторизовані!**", parse_mode='Markdown')
        logging.info(f"Користувач {user_id} вже авторизований")
    else:
        bot.send_message(call.from_user.id, "✏️ **Введіть ваше ім'я та прізвище:**", parse_mode='Markdown')
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
    user_cache[user_id] = True
    bot.send_message(message.chat.id, "🎉 **Ви успішно зареєстровані!**", parse_mode='Markdown')
    logging.info(f"Користувач {user_id} зареєстрований. Місто: {city}, Телефон: {phone}")
    send_main_menu(message.chat.id)

def send_main_menu(chat_id):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton('📝 Зробити запит', callback_data='make_request'))
    bot.send_message(chat_id, "🔔 **Оберіть одну з опцій:**", reply_markup=markup, parse_mode='Markdown')
    logging.info(f"Користувачу {chat_id} надіслано головне меню")

@bot.message_handler(commands=['export_requests'])
def export_requests_command(message):
    user_id = message.from_user.id
    if user_id in config.ADMIN_NAMES:
        file_path = database.export_requests_to_excel()
        with open(file_path, 'rb') as file:
            bot.send_document(user_id, file)
        logging.info(f"Адміністратор {user_id} експортував запити в Excel")
    else:
        bot.send_message(message.chat.id, "⛔️ У вас немає прав для експорту запитів.")
        logging.warning(f"Користувач {user_id} намагався експортувати запити без прав")

@bot.message_handler(commands=['import_requests'])
def import_requests_command(message):
    user_id = message.from_user.id
    if user_id in config.ADMIN_NAMES:
        bot.send_message(user_id, "🗂️ Функція імпорту запитів запущена.")
        logging.info(f"Адміністратор {user_id} виконав імпорт запитів")
    else:
        bot.send_message(message.chat.id, "⛔️ У вас немає прав для імпорту запитів.")
        logging.warning(f"Користувач {user_id} намагався виконати імпорт запитів без прав")

def process_amount(message):
    amount = message.text
    if not amount.isdigit():
        bot.send_message(message.chat.id, "❗️ **Будь ласка, введіть коректне число для суми.**", parse_mode='Markdown')
        logging.warning(f"Користувач {message.from_user.id} ввів некоректну суму: {amount}")
        bot.register_next_step_handler(message, process_amount)
        return
    bot.send_message(message.chat.id, "🖋 **Введіть коментар:**", parse_mode='Markdown')
    bot.register_next_step_handler(message, process_comment, amount)
    logging.info(f"Користувач {message.from_user.id} ввів суму: {amount}")

def process_comment(message, amount):
    comment = message.text
    markup = types.InlineKeyboardMarkup()
    skip_button = types.InlineKeyboardButton('⏭ Пропустити', callback_data=f'skip_file|{amount}|{comment}')
    markup.add(skip_button)
    bot.send_message(message.chat.id, "📎 **Тепер можна прикріпити фото або PDF-файл. Якщо файл не потрібен, пропустіть цей крок.**", reply_markup=markup, parse_mode='Markdown')
    logging.info(f"Користувач {message.from_user.id} додав коментар: {comment}")
    bot.register_next_step_handler(message, process_file, amount, comment)

@bot.callback_query_handler(func=lambda call: call.data.startswith('skip_file'))
def skip_file(call):
    _, amount, comment = call.data.split('|')
    user_id = call.from_user.id
    request_id, request_number = database.add_request(user_id, amount, comment, None)
    notify_admin_about_request(request_id, request_number, amount, comment, user_id)
    bot.send_message(call.message.chat.id, f"📩 **Ваш запит №{request_number}: {amount} прийнятий на розгляд.**", parse_mode='Markdown')
    logging.info(f"Запит №{request_number} від користувача {user_id} додано без файлу")

def process_file(message, amount, comment):
    try:
        file_path = None
        user_id = message.from_user.id
        if message.content_type == 'photo':
            file_info = bot.get_file(message.photo[-1].file_id)
            downloaded_file = bot.download_file(file_info.file_path)
            file_path = os.path.join(UPLOAD_FOLDER, file_info.file_unique_id + '.jpg')
            with open(file_path, 'wb') as new_file:
                new_file.write(downloaded_file)
        elif message.content_type == 'document':
            file_extension = os.path.splitext(message.document.file_name)[-1].lower()
            supported_formats = ['.pdf', '.jpg', '.jpeg', '.png', '.txt', '.doc', '.docx', '.xls', '.xlsx']
            if file_extension not in supported_formats:
                bot.send_message(message.chat.id, "❗️ **Формат файла не поддерживается. Разрешенные форматы: PDF, JPG, JPEG, PNG, TXT, DOC, DOCX, XLS, XLSX.**")
                logging.warning(f"Формат файла {file_extension} не поддерживается для пользователя {user_id}")
                return
            file_info = bot.get_file(message.document.file_id)
            downloaded_file = bot.download_file(file_info.file_path)
            file_path = os.path.join(UPLOAD_FOLDER, message.document.file_name)
            with open(file_path, 'wb') as new_file:
                new_file.write(downloaded_file)

        request_id, request_number = database.add_request(user_id, amount, comment, file_path)
        notify_admin_about_request(request_id, request_number, amount, comment, user_id, file_path)
        bot.send_message(message.chat.id, f"📩 **Ваш запит №{request_number}: {amount} прийнятий на розгляд.**", parse_mode='Markdown')
        logging.info(f"Запит №{request_number} від користувача {user_id} додано з файлом {file_path if file_path else 'без файлу'}")

    except Exception as e:
        error_message = f"❗️ **Произошла ошибка при обработке файла. Причина: {str(e)}.** Пожалуйста, попробуйте снова или загрузите другой файл."
        bot.send_message(message.chat.id, error_message)
        logging.error(f"Ошибка при обработке файла для пользователя {message.from_user.id}: {str(e)}")

def notify_admin_about_request(request_id, request_number, amount, comment, user_id, file_path=None):
    user_info = database.get_user_info(user_id)
    request_text = (f"🆕 **Запит №{request_number}** від {user_info['name']}, {user_info['city']} (📞 Телефон: {user_info['phone']}):\n"
                    f"💰 **Сума:** {amount}\n"
                    f"🖋 **Коментар:** {comment}\n"
                    f"📎 **Файл:** {'Прикріплено' if file_path else 'Файл не додано.'}")
    request_message = bot.send_message(config.ADMIN_CHAT_ID, request_text, parse_mode='Markdown')

    if file_path:
        with open(file_path, 'rb') as file:
            bot.send_document(config.ADMIN_CHAT_ID, file) if file_path.endswith(('.pdf', '.txt', '.doc', '.docx', '.xls', '.xlsx')) else bot.send_photo(config.ADMIN_CHAT_ID, file)

    markup = types.InlineKeyboardMarkup()
    approve_button = types.InlineKeyboardButton('✅ Погодити без коментаря', callback_data=f'approve_without_comment_{request_id}')
    approve_with_comment_button = types.InlineKeyboardButton('✏️ Погодити з коментарем', callback_data=f'approve_with_comment_{request_id}')
    reject_button = types.InlineKeyboardButton('❌ Відхилити', callback_data=f'reject_{request_id}')
    markup.add(approve_button, approve_with_comment_button, reject_button)
    bot.edit_message_reply_markup(config.ADMIN_CHAT_ID, request_message.message_id, reply_markup=markup)
    logging.info(f"Надіслано запит №{request_number} адміністратору")

@bot.callback_query_handler(func=lambda call: call.data.startswith('approve_without_comment_'))
def approve_without_comment(call):
    request_id = int(call.data.split('_')[-1])
    admin_name = config.ADMIN_NAMES.get(call.from_user.id, "Адміністратор")
    
    database.update_request_status(request_id, "Погоджено")
    request_info = database.get_request_info(request_id)
    bot.send_message(request_info['user_id'], f"Ваш запит №{request_info['request_number']} було погоджено адміністратором {admin_name} без коментаря.")
    bot.edit_message_text(f"Запит №{request_id} погоджено адміністратором {admin_name}.", config.ADMIN_CHAT_ID, call.message.message_id)
    logging.info(f"Запит №{request_id} погоджено без коментаря")

@bot.callback_query_handler(func=lambda call: call.data.startswith('approve_with_comment_'))
def approve_with_comment(call):
    request_id = int(call.data.split('_')[-1])
    bot.send_message(call.message.chat.id, "✏️ Введіть ваш коментар до погодження:", parse_mode='Markdown')
    bot.register_next_step_handler(call.message, process_approve_comment, request_id, call.message.message_id)
    logging.info(f"Адміністратор обрав погодження з коментарем для запиту №{request_id}")

def process_approve_comment(message, request_id, admin_message_id):
    admin_comment = message.text
    request_info = database.get_request_info(request_id)
    database.update_request_status(request_id, "Погоджено", admin_comment)

    try:
        bot.edit_message_text(
            f"Запит №{request_info['request_number']} погоджено з коментарем адміністратора: {admin_comment}",
            chat_id=config.ADMIN_CHAT_ID,
            message_id=admin_message_id,
            parse_mode='Markdown'
        )
    except telebot.apihelper.ApiTelegramException as e:
        logging.warning(f"Не вдалося оновити повідомлення з кнопками: {e}")

    bot.send_message(
        request_info['user_id'],
        f"Ваш запит №{request_info['request_number']} погоджено з коментарем адміністратора: {admin_comment}"
    )
    logging.info(f"Запит №{request_id} погоджено адміністратором з коментарем: {admin_comment}")

@bot.callback_query_handler(func=lambda call: call.data.startswith('reject_'))
def reject_request(call):
    request_id = int(call.data.split('_')[-1])
    admin_name = config.ADMIN_NAMES.get(call.from_user.id, "Адміністратор")
    
    database.update_request_status(request_id, "Відхилено")
    request_info = database.get_request_info(request_id)
    bot.send_message(request_info['user_id'], f"Ваш запит №{request_info['request_number']} було відхилено адміністратором {admin_name}.")
    bot.edit_message_text(f"Запит №{request_id} відхилено адміністратором {admin_name}.", config.ADMIN_CHAT_ID, call.message.message_id)
    logging.info(f"Запит №{request_id} відхилено адміністратором {admin_name}")

@bot.message_handler(commands=['stats'])
def send_stats(message):
    if message.from_user.id in config.ADMIN_NAMES:
        total_requests = database.get_total_requests()
        approved_requests = database.get_approved_requests()
        rejected_requests = database.get_rejected_requests()

        bot.send_message(
            message.chat.id,
            f"📊 Статистика запитів:\nЗагалом запитів: {total_requests}\nПогоджено: {approved_requests}\nВідхилено: {rejected_requests}",
            parse_mode='Markdown'
        )
        logging.info(f"Адміністратор {message.from_user.id} запросив статистику")
    else:
        bot.send_message(message.chat.id, "⛔️ У вас немає прав для перегляду статистики.")
        logging.warning(f"Користувач {message.from_user.id} намагався отримати доступ до статистики без прав")

if __name__ == "__main__":
    run_scheduler()
    bot.polling(none_stop=True)
