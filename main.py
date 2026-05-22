import asyncio
import os
import random
import json
import urllib.parse
import urllib.request
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
SESSION_STRING = os.environ["SESSION_STRING"])

client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)
ai = anthropic.Anthropic(api_key=ANTHROPIC_KEY)

# ============ НАСТРОЙКИ ============

OWNER_INFO = """
Имя: Кристофер
Работа: Uzum (узум) — крупный маркетплейс в Узбекистане
Город: Ташкент, Узбекистан
Стиль общения: коротко, по делу, иногда "щас", "норм", "блин"
"""

GIRLFRIEND_PHONE = "+998901227646"
girlfriend_id = None
original_profile = {}
games = {}
invisible_mode = False
bot_mood = "normal"
blocked_users = set()

# Память разговоров: user_id -> list of {role, content}
conversation_memory = defaultdict(list)
MAX_MEMORY = 10  # последних сообщений на человека

# Сводка пропущенных: user_id -> list of messages
missed_messages = defaultdict(list)

ANIMATIONS = [
    ["🔥", "🔥🔥", "🔥🔥🔥", "💥", "✨"],
    ["⭐", "🌟", "💫", "✨", "🌠"],
    ["😴", "😴💤", "😴💤💤", "🛌💤", "🤖"],
    ["👻", "👻💀", "💀👻", "👻", "😱"],
]

BALL_ANSWERS = [
    "✅ Определённо да", "✅ Скорее всего да",
    "🌫️ Туманно, спроси позже", "❌ Сомневаюсь",
    "❌ Определённо нет", "🔮 Звёзды говорят да",
    "💫 Всё возможно", "⚡ Не рассчитывай на это",
    "🎯 Да, но осторожно", "🌙 Спроси ночью — тогда точнее",
]

GROUP_REPLIES = [
    "Занят, позже отпишет",
    "Не в сети он сейчас",
    "Щас недоступен, увидит позже",
]

def get_tashkent_hour():
    return (datetime.now(timezone.utc) + timedelta(hours=5)).hour

def get_time_context():
    hour = get_tashkent_hour()
    if 6 <= hour < 11:
        return "утро, Кристофер только проснулся"
    elif 11 <= hour < 18:
        return "день, Кристофер на работе в Uzum"
    elif 18 <= hour < 23:
        return "вечер, Кристофер отдыхает после работы"
    else:
        return "ночь, Кристофер спит"

def get_mood_context():
    return {
        "normal": "нейтральный, по-человечески",
        "evil": "немного раздражённый, можно лёгкий мат",
        "happy": "весёлый и позитивный",
        "sad": "грустный и вялый",
    }.get(bot_mood, "нейтральный")

def build_system_prompt(is_group=False):
    if is_group:
        return f"""Ты — ИИ-агент Кристофера в групповом чате Telegram.
{OWNER_INFO}
Отвечай от третьего лица — "он занят", "он не в сети".
Настроение: {get_mood_context()}
Коротко, 1 предложение, живо."""

    return f"""Ты — личный ИИ-агент Кристофера в Telegram. Ты отвечаешь вместо него.

О ХОЗЯИНЕ:
{OWNER_INFO}

ТЕКУЩИЙ КОНТЕКСТ: {get_time_context()}
НАСТРОЕНИЕ: {get_mood_context()}

ТВОИ ВОЗМОЖНОСТИ:
1. Отвечаешь на вопросы о Кристофере (кто он, где работает, когда будет)
2. Решаешь когда ответить по теме а когда сказать что занят
3. Помнишь контекст разговора с этим человеком
4. На срочные сообщения реагируешь сразу

ПРАВИЛА ОТВЕТОВ:
- Пиши от первого лица ("я занят", "напишу позже") — как будто это сам Кристофер
- С заглавной буквы, коротко 1-2 предложения
- Живо и естественно, иногда "щас", "норм", "блин"
- Без лишних эмодзи, максимум 1
- Если спрашивают о работе — говори что работаешь в Uzum в Ташкенте
- Если спрашивают когда будет — говори что освободится позже и напишет

ТИПЫ СООБЩЕНИЙ И КАК ОТВЕЧАТЬ:
- СРОЧНОЕ → сразу отвечай что увидел, постараешься ответить скорее
- ВОПРОС О КРИСТОФЕРЕ → отвечай по теме коротко
- ВОПРОС НА КОТОРЫЙ МОЖНО ОТВЕТИТЬ → ответь коротко
- ПРИВЕТ/МЕЛКИЙ РАЗГОВОР → скажи привет и что занят
- ОСТАЛЬНОЕ → скажи что занят, ответишь позже
"""

