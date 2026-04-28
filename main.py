import asyncio
import os
import random
from datetime import datetime
from telethon import TelegramClient, events
from telethon.sessions import StringSession
import anthropic

API_ID = int(os.environ["API_ID"])
API_HASH = os.environ["API_HASH"]
ANTHROPIC_KEY = os.environ["ANTHROPIC_KEY"]
SESSION_STRING = os.environ["SESSION_STRING"]

client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)
ai = anthropic.Anthropic(api_key=ANTHROPIC_KEY)

# 🎭 Разные анимации
ANIMATIONS = [
    ["🌑", "🌒", "🌓", "🌔", "🌕", "🌖", "🌗", "🌘", "🌑"],
    ["🔥", "🔥🔥", "🔥🔥🔥", "💥", "✨"],
    ["⭐", "🌟", "💫", "✨", "🌠"],
    ["😴", "😴💤", "😴💤💤", "🛌💤", "🤖"],
    ["👻", "👻💀", "💀👻", "👻", "😱"],
    ["🌍", "🌎", "🌏", "🌍", "🌐"],
]

# ⏰ Смешные ответы по времени суток (UTC+5 — Ташкент)
FUNNY_MORNING = [
    "☀️ Хозяин ещё не проснулся, звони в дверь громче!",
    "🥱 Слишком рано... он спит как медведь",
    "☕ Без кофе не отвечает. Я пробовал.",
]

FUNNY_DAY = [
    "🏃 Убежал куда-то, вернётся скоро!",
    "🎮 Скорее всего играет и делает вид что не видит",
    "📵 Телефон в кармане, карман в штанах, штаны где-то там",
    "🌀 Завис как Windows 98, перезагрузка скоро",
]

FUNNY_EVENING = [
    "🌆 Ужинает, мешать не советую",
    "📺 Смотрит сериал и притворяется занятым",
    "🛋️ Лежит на диване в режиме 'не трогать'",
]

FUNNY_NIGHT = [
    "🌙 Спит без задних ног... или не спит 👀",
    "👻 Тссс... ночь. Тут водятся призраки 👻💀",
    "🦇 В этот час хозяин превращается в летучую мышь",
    "😈 3 часа ночи... ты уверен что хочешь писать?",
    "🌑 Темно. Тихо. Хозяин исчез в ночи...",
]

def get_time_mood():
    """Возвращает время суток по Ташкенту (UTC+5)"""
    hour = (datetime.utcnow().hour + 5) % 24
    if 6 <= hour < 11:
        return "morning", random.choice(FUNNY_MORNING)
    elif 11 <= hour < 18:
        return "day", random.choice(FUNNY_DAY)
    elif 18 <= hour < 23:
        return "evening", random.choice(FUNNY_EVENING)
    else:
        return "night", random.choice(FUNNY_NIGHT)

def get_system_prompt(time_of_day):
    """Системный промпт зависит от времени"""
    base = "Ты автоответчик пользователя Telegram. Отвечай коротко, по-дружески, как живой человек."
    if time_of_day == "night":
        return base + " Сейчас ночь — отвечай таинственно и немного страшно, используй 👻🌑💀. Намекни что хозяин может и не спать..."
    elif time_of_day == "morning":
        return base + " Сейчас утро — хозяин только просыпается, отвечай сонно и лениво 😴☕"
    elif time_of_day == "evening":
        return base + " Сейчас вечер — хозяин отдыхает, отвечай расслабленно 🌆"
    else:
        return base + " Хозяин занят днём, отвечай бодро и с юмором 😄"

@client.on(events.NewMessage(incoming=True, func=lambda e: e.is_private))
async def handler(event):
    if not event.raw_text or event.raw_text.strip() == "":
        return

    # Случайная анимация
    animation = random.choice(ANIMATIONS)
    msg = await event.respond(animation[0])
    for frame in animation[1:]:
        await asyncio.sleep(0.4)
        await msg.edit(frame)

    # Определяем время суток
    time_of_day, funny_reply = get_time_mood()

    # 30% шанс — смешной автоответ без ИИ
    if random.random() < 0.3:
        await asyncio.sleep(0.5)
        await msg.edit(funny_reply)
        return

    # 70% — ИИ отвечает с учётом времени
    try:
        response = ai.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=300,
            system=get_system_prompt(time_of_day),
            messages=[{"role": "user", "content": event.raw_text}]
        )
        final = response.content[0].text
        # Иногда добавляем смешной комментарий в конце
        if random.random() < 0.4:
            final += f"\n\n{funny_reply}"
        await msg.edit(final)
    except Exception as e:
        await msg.edit(funny_reply)

async def main():
    await client.start()
    print("Бот запущен! ✅")
    await client.run_until_disconnected()

asyncio.run(main())
