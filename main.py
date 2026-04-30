import asyncio
import os
import random
import re
from datetime import datetime, timezone, timedelta
from collections import defaultdict
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.tl.types import UserStatusOnline
from telethon.tl.functions.account import UpdateProfileRequest, UpdateStatusRequest
from telethon.tl.functions.photos import UploadProfilePhotoRequest as PhotoUpload
from telethon.tl.functions.users import GetFullUserRequest
import anthropic

API_ID = int(os.environ["API_ID"])
API_HASH = os.environ["API_HASH"]
ANTHROPIC_KEY = os.environ["ANTHROPIC_KEY"]
SESSION_STRING = os.environ["SESSION_STRING"]

client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)
ai = anthropic.Anthropic(api_key=ANTHROPIC_KEY)

GIRLFRIEND_PHONE = "+998901227646"
girlfriend_id = None
original_profile = {}
games = {}
stats = defaultdict(lambda: defaultdict(int))  # chat_id -> user_id -> count
invisible_mode = False
bot_mood = "normal"  # normal / evil / happy / sad

ANIMATIONS = [
    ["🔥", "🔥🔥", "🔥🔥🔥", "💥", "✨"],
    ["⭐", "🌟", "💫", "✨", "🌠"],
    ["😴", "😴💤", "😴💤💤", "🛌💤", "🤖"],
    ["👻", "👻💀", "💀👻", "👻", "😱"],
]

FUNNY_MORNING = [
    "Ааа, рано ещё... позже напишу",
    "Сплю пока, не трогай 😴",
    "Без кофе не соображаю, позже",
    "Только встал, дай прийти в себя",
]
FUNNY_DAY = [
    "Занят щас, позже отпишу",
    "Не могу, позже",
    "Блин, занят. Отвечу как смогу",
    "Щас не до этого, позже гляну",
    "Занят, не теряй — отвечу",
]
FUNNY_EVENING = [
    "Отдыхаю, позже напишу",
    "Вечер, устал немного. Позже",
    "Щас занят, отпишу чуть позже",
]
FUNNY_NIGHT = [
    "Лёг уже, завтра отвечу",
    "Ночь же, сплю 😴",
    "Завтра напишу, уже сплю",
    "Поздно уже... завтра",
]

GROUP_REPLIES = [
    "Занят, позже отпишет",
    "Не в сети он сейчас",
    "Занят он, увидит позже",
    "Щас недоступен, позже ответит",
]

BALL_ANSWERS = [
    "✅ Определённо да",
    "✅ Скорее всего да",
    "🌫️ Туманно, спроси позже",
    "❌ Сомневаюсь",
    "❌ Определённо нет",
    "🔮 Звёзды говорят да",
    "💫 Всё возможно",
    "⚡ Не рассчитывай на это",
    "🎯 Да, но осторожно",
    "🌙 Спроси ночью — тогда точнее",
]

def get_tashkent_hour():
    return (datetime.now(timezone.utc) + timedelta(hours=5)).hour

def get_time_mood():
    hour = get_tashkent_hour()
    if 6 <= hour < 11:
        return "morning", random.choice(FUNNY_MORNING)
    elif 11 <= hour < 18:
        return "day", random.choice(FUNNY_DAY)
    elif 18 <= hour < 23:
        return "evening", random.choice(FUNNY_EVENING)
    else:
        return "night", random.choice(FUNNY_NIGHT)

def get_system_prompt(time_of_day, is_group=False):
    global bot_mood

    mood_ctx = {
        "normal": "Отвечай нейтрально и по-человечески",
        "evil": "Отвечай немного грубо и раздражённо, как будто тебя отвлекли от важного дела. Можно лёгкий мат",
        "happy": "Отвечай весело и позитивно, можно с юмором и эмодзи",
        "sad": "Отвечай грустно и вяло, как будто что-то случилось",
    }.get(bot_mood, "Отвечай нейтрально")

    if is_group:
        return f"""Ты — автоответчик человека в групповом чате Telegram.
Отвечай от третьего лица — "он занят", "он не в сети".
НАСТРОЕНИЕ: {mood_ctx}
СТИЛЬ: коротко, 1 предложение, живо, без лишних эмодзи.
"""
    hour = get_tashkent_hour()
    if 6 <= hour < 11:
        time_ctx = "Сейчас утро, человек только проснулся"
    elif 11 <= hour < 18:
        time_ctx = "Сейчас день, человек занят делами"
    elif 18 <= hour < 23:
        time_ctx = "Сейчас вечер, человек отдыхает"
    else:
        time_ctx = "Сейчас ночь, человек спит"

    return f"""Ты — автоответчик реального живого человека в Telegram.

КОНТЕКСТ: {time_ctx}
НАСТРОЕНИЕ: {mood_ctx}

ПРАВИЛА:
- Всегда с заглавной буквы
- Максимум 1-2 предложения
- Живо и естественно
- Иногда: "щас", "норм", "оч", "неа", "ага"
- Скажи что занят / не в сети / отвечу позже
- Без шаблонов типа "я недоступен"
- Без лишних эмодзи, максимум 1

ХОРОШИЕ ПРИМЕРЫ:
"Занят щас, позже напишу"
"Блин, не могу сейчас. Позже"
"Щас не могу, позже гляну"
"""

