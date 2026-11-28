from html import escape
import re

from django.core.mail import EmailMultiAlternatives
from django.conf import settings

# Study 1 invitation (privdev/study1 fork). Written as a personal study invitation, not an
# "account created" notice: that wording, an empty <img> and a thin text part pushed the
# original template into Gmail's spam folder.
INVITATION_EMAIL_TEMPLATES = {
    "pt-BR": {
        "subject": "Convite para o Estudo 1 do PrivDev (AISE Lab, PUC-Rio)",
        "text": """Olá,

{inviter} convidou você para participar do Estudo 1 do projeto PrivDev, do AISE Lab da PUC-Rio.

No estudo, você classifica registros de fraquezas de software (catálogos CWE e CVE) quanto à sua relação com a privacidade: duas perguntas por registro, com uma breve justificativa. Pessoas da área jurídica e da área técnica respondem às mesmas perguntas.

O que pedimos:
- Parte 1: os 45 registros iniciais, com justificativa.
- Parte 2: pelo menos 150 registros.
- Meta: até 15 de dezembro. O formulário continua aberto depois dessa data.

Como começar:
{video_text}- Ative sua conta e defina sua senha (o link vale 7 dias):
{link}
- Preencha o perfil (uma única vez) e comece a Parte 1. O guia de anotação fica ao lado de cada registro.

Dúvidas, ou se o link vencer: responda a este e-mail.

Se você não esperava este convite, pode ignorar esta mensagem.

Equipe PrivDev
AISE Lab, PUC-Rio
""",
        "html": """<!DOCTYPE html>
<html lang="pt-BR">
<body style="font-family: Arial, sans-serif; color: #222; line-height: 1.6; max-width: 600px;">
    <p>Olá,</p>

    <p><strong>{inviter_html}</strong> convidou você para participar do <strong>Estudo 1 do projeto PrivDev</strong>, do AISE Lab da PUC-Rio.</p>

    <p>No estudo, você classifica registros de fraquezas de software (catálogos CWE e CVE) quanto à sua relação com a privacidade: duas perguntas por registro, com uma breve justificativa. Pessoas da área jurídica e da área técnica respondem às mesmas perguntas.</p>

    <p style="margin-bottom: 4px;"><strong>O que pedimos</strong></p>
    <ul style="margin-top: 0;">
        <li>Parte 1: os 45 registros iniciais, com justificativa.</li>
        <li>Parte 2: pelo menos 150 registros.</li>
        <li>Meta: até 15 de dezembro. O formulário continua aberto depois dessa data.</li>
    </ul>

    <p style="margin-bottom: 4px;"><strong>Como começar</strong></p>
{video_html}    <p style="margin-top: 0;">&bull; Ative sua conta e defina sua senha (o link vale 7 dias):</p>
    <p style="margin: 16px 0 20px;"><a href="{link}" style="display:inline-block; background-color:#1e2f93; color:#ffffff; padding:12px 18px; text-decoration:none; border-radius:6px; font-weight:bold;">Ativar conta e definir senha</a></p>
    <p>&bull; Preencha o perfil (uma única vez) e comece a Parte 1. O guia de anotação fica ao lado de cada registro.</p>

    <p>Dúvidas, ou se o link vencer: responda a este e-mail.</p>

    <p style="font-size: 13px; color: #555;">Se você não esperava este convite, pode ignorar esta mensagem.</p>

    <p>Equipe PrivDev<br>AISE Lab, PUC-Rio</p>
</body>
</html>
""",
    },
    "en": {
        "subject": "Invitation to PrivDev Study 1 (AISE Lab, PUC-Rio)",
        "text": """Hello,

{inviter} has invited you to take part in Study 1 of the PrivDev project at the AISE Lab, PUC-Rio.

In the study you classify software weakness records (the CWE and CVE catalogues) by how they relate to privacy: two questions per record, with a short justification. Legal and technical participants answer the same questions.

What we ask:
- Part 1: the 45 starting records, with a justification.
- Part 2: at least 150 records.
- Goal: by 15 December. The form stays open after that date.

How to start:
{video_text}- Activate your account and set your password (the link is valid for 7 days):
{link}
- Fill in the profile (once) and start Part 1. The annotation guide is shown next to every record.

Questions, or if the link expires: reply to this email.

If you were not expecting this invitation, you can ignore this message.

The PrivDev team
AISE Lab, PUC-Rio
""",
        "html": """<!DOCTYPE html>
<html lang="en">
<body style="font-family: Arial, sans-serif; color: #222; line-height: 1.6; max-width: 600px;">
    <p>Hello,</p>

    <p><strong>{inviter_html}</strong> has invited you to take part in <strong>Study 1 of the PrivDev project</strong> at the AISE Lab, PUC-Rio.</p>

    <p>In the study you classify software weakness records (the CWE and CVE catalogues) by how they relate to privacy: two questions per record, with a short justification. Legal and technical participants answer the same questions.</p>

    <p style="margin-bottom: 4px;"><strong>What we ask</strong></p>
    <ul style="margin-top: 0;">
        <li>Part 1: the 45 starting records, with a justification.</li>
        <li>Part 2: at least 150 records.</li>
        <li>Goal: by 15 December. The form stays open after that date.</li>
    </ul>

    <p style="margin-bottom: 4px;"><strong>How to start</strong></p>
{video_html}    <p style="margin-top: 0;">&bull; Activate your account and set your password (the link is valid for 7 days):</p>
    <p style="margin: 16px 0 20px;"><a href="{link}" style="display:inline-block; background-color:#1e2f93; color:#ffffff; padding:12px 18px; text-decoration:none; border-radius:6px; font-weight:bold;">Activate account and set password</a></p>
    <p>&bull; Fill in the profile (once) and start Part 1. The annotation guide is shown next to every record.</p>

    <p>Questions, or if the link expires: reply to this email.</p>

    <p style="font-size: 13px; color: #555;">If you were not expecting this invitation, you can ignore this message.</p>

    <p>The PrivDev team<br>AISE Lab, PUC-Rio</p>
</body>
</html>
""",
    },
}

