import asyncio
import os
import random
from datetime import datetime
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.tl.types import UserStatusOnline
import anthropic

API_ID = int(os.environ["API_ID"])
API_HASH = os.environ["API_HASH"]
ANTHROPIC_KEY = os.environ["ANTHROPIC_KEY"]
SESSION_STRING = os.environ["SESSION_STRING"]

client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)
ai = anthropic.Anthropic(api_key=ANTHROPIC_KEY)

# 💕 Номер девушки
GIRLFRIEND_PHONE = "+998901227646"
girlfriend_id = None

# 🎭 Анимации для всех
ANIMATIONS = [
    ["🔥", "🔥🔥", "🔥🔥🔥", "💥", "✨"],
    ["⭐", "🌟", "💫", "✨", "🌠"],
    ["😴", "😴💤", "😴💤💤", "🛌💤", "🤖"],
    ["👻", "👻💀", "💀👻", "👻", "😱"],
]

# 💕 Анимации для девушки
GIRLFRIEND_ANIMATIONS = [
    ["🤍", "🩷", "❤️", "🩷", "🤍"],
    ["💫", "✨", "💕", "✨", "💫"],
    ["🌹", "🌸", "🌺", "🌸", "🌹"],
]

FUNNY_MORNING = [
    "☀️ ещё сплю, позже",
    "🥱 рано ещё. ок?",
    "☕ без кофе не отвечаю",
]
FUNNY_DAY = [
    "📵 занят, позже",
    "🏃 не в сети, ок",
    "🎮 ладно, напишу потом",
    "🌀 понял, скоро буду",
]
FUNNY_EVENING = [
    "🌆 отдыхаю, позже напишу",
    "📺 ладно, понял",
    "🛋️ не в сети сейчас",
]
FUNNY_NIGHT = [
    "🌙 сплю. ок?",
    "👻 ночь уже...",
    "😴 понял, завтра отвечу",
]

GF_MORNING = [
    "доброе утро солнышко ☀️❤️ сплю ещё, скоро напишу",
    "привет моя хорошая 🌸 только проснулся, скучаю",
]
GF_DAY = [
    "привет любимая ❤️ занят сейчас, но думаю о тебе",
    "солнышко 🌹 не в сети, скоро вернусь. скучаю",
    "привет 💕 занят немного, напишу как освобожусь",
]
GF_EVENING = [
    "привет моя хорошая 🌸 скоро буду, скучаю по тебе ❤️",
    "солнышко 💕 отдыхаю, напишу чуть позже. люблю",
]
GF_NIGHT = [
    "сплю уже 😴❤️ спокойной ночи моя хорошая",
    "ночь уже 🌙 ложись спать, напишу утром. люблю 💕",
    "засыпаю 😴 спокойной ночи солнышко ❤️",
]

def get_time_mood(is_girlfriend=False):
    hour = (datetime.now().hour + 5) % 24
    if is_girlfriend:
        if 6 <= hour < 11:
            return "morning", random.choice(GF_MORNING)
        elif 11 <= hour < 18:
            return "day", random.choice(GF_DAY)
        elif 18 <= hour < 23:
            return "evening", random.choice(GF_EVENING)
        else:
            return "night", random.choice(GF_NIGHT)
    else:
        if 6 <= hour < 11:
            return "morning", random.choice(FUNNY_MORNING)
        elif 11 <= hour < 18:
            return "day", random.choice(FUNNY_DAY)
        elif 18 <= hour < 23:
            return "evening", random.choice(FUNNY_EVENING)
        else:
            return "night", random.choice(FUNNY_NIGHT)

def get_system_prompt(time_of_day, is_girlfriend=False):
    if is_girlfriend:
        base = """Ты — автоответчик парня в Telegram. Пишешь его девушке.

СТИЛЬ (очень важно):
- Нежно, тепло, с любовью
- Коротко — 1-2 предложения
- Используй: солнышко, любимая, моя хорошая
- Добавляй сердечки: ❤️ 💕 🌹 🌸
- Скажи что не в сети но думаешь о ней
- Пиши без заглавных букв как в чате"""
        if time_of_day == "night":
            base += "\n- Ночь — пожелай спокойной ночи нежно"
        return base
    else:
        base = """Ты — автоответчик в Telegram.
- Пиши коротко, 1-2 предложения
- Без заглавных букв
- Слова: ок, ладно, понял
- Скажи что не в сети"""
        if time_of_day == "night":
            base += "\n- Ночь, добавь 🌙"
        return base

@client.on(events.NewMessage(incoming=True, func=lambda e: e.is_private))
async def handler(event):
    if not event.raw_text or event.raw_text.strip() == "":
        return

    # ✅ Проверяем онлайн ли хозяин — если да, не отвечаем
    try:
        me = await client.get_me()
        my_entity = await client.get_entity(me.id)
        if isinstance(my_entity.status, UserStatusOnline):
            return
    except Exception:
        pass

    # Девушка или нет
    is_girlfriend = (girlfriend_id is not None and event.sender_id == girlfriend_id)

    # Анимация
    if is_girlfriend:
        animation = random.choice(GIRLFRIEND_ANIMATIONS)
    else:
        animation = random.choice(ANIMATIONS)

    msg = await event.respond(animation[0])
    for frame in animation[1:]:
        await asyncio.sleep(0.4)
        await msg.edit(frame)

    time_of_day, auto_reply = get_time_mood(is_girlfriend)

    # 25% шанс авто-ответа (только не для девушки)
    if not is_girlfriend and random.random() < 0.25:
        await asyncio.sleep(0.3)
        await msg.edit(auto_reply)
        return

    # ИИ отвечает
    try:
        response = ai.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=100,
            system=get_system_prompt(time_of_day, is_girlfriend),
            messages=[{"role": "user", "content": event.raw_text}]
        )
        await msg.edit(response.content[0].text)
    except Exception:
        await msg.edit(auto_reply)

async def main():
    global girlfriend_id
    await client.start()

    # Находим ID девушки
    try:
        gf = await client.get_entity(GIRLFRIEND_PHONE)
        girlfriend_id = gf.id
        print(f"Девушка найдена ✅ ID: {girlfriend_id}")
    except Exception as e:
        print(f"Девушка не найдена ❌ {e}")

    print("Бот запущен! ✅")
    await client.run_until_disconnected()

asyncio.run(main())
