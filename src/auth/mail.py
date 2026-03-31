import smtplib
from email.message import EmailMessage
from src.config import Config


def send_invite_email(to_email: str, alias: str, invite_token: str):
    """Отправка письма с логином/временным паролем"""
    msg = EmailMessage()
    msg["Subject"] = f"[{Config.PROJECT_NAME}] Приглашение и данные для входа"
    msg["From"] = Config.SMTP_USER
    msg["To"] = to_email

    invite_link = f"{Config.FRONTEND_URL}/signup?token={invite_token}"

    msg.set_content(
        f"""Здравствуйте {alias}!

        Вас пригласили в {Config.PROJECT_NAME}.
        Для завершения регистрации и установки пароля перейдите по ссылке:

        {invite_link}

        Логин: {to_email}

        Ссылка действует {Config.INVITE_TTL_HOURS} часов.

        Если вы не запрашивали доступ, просто проигнорируйте это письмо.
        """
    )
    
    with smtplib.SMTP(host=Config.SMTP_HOST, port=Config.SMTP_PORT) as s:
        if Config.SMTP_USER and Config.SMTP_PASS:
            s.starttls()
            s.login(Config.SMTP_USER, Config.SMTP_PASS)
        s.send_message(msg)