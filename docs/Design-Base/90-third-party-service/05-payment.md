# 05-payment — 金流 Client(Stripe / 綠界)

> **何時讀**:做付款 / 訂閱才讀。

金錢相關**最高敏感度**:金額精度 / webhook 簽章驗 / idempotency key 缺一不可。

---

## 共通原則(永遠遵守)

- **金額**:走整數(分 / cents);**禁** float。對齊 `04-databases/05-precision.md`(`Numeric(18, 2)` 做 DB 儲存,client 與第三方介面用 cents)
- **idempotency**:POST 建立付款 / 退款必帶 `Idempotency-Key`(避免網路重試重扣);Stripe / 綠界都支援
- **Webhook 簽章驗證**:**永遠**驗,**禁**因「測試方便」跳過
- **金額來源**:後端**必**自己算,**禁**信前端送來的金額(防竄改)
- **狀態以 webhook 為準**:redirect 回前端的成功頁**不**等於成功;以 webhook `payment_succeeded` 為準
- **log 機密過濾**:卡號 / CVV / token 全值禁 log(對齊 `00-overview/02-secrets.md`)

## Stripe 範本

```
STRIPE_SECRET_KEY=sk_live_...          # 機密
STRIPE_WEBHOOK_SECRET=whsec_...        # 機密(用於 webhook 簽章驗)
STRIPE_PUBLISHABLE_KEY=pk_live_...     # 前端用,可公開
```

```python
# app/clients/stripe/client.py
import stripe                          # 加進 01-versions.md

class StripeError(AppError): ...
class StripeWebhookError(StripeError): ...

class StripeClient:
    def __init__(self, secret_key: str, webhook_secret: str) -> None:
        stripe.api_key = secret_key
        self._webhook_secret = webhook_secret

    async def create_intent(self, *, amount_cents: int, currency: str, idempotency_key: str) -> str:
        try:
            intent = await stripe.PaymentIntent.create_async(
                amount=amount_cents,
                currency=currency,
                automatic_payment_methods={"enabled": True},
                idempotency_key=idempotency_key,
            )
        except stripe.error.StripeError as e:
            raise StripeError(f"Stripe error: {e}") from e
        return intent.client_secret

    def verify_webhook(self, payload: bytes, sig_header: str) -> stripe.Event:
        try:
            return stripe.Webhook.construct_event(payload, sig_header, self._webhook_secret)
        except (ValueError, stripe.error.SignatureVerificationError) as e:
            raise StripeWebhookError("invalid webhook signature") from e
```

```python
# app/api/v1/webhooks.py
@router.post("/webhooks/stripe", include_in_schema=False)
async def stripe_webhook(
    request: Request,
    stripe_client: StripeClient = Depends(get_stripe_client),
    payment_service: PaymentService = Depends(),
) -> ApiResponse[None]:
    payload = await request.body()
    sig = request.headers.get("stripe-signature", "")
    event = stripe_client.verify_webhook(payload, sig)   # 驗簽
    # idempotent handling — 用 event.id 去重
    if await payment_service.event_already_processed(event.id):
        return ApiResponse(data=None)
    if event.type == "payment_intent.succeeded":
        await payment_service.mark_paid(event.data.object.id)
    elif event.type == "charge.refunded":
        await payment_service.mark_refunded(event.data.object.id)
    await payment_service.record_event(event.id)
    return ApiResponse(data=None)
```

## 綠界範本

綠界(ECPay)走 form POST + CheckMacValue(MD5 / SHA256 雜湊驗證):

```python
import hashlib

def verify_check_mac_value(params: dict[str, str], hash_key: str, hash_iv: str) -> bool:
    received = params.pop("CheckMacValue")
    sorted_params = sorted(params.items())
    raw = f"HashKey={hash_key}&" + "&".join(f"{k}={v}" for k, v in sorted_params) + f"&HashIV={hash_iv}"
    # ECPay url-encode 規則
    encoded = url_encode_ecpay(raw)
    expected = hashlib.sha256(encoded.lower().encode()).hexdigest().upper()
    return expected == received
```

```python
# app/api/v1/webhooks.py
@router.post("/webhooks/ecpay", include_in_schema=False)
async def ecpay_webhook(
    request: Request,
    ecpay: EcpayClient = Depends(get_ecpay_client),
    payment_service: PaymentService = Depends(),
) -> Response:
    form = await request.form()
    params = dict(form)
    if not ecpay.verify_check_mac_value(params):
        raise EcpayWebhookError("invalid CheckMacValue")
    if params["RtnCode"] == "1":
        await payment_service.mark_paid(params["MerchantTradeNo"])
    return PlainTextResponse("1|OK")   # 綠界規定的 ack 字串
```

## DB schema

`payments`(對齊 `04-databases/00-overview.md` BaseModel):

```python
class Payment(BaseModel):
    __tablename__ = "payments"

    user_uid: Mapped[UUID] = mapped_column(PG_UUID, nullable=False)
    amount_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    provider: Mapped[str] = mapped_column(String(20), nullable=False)   # stripe / ecpay
    provider_id: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    idempotency_key: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
```

webhook event 去重表 `payment_events(provider, event_id)` unique。

## 不要做

- ❌ 跳過簽章驗(任何人可偽造 webhook 假裝付款成功)
- ❌ 用 redirect URL 上的 success flag 當付款成功(可被偽造)
- ❌ 信前端送的金額(必後端算)
- ❌ 用 float 算金額(精度問題)
- ❌ 漏 idempotency_key(網路重試會重複扣)
- ❌ 把第三方錯誤訊息直接回給前端(可能洩內部架構)
