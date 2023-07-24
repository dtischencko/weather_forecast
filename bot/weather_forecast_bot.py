import psycopg2
import telebot
from telebot import types
import os


BOT_TOKEN = os.environ['BOT_TOKEN']
DB_HOST = os.environ['DB_HOST']
DB_PORT = os.environ['DB_PORT']
DB_USER = os.environ['DB_USER']
DB_PASSWORD = os.environ['DB_PASSWORD']
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
        pg_conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
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
