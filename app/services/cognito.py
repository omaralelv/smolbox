from __future__ import annotations

from dataclasses import dataclass
from functools import cached_property
import secrets
import string

from app.core.config import Settings
from app.models.user import User


class CognitoSyncError(RuntimeError):
    pass


@dataclass
class CognitoUserSync:
    settings: Settings

    @property
    def enabled(self) -> bool:
        return self.settings.cognito_enabled

    def ensure_user(self, user: User, *, password: str | None = None) -> str | None:
        if not self.enabled:
            return None

        existing_sub = self._get_user_sub(user.email)
        if existing_sub is None:
            existing_sub = self._create_user(user, temporary_password=password)
        elif password:
            self.set_password(user.email, password, temporary=True)

        if user.is_active:
            self.enable_user(user.email)
        else:
            self.disable_user(user.email)
        return existing_sub

    def set_password(self, email: str, password: str, *, temporary: bool = True) -> None:
        if not self.enabled:
            return
        self.client.admin_set_user_password(
            UserPoolId=self._user_pool_id(),
            Username=email,
            Password=password,
            Permanent=not temporary,
        )

    def enable_user(self, email: str) -> None:
        if not self.enabled:
            return
        self.client.admin_enable_user(
            UserPoolId=self._user_pool_id(),
            Username=email,
        )

    def disable_user(self, email: str) -> None:
        if not self.enabled:
            return
        self.client.admin_disable_user(
            UserPoolId=self._user_pool_id(),
            Username=email,
        )

    def delete_user(self, email: str) -> None:
        if not self.enabled:
            return
        try:
            self.client.admin_delete_user(
                UserPoolId=self._user_pool_id(),
                Username=email,
            )
        except self.client.exceptions.UserNotFoundException:
            return

    def _create_user(self, user: User, *, temporary_password: str | None) -> str:
        temporary_password = temporary_password or _generate_temporary_password()
        attributes = [
            {"Name": "email", "Value": user.email},
            {"Name": "email_verified", "Value": "true"},
            {"Name": "name", "Value": user.full_name},
        ]
        payload = {
            "UserPoolId": self._user_pool_id(),
            "Username": user.email,
            "UserAttributes": attributes,
            "DesiredDeliveryMediums": ["EMAIL"],
            "TemporaryPassword": temporary_password,
        }

        try:
            response = self.client.admin_create_user(**payload)
        except self.client.exceptions.UsernameExistsException:
            existing_sub = self._get_user_sub(user.email)
            if existing_sub is not None:
                return existing_sub
            raise

        user_payload = response.get("User", {})
        subject = self._extract_sub(user_payload.get("Attributes", []))
        if subject:
            return subject

        existing_sub = self._get_user_sub(user.email)
        if existing_sub:
            return existing_sub
        raise CognitoSyncError("Cognito did not return a user id")
    def _get_user_sub(self, email: str) -> str | None:
        try:
            response = self.client.admin_get_user(
                UserPoolId=self._user_pool_id(),
                Username=email,
            )
        except self.client.exceptions.UserNotFoundException:
            return None
        return self._extract_sub(response.get("UserAttributes", []))

    def _extract_sub(self, attributes: list[dict[str, str]]) -> str | None:
        for attribute in attributes:
            if attribute.get("Name") == "sub" and attribute.get("Value"):
                return attribute["Value"]
        return None

    @cached_property
    def client(self):
        try:
            import boto3
        except ImportError as exc:  # pragma: no cover - dependency configuration
            raise CognitoSyncError("boto3 is required when Cognito is enabled") from exc

        return boto3.client(
            "cognito-idp",
            region_name=self.settings.aws_region,
            aws_access_key_id=self.settings.aws_access_key_id,
            aws_secret_access_key=self.settings.aws_secret_access_key,
            aws_session_token=self.settings.aws_session_token or None,
        )

    def _user_pool_id(self) -> str:
        if not self.settings.cognito_user_pool_id:
            raise CognitoSyncError("COGNITO_USER_POOL_ID is required when Cognito is enabled")
        return self.settings.cognito_user_pool_id


def _generate_temporary_password() -> str:
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*()-_=+"
    required = [
        secrets.choice(string.ascii_uppercase),
        secrets.choice(string.ascii_lowercase),
        secrets.choice(string.digits),
        secrets.choice("!@#$%^&*()-_=+"),
    ]
    required.extend(secrets.choice(alphabet) for _ in range(20))
    return "".join(secrets.SystemRandom().sample(required, len(required)))
