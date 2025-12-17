import asyncio
import os
import time
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart
from answer_module import SkyAnswers

BOT_TOKEN = "8233085354:AAGXZ1GPyiDVW-wG3_Yj_DP_cuahx9PFrsw"  # или os.getenv("BOT_TOKEN")

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
        header = f"<b>📝 Задание {task['task_number']}</b>\n"
        
        question = task['question'].strip()
        question_part = f"<i>{question}</i>\n" if question else ""
        
        ans_list = [a.strip() for a in task['answers'] if a.strip()]
        
        if not ans_list:
            answers_part = "Нет ответа\n"
        elif any("File upload" in a for a in ans_list):
            answers_part = "⚠️ <b>Требуется загрузка файла</b>\n"
        elif len(ans_list) % 2 == 0 and all("→" not in a and " - " not in a for a in ans_list):
            # Соотнесение пар
            answers_part = "\n".join(f"<b>{ans_list[i]}</b> → {ans_list[i+1]}" for i in range(0, len(ans_list), 2)) + "\n"
        elif any("→" in a or " - " in a for a in ans_list):
            # Уже готовые пары
            answers_part = "\n".join(ans_list) + "\n"
        elif "вычеркни" in question.lower():
            answers_part = "Вычеркнуть:\n" + "\n".join(f"❌ {ans}" for ans in ans_list) + "\n"
        else:
            # Только правильные ответы (без "слово → слово")
            clean_answers = []
            for ans in ans_list:
                if "→" in ans:
                    clean_answers.append(ans.split("→", 1)[1].strip())
                elif " - " in ans:
                    clean_answers.append(ans.split(" - ", 1)[1].strip())
                else:
                    clean_answers.append(ans)
            answers_part = "\n".join(f"✅ {ans}" for ans in clean_answers) + "\n"
        
        full_text = header + question_part + answers_part + f"<i>Получено за {elapsed} сек.</i>"
        await message.answer(full_text, parse_mode="HTML")
        await asyncio.sleep(0.3)

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