_online_cache = {"status": False, "updated": 0}

async def is_online():
    global invisible_mode
    if invisible_mode:
        return False
    now = asyncio.get_event_loop().time()
    if now - _online_cache["updated"] < 10:
        return _online_cache["status"]
    try:
        me = await client.get_me()
        my_entity = await client.get_entity(me.id)
        _online_cache["status"] = isinstance(my_entity.status, UserStatusOnline)
        _online_cache["updated"] = now
        return _online_cache["status"]
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
`.копировать` — скопировать чужой профиль
`.восстановить` — вернуть свой профиль
`.я` — информация о себе

🎮 **Игры:**
`.игра` — угадай число (1-100)
`.г <число>` — сделать попытку
`.кубик` — бросить кубик
`.монета` — орёл или решка
`.шар вопрос` — магический шар

🌦️ **Погода:**
`.погода Ташкент` — погода в городе

📊 **Статистика:**
`.стат` — кто чаще пишет в этом чате

⏰ **Напоминания:**
`.напомни 10 текст` — напомнить через N минут

🔒 **Режим:**
`.невидимка` — включить невидимку (бот отвечает всем)
`.видимка` — выключить невидимку
`.настроение злой` — сменить настроение бота
`.настроение весёлый` — весёлый режим
`.настроение грустный` — грустный режим
`.настроение норм` — обычный режим

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
    try:
        file = await reply.download_media(bytes)
        uploaded = await client.upload_file(file, file_name="photo.jpg")
        await client(PhotoUpload(file=uploaded))
        await client.send_message(event.chat_id, "✅ Фото профиля обновлено!")
    except Exception as e:
        await client.send_message(event.chat_id, f"❌ Ошибка: {e}")

@client.on(events.NewMessage(outgoing=True, pattern=r'^\.копировать$'))
async def cmd_copy_profile(event):
    await event.delete()
    reply = await event.get_reply_message()
    if not reply:
        await client.send_message(event.chat_id, "❌ Ответь на сообщение человека")
        return
    try:
        me = await client.get_me()
        my_full = await client(GetFullUserRequest(me.id))
        original_profile["first_name"] = getattr(me, 'first_name', '') or ""
        original_profile["last_name"] = getattr(me, 'last_name', '') or ""
        original_profile["about"] = getattr(my_full.full_user, 'about', '') or ""

        user = await reply.get_sender()
        user_full = await client(GetFullUserRequest(user.id))

        await client(UpdateProfileRequest(
            first_name=getattr(user, 'first_name', '') or "",
            last_name=getattr(user, 'last_name', '') or ""
        ))

        user_about = getattr(user_full.full_user, 'about', '') or ""
        if user_about:
            await client(UpdateProfileRequest(about=user_about))

        photos = await client.get_profile_photos(user.id)
        if photos:
            file = await client.download_media(photos[0], bytes)
            uploaded = await client.upload_file(file, file_name="photo.jpg")
            await client(PhotoUpload(file=uploaded))
            await client.send_message(event.chat_id, f"✅ Скопировал профиль **{user.first_name}**!\nДля возврата: `.восстановить`")
        else:
            await client.send_message(event.chat_id, f"✅ Скопировал профиль **{user.first_name}**!\nДля возврата: `.восстановить`")
    except Exception as e:
        await client.send_message(event.chat_id, f"❌ Ошибка: {e}")

@client.on(events.NewMessage(outgoing=True, pattern=r'^\.восстановить$'))
async def cmd_restore_profile(event):
    await event.delete()
    if not original_profile:
        await client.send_message(event.chat_id, "❌ Нечего восстанавливать")
        return
    try:
        await client(UpdateProfileRequest(
            first_name=original_profile.get("first_name", ""),
            last_name=original_profile.get("last_name", ""),
            about=original_profile.get("about", "")
        ))
        await client.send_message(event.chat_id, "✅ Профиль восстановлен!\n⚠️ Фото восстанови через `.фото`")
    except Exception as e:
        await client.send_message(event.chat_id, f"❌ Ошибка: {e}")