INVITATION_VIDEO_TEXT = {
    "pt-BR": "- Antes de começar, assista ao vídeo tutorial (cerca de 13 minutos):\n{url}\n",
    "en": "- Before you start, watch the tutorial video (about 13 minutes):\n{url}\n",
}
INVITATION_VIDEO_HTML = {
    "pt-BR": ("&bull; Antes de começar, assista ao vídeo tutorial (cerca de 13 minutos):", "Assistir ao vídeo tutorial"),
    "en": ("&bull; Before you start, watch the tutorial video (about 13 minutes):", "Watch the tutorial video"),
}
_YOUTUBE_ID = re.compile(r"(?:youtu\.be/|youtube\.com/(?:watch\?(?:.*&)?v=|embed/|shorts/))([A-Za-z0-9_-]{11})")


def youtube_id(url):
    match = _YOUTUBE_ID.search(url or "")
    return match.group(1) if match else None


def video_html(url, language):
    """E-mail block for the tutorial video: a clickable YouTube thumbnail (mail clients such
    as Gmail strip iframes) plus a plain link; just the link for a non-YouTube URL."""
    intro, label = INVITATION_VIDEO_HTML[language]
    href = escape(url, quote=True)
    video = youtube_id(url)
    thumb = (
        f'        <a href="{href}"><img src="https://img.youtube.com/vi/{video}/hqdefault.jpg" '
        f'alt="{escape(label)}" width="360" style="display:block; border:0; border-radius:6px;"></a>\n'
        if video else ""
    )
    return (
        f'    <p style="margin: 0 0 8px;">{intro}</p>\n'
        f'    <div style="margin: 0 0 20px;">\n{thumb}'
        f'        <a href="{href}" style="display:inline-block; margin-top:8px; font-weight:bold;">&#9654; {escape(label)}</a>\n'
        f'    </div>\n'
    )


DEFAULT_INVITATION_EMAIL_LANGUAGE = "pt-BR"
SUPPORTED_INVITATION_EMAIL_LANGUAGES = tuple(INVITATION_EMAIL_TEMPLATES.keys())


def get_invitation_email_template(language):
    return INVITATION_EMAIL_TEMPLATES.get(
        language,
        INVITATION_EMAIL_TEMPLATES[DEFAULT_INVITATION_EMAIL_LANGUAGE],
    )


def _inviter_name(invitation, language):
    person = getattr(invitation, "invited_by", None)
    name = " ".join(filter(None, [getattr(person, "first_name", ""), getattr(person, "last_name", "")])).strip()
    return name or ("A equipe do PrivDev" if language == "pt-BR" else "The PrivDev team")


def send_invitation_email(invitation, link, language=DEFAULT_INVITATION_EMAIL_LANGUAGE):
    template = get_invitation_email_template(language)
    lang = language if language in INVITATION_EMAIL_TEMPLATES else DEFAULT_INVITATION_EMAIL_LANGUAGE
    url = getattr(settings, "INVITATION_VIDEO_URL", "")
    video_text = INVITATION_VIDEO_TEXT[lang].format(url=url) if url else ""
    video_block = video_html(url, lang) if url else ""
    subject = template["subject"]
    inviter = _inviter_name(invitation, lang)
    text_message = template["text"].format(
        invitation=invitation, link=link, video_text=video_text, inviter=inviter)
    html_message = template["html"].format(
        invitation=invitation, link=escape(link, quote=True), video_html=video_block,
        inviter_html=escape(inviter))

    msg = EmailMultiAlternatives(
        subject=subject,
        body=text_message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[invitation.email],
    )
    msg.attach_alternative(html_message, "text/html")
    msg.send(fail_silently=False)
