import telebot
import sqlite3
import datetime
from apscheduler.schedulers.background import BackgroundScheduler
import requests
import json

API_TOKEN = ""
API_KEY = ""

bot = telebot.TeleBot(API_TOKEN)
birthdaysdb = 'birthdays.db'
user_states = {}
scheduler = BackgroundScheduler()


def init_db():
    conn = sqlite3.connect(birthdaysdb)
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY)")
    conn.commit()
    conn.close()

def create_user_table(user_id):
    conn = sqlite3.connect(birthdaysdb)
    cursor = conn.cursor()
    table_name = f"user_{user_id}"
    cursor.execute(f'''
        CREATE TABLE IF NOT EXISTS {table_name} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            birthdate TEXT NOT NULL,
            preferences TEXT NOT NULL)
    ''')
    cursor.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
    conn.commit()
    conn.close()

def add_birthday(user_id, name, birthdate, preferences):
    conn = sqlite3.connect(birthdaysdb)
    cursor = conn.cursor()
    table_name = f"user_{user_id}"
    cursor.execute(f"INSERT INTO {table_name} (name, birthdate, preferences) VALUES (?, ?, ?)",(name, birthdate, preferences))
    conn.commit()
    conn.close()


def check_birthdays():
    conn = sqlite3.connect(birthdaysdb)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users")
    users = cursor.fetchall()
    today = datetime.date.today()
    tomorrow = today + datetime.timedelta(days=1)

    for (user_id,) in users:
        table_name = f"user_{user_id}"

        cursor.execute(f"SELECT * FROM {table_name}")
        data = cursor.fetchall()

        for person in data:
            birthday_str = person[2]
            try:
                birthday_date = datetime.datetime.strptime(birthday_str, '%d.%m.%Y').date()

                if (birthday_date.month == today.month and birthday_date.day == today.day):
                    questionai = f'Нипиши 10 подарков через запятую которые стоит подарить человеку если он {person[3]}. В ответ выведи только 10 идей подарков через запятую без сторонний символов'
                    response = requests.post(url="https://openrouter.ai/api/v1/chat/completions",
                    headers={"Authorization": f"Bearer {API_KEY}","HTTP-Referer": "<YOUR_SITE_URL>", "X-Title": "<YOUR_SITE_NAME>", },
                    data=json.dumps({"model": "amazon/nova-2-lite-v1:free","messages": [{"role": "user", "content": questionai}]}))
                    response.raise_for_status()
                    response_data = response.json()
                    answer_content = response_data['choices'][0]['message']['content']
                    message=f'Сегодня день рождения у {person[1]}! Советую подарить {answer_content}'
                    bot.send_message(chat_id=user_id, text=message, parse_mode='Markdown')

                if (birthday_date.month == tomorrow.month and birthday_date.day == tomorrow.day):
                    questionai = f'Нипиши 10 подарков через запятую которые стоит подарить человеку если он {person[3]}. В ответ выведи только 10 идей подарков через запятую без сторонний символов'
                    response = requests.post(url="https://openrouter.ai/api/v1/chat/completions",
                    headers={"Authorization": f"Bearer {API_KEY}","HTTP-Referer": "<YOUR_SITE_URL>", "X-Title": "<YOUR_SITE_NAME>", },
                    data=json.dumps({"model": "amazon/nova-2-lite-v1:free","messages": [{"role": "user", "content": questionai}]}))
                    response.raise_for_status()
                    response_data = response.json()
                    answer_content = response_data['choices'][0]['message']['content']
                    message=f'Завтра день рождения у {person[1]}. Советую подарить {answer_content}'
                    bot.send_message(chat_id=user_id, text=message, parse_mode='Markdown')
            except ValueError:
                print(f"Ошибка проверки дат: {birthday_str}")

    conn.close()


@bot.message_handler(commands=['start'])
def greeting(message):
    user_id = message.chat.id
    create_user_table(user_id)
    bot.reply_to(message,f"Привет. Я бот для, который может помочь тебе с запоминание дня рождения твоих друзей.")
    bot.send_message(message.chat.id, "Введи имя человека:")
    user_states[user_id] = {'state': 'awaiting_name'}

@bot.message_handler(content_types=['text'])
def handle_text(message):
    user_id = message.chat.id
    user_data = user_states.get(user_id, {})
    state = user_data.get('state')

    if state == 'awaiting_name':
        user_states[user_id] = {'state': 'awaiting_preferences', 'name': message.text}
        bot.send_message(user_id,"Теперь введите некоторые факты о человеке (например, играет в футбол, любит читать книги):",parse_mode='Markdown')

    elif state == 'awaiting_preferences':
        user_data['preferences'] = message.text
        user_data['state'] = 'awaiting_date'
        bot.send_message(user_id,"Теперь введите дату рождения (в формате ДД.ММ.ГГГГ):",parse_mode='Markdown')

    elif state == 'awaiting_date':
        name = user_data['name']
        preferences = user_data.get('preferences')
        birthdate = message.text

        try:
            datetime.datetime.strptime(birthdate, '%d.%m.%Y')
            add_birthday(user_id, name, birthdate, preferences)
            bot.send_message(user_id, "Человек добавлен.")
            if user_id in user_states:
                del user_states[user_id]
            bot.send_message(user_id, "Чтобы добавить еще одного человека, введите его имя:")
            user_states[user_id] = {'state': 'awaiting_name'}
        except ValueError:
            bot.send_message(user_id, "Неверный формат даты.",parse_mode='Markdown')


if __name__ == '__main__':
    init_db()


    scheduler.add_job(check_birthdays, 'cron',hour=8, minute=25)
    scheduler.start()


    try:
        bot.polling(none_stop=True)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()