@client.on(events.NewMessage(outgoing=True, pattern=r'^\.я$'))
async def cmd_me(event):
    await event.delete()
    try:
        me = await client.get_me()
        me_full = await client(GetFullUserRequest(me.id))
        bio = getattr(me_full.full_user, 'about', '') or 'нет'
        await client.send_message(event.chat_id, f"""👤 **Информация о тебе:**

🔹 Имя: {me.first_name or ''} {me.last_name or ''}
🔹 Username: @{me.username or 'нет'}
🔹 ID: `{me.id}`
🔹 Bio: {bio}
🔹 Телефон: `{me.phone or 'скрыт'}`
""")
    except Exception as e:
        await client.send_message(event.chat_id, f"❌ Ошибка: {e}")

@client.on(events.NewMessage(outgoing=True, pattern=r'^\.ping$'))
async def cmd_ping(event):
    await event.delete()
    mood_labels = {"normal": "😐 Норм", "evil": "😠 Злой", "happy": "😄 Весёлый", "sad": "😢 Грустный"}
    invis = "🔒 Вкл" if invisible_mode else "🔓 Выкл"
    await client.send_message(event.chat_id, f"🟢 Бот работает!\n🎭 Настроение: {mood_labels.get(bot_mood, 'Норм')}\n👁 Невидимка: {invis}")

# ============ ПОГОДА ============

@client.on(events.NewMessage(outgoing=True, pattern=r'^\.погода (.+)$'))
async def cmd_weather(event):
    await event.delete()
    city = event.pattern_match.group(1)
    try:
        import urllib.request
        import json
        url = f"https://wttr.in/{urllib.parse.quote(city)}?format=j1&lang=ru"
        with urllib.request.urlopen(url, timeout=5) as r:
            data = json.loads(r.read())
        current = data["current_condition"][0]
        temp = current["temp_C"]
        feels = current["FeelsLikeC"]
        desc = current["lang_ru"][0]["value"]
        wind = current["windspeedKmph"]
        humidity = current["humidity"]
        await client.send_message(event.chat_id, f"""🌦️ **Погода в {city}:**

🌡️ Температура: **{temp}°C** (ощущается {feels}°C)
☁️ {desc}
💨 Ветер: {wind} км/ч
💧 Влажность: {humidity}%
""")
    except Exception as e:
        await client.send_message(event.chat_id, f"❌ Не удалось получить погоду для **{city}**\nПроверь название города")

# ============ СТАТИСТИКА ============

@client.on(events.NewMessage(incoming=True))
async def track_messages(event):
    if event.sender_id:
        stats[event.chat_id][event.sender_id] += 1

@client.on(events.NewMessage(outgoing=True, pattern=r'^\.стат$'))
async def cmd_stats(event):
    await event.delete()
    chat_id = event.chat_id
    if not stats[chat_id]:
        await client.send_message(chat_id, "📊 Статистика пока пустая — никто не писал с момента запуска бота")
        return
    sorted_users = sorted(stats[chat_id].items(), key=lambda x: x[1], reverse=True)[:10]
    text = "📊 **Кто чаще пишет:**\n\n"
    medals = ["🥇", "🥈", "🥉"]
    for i, (user_id, count) in enumerate(sorted_users):
        try:
            user = await client.get_entity(user_id)
            name = getattr(user, 'first_name', 'Неизвестный') or 'Неизвестный'
            username = f"@{user.username}" if getattr(user, 'username', None) else ""
            medal = medals[i] if i < 3 else f"{i+1}."
            text += f"{medal} {name} {username} — **{count}** сообщ.\n"
        except Exception:
            text += f"{i+1}. Неизвестный — **{count}** сообщ.\n"
    await client.send_message(chat_id, text)

# ============ НАПОМИНАНИЯ ============

@client.on(events.NewMessage(outgoing=True, pattern=r'^\.напомни (\d+) (.+)$'))
async def cmd_remind(event):
    await event.delete()
    minutes = int(event.pattern_match.group(1))
    text = event.pattern_match.group(2)
    chat_id = event.chat_id
    await client.send_message(chat_id, f"⏰ Напомню через **{minutes} мин:** _{text}_")

    async def remind():
        await asyncio.sleep(minutes * 60)
        await client.send_message(chat_id, f"⏰ **Напоминание!**\n\n{text}")

    asyncio.create_task(remind())

# ============ НЕВИДИМКА ============

@client.on(events.NewMessage(outgoing=True, pattern=r'^\.невидимка$'))
async def cmd_invisible_on(event):
    global invisible_mode
    await event.delete()
    invisible_mode = True
    try:
        await client(UpdateStatusRequest(offline=True))
    except Exception:
        pass
    await client.send_message(event.chat_id, "🔒 Невидимка **включена** — бот будет отвечать за тебя\nВыключить: `.видимка`")

