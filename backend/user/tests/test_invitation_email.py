from types import SimpleNamespace

from django.core import mail
from django.test import SimpleTestCase, override_settings

from user.utils import send_invitation_email

INVITATION = SimpleNamespace(email="invitee@example.com", role="standard")
VIDEO = "https://youtu.be/example?a=1&b=2"


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
                   DEFAULT_FROM_EMAIL="from@example.com")
class InvitationVideoTests(SimpleTestCase):
    def _send(self, language):
        send_invitation_email(INVITATION, "https://app/invite/x", language=language)
        msg = mail.outbox[-1]
        return msg.body, msg.alternatives[0][0]

    @override_settings(INVITATION_VIDEO_URL="")
    def test_no_video_line_when_unset(self):
        for language in ("pt-BR", "en"):
            text, html = self._send(language)
            self.assertNotIn("youtu", text)
            self.assertNotIn("vídeo tutorial", html)
            self.assertNotIn("tutorial video", html)
            self.assertIn("https://app/invite/x", text)

    @override_settings(INVITATION_VIDEO_URL=VIDEO)
    def test_video_link_in_both_languages(self):
        text, html = self._send("pt-BR")
        self.assertIn("assista ao vídeo tutorial:\n" + VIDEO, text)
        self.assertIn('href="https://youtu.be/example?a=1&amp;b=2"', html)
        self.assertNotIn("img.youtube.com", html)
        text, html = self._send("en")
        self.assertIn("watch the tutorial video:\n" + VIDEO, text)
        self.assertIn("Watch the tutorial video</a>", html)

    @override_settings(INVITATION_VIDEO_URL="https://youtu.be/5byUtzKvO7w")
    def test_youtube_thumbnail_links_to_video(self):
        _, html = self._send("pt-BR")
        self.assertIn('src="https://img.youtube.com/vi/5byUtzKvO7w/hqdefault.jpg"', html)
        self.assertIn('<a href="https://youtu.be/5byUtzKvO7w"><img', html)
        self.assertNotIn("<iframe", html)

    def test_youtube_id_forms(self):
        from user.utils import youtube_id
        for url in ("https://youtu.be/5byUtzKvO7w", "https://www.youtube.com/watch?v=5byUtzKvO7w",
                    "https://www.youtube.com/watch?feature=x&v=5byUtzKvO7w"):
            self.assertEqual(youtube_id(url), "5byUtzKvO7w")
        self.assertIsNone(youtube_id("https://example.com/video"))

    @override_settings(INVITATION_VIDEO_URL=VIDEO)
    def test_unknown_language_falls_back_to_portuguese(self):
        text, _ = self._send("de")
        self.assertIn("vídeo tutorial", text)