_online_cache = {"status": False, "updated": 0}

async def is_online():
    if invisible_mode:
        return False
    now = asyncio.get_event_loop().time()
    if now - _online_cache["updated"] < 10:
        return _online_cache["status"]
    try:
        me = await client.get_me()
        entity = await client.get_entity(me.id)
        _online_cache["status"] = isinstance(entity.status, UserStatusOnline)
        _online_cache["updated"] = now
        return _online_cache["status"]
    except Exception:
        return False

def add_to_memory(user_id, role, content):
    conversation_memory[user_id].append({"role": role, "content": content})
    if len(conversation_memory[user_id]) > MAX_MEMORY * 2:
        conversation_memory[user_id] = conversation_memory[user_id][-MAX_MEMORY * 2:]

def get_memory(user_id):
    return conversation_memory[user_id][-MAX_MEMORY:]

# ============ ПОМОЩЬ ============

@client.on(events.NewMessage(outgoing=True, pattern=r'^\.help$'))
async def cmd_help(event):
    await event.delete()
    await client.send_message(event.chat_id, """🤖 **Команды агента:**

👤 **Профиль:**
`.имя Новое Имя` — сменить имя
`.био Текст` — сменить bio
`.фото` — поставить фото (ответь на фото)
`.копировать` — скопировать чужой профиль
`.восстановить` — вернуть свой профиль
`.я` — информация о себе

🚫 **Стоп-лист:**
`.стоп` — бот не отвечает этому человеку
`.старт` — снять блокировку
`.стоплист` — список заблокированных

📋 **Сводка:**
`.сводка` — пропущенные сообщения
`.очистить` — очистить сводку

🌦️ **Погода:**
`.погода Ташкент` — погода в городе

📊 **Статистика:**
`.стат` — кто чаще пишет

⏰ **Напоминания:**
`.напомни 10 текст` — через N минут

🔒 **Режим:**
`.невидимка` — включить невидимку
`.видимка` — выключить невидимку
`.настроение злой/весёлый/грустный/норм`

🎮 **Игры (для всех):**
`.шар вопрос` — магический шар
`.игра` — угадай число
`.г <число>` — попытка
`.кубик` — кубик
`.монета` — орёл/решка

ℹ️ `.ping` — статус бота
""")

# ============ ПРОФИЛЬ ============

@client.on(events.NewMessage(outgoing=True, pattern=r'^\.имя (.+)$'))
async def cmd_name(event):
    await event.delete()
    parts = event.pattern_match.group(1).split(None, 1)
    first = parts[0]
    last = parts[1] if len(parts) > 1 else ""
    await client(UpdateProfileRequest(first_name=first, last_name=last))
    await client.send_message(event.chat_id, f"✅ Имя: **{first} {last}**")

@client.on(events.NewMessage(outgoing=True, pattern=r'^\.био (.+)$'))
async def cmd_bio(event):
    await event.delete()
    bio = event.pattern_match.group(1)
    await client(UpdateProfileRequest(about=bio))
    await client.send_message(event.chat_id, f"✅ Bio: _{bio}_")

@client.on(events.NewMessage(outgoing=True, pattern=r'^\.фото$'))
async def cmd_photo(event):
    await event.delete()
    reply = await event.get_reply_message()
    if not reply or not reply.photo:
        await client.send_message(event.chat_id, "❌ Ответь на фото")
        return
    try:
        file = await reply.download_media(bytes)
        uploaded = await client.upload_file(file, file_name="photo.jpg")
        await client(PhotoUpload(file=uploaded))
        await client.send_message(event.chat_id, "✅ Фото обновлено!")
    except Exception as e:
        await client.send_message(event.chat_id, f"❌ Ошибка: {e}")

