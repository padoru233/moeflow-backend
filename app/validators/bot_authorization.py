from marshmallow import fields

from .custom_schema import DefaultSchema


class BotAuthorizationCodeSchema(DefaultSchema):
    client_id = fields.Str(required=True)
    redirect_uri = fields.Url(required=True)
    code_challenge = fields.Str(required=True)


class BotAuthorizationTokenSchema(DefaultSchema):
    client_id = fields.Str(required=True)
    client_secret = fields.Str(required=True)
    redirect_uri = fields.Url(required=True)
    code = fields.Str(required=True)
    code_verifier = fields.Str(required=True)
