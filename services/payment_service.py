import aiohttp


async def create_cryptobot_invoice(amount_usd: float, token: str):
    if not token:
        return {"success": False, "error": "CryptoBot token not set"}
    url = "https://pay.crypt.bot/api/createInvoice"
    headers = {"Crypto-Pay-API-Token": token, "Content-Type": "application/json"}
    payload = {"asset": "USDT", "amount": str(amount_usd), "description": "Подписка Aegis VK"}
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload, headers=headers) as resp:
            data = await resp.json()
            if data.get("ok"):
                return {"success": True, "pay_url": data["result"].get("bot_invoice_url")}
            return {"success": False, "error": data.get("error", {}).get("message", "Error")}


async def create_xrocket_invoice(amount_usd: float, token: str):
    if not token:
        return {"success": False, "error": "XRocket token not set"}

    # Официальный эндпоинт xRocket Pay API для создания инвойсов
    url = "https://pay.api.xrocket.exchange/api/v1/invoices"

    # Авторизация строго по стандарту Bearer Token из документации
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    # Параметры инвойса согласно Pay API
    payload = {
        "amount": amount_usd,
        "currency": "TON",
        "description": "Подписка Aegis VK",
        "commentsEnabled": True
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload, headers=headers) as resp:
            try:
                data = await resp.json()
                if resp.status in (200, 201) and (data.get("success") or "data" in data):
                    res = data.get("data", {})
                    return {"success": True, "pay_url": res.get("link") or res.get("url")}
                return {"success": False, "error": data.get("message", f"XRocket error code {resp.status}")}
            except Exception as e:
                return {"success": False, "error": str(e)}