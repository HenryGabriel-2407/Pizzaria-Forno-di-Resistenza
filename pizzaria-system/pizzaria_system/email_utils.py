import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from pizzaria_system.settings import Settings

settings = Settings()


def send_reset_password_email(to_email: str, code: str, ttl_minutes: int) -> bool:
    """
    Envia e-mail HTML com código de redefinição de senha.
    """
    subject = "Redefinição de Senha - Forno di Resistenza"

    template_path = Path(__file__).parent / "templates" / "reset_password.html"
    with open(template_path, "r", encoding="utf-8") as f:
        html_template = f.read()

    # Substitui os placeholders
    html_body = html_template.replace("{{code}}", code).replace("{{ttl_minutes}}", str(ttl_minutes))

    plain_body = f"Seu código de redefinição de senha é: {code}\n\nO código expira em {ttl_minutes} minutos.\n\nSe você não solicitou esta redefinição, ignore este e-mail."

    msg = MIMEMultipart("alternative")
    msg["From"] = settings.SMTP_FROM_EMAIL
    msg["To"] = to_email
    msg["Subject"] = subject

    part_plain = MIMEText(plain_body, "plain", "utf-8")
    part_html = MIMEText(html_body, "html", "utf-8")
    msg.attach(part_plain)
    msg.attach(part_html)

    try:
        server = smtplib.SMTP(settings.SMTP_SERVER, settings.SMTP_PORT)
        server.starttls()
        server.login(settings.SMTP_FROM_EMAIL, settings.SMTP_PASSWORD)
        server.sendmail(settings.SMTP_FROM_EMAIL, to_email, msg.as_string())
        server.quit()
        return True
    except Exception as e:
        print(f"Erro ao enviar e-mail: {e}")
        return False


# Mantém a função genérica send_email se necessário
def send_email(to_email: str, subject: str, body: str) -> bool:
    # Para compatibilidade com outros usos, mantemos versão simples (pode ser removida se não for mais utilizada)
    msg = MIMEMultipart()
    msg["From"] = settings.SMTP_FROM_EMAIL
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain", "utf-8"))

    try:
        server = smtplib.SMTP(settings.SMTP_SERVER, settings.SMTP_PORT)
        server.starttls()
        server.login(settings.SMTP_FROM_EMAIL, settings.SMTP_PASSWORD)
        server.sendmail(settings.SMTP_FROM_EMAIL, to_email, msg.as_string())
        return True
    except Exception:
        return False
