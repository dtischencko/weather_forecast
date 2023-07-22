import psycopg2
import telebot
from telebot import types
import os
from sshtunnel import SSHTunnelForwarder


BOT_TOKEN = os.environ.get('BOT_TOKEN')
SSH_HOST = os.environ.get('SSH_HOST')
SSH_PORT = os.environ.get('SSH_PORT')
SSH_USER = os.environ.get('SSH_USER')
SSH_PASSWORD = os.environ.get('SSH_PASSWORD')
DB_HOST = os.environ.get('DB_HOST')
DB_PORT = os.environ.get('DB_PORT')
DB_USER = os.environ.get('DB_USER')
DB_PASSWORD = os.environ.get('DB_PASSWORD')
bot = telebot.TeleBot(BOT_TOKEN)


@bot.message_handler(commands=['start'])
def handle_button(message):
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    button = types.KeyboardButton(text='Precipitation')
    keyboard.add(button)
    bot.send_message(message.chat.id, "Doing weather prediction in Russia, Krasnodar...", reply_markup=keyboard)


@bot.message_handler(func=lambda message: True)
def handle_reply(message):
    if message.text == 'Precipitation':
        with SSHTunnelForwarder(
            ssh_address_or_host=SSH_HOST,
            ssh_port=SSH_PORT,
            ssh_username=SSH_USER,
            ssh_password=SSH_PASSWORD,
            remote_bind_address=(DB_HOST, DB_PORT)
        ) as tunnel:
            pg_conn = psycopg2.connect(
                host='127.0.0.1',
                port=tunnel.local_bind_port,
                database='weather_forecast',
                user=DB_USER,
                password=DB_PASSWORD
            )
            pg_cursor = pg_conn.cursor()
            pg_cursor.execute(
                """SELECT prediction FROM public.predictions WHERE id = (SELECT id FROM public.predictions ORDER BY date_saved DESC LIMIT 1);""")
            result = pg_cursor.fetchone()[0]
            print(result)
            bot.send_message(message.chat.id, str(result))
            pg_cursor.close()
            pg_conn.close()


bot.polling()
