import asyncio
import os
import time
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart
from answer_module import SkyAnswers

BOT_TOKEN = os.getenv("BOT_TOKEN", "8233085354:AAGXZ1GPyiDVW-wG3_Yj_DP_cuahx9PFrsw")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

@dp.message(CommandStart())
async def start(message: types.Message):
    await message.answer("🔵 Skysmart Answers\n\nОтправь ссылку на задание.\n\n@unreaskn")

@dp.message()
async def handle(message: types.Message):
    text = message.text.strip()
    if not text.startswith("https://edu.skysmart.ru/student/"):
        await message.answer("❌ Неверная ссылка")
        return
    
    task_hash = text.split("/")[-1]
    if not task_hash:
        await message.answer("❌ Пустая ссылка")
        return
    
    status = await message.answer("⏳")
    start_time = time.time()
    
    sky = SkyAnswers(task_hash)
    answers = await sky.get_answers()
    
    elapsed = round(time.time() - start_time, 1)
    await status.delete()
    
    if not answers:
        await message.answer("❌ Ответы не найдены")
        return
    
    for task in answers:
        q = task['question'].strip().lower()
        header = f"<b>Задание {task['task_number']}</b>"
        if task['question']:
            header += f"\n<i>{task['question'].strip()}</i>"
        
        clean = []
        for a in task['answers']:
            a = a.strip()
            if "→" in a:
                left = a.split("→", 1)[0].strip()
                right = a.split("→", 1)[1].strip()
                # Для "Choose the correct options" — только левая часть
                if "choose the correct options" in q or "выбери правильный" in q:
                    clean.append(left)
                else:
                    clean.append(right)
            elif " - " in a:
                clean.append(a.split(" - ", 1)[1].strip())
            else:
                clean.append(a)
        
        if "вычеркни" in q:
            answers_part = "\n".join(f"❌ ~~{a}~~" for a in clean)
        else:
            answers_part = "\n".join(f"✅ {a}" for a in clean)
        
        await message.answer(f"{header}\n\n{answers_part}\n\n<i>⚡ {elapsed} сек • @unreaskn</i>", parse_mode="HTML")
        await asyncio.sleep(0.2)

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
