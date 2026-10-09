import aiohttp


async def create_cryptobot_invoice(amount_usd: float, description: str, token: str):
    if not token:
        return {"success": False, "error": "Токен CryptoBot не настроен в системе."}

    url = "https://pay.crypt.bot/api/createInvoice"
    headers = {
        "Crypto-Pay-API-Token": token,
        "Content-Type": "application/json"
    }
    payload = {
        "asset": "USDT",
        "amount": f"{amount_usd:.2f}",
        "description": description
    }

    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(url, json=payload, headers=headers) as resp:
                data = await resp.json()
                if data.get("ok"):
                    return {"success": True, "pay_url": data["result"].get("bot_invoice_url")}
                err = data.get("error", {}).get("message", "Неизвестная ошибка CryptoBot")
                return {"success": False, "error": f"Ошибка CryptoBot: {err}"}
        except Exception as e:
            return {"success": False, "error": f"Ошибка соединения с CryptoBot: {str(e)}"}


async def create_xrocket_invoice(amount_usd: float, description: str, token: str):
    if not token:
        return {"success": False, "error": "Токен XRocket не настроен в системе."}

    url = "https://pay.api.xrocket.exchange/api/v1/invoices"
    headers = {
        "Authorization": f"Bearer {token.strip()}",
        "Content-Type": "application/json"
    }

    # Принудительно форматируем сумму в строку с 2 знаками после запятой (например, "3.00", "7.00", "24.00")
    payload = {
        "priceAmount": f"{amount_usd:.2f}",
        "priceCurrency": "USDT",
        "currency": "USDT",
        "description": description,
        "commentsEnabled": False
    }

    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(url, json=payload, headers=headers) as resp:
                data = await resp.json()
                print(f"📦 XRocket Response [{resp.status}]: {data}")

                if resp.status in (200, 201) and (data.get("success") or "data" in data):
                    res = data.get("data", {})
                    pay_url = res.get("link") or res.get("url")
                    if pay_url:
                        return {"success": True, "pay_url": pay_url}
                    return {"success": False, "error": "Не удалось получить ссылку на оплату от XRocket."}

                err_msg = data.get("message") or data.get("error") or data.get("detail") or str(data)
                return {"success": False, "error": f"Ошибка XRocket ({resp.status}): {err_msg}"}
        except Exception as e:
            return {"success": False, "error": f"Ошибка соединения с XRocket: {str(e)}"}