import asyncio
import os
from telethon import TelegramClient, events
from telethon.sessions import StringSession
import anthropic

API_ID = int(os.environ["API_ID"])
API_HASH = os.environ["API_HASH"]
ANTHROPIC_KEY = os.environ["ANTHROPIC_KEY"]
SESSION_STRING = os.environ["SESSION_STRING"]

# Используем StringSession вместо файла
client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)
ai = anthropic.Anthropic(api_key=ANTHROPIC_KEY)

@client.on(events.NewMessage(incoming=True, func=lambda e: e.is_private))
async def handler(event):
    # Анимация
    msg = await event.respond("💤")
    frames = ["💤", "💤.", "💤..", "💤...", "🤖"]
    for frame in frames:
        await asyncio.sleep(0.4)
        await msg.edit(frame)

    # ИИ отвечает
    response = ai.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=300,
        system="Ты автоответчик пользователя Telegram. Отвечай коротко, по-дружески, как живой человек. Используй эмодзи. Скажи что хозяин не в сети и вернётся позже.",
        messages=[{"role": "user", "content": event.raw_text}]
    )

    await msg.edit(response.content[0].text)

async def main():
    await client.start()
    print("Бот запущен! ✅")
    await client.run_until_disconnected()

asyncio.run(main())
