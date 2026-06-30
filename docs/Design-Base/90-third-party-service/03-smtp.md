# 03-smtp — SMTP / Email Client

> **何時讀**:寫信件功能(註冊驗證 / 通知 / 重設密碼)才讀。

寄信走 `app/clients/smtp/`,**禁**在 service / api 直 `smtplib.SMTP(...)`。

---

## Transactional vs Marketing

兩類嚴格分開,**不**混用:

| | Transactional | Marketing |
| --- | --- | --- |
| 觸發 | user 行為(註冊 / 重設) | 主動推播(電子報) |
| 退訂 | 不需(法律 + 用戶體驗都不該擋) | **必有**退訂連結 + DB `email_opt_in` |
| 走哪 | 主 SMTP / SendGrid transactional | 獨立 ESP(Mailchimp / SendGrid Marketing)|
| 寄送頻率 | 即時 | 排程(可批次) |
| log 等級 | error 才警報 | 量太大 / 退信率高才警報 |

本檔規範 transactional;marketing 走另一檔(視專案)。

## env 設定

```
SMTP_HOST=smtp.sendgrid.net
SMTP_PORT=587                # TLS;465 走 implicit TLS
SMTP_USER=apikey
SMTP_PASSWORD=<runtime-injected>
SMTP_FROM=noreply@<domain>
SMTP_FROM_NAME=<Project>
```

對齊 `00-overview/02-secrets.md`:`SMTP_PASSWORD` 為機密。

## Client 範本

```python
# app/clients/smtp/client.py
import aiosmtplib
from email.message import EmailMessage

class SmtpError(AppError): ...
class SmtpDeliveryError(SmtpError): ...

class SmtpClient:
    def __init__(self, host: str, port: int, user: str, password: str, sender: str) -> None:
        self._host = host
        self._port = port
        self._user = user
        self._password = password
        self._sender = sender

    async def send(self, *, to: str, subject: str, html: str, text: str) -> None:
        msg = EmailMessage()
        msg["From"] = self._sender
        msg["To"] = to
        msg["Subject"] = subject
        msg.set_content(text)
        msg.add_alternative(html, subtype="html")
        try:
            await aiosmtplib.send(
                msg,
                hostname=self._host,
                port=self._port,
                username=self._user,
                password=self._password,
                start_tls=True,
                timeout=30.0,
            )
        except aiosmtplib.SMTPException as e:
            raise SmtpDeliveryError(f"SMTP 寄送失敗:{e}") from e
```

> 用 `aiosmtplib`(async)而非 stdlib `smtplib`(blocking;會卡 event loop,違反 `03-backend/03-async-and-tx.md`)。`aiosmtplib` 加進 `00-overview/01-versions.md` 套件清單。

## 模板與多語

- HTML / text 雙版同寄(部分 client 不支援 HTML)
- i18n:對齊 `02-frontend/00-overview.md § i18n`,後端模板放 `app/templates/email/<locale>/<name>.{html,txt}`
- 渲染用 Jinja2 或同等(加入 `01-versions.md` 後使用)
- **禁**字串拼接組信件主旨 / body(SQL injection 等級的風險:HTML injection / phishing)

## 退信處理

- 同步 SMTP 失敗 → raise `SmtpDeliveryError` → service 寫 audit log
- 非同步 bounce(收到後若干小時)→ 配合 ESP webhook 收 bounce event,標 `email_invalid=True` 防再寄
- bounce / spam complaint 過閾值 → reflect 候選(可能是 sending reputation 問題)

## 測試

- 單元測試走 mock(`unittest.mock` 或 `respx`-like)
- e2e 用 sandbox(SendGrid Inspect mode)
- **禁**用真實 user email 跑測試
