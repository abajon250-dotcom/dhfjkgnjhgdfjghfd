import logging
import uuid
from decimal import Decimal, ROUND_HALF_UP

import aiohttp

logger = logging.getLogger(__name__)

_HTTP_HEADERS = {
    "Accept": "application/json",
    "Content-Type": "application/json",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
    ),
}

XROCKET_INVOICES_URL = "https://pay.api.xrocket.exchange/api/v1/invoices"
CRYPTOBOT_INVOICE_URL = "https://pay.crypt.bot/api/createInvoice"
CRYPTOBOT_GET_INVOICES_URL = "https://pay.crypt.bot/api/getInvoices"


def _format_amount(amount: float) -> str:
    quantized = Decimal(str(amount)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return format(quantized, "f")


def _problem_message(status: int, data) -> str:
    if isinstance(data, dict):
        detail = data.get("detail") or data.get("title") or data.get("message")
        if isinstance(data.get("error"), dict):
            detail = detail or data["error"].get("message")
        elif isinstance(data.get("error"), str):
            detail = detail or data.get("error")
        if detail:
            return f"{status}: {detail}"
        return f"{status}: {data}"
    return f"{status}: {data}"


def _extract_xrocket_pay_url(invoice: dict) -> str | None:
    if not isinstance(invoice, dict):
        return None
    links = invoice.get("links") if isinstance(invoice.get("links"), dict) else {}
    return (
            links.get("telegramBotLink")
            or links.get("telegramMiniAppLink")
            or links.get("webLink")
            or invoice.get("link")
            or (invoice.get("url") if isinstance(invoice.get("url"), str) else None)
    )


async def _post_json(url: str, payload: dict, headers: dict) -> tuple[int, object]:
    merged = {**_HTTP_HEADERS, **headers}
    timeout = aiohttp.ClientTimeout(total=30)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.post(url, json=payload, headers=merged) as resp:
            try:
                data = await resp.json(content_type=None)
            except Exception:
                text = await resp.text()
                data = {"detail": text[:500]}
            return resp.status, data


async def create_cryptobot_invoice(amount_usd: float, description: str, token: str):
    token = (token or "").strip()
    if not token:
        return {"success": False, "error": "Токен CryptoBot не настроен в .env (CRYPTOBOT_TOKEN)."}

    payload = {
        "asset": "USDT",
        "amount": _format_amount(amount_usd),
        "description": description[:1024],
    }
    headers = {"Crypto-Pay-API-Token": token}

    try:
        status, data = await _post_json(CRYPTOBOT_INVOICE_URL, payload, headers)
    except Exception as e:
        logger.exception("CryptoBot connection error")
        return {"success": False, "error": f"Ошибка соединения с CryptoBot: {e}"}

    if isinstance(data, dict) and data.get("ok"):
        result = data.get("result") or {}
        pay_url = result.get("bot_invoice_url") or result.get("pay_url") or result.get("mini_app_invoice_url")
        invoice_id = result.get("invoice_id")
        if pay_url and invoice_id:
            return {"success": True, "pay_url": pay_url, "invoice_id": str(invoice_id)}
        return {"success": False, "error": "CryptoBot не вернул ссылку или ID счета."}

    return {"success": False, "error": f"Ошибка CryptoBot ({_problem_message(status, data)})"}


async def check_cryptobot_invoice(invoice_id: str, token: str) -> bool:
    token = (token or "").strip()
    if not token or not invoice_id:
        return False

    payload = {"invoice_ids": [int(invoice_id)]}
    headers = {"Crypto-Pay-API-Token": token}

    try:
        status, data = await _post_json(CRYPTOBOT_GET_INVOICES_URL, payload, headers)
        if status == 200 and isinstance(data, dict) and data.get("ok"):
            items = data.get("result", {}).get("items", [])
            if items and items[0].get("status") == "paid":
                return True
    except Exception:
        logger.exception("Error checking CryptoBot invoice")
    return False


async def create_xrocket_invoice(
        amount_usd: float,
        description: str,
        token: str,
        *,
        user_id: int | None = None,
        username: str | None = None,
):
    token = (token or "").strip()
    if not token:
        return {"success": False, "error": "Токен xRocket не настроен в .env (XROCKET_TOKEN)."}

    client_invoice_id = f"aegis-{user_id or 0}-{uuid.uuid4().hex[:12]}"
    payload = {
        "priceAmount": _format_amount(amount_usd),
        "priceCurrency": "USDT",
        "payCurrencies": ["USDT"],
        "description": (description or "Aegis VK")[:1000],
        "numPayments": 1,
        "expiresIn": 3_600_000,
        "clientInvoiceId": client_invoice_id,
        "isFeePaidByUser": False,
    }
    if user_id:
        customer = {"id": str(user_id), "telegramId": str(user_id)}
        if username:
            customer["telegramUsername"] = username.lstrip("@")
        payload["customer"] = customer

    headers = {"Authorization": f"Bearer {token}"}

    try:
        status, data = await _post_json(XROCKET_INVOICES_URL, payload, headers)
    except Exception as e:
        logger.exception("xRocket connection error")
        return {"success": False, "error": f"Ошибка соединения с xRocket: {e}"}

    invoice = data
    if isinstance(data, dict) and isinstance(data.get("data"), dict):
        invoice = data["data"]

    if status in (200, 201) and isinstance(invoice, dict):
        pay_url = _extract_xrocket_pay_url(invoice)
        invoice_id = invoice.get("id") or invoice.get("invoiceId")
        if pay_url and invoice_id:
            return {"success": True, "pay_url": pay_url, "invoice_id": str(invoice_id)}
        return {"success": False, "error": "xRocket создал счет, но не вернул ссылку или ID."}

    return {"success": False, "error": f"Ошибка xRocket ({_problem_message(status, data)})"}


async def check_xrocket_invoice(invoice_id: str, token: str) -> bool:
    token = (token or "").strip()
    if not token or not invoice_id:
        return False

    url = f"{XROCKET_INVOICES_URL}/{invoice_id}"
    headers = {**_HTTP_HEADERS, "Authorization": f"Bearer {token}"}
    timeout = aiohttp.ClientTimeout(total=30)

    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.get(url, headers=headers) as resp:
            try:
                data = await resp.json(content_type=None)
            except Exception:
                return False

            invoice = data
            if isinstance(data, dict) and isinstance(data.get("data"), dict):
                invoice = data["data"]

            if resp.status in (200, 201) and isinstance(invoice, dict):
                status_str = str(invoice.get("status", "")).upper()
                if status_str in ("PAID", "COMPLETED", "SUCCESS"):
                    return True
    return False