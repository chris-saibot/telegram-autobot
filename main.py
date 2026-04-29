import asyncio
import os
import random
from datetime import datetime
from PIL import Image
import io
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.tl.types import UserStatusOnline
from telethon.tl.functions.account import UpdateProfileRequest
from telethon.tl.functions.photos import UploadProfilePhotoRequest as PhotoUpload
import anthropic

API_ID = int(os.environ["API_ID"])
API_HASH = os.environ["API_HASH"]
ANTHROPIC_KEY = os.environ["ANTHROPIC_KEY"]
SESSION_STRING = os.environ["SESSION_STRING"]

client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)
ai = anthropic.Anthropic(api_key=ANTHROPIC_KEY)

GIRLFRIEND_PHONE = None
girlfriend_id = None
original_profile = {}
games = {}

ANIMATIONS = [
    ["🔥", "🔥🔥", "🔥🔥🔥", "💥", "✨"],
    ["⭐️", "🌟", "💫", "✨", "🌠"],
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

GROUP_REPLIES = [
    "Занят сейчас, позже отпишет",
    "Не в сети он, как появится — ответит",
    "Блин, занят. Позже напишет",
    "Сейчас недоступен, увидит позже",
]

def to_jpeg(data: bytes) -> io.BytesIO:
    img = Image.open(io.BytesIO(data))
    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="JPEG")
    buf.seek(0)
    return buf

def get_time_mood(is_girlfriend=False):
    hour = (datetime.now().hour + 5) % 24
    if is_girlfriend:
        if 6 <= hour < 11:
            return "morning", "Доброе утро солнышко ☀️❤️"
        elif 11 <= hour < 18:
            return "day", "Привет любимая ❤️"
        elif 18 <= hour < 23:
            return "evening", "Привет моя хорошая 🌸"
        else:
            return "night", "Сплю уже 😴❤️"
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
    if is_group:
        return """Ты — автоответчик человека в групповом чате Telegram.
Отвечай от третьего лица — говори "он занят", "он не в сети".
СТИЛЬ: коротко, 1 предложение, с заглавной буквы, без лишних эмодзи.
ПРИМЕРЫ: "Занят сейчас, позже отпишет" / "Не в сети, увидит позже"
"""
    else:
        base = """Ты — автоответчик реального человека в Telegram.
СТИЛЬ:
- С заглавной буквы
- Коротко — 1-2 предложения
- По-человечески, не как робот
- Иногда лёгкий мат типа "блин" — редко
- Скажи что не в сети, ответишь позже
- Без лишних эмодзи, максимум 1
"""
        if time_of_day == "night":
            base += "\n- Ночь, добавь что лёг спать"
        elif time_of_day == "morning":
            base += "\n- Утро, намекни что только проснулся"
        return base

async def is_online():
    try:
        me = await client.get_me()
        my_entity = await client.get_entity(me.id)
        return isinstance(my_entity.status, UserStatusOnline)
    except Exception:
        return False

# ============ ПОМОЩЬ ============

@client.on(events.NewMessage(outgoing=True, pattern=r'^\.help$'))
async def cmd_help(event):
    await event.delete()
    await client.send_message(event.chat_id, """🤖 **Команды бота:**

👤 **Профиль:**
`.имя Новое Имя` — сменить имя
`.био Текст` — сменить bio
`.фото` — ответь на фото чтобы поставить аватарку
`.копировать` — ответь на сообщение чтобы скопировать профиль
`.восстановить` — вернуть свой профиль обратно
`.я` — информация о себе

🎮 **Игры:**
`.игра` — угадай число (1-100)
`.г <число>` — сделать попытку
`.кубик` — бросить кубик
`.монета` — орёл или решка
`.шар вопрос` — магический шар

ℹ️ **Другое:**
`.ping` — проверить бота
`.help` — это меню
""")

# ============ ПРОФИЛЬ ============

@client.on(events.NewMessage(outgoing=True, pattern=r'^\.имя (.+)$'))
async def cmd_name(event):
    await event.delete()
    name_parts = event.pattern_match.group(1).split(None, 1)
    first = name_parts[0]
    last = name_parts[1] if len(name_parts) > 1 else ""
    await client(UpdateProfileRequest(first_name=first, last_name=last))
    await client.send_message(event.chat_id, f"✅ Имя изменено на **{first} {last}**")

@client.on(events.NewMessage(outgoing=True, pattern=r'^\.био (.+)$'))
async def cmd_bio(event):
    await event.delete()
    bio = event.pattern_match.group(1)
    await client(UpdateProfileRequest(about=bio))
    await client.send_message(event.chat_id, f"✅ Bio изменено на:\n_{bio}_")

@client.on(events.NewMessage(outgoing=True, pattern=r'^\.фото$'))
async def cmd_photo(event):
    await event.delete()
    reply = await event.get_reply_message()
    if not reply or not reply.photo:
        await client.send_message(event.chat_id, "❌ Ответь на фото командой .фото")
        return
    file = await reply.download_media(bytes)
    file = to_jpeg(file)  # конвертация в JPEG
    await client(PhotoUpload(file=await client.upload_file(file)))
    await client.send_message(event.chat_id, "✅ Фото профиля обновлено!")

