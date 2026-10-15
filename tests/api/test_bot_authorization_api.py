from app.apis.bot_authorization import create_code_challenge
from app.models.team import TeamRole
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

    def exchange_for(self, user):
        redirect_uri = "https://bot.example.com/trans/auth/moeflow/callback"
        verifier = "c" * 64
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
        exchanged = self.post(
            "/v1/bot-authorization/tokens",
            json={
                "client_id": "trans-progress",
                "client_secret": "bot-client-secret",
                "redirect_uri": redirect_uri,
                "code": created.json["code"],
                "code_verifier": verifier,
            },
        )
        self.assertErrorEqual(exchanged)
        return exchanged.json

    def test_reports_only_teams_the_user_creates_or_administers(self):
        team = self.create_team("owned")
        creator = self.get_creator(team)
        admin = self.create_user("team-admin")
        admin.join(team, TeamRole.by_system_code("admin"))
        member = self.create_user("team-member")
        member.join(team, TeamRole.by_system_code("member"))
        outsider = self.create_user("outsider")

        expected = [{"id": str(team.id), "name": team.name}]
        self.assertEqual(self.exchange_for(creator)["admin_teams"], expected)
        self.assertEqual(self.exchange_for(admin)["admin_teams"], expected)
        self.assertEqual(self.exchange_for(member)["admin_teams"], [])
        self.assertEqual(self.exchange_for(outsider)["admin_teams"], [])
