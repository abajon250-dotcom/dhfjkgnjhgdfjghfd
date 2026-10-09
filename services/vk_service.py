import asyncio
import random
import vk_api
import requests
from urllib3.exceptions import InsecureRequestWarning
from vk_api.upload import VkUpload

# Отключаем предупреждения о неиспользуемом SSL
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)


def _create_vk_session(token=None):
    """Создает сессию с отключенной проверкой SSL (обход антивирусов и прокси)"""
    session = requests.Session()
    session.verify = False
    return vk_api.VkApi(token=token, session=session)


async def get_vk_account(token: str):
    loop = asyncio.get_running_loop()

    def _check():
        try:
            vk_session = _create_vk_session(token=token)
            vk = vk_session.get_api()

            # Проверка профиля
            user_info = vk.users.get(fields="photo_200")[0]
            name = f"{user_info.get('first_name', '')} {user_info.get('last_name', '')}".strip()

            # Безопасное получение друзей
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


async def change_vk_name(token: str, first_name: str, last_name: str):
    loop = asyncio.get_running_loop()

    def _run():
        try:
            vk_session = _create_vk_session(token=token)
            vk = vk_session.get_api()
            vk.account.saveProfileInfo(first_name=first_name, last_name=last_name)
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    return await loop.run_in_executor(None, _run)


async def change_vk_password(token: str, old_pass: str, new_pass: str):
    loop = asyncio.get_running_loop()

    def _run():
        try:
            vk_session = _create_vk_session(token=token)
            vk = vk_session.get_api()
            vk.account.changePassword(old_password=old_pass, new_password=new_pass)
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    return await loop.run_in_executor(None, _run)


async def change_vk_avatar(token: str, image_path: str):
    loop = asyncio.get_running_loop()

    def _run():
        try:
            vk_session = _create_vk_session(token=token)
            upload = VkUpload(vk_session)
            upload.photo_profile(photo=image_path)
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    return await loop.run_in_executor(None, _run)


async def get_vk_friends_txt(token: str, filename: str):
    loop = asyncio.get_running_loop()

    def _run():
        try:
            vk_session = _create_vk_session(token=token)
            vk = vk_session.get_api()
            friends = vk.friends.get(fields="domain")
            count = friends.get('count', 0)
            items = friends.get('items', [])
            with open(filename, "w", encoding="utf-8") as f:
                f.write(f"Список друзей (Всего: {count})\n" + "=" * 30 + "\n\n")
                for i, fr in enumerate(items, 1):
                    f.write(f"{i}. {fr.get('first_name')} {fr.get('last_name')} (id{fr.get('id')})\n")
            return {"success": True, "count": count}
        except Exception as e:
            return {"success": False, "error": str(e)}

    return await loop.run_in_executor(None, _run)


async def get_vk_security_notifications(token: str):
    loop = asyncio.get_running_loop()

    def _run():
        try:
            vk_session = _create_vk_session(token=token)
            vk = vk_session.get_api()
            dialogs = vk.messages.getConversations(count=5, filter='all')
            messages_text = []
            for item in dialogs.get('items', []):
                last_msg = item.get('last_message', {})
                text = last_msg.get('text', '')
                peer_id = last_msg.get('peer_id', 0)
                messages_text.append(f"💬 Уведомление / Вход (ID чата: {peer_id}):\n{text}\n")
            if not messages_text:
                return {"success": True, "notifications": "Входных уведомлений или СМС нет."}
            return {"success": True, "notifications": "\n".join(messages_text)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    return await loop.run_in_executor(None, _run)


async def send_vk_message(token: str, target: str, text: str):
    loop = asyncio.get_running_loop()

    def _send():
        try:
            vk_session = _create_vk_session(token=token)
            vk = vk_session.get_api()
            vk.messages.send(
                user_id=int(target),
                message=text,
                random_id=random.randint(1, 2147483647)
            )
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    return await loop.run_in_executor(None, _send)


async def get_vk_friends(token: str):
    loop = asyncio.get_running_loop()

    def _get():
        try:
            vk_session = _create_vk_session(token=token)
            vk = vk_session.get_api()
            friends = vk.friends.get()
            return friends.get('items', [])
        except:
            return []

    return await loop.run_in_executor(None, _get)