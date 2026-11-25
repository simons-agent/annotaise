from html import escape
import re

from django.core.mail import EmailMultiAlternatives
from django.conf import settings

INVITATION_EMAIL_TEMPLATES = {
    "pt-BR": {
        "subject": "[Annotaise] Sua conta foi criada - complete seu cadastro",
        "text": """
Você foi convidado para acessar a Annotaise como {invitation.role}.

Complete seu cadastro pelo link:
{link}
{video_text}
Se você não reconhece este convite, ignore este e-mail.
""",
        "html": """
<!DOCTYPE html>
<html>
<body style="font-family: Arial, sans-serif; color: #333; line-height: 1.6;">
    <p>Olá!</p>

    <p>
        Uma conta foi criada para o seu e-mail na
        <strong>Annotaise – Alse Labeling Platform</strong>.
    </p>

    <p>Aqui estão seus dados para iniciar:</p>

    <ul>
        <li><strong>E-mail:</strong> {invitation.email}</li>
        <li><strong>Papel:</strong> {invitation.role}</li>
    </ul>

    <p>
        Para ativar sua conta e definir sua senha, clique no link abaixo:
    </p>

    <p style="margin: 20px 0;">
        <a href="{link}" 
           style="background-color: #4A6CF7; 
                  color: white; 
                  padding: 12px 18px; 
                  text-decoration: none; 
                  border-radius: 6px;
                  font-weight: bold;">
            Ativar minha conta
        </a>
    </p>

{video_html}
    <p>
        Se você não reconhece este convite, basta ignorar este e-mail.
    </p>

    <br>

    <p style="font-size: 14px; color: #555;">
        Bem-vindo à plataforma Annotaise.
    </p>

    <div style="margin-top: 25px; text-align: center;">
        <img src="" alt="Annotaise Logo" width="280">
    </div>
</body>
</html>
""",
    },
    "en": {
        "subject": "[Annotaise] Your account was created - complete your registration",
        "text": """
You were invited to access Annotaise as {invitation.role}.

Complete your registration using this link:
{link}
{video_text}
If you do not recognize this invitation, ignore this email.
""",
        "html": """
<!DOCTYPE html>
<html>
<body style="font-family: Arial, sans-serif; color: #333; line-height: 1.6;">
    <p>Hello!</p>

    <p>
        An account was created for your email on
        <strong>Annotaise - Alse Labeling Platform</strong>.
    </p>

    <p>Here are your details to get started:</p>

    <ul>
        <li><strong>Email:</strong> {invitation.email}</li>
        <li><strong>Role:</strong> {invitation.role}</li>
    </ul>

    <p>
        To activate your account and set your password, click the link below:
    </p>

    <p style="margin: 20px 0;">
        <a href="{link}" 
           style="background-color: #4A6CF7; 
                  color: white; 
                  padding: 12px 18px; 
                  text-decoration: none; 
                  border-radius: 6px;
                  font-weight: bold;">
            Activate my account
        </a>
    </p>

{video_html}
    <p>
        If you do not recognize this invitation, you can ignore this email.
    </p>

    <br>

    <p style="font-size: 14px; color: #555;">
        Welcome to the Annotaise platform.
    </p>

    <div style="margin-top: 25px; text-align: center;">
        <img src="" alt="Annotaise Logo" width="280">
    </div>
</body>
</html>
""",
    },
}

INVITATION_VIDEO_TEXT = {
    "pt-BR": "\nAntes de começar, assista ao vídeo tutorial:\n{url}\n",
    "en": "\nBefore you start, watch the tutorial video:\n{url}\n",
}
INVITATION_VIDEO_HTML = {
    "pt-BR": ("Antes de começar, assista ao vídeo tutorial:", "Assistir ao vídeo tutorial"),
    "en": ("Before you start, watch the tutorial video:", "Watch the tutorial video"),
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
        f'    <p style="margin: 20px 0 8px;">{escape(intro)}</p>\n'
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


def send_invitation_email(invitation, link, language=DEFAULT_INVITATION_EMAIL_LANGUAGE):
    template = get_invitation_email_template(language)
    lang = language if language in INVITATION_EMAIL_TEMPLATES else DEFAULT_INVITATION_EMAIL_LANGUAGE
    url = getattr(settings, "INVITATION_VIDEO_URL", "")
    video_text = INVITATION_VIDEO_TEXT[lang].format(url=url) if url else ""
    video_block = video_html(url, lang) if url else ""
    subject = template["subject"]
    text_message = template["text"].format(invitation=invitation, link=link, video_text=video_text)
    html_message = template["html"].format(
        invitation=invitation, link=link, video_html=video_block)

    msg = EmailMultiAlternatives(
        subject=subject,
        body=text_message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[invitation.email],
    )
    msg.attach_alternative(html_message, "text/html")
    msg.send(fail_silently=False)
