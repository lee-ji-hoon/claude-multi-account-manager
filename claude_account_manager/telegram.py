"""
Telegram Bot API helper for account sync between machines.

Uses pinned message as a sync point:
- push: sends document → pins it
- pull: reads pinned message → downloads document
"""
import json
import os
import urllib.request
import urllib.error
from pathlib import Path


TELEGRAM_CONFIG = Path.home() / ".claude" / "hooks" / "telegram-config.json"


def load_telegram_config():
    """텔레그램 봇 설정 로드 (bot_token, chat_id)"""
    if not TELEGRAM_CONFIG.exists():
        return None
    try:
        return json.loads(TELEGRAM_CONFIG.read_text())
    except Exception:
        return None


def _build_multipart(fields, files):
    """multipart/form-data 빌드 (stdlib only)"""
    boundary = "----ClaudeAccountSync"
    body = b""

    for key, value in fields.items():
        body += f"--{boundary}\r\n".encode()
        body += f'Content-Disposition: form-data; name="{key}"\r\n\r\n'.encode()
        body += f"{value}\r\n".encode()

    for key, (filename, filedata, content_type) in files.items():
        body += f"--{boundary}\r\n".encode()
        body += f'Content-Disposition: form-data; name="{key}"; filename="{filename}"\r\n'.encode()
        body += f"Content-Type: {content_type}\r\n\r\n".encode()
        body += filedata + b"\r\n"

    body += f"--{boundary}--\r\n".encode()
    return body, f"multipart/form-data; boundary={boundary}"


def _api_call(method, bot_token, data=None, files=None):
    """Telegram Bot API 호출"""
    url = f"https://api.telegram.org/bot{bot_token}/{method}"

    if files:
        body, content_type = _build_multipart(data or {}, files)
        req = urllib.request.Request(url, data=body)
        req.add_header("Content-Type", content_type)
    elif data:
        json_data = json.dumps(data).encode()
        req = urllib.request.Request(url, data=json_data)
        req.add_header("Content-Type", "application/json")
    else:
        req = urllib.request.Request(url)

    with urllib.request.urlopen(req, timeout=30) as response:
        return json.loads(response.read().decode())


def send_document(bot_token, chat_id, filename, filedata, caption=""):
    """파일 전송"""
    return _api_call(
        "sendDocument",
        bot_token,
        data={"chat_id": str(chat_id), "caption": caption},
        files={"document": (filename, filedata, "application/json")},
    )


def pin_message(bot_token, chat_id, message_id):
    """메시지 고정 (알림 없이)"""
    return _api_call(
        "pinChatMessage",
        bot_token,
        data={"chat_id": chat_id, "message_id": message_id, "disable_notification": True},
    )


def get_chat(bot_token, chat_id):
    """채팅 정보 조회 (pinned_message 포함)"""
    return _api_call("getChat", bot_token, data={"chat_id": chat_id})


def get_file_info(bot_token, file_id):
    """파일 정보 조회"""
    return _api_call("getFile", bot_token, data={"file_id": file_id})


def download_file(bot_token, file_path):
    """파일 다운로드"""
    url = f"https://api.telegram.org/file/bot{bot_token}/{file_path}"
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=30) as response:
        return response.read()
