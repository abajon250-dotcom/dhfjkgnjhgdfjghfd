import aiohttp


async def create_cryptobot_invoice(amount_usd: float, description: str, token: str):
    if not token:
        return {"success": False, "error": "CryptoBot token not set"}

    url = "https://pay.crypt.bot/api/createInvoice"
    headers = {
        "Crypto-Pay-API-Token": token,
        "Content-Type": "application/json"
    }
    payload = {
        "asset": "USDT",
        "amount": str(amount_usd),
        "description": description
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload, headers=headers) as resp:
            try:
                data = await resp.json()
                if data.get("ok"):
                    return {"success": True, "pay_url": data["result"].get("bot_invoice_url")}
                err = data.get("error", {}).get("message", "Error")
                return {"success": False, "error": err}
            except Exception as e:
                return {"success": False, "error": str(e)}


async def create_xrocket_invoice(amount_usd: float, description: str, token: str):
    if not token:
        return {"success": False, "error": "XRocket token not set"}

    url = "https://pay.api.xrocket.exchange/api/v1/invoices"
    headers = {
        "Authorization": f"Bearer {token.strip()}",
        "Content-Type": "application/json"
    }

    # Корректный пейлоад с обязательными полями валюты и цены для xRocket Pay API
    payload = {
        "amount": float(amount_usd),
        "currency": "USDT",
        "priceCurrency": "USDT",
        "description": description,
        "commentsEnabled": False
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload, headers=headers) as resp:
            try:
                data = await resp.json()
                print(f"📦 XRocket Response [{resp.status}]: {data}")

                if resp.status in (200, 201) and (data.get("success") or "data" in data):
                    res = data.get("data", {})
                    return {"success": True, "pay_url": res.get("link") or res.get("url")}

                err_msg = data.get("message") or data.get("error") or data.get("description") or str(data)
                return {"success": False, "error": f"xRocket error: {err_msg}"}
            except Exception as e:
                text_resp = await resp.text()
                return {"success": False, "error": f"JSON error: {e} | Text: {text_resp}"}