import asyncio
import os
import time
from threading import Thread
import streamlit as st
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart
from answer_module import SkyAnswers

BOT_TOKEN = os.getenv("BOT_TOKEN", "8233085354:AAGXZ1GPyiDVW-wG3_Yj_DP_cuahx9PFrsw")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Telegram обработчики
@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    await message.answer(
        "<b>🔵 Skysmart Answers</b>\n\n"
        "Отправь ссылку на задание Skysmart.\n\n"
        "<i>Сделано @unreaskn</i>",
        parse_mode="HTML"
    )

@dp.message()
async def tg_handle(message: types.Message):
    text = message.text.strip()
    if not text.startswith("https://edu.skysmart.ru/student/"):
        await message.answer("❌ Неверная ссылка")
        return
    task_hash = text.split("/")[-1]
    status = await message.answer("⏳ Загрузка...")
    start = time.time()
    sky = SkyAnswers(task_hash)
    answers = await sky.get_answers()
    elapsed = round(time.time() - start, 1)
    await status.delete()
    if not answers:
        await message.answer("❌ Ответы не найдены")
        return
    for task in answers:
        q = task['question'].strip()
        header = f"<b>📝 Задание {task['task_number']}</b>\n"
        if q:
            header += f"<i>{q}</i>\n\n"
        clean = [a.split("→",1)[1].strip() if "→" in a else a.split(" - ",1)[1].strip() if " - " in a else a.strip() for a in task['answers']]
        if "вычеркни" in q.lower():
            part = "<b>Вычеркнуть:</b>\n" + "\n".join(f"❌ ~~{a}~~" for a in clean)
        else:
            part = "\n".join(f"✅ <code>{a}</code>" for a in clean)
        await message.answer(header + part + f"\n\n<i>⚡ За {elapsed} сек.</i>", parse_mode="HTML")
        await asyncio.sleep(0.3)

async def run_bot():
    await dp.start_polling(bot)

# Streamlit веб-интерфейс
st.set_page_config(page_title="Skysmart Answers", page_icon="🔵", layout="centered")
st.markdown("<h1 style='text-align: center;'>🔵 Skysmart Answers</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center;'>Мгновенные чистые ответы • @unreaskn</p>", unsafe_allow_html=True)

link = st.text_input("🔗 Ссылка на задание", placeholder="https://edu.skysmart.ru/student/...")

if link:
    if "edu.skysmart.ru/student/" not in link:
        st.error("❌ Неверная ссылка")
    else:
        with st.spinner("⏳ Загружаем ответы..."):
            task_hash = link.split("/")[-1]
            sky = SkyAnswers(task_hash)
            answers = asyncio.run(sky.get_answers())
        if not answers:
            st.error("❌ Ответы не найдены")
        else:
            st.success(f"✅ Найдено {len(answers)} заданий")
            for task in answers:
                with st.expander(f"📝 Задание {task['task_number']} — {task['question'] or 'Без вопроса'}", expanded=True):
                    clean = [a.split("→",1)[1].strip() if "→" in a else a.split(" - ",1)[1].strip() if " - " in a else a.strip() for a in task['answers']]
                    if "вычеркни" in task['question'].lower():
                        st.markdown("<b>Вычеркнуть:</b>", unsafe_allow_html=True)
                        for a in clean:
                            st.markdown(f"❌ ~~{a}~~")
                    else:
                        for a in clean:
                            st.success(f"✅ {a}")
st.markdown("---")
st.markdown("<center>❤️ @unreaskn</center>", unsafe_allow_html=True)

# Запуск бота в фоне
if "bot_started" not in st.session_state:
    Thread(target=asyncio.run, args=(run_bot(),), daemon=True).start()
    st.session_state.bot_started = True
