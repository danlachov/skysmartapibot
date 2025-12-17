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

@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    await message.answer("🔵 Skysmart Answers\n\nОтправь ссылку на задание.\n\n@unreaskn", parse_mode="HTML")

@dp.message()
async def tg_handle(message: types.Message):
    text = message.text.strip()
    if not text.startswith("https://edu.skysmart.ru/student/"):
        await message.answer("❌ Неверная ссылка")
        return
    task_hash = text.split("/")[-1]
    status = await message.answer("⏳")
    start = time.time()
    sky = SkyAnswers(task_hash)
    answers = await sky.get_answers()
    elapsed = round(time.time() - start, 1)
    await status.delete()
    if not answers:
        await message.answer("❌ Не найдено")
        return
    for task in answers:
        q = task['question'].strip()
        header = f"<b>Задание {task['task_number']}</b>"
        if q:
            header += f"\n{q}"
        clean = [a.split("→",1)[1].strip() if "→" in a else a.split(" - ",1)[1].strip() if " - " in a else a.strip() for a in task['answers']]
        if "вычеркни" in q.lower():
            part = "\n".join(f"❌ ~~{a}~~" for a in clean)
        else:
            part = "\n".join(f"✅ {a}" for a in clean)
        await message.answer(f"{header}\n\n{part}\n\n<i>{elapsed} сек</i>", parse_mode="HTML")
        await asyncio.sleep(0.2)

async def run_bot():
    await dp.start_polling(bot)

# Минималистичный дизайн Streamlit
st.set_page_config(page_title="Skysmart Answers", page_icon="🔵", layout="centered")

st.markdown("""
<style>
    .main {background-color: #f8f9fa; padding-top: 2rem;}
    .stTextInput > div > div > input {border-radius: 12px; padding: 12px;}
    .stButton > button {background-color: #007bff; color: white; border-radius: 12px; width: 100%; height: 50px;}
    h1 {text-align: center; color: #007bff;}
    .footer {text-align: center; margin-top: 4rem; color: #6c757d; font-size: 0.9rem;}
</style>
""", unsafe_allow_html=True)

st.markdown("<h1>🔵 Skysmart Answers</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center; color: #6c757d;'>Чистые ответы мгновенно</p>", unsafe_allow_html=True)

link = st.text_input("", placeholder="https://edu.skysmart.ru/student/...")

if link:
    if "edu.skysmart.ru/student/" not in link:
        st.error("Неверная ссылка")
    else:
        with st.spinner(""):
            task_hash = link.split("/")[-1]
            sky = SkyAnswers(task_hash)
            answers = asyncio.run(sky.get_answers())
        if not answers:
            st.error("Ответы не найдены")
        else:
            for task in answers:
                with st.expander(f"Задание {task['task_number']}", expanded=True):
                    q = task['question'].strip()
                    if q:
                        st.caption(q)
                    clean = [a.split("→",1)[1].strip() if "→" in a else a.split(" - ",1)[1].strip() if " - " in a else a.strip() for a in task['answers']]
                    if "вычеркни" in task['question'].lower():
                        for a in clean:
                            st.markdown(f"~~{a}~~")
                    else:
                        for a in clean:
                            st.markdown(f"**{a}**")

st.markdown("<div class='footer'>@unreaskn</div>", unsafe_allow_html=True)

# Запуск бота в фоне
if "bot_started" not in st.session_state:
    Thread(target=asyncio.run, args=(run_bot(),), daemon=True).start()
    st.session_state.bot_started = True
