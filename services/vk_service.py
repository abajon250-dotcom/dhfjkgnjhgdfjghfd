import asyncio
import random
import vk_api
import requests
from urllib3.exceptions import InsecureRequestWarning
from vk_api.upload import VkUpload

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

def _create_vk_session(token=None):
    session = requests.Session()
    session.verify = False
    return vk_api.VkApi(token=token, session=session)

async def get_vk_account(token: str):
    loop = asyncio.get_running_loop()
    def _check():
        try:
            vk_session = _create_vk_session(token=token)
            vk = vk_session.get_api()
            
            user_info = vk.users.get(fields="photo_200")[0]
            name = f"{user_info.get('first_name', '')} {user_info.get('last_name', '')}".strip()
            
            count = 0
            try:
                friends = vk.friends.get()
                count = friends.get('count', len(friends.get('items', [])))
            except Exception:
                pass
            
            return {"valid": True, "name": name, "friends": count, "token": token}
        except Exception as e:
            print(f"❌ Ошибка VK API при проверке токена: {e}")
            return {"valid": False, "error": str(e)}
    return await loop.run_in_executor(None, _check)

async def check_vk_account(raw_acc: str):
    token = raw_acc.split(":")[-1].strip() if ":" in raw_acc else raw_acc.strip()
    res = await get_vk_account(token)
    if res.get("valid"):
        return {"valid": True, "token": token, "name": res["name"], "friends": res["friends"]}
    return {"valid": False, "error": res.get("error")}
