import asyncio
import time
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart
from aiogram.types import Update
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web
from answer_module import SkyAnswers

import os
BOT_TOKEN = os.getenv("BOT_TOKEN")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

@dp.message(CommandStart())
async def start(message: types.Message):
    await message.answer("Отправь ссылку на задание Skysmart.")

@dp.message()
async def handle_link(message: types.Message):
    text = message.text.strip()
    if not text.startswith("https://edu.skysmart.ru/student/"):
        await message.answer("Неверная ссылка.")
        return
    task_hash = text.split("/")[-1]
    if not task_hash:
        await message.answer("Неверная ссылка.")
        return
    
    status = await message.answer("Загружаю ответы...")
    start_time = time.time()
    
    sky = SkyAnswers(task_hash)
    answers_list = await sky.get_answers()
    
    elapsed = round(time.time() - start_time, 1)
    await status.delete()
    
    if not answers_list:
        await message.answer("Ответы не найдены.")
        return
    
    for task in answers_list:
        header = f"<b>📝 Задание {task['task_number']}</b>"
        
        question = task['question'].strip()
        if question:
            suffix = ""
            if not (question.endswith("?") or question.endswith("!") or 
                    any(word in question.lower() for word in ["выбери", "выбрать", "запиши", "напиши", "вычеркни", "соотнеси", "выполни"])):
                suffix = " — выбери правильный ответ или запиши ответ"
            question_part = f"\n<i>{question}{suffix}</i>"
        else:
            question_part = ""
        
        answers_part = ""
        if task['answers']:
            ans_list = [a.strip() for a in task['answers'] if a.strip()]
            
            if any("File upload" in a for a in ans_list):
                answers_part = "\n⚠️ <b>Требуется загрузка файла</b>"
            
            elif len(ans_list) % 2 == 0 and all("→" not in a for a in ans_list):
                formatted = []
                i = 0
                while i < len(ans_list) - 1:
                    left = ans_list[i]
                    right = ans_list[i + 1]
                    formatted.append(f"<b>{left}</b> → {right}")
                    i += 2
                answers_part = "\n" + "\n".join(formatted)
            
            elif "вычеркни" in question.lower():
                answers_part = "\nВычеркнуть:\n" + "\n".join(f"❌ {ans}" for ans in ans_list)
            
            else:
                answers_part = "\n" + "\n".join(f"✅ {ans}" for ans in ans_list)
        else:
            answers_part = "\nНет ответа"
        
        full_text = header + question_part + answers_part + f"\n\n<i>Получено за {elapsed} сек.</i>"
        await message.answer(full_text, parse_mode="HTML")
        await asyncio.sleep(0.3)

app = web.Application()
SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path="/webhook")
setup_application(app, dp, bot=bot)

if __name__ == "__main__":

    web.run_app(app, host="0.0.0.0", port=8000)
