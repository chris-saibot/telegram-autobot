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

GIRLFRIEND_PHONE = "+998901227646"
girlfriend_id = None

ANIMATIONS = [
    ["🔥", "🔥🔥", "🔥🔥🔥", "💥", "✨"],
    ["⭐", "🌟", "💫", "✨", "🌠"],
    ["😴", "😴💤", "😴💤💤", "🛌💤", "🤖"],
    ["👻", "👻💀", "💀👻", "👻", "😱"],
]

GIRLFRIEND_ANIMATIONS = [
    ["🤍", "🩷", "❤️", "🩷", "🤍"],
    ["💫", "✨", "💕", "✨", "💫"],
    ["🌹", "🌸", "🌺", "🌸", "🌹"],
]

FUNNY_MORNING = [
    "Сплю ещё, напишу позже",
    "Рано, позже отвечу",
    "Без кофе пока не соображаю, позже",
]
FUNNY_DAY = [
    "Занят сейчас, позже напишу",
    "Не в сети, позже",
    "Занят, отвечу как освобожусь",
    "Сейчас не могу, позже",
]
FUNNY_EVENING = [
    "Отдыхаю, позже напишу",
    "Не в сети сейчас, позже",
    "Занят, скоро буду",
]
FUNNY_NIGHT = [
    "Сплю уже, завтра отвечу",
    "Ночь уже, позже",
    "Лёг спать, завтра напишу",
]

GF_MORNING = [
    "Доброе утро солнышко ☀️❤️ Сплю ещё, скоро напишу",
    "Привет моя хорошая 🌸 Только просыпаюсь, скучаю",
]
GF_DAY = [
    "Привет любимая ❤️ Занят сейчас, но думаю о тебе",
    "Солнышко 🌹 Не в сети, скоро вернусь. Скучаю",
    "Привет 💕 Занят немного, напишу как освобожусь",
]
GF_EVENING = [
    "Привет моя хорошая 🌸 Скоро буду, скучаю по тебе ❤️",
    "Солнышко 💕 Отдыхаю, напишу чуть позже. Люблю",
]
GF_NIGHT = [
    "Сплю уже 😴❤️ Спокойной ночи моя хорошая",
    "Ночь уже 🌙 Ложись спать, напишу утром. Люблю 💕",
    "Засыпаю 😴 Спокойной ночи солнышко ❤️",
]

GROUP_REPLIES = [
    "Занят сейчас, позже отпишет",
    "Не в сети он, как появится — ответит",
    "Блин, занят. Позже напишет",
    "Сейчас недоступен, увидит позже",
    "Занят, как освобожусь — отпишет",
    "Не в сети, позже напишет",
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

def get_system_prompt(time_of_day, is_girlfriend=False, is_group=False):
    if is_girlfriend:
        base = """Ты — автоответчик парня в Telegram. Пишешь его девушке.
СТИЛЬ:
- Нежно, тепло, с любовью
- Коротко — 1-2 предложения
- Пиши с заглавной буквы
- Используй: солнышко, любимая, моя хорошая
- Добавляй сердечки: ❤️ 💕 🌹 🌸
- Скажи что не в сети но думаешь о ней
- Пиши как живой человек, не как робот"""
        if time_of_day == "night":
            base += "\n- Ночь — пожелай спокойной ночи нежно"
        return base
    elif is_group:
        return """Ты — автоответчик человека в групповом чате Telegram.
Его упомянули в группе. Отвечай ОТ ТРЕТЬЕГО ЛИЦА — то есть говори "он занят", "он не в сети".

СТИЛЬ:
- Очень коротко — 1 предложение
- С заглавной буквы
- Говори что хозяин занят / не в сети / увидит позже
- Иногда лёгкий мат типа "блин" — редко
- Без лишних эмодзи

ПРИМЕРЫ хороших ответов:
"Занят сейчас, позже отпишет"
"Не в сети он, как появится — ответит"
"Блин, занят он. Позже напишет"
"Сейчас недоступен, увидит позже"
"""
    else:
        base = """Ты — автоответчик реального человека в Telegram.
СТИЛЬ:
- С заглавной буквы
- Коротко — 1-2 предложения
- Немного официально но по-человечески
- Иногда лёгкий мат типа "блин" — редко
- Скажи что не в сети, ответишь позже
- Без лишних эмодзи, максимум 1
ПРИМЕРЫ:
"Занят сейчас, напишу позже"
"Не в сети, отвечу как смогу"
"Блин, занят. Позже напишу"
"""
        if time_of_day == "night":
            base += '\n- Ночь уже, добавь что лёг спать'
        elif time_of_day == "morning":
            base += '\n- Утро, намекни что только проснулся'
        return base

async def is_online():
    try:
        me = await client.get_me()
        my_entity = await client.get_entity(me.id)
        return isinstance(my_entity.status, UserStatusOnline)
    except Exception:
        return False

# 📩 Личные сообщения
@client.on(events.NewMessage(incoming=True, func=lambda e: e.is_private))
async def handler_private(event):
    if not event.raw_text or event.raw_text.strip() == "":
        return

    if await is_online():
        return

    is_girlfriend = (girlfriend_id is not None and event.sender_id == girlfriend_id)

    if is_girlfriend:
        animation = random.choice(GIRLFRIEND_ANIMATIONS)
    else:
        animation = random.choice(ANIMATIONS)

    msg = await event.respond(animation[0])
    for frame in animation[1:]:
        await asyncio.sleep(0.4)
        await msg.edit(frame)

    time_of_day, auto_reply = get_time_mood(is_girlfriend)

    if not is_girlfriend and random.random() < 0.25:
        await asyncio.sleep(0.3)
        await msg.edit(auto_reply)
        return

    try:
        response = ai.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=100,
            system=get_system_prompt(time_of_day, is_girlfriend),
            messages=[{"role": "user", "content": event.raw_text}]
        )
        await msg.edit(response.content[0].text)
    except Exception:
        await msg.edit(auto_reply)

# 👥 Упоминания в группах
@client.on(events.NewMessage(incoming=True, func=lambda e: not e.is_private))
async def handler_group(event):
    if not event.raw_text or event.raw_text.strip() == "":
        return

    if await is_online():
        return

    me = await client.get_me()
    mentioned = False

    if event.mentioned:
        mentioned = True
    elif me.username and f"@{me.username}" in event.raw_text:
        mentioned = True

    if not mentioned:
        return

    await asyncio.sleep(random.uniform(1, 3))

    try:
        response = ai.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=60,
            system=get_system_prompt(None, is_group=True),
            messages=[{"role": "user", "content": event.raw_text}]
        )
        await event.reply(response.content[0].text)
    except Exception:
        await event.reply(random.choice(GROUP_REPLIES))

async def main():
    global girlfriend_id
    await client.start()

    try:
        gf = await client.get_entity(GIRLFRIEND_PHONE)
        girlfriend_id = gf.id
        print(f"Девушка найдена ✅ ID: {girlfriend_id}")
    except Exception as e:
        print(f"Девушка не найдена ❌ {e}")

    print("Бот запущен! ✅")
    await client.run_until_disconnected()

asyncio.run(main())
