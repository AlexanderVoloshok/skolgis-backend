import smtplib
from email.message import EmailMessage
from config import Config


def send_invite_email(to_email: str, alias: str, temp_password: str):
    """Отправка письма с логином/временным паролем"""
    msg = EmailMessage()
    msg["Subject"] = f"[{Config.PROJECT_NAME}] Приглашение и данные для входа"
    msg["From"] = Config.MAIL_FROM
    msg["To"] = to_email
    msg.set_content(
        f"""Здравствуйте {alias}!

        Вас пригласили в {Config.PROJECT_NAME}.
        Данные для входа:

        Логин: {to_email}
        Пароль: {temp_password}

        Ссылка на вход: http://89.223.68.75/skolgis-frontend/
        Ссылка действует {Config.INVITE_TTL_HOURS} часов.

        Если вы не ожидаете это письмо — просто игнорируйте его.
        """
    )
    with smtplib.SMTP(host=Config.SMTP_HOST, port=Config.SMTP_PORT) as s:
        if Config.SMTP_USER and Config.SMTP_PASS:
            s.starttls()
            s.login(Config.SMTP_USER, Config.SMTP_PASS)
        s.send_message(msg)