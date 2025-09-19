import telebot
import sqlite3
import random
import time

TOKEN = "bot_token"
bot = telebot.TeleBot("my_token")

# === база данных ===
conn = sqlite3.connect("game.db", check_same_thread=False)
cursor = conn.cursor()

# таблица игроков (глобальные очки и общий таймер)
cursor.execute("""
CREATE TABLE IF NOT EXISTS players (
    user_id INTEGER PRIMARY KEY,
    name TEXT,
    points INTEGER DEFAULT 0,
    last_dep INTEGER DEFAULT 0
)
""")

# таблица для связи пользователей с чатами (чтобы показывать топ чата)
cursor.execute("""
CREATE TABLE IF NOT EXISTS chats (
    user_id INTEGER,
    chat_id INTEGER,
    PRIMARY KEY(user_id, chat_id)
)
""")
conn.commit()

# === список предметов ===
items = [
    {"emoji": "🍎", "price": 10, "chance": 50},
    {"emoji": "🍌", "price": 30, "chance": 30},
    {"emoji": "🍒", "price": 70, "chance": 15},
    {"emoji": "🍍", "price": 150, "chance": 5},
]

def roll_item():
    total = sum(item["chance"] for item in items)
    r = random.randint(1, total)
    cumulative = 0
    for item in items:
        cumulative += item["chance"]
        if r <= cumulative:
            return item

# === функции работы с БД ===
def get_player(user_id, name):
    cursor.execute("SELECT * FROM players WHERE user_id=?", (user_id,))
    player = cursor.fetchone()
    if not player:
        cursor.execute("INSERT INTO players (user_id, name) VALUES (?, ?)", (user_id, name))
        conn.commit()
        return (user_id, name, 0, 0)
    else:
        cursor.execute("UPDATE players SET name=? WHERE user_id=?", (name, user_id))
        conn.commit()
        return player

def update_player(user_id, points=None, last_dep=None):
    if points is not None and last_dep is not None:
        cursor.execute("UPDATE players SET points=?, last_dep=? WHERE user_id=?", (points, last_dep, user_id))
    elif points is not None:
        cursor.execute("UPDATE players SET points=? WHERE user_id=?", (points, user_id))
    elif last_dep is not None:
        cursor.execute("UPDATE players SET last_dep=? WHERE user_id=?", (last_dep, user_id))
    conn.commit()

def register_chat(user_id, chat_id):
    cursor.execute("SELECT * FROM chats WHERE user_id=? AND chat_id=?", (user_id, chat_id))
    if not cursor.fetchone():
        cursor.execute("INSERT INTO chats (user_id, chat_id) VALUES (?, ?)", (user_id, chat_id))
        conn.commit()

# === команды ===
@bot.message_handler(commands=["dep"])
def dep(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    name = message.from_user.first_name

    register_chat(user_id, chat_id)
    player = get_player(user_id, name)
    points = player[2]
    last_dep = player[3]
    current_time = int(time.time())

    if current_time - last_dep >= 8*3600:
        item = roll_item()
        new_points = points + item["price"]
        update_player(user_id, new_points, current_time)
        bot.reply_to(
            message,
            f"{name}, тебе выпало {item['emoji']} за {item['price']} очков!\n"
            f"Теперь у тебя {new_points} очков."
        )
    else:
        remaining = 8*3600 - (current_time - last_dep)
        hours = remaining // 3600
        minutes = (remaining % 3600) // 60
        bot.reply_to(message, f"{name}, жди ещё {hours} ч {minutes} мин.")

@bot.message_handler(commands=["stats"])
def stats(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    name = message.from_user.first_name

    register_chat(user_id, chat_id)
    player = get_player(user_id, name)
    points = player[2]
    last_dep = player[3]
    current_time = int(time.time())

    if current_time - last_dep >= 8*3600:
        wait = "Можно делать деп!"
    else:
        remaining = 8*3600 - (current_time - last_dep)
        hours = remaining // 3600
        minutes = (remaining % 3600) // 60
        wait = f"Ждать ещё {hours} ч {minutes} мин."

    bot.reply_to(message, f"{name}, твои очки: {points}\n{wait}")

@bot.message_handler(commands=["topchat"])
def top_chat(message):
    chat_id = message.chat.id
    cursor.execute("""
        SELECT p.name, p.points 
        FROM players p
        JOIN chats c ON p.user_id = c.user_id
        WHERE c.chat_id=?
        ORDER BY p.points DESC LIMIT 10
    """, (chat_id,))
    leaders = cursor.fetchall()

    text = "🏆 ТОП игроков чата:\n"
    for i, (name, points) in enumerate(leaders, start=1):
        text += f"{i}. {name} — {points} очков\n"

    bot.reply_to(message, text)

@bot.message_handler(commands=["topworld"])
def top_world(message):
    cursor.execute("""
        SELECT name, points
        FROM players
        ORDER BY points DESC LIMIT 10
    """)
    leaders = cursor.fetchall()

    text = "🌍 ТОП игроков мира:\n"
    for i, (name, points) in enumerate(leaders, start=1):
        text += f"{i}. {name} — {points} очков\n"

    bot.reply_to(message, text)

# === запуск ==

bot.polling(none_stop=True)
