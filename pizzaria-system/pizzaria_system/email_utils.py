import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Optional

from pizzaria_system.models import Comanda
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


def gerar_html_recibo(comanda: "Comanda") -> str:
    itens_html = "".join(
        f"""<tr>
          <td style="text-align:center">{item.quantidade}x</td>
          <td>{item.produto_rel.nome if item.produto_rel else (item.combo_rel.nome if item.combo_rel else 'XXXX')}</td>
          <td style="text-align:right">R$ {item.preco_unitario:.2f}</td>
          <td style="text-align:right">R$ {item.subtotal:.2f}</td>
        </tr>"""
        for item in comanda.pedido_itens
    )

    def nome_cliente(c: Comanda) -> Optional[str]:
        if c.cliente_rel:
            return c.cliente_rel.nome
        if c.observacao_geral and c.observacao_geral.startswith("Cliente: "):
            return c.observacao_geral[9:]
        return None

    cliente_nome = nome_cliente(comanda) or "XXXX"
    mesa_numero = comanda.mesa_rel.numero if comanda.mesa_rel else "XXXX"
    garcom_nome = comanda.garcom_rel.nome if comanda.garcom_rel else "XXXX"
    metodo_nome = comanda.metodo_pagamento_rel.nome if comanda.metodo_pagamento_rel else "XXXX"
    data_reg = comanda.data_registro.strftime("%d/%m/%Y %H:%M") if comanda.data_registro else "XXXX"

    troco_html = f"R$ {comanda.troco:.2f}" if comanda.troco > 0 else "XXXX"
    desconto_html = f"<p><b>Desconto:</b> -R$ {comanda.desconto_aplicado:.2f}</p>" if comanda.desconto_aplicado > 0 else ""
    entrega_html = f"<p><b>Taxa entrega:</b> R$ {comanda.taxa_entrega:.2f}</p>" if comanda.taxa_entrega > 0 else ""
    cupom_html = f"<p><b>Cupom:</b> {comanda.cod_promocional_rel.codigo} ({comanda.cod_promocional_rel.desconto_percentual}% OFF)</p>" if comanda.cod_promocional_rel else ""

    return f"""<html>
<head><meta charset="utf-8"><title>Recibo #{comanda.id}</title>
<style>
  body {{ font-family: monospace; padding: 20px; max-width: 400px; margin: 0 auto; }}
  h1 {{ text-align: center; font-size: 18px; }}
  h2 {{ text-align: center; font-size: 14px; color: #555; }}
  table {{ width: 100%; border-collapse: collapse; margin: 16px 0; font-size: 13px; }}
  th {{ border-bottom: 2px solid #333; padding: 6px 4px; text-align: left; }}
  td {{ border-bottom: 1px solid #DDD; padding: 6px 4px; }}
  .total-row {{ font-weight: bold; }}
  .footer {{ text-align: center; margin-top: 20px; font-size: 12px; color: #888; }}
  .line {{ border-top: 1px dashed #333; margin: 12px 0; }}
</style></head>
<body>
  <h1>RECIBO</h1>
  <h2>Comanda #{comanda.id}</h2>
  <div class="line"></div>
  <p><b>Mesa:</b> {mesa_numero}</p>
  <p><b>Garçom:</b> {garcom_nome}</p>
  <p><b>Cliente:</b> {cliente_nome}</p>
  <p><b>Pagamento:</b> {metodo_nome}</p>
  <p><b>Data:</b> {data_reg}</p>
  <div class="line"></div>
  <table>
    <tr><th>Qtd</th><th>Item</th><th>Valor</th><th>Subtotal</th></tr>
    {itens_html}
  </table>
  <div class="line"></div>
  <p><b>Subtotal:</b> R$ {comanda.preco_total:.2f}</p>
  {desconto_html}
  {entrega_html}
  <p style="font-size:16px"><b>VALOR A PAGAR: R$ {comanda.valor_a_pagar:.2f}</b></p>
  <div class="line"></div>
  <p><b>Troco:</b> {troco_html}</p>
  {cupom_html}
  <div class="footer">
    <p>Obrigado pela preferência!</p>
    <p>Pizzaria Forno di Resistenza</p>
  </div>
</body></html>"""


def send_receipt_email(comanda: "Comanda") -> bool:

    if not comanda.cliente_rel or not comanda.cliente_rel.email:
        return False

    html = gerar_html_recibo(comanda)
    to_email = comanda.cliente_rel.email
    subject = f"Recibo - Comanda #{comanda.id} - Forno di Resistenza"

    msg = MIMEMultipart("alternative")
    msg["From"] = settings.SMTP_FROM_EMAIL
    msg["To"] = to_email
    msg["Subject"] = subject

    plain_body = f"""Olá {comanda.cliente_rel.nome},\n\nSegue o recibo da sua comanda #{comanda.id}.\n\nAtenciosamente,\nPizzaria Forno di Resistenza"""

    msg.attach(MIMEText(plain_body, "plain", "utf-8"))
    msg.attach(MIMEText(html, "html", "utf-8"))

    try:
        server = smtplib.SMTP(settings.SMTP_SERVER, settings.SMTP_PORT)
        server.starttls()
        server.login(settings.SMTP_FROM_EMAIL, settings.SMTP_PASSWORD)
        server.sendmail(settings.SMTP_FROM_EMAIL, to_email, msg.as_string())
        server.quit()
        return True
    except Exception as e:
        print(f"Erro ao enviar recibo por e-mail: {e}")
        return False
