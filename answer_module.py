# answer_module.py
import asyncio
import base64
import re
import aiohttp
from bs4 import BeautifulSoup
from user_agent import generate_user_agent

url_room = 'https://api-edu.skysmart.ru/api/v1/task/preview'
url_auth2 = 'https://api-edu.skysmart.ru/api/v1/user/registration/teacher'
url_steps = 'https://api-edu.skysmart.ru/api/v1/content/step/load?stepUuid='

def clean_text(text: str) -> str:
    return re.sub(r'\s+', ' ', text.strip())

class SkysmartAPIClient:
    def __init__(self):
        self.session = aiohttp.ClientSession()
        self.token = ''
        self.user_agent = generate_user_agent()

    async def close(self):
        await self.session.close()

    async def _authenticate(self):
        headers = {'Content-Type': 'application/json', 'User-Agent': self.user_agent}
        async with self.session.post(url_auth2, headers=headers) as resp:
            if resp.status == 200:
                data = await resp.json()
                self.token = data["jwtToken"]

    async def _get_headers(self):
        if not self.token:
            await self._authenticate()
        return {
            'Content-Type': 'application/json',
            'User-Agent': self.user_agent,
            'Authorization': f'Bearer {self.token}'
        }

    async def get_room(self, task_hash):
        payload = {"taskHash": task_hash}
        headers = await self._get_headers()
        async with self.session.post(url_room, headers=headers, json=payload) as resp:
            if resp.status == 200:
                data = await resp.json()
                return data['meta']['stepUuids']
            return []

    async def get_task_html(self, uuid):
        headers = await self._get_headers()
        async with self.session.get(f"{url_steps}{uuid}", headers=headers) as resp:
            if resp.status == 200:
                data = await resp.json()
                return data['content']
            return ""

class SkyAnswers:
    def __init__(self, task_hash: str):
        self.task_hash = task_hash

    @staticmethod
    def extract_question(soup):
        instr = soup.find("vim-instruction")
        if instr and instr.text.strip():
            return clean_text(instr.text)
        # Fallback: clean main text
        exclude = ['vim-test-item', 'vim-input-answers', 'vim-select-item', 'math-input-answer', 'vim-strike-out-item']
        for tag in soup.find_all(exclude):
            tag.decompose()
        text = soup.get_text(separator=" ")
        return re.sub(r'\s+', ' ', text.strip())[:500]

    @staticmethod
    def parse_answers(soup):
        answers = []
        q_lower = soup.get_text().lower()

        # Multiple choice
        for item in soup.find_all('vim-test-item', attrs={'correct': 'true'}):
            answers.append(item.get_text(strip=True))

        # Select correct
        for item in soup.find_all('vim-select-item', attrs={'correct': 'true'}):
            answers.append(item.get_text(strip=True))

        # Input fills
        for inp in soup.find_all('vim-input-answers'):
            for item in inp.find_all('vim-input-item'):
                answers.append(item.get_text(strip=True))

        # Math
        for math in soup.find_all('math-input-answer'):
            answers.append(math.get_text(strip=True))

        # Strike out
        if "вычеркни" in q_lower or "cross out" in q_lower:
            for item in soup.find_all('vim-strike-out-item', attrs={'striked': 'true'}):
                answers.append(item.get_text(strip=True))

        # Drag and drop text
        for drop in soup.find_all('vim-dnd-text-drop'):
            drag_ids = drop.get('drag-ids', '').split(',')
            for drag_id in drag_ids:
                drag = soup.find('vim-dnd-text-drag', attrs={'answer-id': drag_id.strip()})
                if drag:
                    left = clean_text(drop.get_text())
                    right = clean_text(drag.get_text())
                    answers.append(f"{left} → {right}" if left else right)

        # Image matching / dnd images
        for drag in soup.find_all(['vim-dnd-image-drag', 'vim-dnd-image-set-drag']):
            answer_id = drag.get('answer-id')
            for drop in soup.find_all(['vim-dnd-image-drop', 'vim-dnd-image-set-drop']):
                drag_ids = drop.get('drag-ids', '').split(',')
                if answer_id in [d.strip() for d in drag_ids]:
                    img = drop.get('image') or drop.img.get('src', '') if drop.img else ''
                    desc = clean_text(drop.get_text()) or "Image"
                    text = clean_text(drag.get_text())
                    answers.append(f"{desc} → {text}" if img or desc else text)

        # Groups / tables
        for row in soup.find_all('vim-groups-row'):
            for item in row.find_all('vim-groups-item'):
                encoded = item.get('text')
                if encoded:
                    try:
                        decoded = base64.b64decode(encoded).decode('utf-8')
                        answers.append(decoded)
                    except:
                        pass

        # Image choices
        for item in soup.find_all('vim-test-image-item', attrs={'correct': 'true'}):
            text = clean_text(item.get_text())
            img = item.find('img')
            src = img.get('src', '') if img else ''
            answers.append(f"{text} (Image: {src})" if src else text)

        # True/False/Not stated detection
        if any(x in q_lower for x in ["true", "false", "not stated", "1", "2", "3"]):
            statements = []
            for div in soup.find_all('div'):
                t = clean_text(div.text)
                if t and (t[0].upper() in "ABCDEFG" and "." in t):
                    statements.append(t)
            if statements:
                answers = [f"{s.split('.',1)[0]}. → {a}" for s, a in zip(statements, answers)]

        return answers or ["No answers found"]

    @staticmethod
    def format_answers(raw_answers, soup):
        q_lower = soup.get_text().lower()
        formatted = []

        if "вычеркни" in q_lower or "cross out" in q_lower:
            for a in raw_answers:
                formatted.append(f"❌ ~~{a}~~")
        elif "match" in q_lower or "соотнес" in q_lower:
            for a in raw_answers:
                formatted.append(f"✅ {a}")
        else:
            for a in raw_answers:
                formatted.append(f"✅ {a}")

        return formatted or ["❌ Нет правильных ответов"]

    async def get_answers(self):
        answers_list = []
        client = SkysmartAPIClient()
        try:
            uuids = await client.get_room(self.task_hash)
            html_list = await asyncio.gather(*(client.get_task_html(u) for u in uuids))

            for idx, html in enumerate(html_list):
                if not html:
                    continue
                soup = BeautifulSoup(html, 'html.parser')
                question = self.extract_question(soup)
                raw_ans = self.parse_answers(soup)
                formatted = self.format_answers(raw_ans, soup)

                answers_list.append({
                    'task_number': idx + 1,
                    'question': question,
                    'formatted_answers': formatted
                })
        finally:
            await client.close()

        return answers_list
