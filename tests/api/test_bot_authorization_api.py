from app.apis.bot_authorization import create_code_challenge
from flask_apikit.exceptions import ValidateError
from tests import MoeAPITestCase


class BotAuthorizationAPITestCase(MoeAPITestCase):
    def setUp(self):
        super().setUp()
        self.app.config["BOT_AUTHORIZATION_CLIENTS"] = {
            "trans-progress": {
                "secret": "bot-client-secret",
                "redirect_uris": [
                    "https://bot.example.com/trans/auth/moeflow/callback"
                ],
            }
        }

    def test_exchanges_a_single_use_pkce_authorization_code(self):
        user = self.create_user("bot-admin")
        verifier = "a" * 64
        redirect_uri = "https://bot.example.com/trans/auth/moeflow/callback"

        created = self.post(
            "/v1/bot-authorization/codes",
            token=user.generate_token(),
            json={
                "client_id": "trans-progress",
                "redirect_uri": redirect_uri,
                "code_challenge": create_code_challenge(verifier),
            },
        )
        self.assertErrorEqual(created)
        code = created.json["code"]

        exchanged = self.post(
            "/v1/bot-authorization/tokens",
            json={
                "client_id": "trans-progress",
                "client_secret": "bot-client-secret",
                "redirect_uri": redirect_uri,
                "code": code,
                "code_verifier": verifier,
            },
        )
        self.assertErrorEqual(exchanged)
        self.assertEqual(exchanged.json["subject"], str(user.id))
        self.assertEqual(exchanged.json["name"], user.name)
        self.assertFalse(exchanged.json["admin"])

        replay = self.post(
            "/v1/bot-authorization/tokens",
            json={
                "client_id": "trans-progress",
                "client_secret": "bot-client-secret",
                "redirect_uri": redirect_uri,
                "code": code,
                "code_verifier": verifier,
            },
        )
        self.assertErrorEqual(replay, ValidateError)

    def test_rejects_an_invalid_pkce_verifier(self):
        user = self.create_user("bot-user")
        redirect_uri = "https://bot.example.com/trans/auth/moeflow/callback"
        created = self.post(
            "/v1/bot-authorization/codes",
            token=user.generate_token(),
            json={
                "client_id": "trans-progress",
                "redirect_uri": redirect_uri,
                "code_challenge": create_code_challenge("a" * 64),
            },
        )
        self.assertErrorEqual(created)

        exchanged = self.post(
            "/v1/bot-authorization/tokens",
            json={
                "client_id": "trans-progress",
                "client_secret": "bot-client-secret",
                "redirect_uri": redirect_uri,
                "code": created.json["code"],
                "code_verifier": "b" * 64,
            },
        )
        self.assertErrorEqual(exchanged, ValidateError)