@client.on(events.NewMessage(outgoing=True, pattern=r'^\.копировать$'))
async def cmd_copy(event):
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
        about = getattr(user_full.full_user, 'about', '') or ""
        if about:
            await client(UpdateProfileRequest(about=about))
        photos = await client.get_profile_photos(user.id)
        if photos:
            file = await client.download_media(photos[0], bytes)
            uploaded = await client.upload_file(file, file_name="photo.jpg")
            await client(PhotoUpload(file=uploaded))
        await client.send_message(event.chat_id, f"✅ Скопировал **{user.first_name}**!\nВернуть: `.восстановить`")
    except Exception as e:
        await client.send_message(event.chat_id, f"❌ Ошибка: {e}")

@client.on(events.NewMessage(outgoing=True, pattern=r'^\.восстановить$'))
async def cmd_restore(event):
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
        await client.send_message(event.chat_id, "✅ Профиль восстановлен!\n⚠️ Фото — через `.фото`")
    except Exception as e:
        await client.send_message(event.chat_id, f"❌ Ошибка: {e}")

@client.on(events.NewMessage(outgoing=True, pattern=r'^\.я$'))
async def cmd_me(event):
    await event.delete()
    try:
        me = await client.get_me()
        me_full = await client(GetFullUserRequest(me.id))
        bio = getattr(me_full.full_user, 'about', '') or 'нет'
        await client.send_message(event.chat_id, f"""👤 **Кристофер:**
🔹 Имя: {me.first_name or ''} {me.last_name or ''}
🔹 Username: @{me.username or 'нет'}
🔹 ID: `{me.id}`
🔹 Bio: {bio}
🔹 Работа: Uzum, Ташкент
""")
    except Exception as e:
        await client.send_message(event.chat_id, f"❌ Ошибка: {e}")

@client.on(events.NewMessage(outgoing=True, pattern=r'^\.ping$'))
async def cmd_ping(event):
    await event.delete()
    mood_labels = {"normal": "😐 Норм", "evil": "😠 Злой", "happy": "😄 Весёлый", "sad": "😢 Грустный"}
    invis = "🔒 Вкл" if invisible_mode else "🔓 Выкл"
    memory_count = sum(len(v) for v in conversation_memory.values())
    await client.send_message(event.chat_id, f"""🟢 Агент активен!
🎭 Настроение: {mood_labels.get(bot_mood, 'Норм')}
👁 Невидимка: {invis}
🧠 Диалогов в памяти: {len(conversation_memory)}
💬 Сообщений помню: {memory_count}
🚫 В стоп-листе: {len(blocked_users)}
📋 Пропущено: {sum(len(v) for v in missed_messages.values())}
""")

# ============ СТОП-ЛИСТ ============

@client.on(events.NewMessage(outgoing=True, pattern=r'^\.стоп$'))
async def cmd_block(event):
    await event.delete()
    reply = await event.get_reply_message()
    if not reply:
        await client.send_message(event.chat_id, "❌ Ответь на сообщение человека")
        return
    user = await reply.get_sender()
    blocked_users.add(user.id)
    name = getattr(user, 'first_name', 'Пользователь')
    await client.send_message(event.chat_id, f"🚫 **{name}** в стоп-листе\nСнять: `.старт`")

@client.on(events.NewMessage(outgoing=True, pattern=r'^\.старт$'))
async def cmd_unblock(event):
    await event.delete()
    reply = await event.get_reply_message()
    if not reply:
        await client.send_message(event.chat_id, "❌ Ответь на сообщение человека")
        return
    user = await reply.get_sender()
    blocked_users.discard(user.id)
    name = getattr(user, 'first_name', 'Пользователь')
    await client.send_message(event.chat_id, f"✅ **{name}** убран из стоп-листа")

@client.on(events.NewMessage(outgoing=True, pattern=r'^\.стоплист$'))
async def cmd_blocklist(event):
    await event.delete()
    if not blocked_users:
        await client.send_message(event.chat_id, "📋 Стоп-лист пустой")
        return
    text = "🚫 **Стоп-лист:**\n\n"
    for uid in blocked_users:
        try:
            user = await client.get_entity(uid)
            name = getattr(user, 'first_name', 'Неизвестный')
            username = f"@{user.username}" if getattr(user, 'username', None) else ""
            text += f"• {name} {username}\n"
        except Exception:
            text += f"• ID: {uid}\n"
    await client.send_message(event.chat_id, text)

# ============ СВОДКА ============

