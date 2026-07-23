import random

import aiosmtplib
from email.message import EmailMessage

from app.config.settings import get_settings

settings = get_settings()


def generate_code(length: int = 6) -> str:
    return "".join(str(random.randint(0, 9)) for _ in range(length))


async def send_verification_code(to_email: str, code: str) -> None:
    msg = EmailMessage()
    msg["From"] = settings.email_from
    msg["To"] = to_email
    msg["Subject"] = "伴行agent - 登录验证码"

    msg.set_content(
        f"""您好，

您的伴行agent 登录验证码为：

  {code}

验证码有效期为 5 分钟，请勿泄露给他人。

如果这不是您本人的操作，请忽略此邮件。

— 伴行agent 团队"""
    )

    await aiosmtplib.send(
        msg,
        hostname=settings.email_host,
        port=settings.email_port,
        username=settings.email_user,
        password=settings.email_pass,
        use_tls=True,
    )