@client.on(events.NewMessage(outgoing=True, pattern=r'^\.видимка$'))
async def cmd_invisible_off(event):
    global invisible_mode
    await event.delete()
    invisible_mode = False
    await client.send_message(event.chat_id, "🔓 Невидимка **выключена** — теперь ты онлайн")

# ============ НАСТРОЕНИЕ ============

@client.on(events.NewMessage(outgoing=True, pattern=r'^\.настроение (.+)$'))
async def cmd_mood(event):
    global bot_mood
    await event.delete()
    mood_input = event.pattern_match.group(1).lower().strip()
    moods = {
        "злой": "evil",
        "evil": "evil",
        "весёлый": "happy",
        "веселый": "happy",
        "happy": "happy",
        "грустный": "sad",
        "sad": "sad",
        "норм": "normal",
        "normal": "normal",
        "обычный": "normal",
    }
    if mood_input not in moods:
        await client.send_message(event.chat_id, "❌ Доступные настроения: `злой`, `весёлый`, `грустный`, `норм`")
        return
    bot_mood = moods[mood_input]
    labels = {"evil": "😠 Злой", "happy": "😄 Весёлый", "sad": "😢 Грустный", "normal": "😐 Обычный"}
    await client.send_message(event.chat_id, f"🎭 Настроение бота: **{labels[bot_mood]}**")

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
async def cmd_ball_out(event):
    await event.delete()
    question = event.pattern_match.group(1)
    await client.send_message(event.chat_id, f"🎱 Вопрос: _{question}_\n\n{random.choice(BALL_ANSWERS)}")

@client.on(events.NewMessage(incoming=True, pattern=r'^\.шар (.+)$'))
async def cmd_ball_in(event):
    question = event.pattern_match.group(1)
    await asyncio.sleep(random.uniform(0.5, 1.5))
    await event.reply(f"🎱 Вопрос: _{question}_\n\n{random.choice(BALL_ANSWERS)}")

@client.on(events.NewMessage(outgoing=True, pattern=r'^\.игра$'))
async def cmd_game_start(event):
    await event.delete()
    number = random.randint(1, 100)
    games[event.chat_id] = {"number": number, "attempts": 0}
    await client.send_message(event.chat_id, "🎮 **Угадай число от 1 до 100!**\nПиши `.г <число>`\nНапример: `.г 50`")

@client.on(events.NewMessage(pattern=r'^\.г (\d+)$'))
async def cmd_game_guess(event):
    if event.out:
        await event.delete()
    chat_id = event.chat_id
    if chat_id not in games:
        if event.out:
            await client.send_message(chat_id, "❌ Сначала начни игру: `.игра`")
        return
    guess = int(event.pattern_match.group(1))
    games[chat_id]["attempts"] += 1
    attempts = games[chat_id]["attempts"]
    number = games[chat_id]["number"]
    sender = await event.get_sender()
    name = getattr(sender, 'first_name', 'Игрок') or 'Игрок'
    if guess < number:
        await event.reply(f"📈 Больше, {name}! (попытка {attempts})")
    elif guess > number:
        await event.reply(f"📉 Меньше, {name}! (попытка {attempts})")
    else:
        del games[chat_id]
        await event.reply(f"🎉 {name} угадал! Число было **{number}**\nПопыток: **{attempts}**")

# ============ АВТООТВЕТЫ ============

@client.on(events.NewMessage(incoming=True, func=lambda e: e.is_private))
async def handler_private(event):
    if not event.raw_text or event.raw_text.strip() == "":
        return
    if event.raw_text.startswith(".шар") or event.raw_text.startswith(".г"):
        return
    if girlfriend_id is not None and event.sender_id == girlfriend_id:
        return
    if await is_online():
        return

    animation = random.choice(ANIMATIONS)
    msg = await event.respond(animation[0])
    for frame in animation[1:]:
        await asyncio.sleep(0.4)
        await msg.edit(frame)

    time_of_day, auto_reply = get_time_mood()

    if random.random() < 0.25:
        await asyncio.sleep(0.3)
        await msg.edit(auto_reply)
        return

    try:
        response = ai.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=100,
            system=get_system_prompt(time_of_day),
            messages=[{"role": "user", "content": event.raw_text}]
        )
        await msg.edit(response.content[0].text)
    except Exception:
        await msg.edit(auto_reply)

@client.on(events.NewMessage(incoming=True, func=lambda e: not e.is_private))
async def handler_group(event):
    if not event.raw_text or event.raw_text.strip() == "":
        return
    if event.raw_text.startswith(".шар") or event.raw_text.startswith(".г"):
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
            model="claude-sonnet-4-6",
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

import urllib.parse
asyncio.run(main())