@client.on(events.NewMessage(outgoing=True, pattern=r'^\.копировать$'))
async def cmd_copy_profile(event):
    await event.delete()
    reply = await event.get_reply_message()
    if not reply:
        await client.send_message(event.chat_id, "❌ Ответь на сообщение человека командой .копировать")
        return

    # Сохраняем свой оригинальный профиль
    me = await client.get_me()
    original_profile["first_name"] = me.first_name or ""
    original_profile["last_name"] = me.last_name or ""
    original_profile["about"] = gitattr(me, "about", "") or ""

    # Получаем профиль цели
    user = await reply.get_sender()

    # Меняем имя
    await client(UpdateProfileRequest(
        first_name=user.first_name or "",
        last_name=user.last_name or ""
    ))

    # Меняем фото если есть
    photos = await client.get_profile_photos(user.id)
    if photos:
        file = await client.download_media(photos[0], bytes)
        file = to_jpeg(file)  # конвертация в JPEG
        await client(PhotoUpload(file=await client.upload_file(file)))
        await client.send_message(event.chat_id, f"✅ Скопировал профиль **{user.first_name}**!\nИмя и фото изменены.\nДля возврата: `.восстановить`")
    else:
        await client.send_message(event.chat_id, f"✅ Скопировал имя **{user.first_name}**!\nФото у него нет.\nДля возврата: `.восстановить`")

@client.on(events.NewMessage(outgoing=True, pattern=r'^\.восстановить$'))
async def cmd_restore_profile(event):
    await event.delete()
    if not original_profile:
        await client.send_message(event.chat_id, "❌ Нечего восстанавливать — сначала используй .копировать")
        return

    await client(UpdateProfileRequest(
        first_name=original_profile.get("first_name", ""),
        last_name=original_profile.get("last_name", ""),
        about=original_profile.get("about", "")
    ))

    await client.send_message(event.chat_id, "✅ Имя и bio восстановлены!\n\n⚠️ Фото восстанови вручную через `.фото`")

@client.on(events.NewMessage(outgoing=True, pattern=r'^\.я$'))
async def cmd_me(event):
    await event.delete()
    me = await client.get_me()
    await client.send_message(event.chat_id, f"""👤 **Информация о тебе:**

🔹 Имя: {me.first_name or ''} {me.last_name or ''}
🔹 Username: @{me.username or 'нет'}
🔹 ID: `{me.id}`
🔹 Телефон: `{me.phone or 'скрыт'}`
""")

@client.on(events.NewMessage(outgoing=True, pattern=r'^\.ping$'))
async def cmd_ping(event):
    await event.delete()
    await client.send_message(event.chat_id, "🟢 Бот работает!")

# ============ ИГРЫ ============

@client.on(events.NewMessage(outgoing=True, pattern=r'^\.кубик$'))
async def cmd_dice(event):
    await event.delete()
    n = random.randint(1, 6)
    faces = {1:"1️⃣", 2:"2️⃣", 3:"3️⃣", 4:"4️⃣", 5:"5️⃣", 6:"6️⃣"}
    await client.send_message(event.chat_id, f"🎲 Выпало: {faces[n]} ({n})")

@client.on(events.NewMessage(outgoing=True, pattern=r'^\.монета$'))
async def cmd_coin(event):
    await event.delete()
    result = random.choice(["👑 Орёл!", "🪙 Решка!"])
    await client.send_message(event.chat_id, result)

@client.on(events.NewMessage(outgoing=True, pattern=r'^\.шар (.+)$'))
async def cmd_ball(event):
    await event.delete()
    question = event.pattern_match.group(1)
    answers = [
        "✅ Определённо да",
        "✅ Скорее всего да",
        "🌫 Туманно, спроси позже",
        "❌ Сомневаюсь",
        "❌ Определённо нет",
        "🔮 Звёзды говорят да",
        "💫 Всё возможно",
        "⚡️ Не рассчитывай на это",
    ]
    await client.send_message(event.chat_id, f"🎱 Вопрос: _{question}_\n\n{random.choice(answers)}")

@client.on(events.NewMessage(outgoing=True, pattern=r'^\.игра$'))
async def cmd_game_start(event):
    await event.delete()
    number = random.randint(1, 100)
    games[event.chat_id] = {"number": number, "attempts": 0}
    await client.send_message(event.chat_id, "🎮 **Угадай число от 1 до 100!**\nПиши `.г <число>` чтобы угадать\nНапример: `.г 50`")

@client.on(events.NewMessage(outgoing=True, pattern=r'^\.г (\d+)$'))
async def cmd_game_guess(event):
    await event.delete()
    chat_id = event.chat_id
    if chat_id not in games:
        await client.send_message(chat_id, "❌ Сначала начни игру: `.игра`")
        return
    guess = int(event.pattern_match.group(1))
    games[chat_id]["attempts"] += 1
    attempts = games[chat_id]["attempts"]
    number = games[chat_id]["number"]
    if guess < number:
        await client.send_message(chat_id, f"📈 Больше! (попытка {attempts})")
    elif guess > number:
        await client.send_message(chat_id, f"📉 Меньше! (попытка {attempts})")
    else:
        del games[chat_id]
        await client.send_message(chat_id, f"🎉 Угадал! Число было **{number}**\nПотрачено попыток: **{attempts}**")

# ============ АВТООТВЕТЫ ============

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
            model="claude-sonnet-4-20250514",
            max_tokens=100,
            system=get_system_prompt(time_of_day, is_girlfriend),
            messages=[{"role": "user", "content": event.raw_text}]
        )
        await msg.edit(response.content[0].text)
    except Exception:
        await msg.edit(auto_reply)

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

    if GIRLFRIEND_PHONE:
        try:
            gf = await client.get_entity(GIRLFRIEND_PHONE)
            girlfriend_id = gf.id
            print(f"Девушка найдена ✅ ID: {girlfriend_id}")
        except Exception as e:
            print(f"Девушка не найдена ❌ {e}")

    print("Бот запущен! ✅")
    await client.run_until_disconnected()

asyncio.run(main())