@client.on(events.NewMessage(outgoing=True, pattern=r'^\.сводка$'))
async def cmd_summary(event):
    await event.delete()
    if not any(missed_messages.values()):
        await client.send_message(event.chat_id, "📋 Пропущенных сообщений нет")
        return

    text = "📋 **Пропущенные сообщения:**\n\n"
    for user_id, messages in missed_messages.items():
        if not messages:
            continue
        try:
            user = await client.get_entity(user_id)
            name = getattr(user, 'first_name', 'Неизвестный')
            username = f"@{user.username}" if getattr(user, 'username', None) else ""
            text += f"👤 **{name}** {username} ({len(messages)} сообщ.):\n"
            for m in messages[-3:]:
                text += f"  • _{m[:50]}{'...' if len(m) > 50 else ''}_\n"
            text += "\n"
        except Exception:
            pass

    # ИИ делает краткую сводку
    try:
        all_msgs = []
        for uid, msgs in missed_messages.items():
            all_msgs.extend(msgs)
        if all_msgs:
            summary = ai.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=150,
                system="Сделай краткую сводку пропущенных сообщений в 2-3 предложениях. На русском, коротко.",
                messages=[{"role": "user", "content": "\n".join(all_msgs)}]
            )
            text += f"\n🧠 **Итог:** {summary.content[0].text}"
    except Exception:
        pass

    await client.send_message(event.chat_id, text)

@client.on(events.NewMessage(outgoing=True, pattern=r'^\.очистить$'))
async def cmd_clear(event):
    await event.delete()
    missed_messages.clear()
    await client.send_message(event.chat_id, "✅ Сводка очищена")

# ============ ПОГОДА ============

@client.on(events.NewMessage(outgoing=True, pattern=r'^\.погода (.+)$'))
async def cmd_weather(event):
    await event.delete()
    city = event.pattern_match.group(1)
    try:
        url = f"https://wttr.in/{urllib.parse.quote(city)}?format=j1&lang=ru"
        with urllib.request.urlopen(url, timeout=5) as r:
            data = json.loads(r.read())
        cur = data["current_condition"][0]
        await client.send_message(event.chat_id, f"""🌦️ **Погода в {city}:**
🌡️ {cur['temp_C']}°C (ощущается {cur['FeelsLikeC']}°C)
☁️ {cur['lang_ru'][0]['value']}
💨 Ветер: {cur['windspeedKmph']} км/ч
💧 Влажность: {cur['humidity']}%
""")
    except Exception:
        await client.send_message(event.chat_id, f"❌ Не удалось получить погоду для **{city}**")

# ============ СТАТИСТИКА ============

stats = defaultdict(lambda: defaultdict(int))

@client.on(events.NewMessage(incoming=True))
async def track_messages(event):
    if event.sender_id:
        stats[event.chat_id][event.sender_id] += 1

@client.on(events.NewMessage(outgoing=True, pattern=r'^\.стат$'))
async def cmd_stats(event):
    await event.delete()
    chat_id = event.chat_id
    if not stats[chat_id]:
        await client.send_message(chat_id, "📊 Статистика пустая")
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
            pass
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
    await client.send_message(event.chat_id, "🔒 Невидимка **включена**\nВыключить: `.видимка`")

@client.on(events.NewMessage(outgoing=True, pattern=r'^\.видимка$'))
async def cmd_invisible_off(event):
    global invisible_mode
    await event.delete()
    invisible_mode = False
    await client.send_message(event.chat_id, "🔓 Невидимка **выключена**")

# ============ НАСТРОЕНИЕ ============

@client.on(events.NewMessage(outgoing=True, pattern=r'^\.настроение (.+)$'))
async def cmd_mood(event):
    global bot_mood
    await event.delete()
    mood_input = event.pattern_match.group(1).lower().strip()
    moods = {
        "злой": "evil", "весёлый": "happy", "веселый": "happy",
        "грустный": "sad", "норм": "normal", "обычный": "normal",
    }
    if mood_input not in moods:
        await client.send_message(event.chat_id, "❌ Доступные: `злой`, `весёлый`, `грустный`, `норм`")
        return
    bot_mood = moods[mood_input]
    labels = {"evil": "😠 Злой", "happy": "😄 Весёлый", "sad": "😢 Грустный", "normal": "😐 Обычный"}
    await client.send_message(event.chat_id, f"🎭 Настроение: **{labels[bot_mood]}**")

