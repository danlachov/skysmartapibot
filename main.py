import asyncio
import os
import time
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart
from answer_module import SkyAnswers

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN not set in environment")

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
            suffix = " — выбери правильный ответ или запиши ответ" if not (
                question.endswith(("?", "!")) or
                any(w in question.lower() for w in ["выбери", "выбрать", "запиши", "напиши", "вычеркни", "соотнеси", "выполни"])
            ) else ""
            question_part = f"\n<i>{question}{suffix}</i>"
        else:
            question_part = ""
        
        answers_part = ""
        if task['answers']:
            ans_list = [a.strip() for a in task['answers'] if a.strip()]
            if any("File upload" in a for a in ans_list):
                answers_part = "\n⚠️ <b>Требуется загрузка файла</b>"
            elif len(ans_list) % 2 == 0 and all("→" not in a for a in ans_list):
                answers_part = "\n" + "\n".join(f"<b>{ans_list[i]}</b> → {ans_list[i+1]}" for i in range(0, len(ans_list), 2))
            elif "вычеркни" in question.lower():
                answers_part = "\nВычеркнуть:\n" + "\n".join(f"❌ {ans}" for ans in ans_list)
            else:
                answers_part = "\n" + "\n".join(f"✅ {ans}" for ans in ans_list)
        else:
            answers_part = "\nНет ответа"
        
        full_text = header + question_part + answers_part + f"\n\n<i>Получено за {elapsed} сек.</i>"
        await message.answer(full_text, parse_mode="HTML")
        await asyncio.sleep(0.3)

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
