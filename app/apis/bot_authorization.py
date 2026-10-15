import base64
import datetime
import hashlib
import secrets
from typing import Any

from flask import current_app
from flask_apikit.exceptions import ValidateError

from app.core.views import MoeAPIView
from app.decorators.auth import token_required
from app.exceptions import NoPermissionError
from app.models.bot_authorization import BotAuthorizationCode
from app.models.user import User
from app.validators.bot_authorization import (
    BotAuthorizationCodeSchema,
    BotAuthorizationTokenSchema,
)

AUTHORIZATION_CODE_LIFETIME = datetime.timedelta(seconds=60)


def get_client(client_id: str) -> dict[str, Any] | None:
    clients = current_app.config["BOT_AUTHORIZATION_CLIENTS"]
    client = clients.get(client_id)
    if not isinstance(client, dict):
        return None
    redirect_uris = client.get("redirect_uris")
    if not isinstance(client.get("secret"), str) or not isinstance(redirect_uris, list):
        return None
    if not all(isinstance(uri, str) for uri in redirect_uris):
        return None
    return client


def get_valid_client(client_id: str, redirect_uri: str) -> dict[str, Any]:
    client = get_client(client_id)
    if client is None or redirect_uri not in client["redirect_uris"]:
        raise NoPermissionError("未授权的客户端或回调地址")
    return client


def sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def create_code_challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


class BotAuthorizationCodeAPI(MoeAPIView):
    @token_required
    def post(self):
        data = self.get_json(BotAuthorizationCodeSchema())
        get_valid_client(data["client_id"], data["redirect_uri"])

        raw_code = secrets.token_urlsafe(32)
        BotAuthorizationCode(
            code_hash=sha256(raw_code),
            client_id=data["client_id"],
            redirect_uri=data["redirect_uri"],
            user_id=str(self.current_user.id),
            code_challenge=data["code_challenge"],
            expires_at=datetime.datetime.utcnow() + AUTHORIZATION_CODE_LIFETIME,
        ).save()

        return {"code": raw_code}


class BotAuthorizationTokenAPI(MoeAPIView):
    def post(self):
        data = self.get_json(BotAuthorizationTokenSchema())
        client = get_valid_client(data["client_id"], data["redirect_uri"])
        if not secrets.compare_digest(data["client_secret"], client["secret"]):
            raise NoPermissionError("客户端凭据无效")

        authorization_code = BotAuthorizationCode.objects(
            code_hash=sha256(data["code"]),
            client_id=data["client_id"],
            redirect_uri=data["redirect_uri"],
            used=False,
            expires_at__gt=datetime.datetime.utcnow(),
        ).modify(set__used=True, new=False)
        if authorization_code is None:
            raise ValidateError({"code": ["授权码无效或已过期"]})

        if not secrets.compare_digest(
            authorization_code.code_challenge,
            create_code_challenge(data["code_verifier"]),
        ):
            raise ValidateError({"code_verifier": ["PKCE 校验失败"]})

        user = User.by_id(authorization_code.user_id)
        if user.banned:
            raise NoPermissionError("用户已被封禁")
        return {
            "subject": str(user.id),
            "name": user.name,
            "admin": user.admin,
        }