# ============ ИГРЫ ============

@client.on(events.NewMessage(outgoing=True, pattern=r'^\.кубик$'))
async def cmd_dice(event):
    await event.delete()
    n = random.randint(1, 6)
    faces = {1:"1️⃣",2:"2️⃣",3:"3️⃣",4:"4️⃣",5:"5️⃣",6:"6️⃣"}
    await client.send_message(event.chat_id, f"🎲 Выпало: {faces[n]} ({n})")

@client.on(events.NewMessage(outgoing=True, pattern=r'^\.монета$'))
async def cmd_coin(event):
    await event.delete()
    await client.send_message(event.chat_id, random.choice(["👑 Орёл!", "🪙 Решка!"]))

@client.on(events.NewMessage(outgoing=True, pattern=r'^\.шар (.+)$'))
async def cmd_ball_out(event):
    await event.delete()
    q = event.pattern_match.group(1)
    await client.send_message(event.chat_id, f"🎱 _{q}_\n\n{random.choice(BALL_ANSWERS)}")

@client.on(events.NewMessage(incoming=True, pattern=r'^\.шар (.+)$'))
async def cmd_ball_in(event):
    q = event.pattern_match.group(1)
    await asyncio.sleep(random.uniform(0.5, 1.5))
    await event.reply(f"🎱 _{q}_\n\n{random.choice(BALL_ANSWERS)}")

@client.on(events.NewMessage(outgoing=True, pattern=r'^\.игра$'))
async def cmd_game_start(event):
    await event.delete()
    games[event.chat_id] = {"number": random.randint(1, 100), "attempts": 0}
    await client.send_message(event.chat_id, "🎮 **Угадай число от 1 до 100!**\nПиши `.г <число>`")

@client.on(events.NewMessage(pattern=r'^\.г (\d+)$'))
async def cmd_game_guess(event):
    if event.out:
        await event.delete()
    chat_id = event.chat_id
    if chat_id not in games:
        if event.out:
            await client.send_message(chat_id, "❌ Начни игру: `.игра`")
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
        await event.reply(f"🎉 {name} угадал! Было **{number}**, попыток: **{attempts}**")

# ============ УМНЫЙ ИИ-АГЕНТ ============

@client.on(events.NewMessage(incoming=True, func=lambda e: e.is_private))
async def handler_private(event):
    if not event.raw_text or event.raw_text.strip() == "":
        return
    if event.raw_text.startswith(".шар") or event.raw_text.startswith(".г"):
        return
    if girlfriend_id is not None and event.sender_id == girlfriend_id:
        return
    if event.sender_id in blocked_users:
        return
    if await is_online():
        return

    user_id = event.sender_id

    # Сохраняем в сводку пропущенных
    missed_messages[user_id].append(event.raw_text)

    # Анимация
    animation = random.choice(ANIMATIONS)
    msg = await event.respond(animation[0])
    for frame in animation[1:]:
        await asyncio.sleep(0.4)
        await msg.edit(frame)

    # Добавляем сообщение в память
    add_to_memory(user_id, "user", event.raw_text)

    # Строим историю для ИИ
    history = get_memory(user_id)

    try:
        response = ai.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=150,
            system=build_system_prompt(),
            messages=history
        )
        reply_text = response.content[0].text

        # Сохраняем ответ в память
        add_to_memory(user_id, "assistant", reply_text)

        await msg.edit(reply_text)

    except Exception:
        fallback = "Занят щас, позже напишу"
        await msg.edit(fallback)

@client.on(events.NewMessage(incoming=True, func=lambda e: not e.is_private))
async def handler_group(event):
    if not event.raw_text or event.raw_text.strip() == "":
        return
    if event.raw_text.startswith(".шар") or event.raw_text.startswith(".г"):
        return
    if await is_online():
        return

    me = await client.get_me()
    mentioned = event.mentioned or (me.username and f"@{me.username}" in event.raw_text)
    if not mentioned:
        return

    await asyncio.sleep(random.uniform(1, 3))

    try:
        response = ai.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=60,
            system=build_system_prompt(is_group=True),
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

    print("Агент запущен! ✅")
    await client.run_until_disconnected()

asyncio.run(main())
