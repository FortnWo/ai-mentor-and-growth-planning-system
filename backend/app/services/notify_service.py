"""
Notification service — SMS and Email.

Phase 2: Provides the interface and stub implementations.
Phase 5: Real implementations activated when system_config is configured.

Error codes:
  NOTIFY_5001 — service not configured
  NOTIFY_5002 — send failure
"""
from __future__ import annotations

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

logger = logging.getLogger("ai_mentor.notify")


class NotifyConfigError(RuntimeError):
    """Raised when required notification service config is missing."""


class NotifySendError(RuntimeError):
    """Raised when the send operation fails."""


# ── SMS ──────────────────────────────────────────────────────────────────────

def _get_sms_config() -> dict | None:
    """Load SMS config from system_config table. Returns None if not configured."""
    try:
        import app.services.system_config_service as scs
        cfg = scs.get_sms_config()
        if not cfg or not cfg.get("access_key_id") or not cfg.get("access_key_secret"):
            return None
        return cfg
    except Exception:
        return None


def send_sms_code(phone: str, code: str) -> None:
    """
    Send a verification code via SMS.
    Raises NotifyConfigError if SMS is not configured.
    Raises NotifySendError on send failure.
    """
    cfg = _get_sms_config()
    if not cfg:
        raise NotifyConfigError("NOTIFY_5001: SMS service is not configured")

    vendor = cfg.get("vendor", "aliyun")
    try:
        if vendor == "aliyun":
            _send_sms_aliyun(phone, code, cfg)
        elif vendor == "tencent":
            _send_sms_tencent(phone, code, cfg)
        else:
            # custom / fallback — log and raise
            logger.warning("notify_service: unsupported SMS vendor=%s", vendor)
            raise NotifyConfigError(f"NOTIFY_5001: Unsupported SMS vendor: {vendor}")
    except (NotifyConfigError, NotifySendError):
        raise
    except Exception as exc:
        logger.error("notify_service: SMS send failed phone=%s error=%s", phone, exc)
        raise NotifySendError(f"NOTIFY_5002: SMS send failed: {exc}") from exc


def _send_sms_aliyun(phone: str, code: str, cfg: dict) -> None:
    try:
        from alibabacloud_dysmsapi20170525 import models as dysms_models
        from alibabacloud_dysmsapi20170525.client import Client
        from alibabacloud_tea_openapi import models as open_api_models
    except ImportError as exc:
        raise NotifyConfigError("NOTIFY_5001: alibabacloud SDK not installed") from exc

    config = open_api_models.Config(
        access_key_id=cfg["access_key_id"],
        access_key_secret=cfg["access_key_secret"],
        endpoint=cfg.get("endpoint", "dysmsapi.aliyuncs.com"),
    )
    client = Client(config)
    request = dysms_models.SendSmsRequest(
        phone_numbers=phone,
        sign_name=cfg.get("sign_name", ""),
        template_code=cfg.get("template_code", ""),
        template_param=f'{{"code":"{code}"}}',
    )
    client.send_sms(request)


def _send_sms_tencent(phone: str, code: str, cfg: dict) -> None:
    try:
        from tencentcloud.sms.v20210111 import sms_client, models as sms_models
        from tencentcloud.common import credential
    except ImportError as exc:
        raise NotifyConfigError("NOTIFY_5001: tencentcloud SDK not installed") from exc

    cred = credential.Credential(cfg["access_key_id"], cfg["access_key_secret"])
    client = sms_client.SmsClient(cred, cfg.get("region", "ap-guangzhou"))
    req = sms_models.SendSmsRequest()
    req.SmsSdkAppId = cfg.get("sdk_app_id", "")
    req.SignName = cfg.get("sign_name", "")
    req.TemplateId = cfg.get("template_code", "")
    req.TemplateParamSet = [code]
    req.PhoneNumberSet = [f"+86{phone}"]
    client.SendSms(req)


# ── Email ─────────────────────────────────────────────────────────────────────

def _get_smtp_config() -> dict | None:
    """Load SMTP config from system_config table. Returns None if not configured."""
    try:
        import app.services.system_config_service as scs
        cfg = scs.get_smtp_config()
        if not cfg or not cfg.get("smtp_host") or not cfg.get("from_email"):
            return None
        return cfg
    except Exception:
        return None


def send_email_code(email: str, code: str) -> None:
    """
    Send a verification code via email.
    Raises NotifyConfigError if SMTP is not configured.
    Raises NotifySendError on send failure.
    """
    cfg = _get_smtp_config()
    if not cfg:
        raise NotifyConfigError("NOTIFY_5001: Email (SMTP) service is not configured")

    try:
        _send_smtp(email, code, cfg)
    except (NotifyConfigError, NotifySendError):
        raise
    except Exception as exc:
        logger.error("notify_service: Email send failed to=%s error=%s", email, exc)
        raise NotifySendError(f"NOTIFY_5002: Email send failed: {exc}") from exc


def _send_smtp(to_email: str, code: str, cfg: dict) -> None:
    host = cfg["smtp_host"]
    port = int(cfg.get("smtp_port", 465))
    from_email = cfg["from_email"]
    password = cfg.get("email_password", "")
    sender_name = cfg.get("sender_name", "AI Mentor System")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = "验证码 — AI Mentor 系统"
    msg["From"] = f"{sender_name} <{from_email}>"
    msg["To"] = to_email

    body = (
        f"你的密码找回验证码为：\n\n"
        f"  {code}\n\n"
        f"验证码 {cfg.get('expire_minutes', 10)} 分钟内有效，请勿泄露给他人。"
    )
    msg.attach(MIMEText(body, "plain", "utf-8"))

    use_ssl = port == 465
    if use_ssl:
        with smtplib.SMTP_SSL(host, port) as server:
            server.login(from_email, password)
            server.sendmail(from_email, to_email, msg.as_string())
    else:
        with smtplib.SMTP(host, port) as server:
            server.starttls()
            server.login(from_email, password)
            server.sendmail(from_email, to_email, msg.as_string())


# ── Available methods ─────────────────────────────────────────────────────────

def get_available_methods() -> list[str]:
    """
    Return list of currently available password-reset methods.
    'admin' is always available. 'phone' and 'email' only when configured.
    """
    methods: list[str] = ["admin"]
    if _get_sms_config():
        methods.append("phone")
    if _get_smtp_config():
        methods.append("email")
    return methods
