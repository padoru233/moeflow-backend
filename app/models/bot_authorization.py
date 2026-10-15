import datetime

from mongoengine import BooleanField, DateTimeField, Document, StringField


class BotAuthorizationCode(Document):
    """A single-use authorization code for a configured Bot client."""

    meta = {
        "indexes": [
            "code_hash",
            {
                "fields": ["expires_at"],
                "expireAfterSeconds": 0,
            },
        ]
    }

    code_hash = StringField(required=True, unique=True)
    client_id = StringField(required=True)
    redirect_uri = StringField(required=True)
    user_id = StringField(required=True)
    code_challenge = StringField(required=True)
    expires_at = DateTimeField(required=True)
    used = BooleanField(default=False)
    created_at = DateTimeField(default=datetime.datetime.utcnow)
