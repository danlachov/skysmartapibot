import asyncio
import base64
import re
import aiohttp
from bs4 import BeautifulSoup
from user_agent import generate_user_agent

url_room = 'https://api-edu.skysmart.ru/api/v1/task/preview'
url_auth2 = 'https://api-edu.skysmart.ru/api/v1/user/registration/teacher'
url_steps = 'https://api-edu.skysmart.ru/api/v1/content/step/load?stepUuid='
url_room_preview = 'https://api-edu.skysmart.ru/api/v1/task/preview'

def remove_extra_newlines(text: str) -> str:
    return re.sub(r'\n+', '\n', text.strip())

class SkysmartAPIClient:
    def __init__(self):
        self.session = aiohttp.ClientSession()
        self.token = ''
        self.user_agent = generate_user_agent()

    async def close(self):
        await self.session.close()

    async def _authenticate(self):
        headers = {
            'Connection': 'keep-alive',
            'Content-Type': 'application/json',
            'User-Agent': self.user_agent
        }
        async with self.session.post(url_auth2, headers=headers) as resp:
            if resp.status == 200:
                json_resp = await resp.json()
                self.token = json_resp["jwtToken"]
            else:
                raise Exception(f"Authentication failed: {resp.status}")

    async def _get_headers(self):
        if not self.token:
            await self._authenticate()
        return {
            'Connection': 'keep-alive',
            'Content-Type': 'application/json',
            'User-Agent': self.user_agent,
            'Accept': 'application/json, text/plain, */*',
            'Authorization': f'Bearer {self.token}'
        }

    async def get_room(self, task_hash):
        payload = {"taskHash": task_hash}
        headers = await self._get_headers()
        async with self.session.post(url_room, headers=headers, json=payload) as resp:
            if resp.status == 200:
                json_resp = await resp.json()
                return json_resp['meta']['stepUuids']
            else:
                raise Exception(f"get_room failed: {resp.status}")

    async def get_task_html(self, uuid):
        headers = await self._get_headers()
        async with self.session.get(f"{url_steps}{uuid}", headers=headers) as resp:
            if resp.status == 200:
                json_resp = await resp.json()
                return json_resp['content']
            else:
                raise Exception(f"get_task_html failed: {resp.status}")

    async def get_room_info(self, task_hash):
        payload = {"taskHash": task_hash}
        headers = await self._get_headers()
        async with self.session.post(url_room_preview, headers=headers, json=payload) as resp:
            if resp.status == 200:
                json_resp = await resp.json()
                return json_resp
            else:
                raise Exception(f"get_room_info failed: {resp.status}")

class SkyAnswers:
    def __init__(self, task_hash: str):
        self.task_hash = task_hash

    async def get_answers(self):
        answers_list = []
        client = SkysmartAPIClient()
        try:
            tasks_uuids = await client.get_room(self.task_hash)
            tasks_html_coroutines = [client.get_task_html(uuid) for uuid in tasks_uuids]
            tasks_html_list = await asyncio.gather(*tasks_html_coroutines, return_exceptions=True)
            for idx, task_html in enumerate(tasks_html_list):
                if isinstance(task_html, Exception):
                    continue
                soup = BeautifulSoup(task_html, 'html.parser')
                task_answer = self._get_task_answer(soup, idx + 1)
                answers_list.append(task_answer)
        finally:
            await client.close()
        return answers_list

    @staticmethod
    def _extract_task_question(soup):
        instruction = soup.find("vim-instruction")
        return instruction.text.strip() if instruction else ""

    @staticmethod
    def _extract_task_full_question(soup):
        elements_to_exclude = [
            'vim-instruction', 'vim-groups', 'vim-test-item',
            'vim-order-sentence-verify-item', 'vim-input-answers',
            'vim-select-item', 'vim-test-image-item', 'math-input-answer',
            'vim-dnd-text-drop', 'vim-dnd-group-drag', 'vim-groups-row',
            'vim-strike-out-item', 'vim-dnd-image-set-drag',
            'vim-dnd-image-drag', 'edu-open-answer'
        ]
        for element in soup.find_all(elements_to_exclude):
            element.decompose()
        return remove_extra_newlines(soup.get_text())

    def _get_task_answer(self, soup, task_number):
        answers = []
        for item in soup.find_all('vim-test-item', attrs={'correct': 'true'}):
            answers.append(item.get_text())
        for item in soup.find_all('vim-order-sentence-verify-item'):
            answers.append(item.get_text())
        for input_answer in soup.find_all('vim-input-answers'):
            input_item = input_answer.find('vim-input-item')
            if input_item:
                answers.append(input_item.get_text())
        for select_item in soup.find_all('vim-select-item', attrs={'correct': 'true'}):
            answers.append(select_item.get_text())
        for image_item in soup.find_all('vim-test-image-item', attrs={'correct': 'true'}):
            answers.append(f"{image_item.get_text()} - Correct")
        for math_answer in soup.find_all('math-input-answer'):
            answers.append(math_answer.get_text())
        for drop in soup.find_all('vim-dnd-text-drop'):
            drag_ids = drop.get('drag-ids', '').split(',')
            for drag_id in drag_ids:
                drag = soup.find('vim-dnd-text-drag', attrs={'answer-id': drag_id})
                if drag:
                    answers.append(drag.get_text())
        for drag_group in soup.find_all('vim-dnd-group-drag'):
            answer_id = drag_group.get('answer-id')
            for group_item in soup.find_all('vim-dnd-group-item'):
                drag_ids = group_item.get('drag-ids', '').split(',')
                if answer_id in drag_ids:
                    answers.append(f"{group_item.get_text()} - {drag_group.get_text()}")
        for group_row in soup.find_all('vim-groups-row'):
            for group_item in group_row.find_all('vim-groups-item'):
                encoded_text = group_item.get('text')
                if encoded_text:
                    try:
                        decoded_text = base64.b64decode(encoded_text).decode('utf-8')
                        answers.append(decoded_text)
                    except:
                        pass
        for striked_item in soup.find_all('vim-strike-out-item', attrs={'striked': 'true'}):
            answers.append(striked_item.get_text())
        for image_drag in soup.find_all('vim-dnd-image-set-drag'):
            answer_id = image_drag.get('answer-id')
            for image_drop in soup.find_all('vim-dnd-image-set-drop'):
                drag_ids = image_drop.get('drag-ids', '').split(',')
                if answer_id in drag_ids:
                    answers.append(f"{image_drop.get('image')} - {image_drag.get_text()}")
        for image_drag in soup.find_all('vim-dnd-image-drag'):
            answer_id = image_drag.get('answer-id')
            for image_drop in soup.find_all('vim-dnd-image-drop'):
                drag_ids = image_drop.get('drag-ids', '').split(',')
                if answer_id in drag_ids:
                    answers.append(f"{image_drop.get_text()} - {image_drag.get_text()}")
        if soup.find('edu-open-answer', attrs={'id': 'OA1'}):
            answers.append('File upload required')
        return {
            'question': self._extract_task_question(soup),
            'full_question': self._extract_task_full_question(soup),
            'answers': answers,
            'task_number': task_number,
        }