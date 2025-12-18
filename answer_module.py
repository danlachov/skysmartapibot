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
                return data.get('meta', {}).get('stepUuids', [])
            return []

    async def get_task_html(self, uuid):
        headers = await self._get_headers()
        async with self.session.get(f"{url_steps}{uuid}", headers=headers) as resp:
            if resp.status == 200:
                data = await resp.json()
                return data.get('content', '')
            return ""

class SkyAnswers:
    def __init__(self, task_hash: str):
        self.task_hash = task_hash

    @staticmethod
    def extract_question(soup):
        instr = soup.find("vim-instruction")
        if instr and instr.get_text(strip=True):
            return clean_text(instr.get_text())
        # Fallback: clean text excluding answer elements
        exclude_tags = ['vim-test-item', 'vim-select-item', 'vim-input-answers', 'math-input-answer',
                        'vim-strike-out-item', 'vim-dnd-text-drag', 'vim-dnd-text-drop']
        for tag in soup.find_all(exclude_tags):
            tag.decompose()
        text = soup.get_text(separator=" ")
        return clean_text(text)[:600]

    @staticmethod
    def parse_matching_images(soup):
        lines = []
        for drag in soup.find_all(['vim-dnd-image-drag', 'vim-dnd-image-set-drag']):
            answer_id = drag.get('answer-id')
            text = clean_text(drag.get_text())
            if not text:
                continue
            img_src = ""
            img_tag = drag.find('img')
            if img_tag:
                img_src = img_tag.get('src', '')
            for drop in soup.find_all(['vim-dnd-image-drop', 'vim-dnd-image-set-drop']):
                drag_ids = drop.get('drag-ids', '').split(',')
                if answer_id in [d.strip() for d in drag_ids]:
                    desc = "Image"
                    drop_img = drop.find('img')
                    if drop_img:
                        src = drop_img.get('src', '')
                        if src:
                            desc = f"[Image: {src}]"
                    lines.append(f"{desc} → {text}")
        return "\n".join(lines) or None

    @staticmethod
    def parse_dnd_text(soup):
        lines = []
        for drop in soup.find_all('vim-dnd-text-drop'):
            drag_ids = drop.get('drag-ids', '').split(',')
            left = clean_text(drop.get_text()) or "_____"
            for drag_id in drag_ids:
                drag = soup.find('vim-dnd-text-drag', attrs={'answer-id': drag_id.strip()})
                if drag:
                    right = clean_text(drag.get_text())
                    lines.append(f"{left} → {right}")
        return "\n".join(lines) or None

    @staticmethod
    def parse_groups_table(soup):
        lines = []
        for row in soup.find_all('vim-groups-row'):
            for item in row.find_all('vim-groups-item'):
                encoded = item.get('text')
                if encoded:
                    try:
                        decoded = base64.b64decode(encoded).decode('utf-8')
                        lines.append(decoded)
                    except:
                        pass
        return "\n".join(lines) or None

    @staticmethod
    def parse_strike_out(soup):
        return "\n".join(f"❌ ~~{clean_text(item.get_text())}~~"
                         for item in soup.find_all('vim-strike-out-item', attrs={'striked': 'true'}))

    @staticmethod
    def parse_multiple_choice(soup):
        items = soup.find_all(['vim-test-item', 'vim-select-item', 'vim-test-image-item'], attrs={'correct': 'true'})
        lines = []
        for item in items:
            text = clean_text(item.get_text())
            img = item.find('img')
            if img:
                src = img.get('src', '')
                text = f"{text} [Image: {src}]" if src else text
            lines.append(f"✅ {text}")
        return "\n".join(lines) or None

    @staticmethod
    def parse_inputs(soup):
        lines = []
        for container in soup.find_all(['vim-input-answers', 'math-input-answer']):
            for item in container.find_all(['vim-input-item', True]):
                text = clean_text(item.get_text())
                if text:
                    lines.append(text)
        return "\n".join(lines) or None

    @staticmethod
    def parse_true_false(soup):
        statements = []
        answers = []
        # Collect correct answers first
        for item in soup.find_all('vim-test-item', attrs={'correct': 'true'}):
            answers.append(item.get_text(strip=True))
        # Find statements (usually in separate divs with letters)
        for div in soup.find_all('div'):
            text = clean_text(div.get_text())
            if len(text) > 10 and text[0] in "ABCDE" and text[1] == ".":
                statements.append(text)
        if len(statements) == len(answers):
            return "\n".join(f"{s} → {a}" for s, a in zip(statements, answers))
        return None

    async def get_answers(self):
        answers_list = []
        client = SkysmartAPIClient()
        try:
            uuids = await client.get_room(self.task_hash)
            htmls = await asyncio.gather(*[client.get_task_html(u) for u in uuids])

            for idx, html in enumerate(htmls):
                if not html:
                    continue
                soup = BeautifulSoup(html, 'html.parser')
                question = self.extract_question(soup)

                formatted = None
                # Priority order
                if soup.find(['vim-dnd-image-drag', 'vim-dnd-image-set-drag']):
                    formatted = self.parse_matching_images(soup)
                elif soup.find('vim-dnd-text-drop'):
                    formatted = self.parse_dnd_text(soup)
                elif soup.find('vim-groups-row'):
                    formatted = self.parse_groups_table(soup)
                elif soup.find('vim-strike-out-item'):
                    formatted = self.parse_strike_out(soup)
                elif soup.find('vim-test-item', attrs={'correct': 'true'}) or soup.find('vim-select-item', attrs={'correct': 'true'}):
                    tf = self.parse_true_false(soup)
                    formatted = tf or self.parse_multiple_choice(soup)
                else:
                    inputs = self.parse_inputs(soup)
                    if inputs:
                        formatted = inputs

                if not formatted:
                    formatted = "Ответы не распознаны"

                answers_list.append({
                    'task_number': idx + 1,
                    'question': question,
                    'formatted_text': formatted
                })
        finally:
            await client.close()

        return answers_list
