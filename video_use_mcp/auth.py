"""OAuth persistence behind the official MCP SDK's PKCE and client validation."""

from __future__ import annotations

import secrets
import time
from urllib.parse import urlencode, urlsplit, urlunsplit, parse_qsl

from mcp.server.auth.provider import (
    AccessToken,
    AuthorizationCode,
    AuthorizationParams,
    AuthorizeError,
    RefreshToken,
    RegistrationError,
    TokenError,
)
from mcp.shared.auth import OAuthClientInformationFull, OAuthToken

from .store import Store, digest

SCOPES = ["video:read", "video:write"]


class AuthProvider:
    def __init__(self, store: Store, origin: str):
        self.store = store
        self.origin = origin
        self.resource = origin + "/mcp"

    async def get_client(self, client_id):
        value = self.store.get("client", client_id)
        return OAuthClientInformationFull.model_validate(value) if value else None

    async def register_client(self, client_info):
        if not client_info.redirect_uris or len(client_info.redirect_uris) > 10:
            raise RegistrationError(
                "invalid_redirect_uri", "Provide between one and ten redirect URIs"
            )
        for uri in client_info.redirect_uris:
            url = urlsplit(str(uri))
            if (
                url.fragment
                or url.username
                or (
                    url.scheme != "https"
                    and not (
                        url.scheme == "http"
                        and url.hostname in {"127.0.0.1", "localhost", "::1"}
                    )
                )
            ):
                raise RegistrationError(
                    "invalid_redirect_uri",
                    "Redirects require HTTPS or a loopback address",
                )
        self.store.put(
            "client", client_info.client_id, client_info.model_dump(mode="json")
        )

    async def authorize(self, client, params: AuthorizationParams):
        if params.resource and params.resource != self.resource:
            raise AuthorizeError(
                "invalid_request", "Resource does not match this MCP server"
            )
        request_id = secrets.token_urlsafe(32)
        self.store.put(
            "authorization_request",
            digest(request_id),
            {
                "client_id": client.client_id,
                "client_name": client.client_name or "Your assistant",
                "params": params.model_dump(mode="json"),
            },
            ttl=600,
        )
        return self.origin + "/?authorize=" + request_id

    def consent(self, uid, request_id, allow=True):
        record = self.store.get(
            "authorization_request", digest(request_id), consume=True
        )
        if not record:
            raise ValueError(
                "This connection request expired. Connect again from your assistant."
            )
        params = AuthorizationParams.model_validate(record["params"])
        query = {"state": params.state} if params.state is not None else {}
        if allow:
            code = secrets.token_urlsafe(32)
            auth_code = AuthorizationCode(
                code=code,
                scopes=params.scopes or SCOPES,
                expires_at=time.time() + 120,
                client_id=record["client_id"],
                code_challenge=params.code_challenge,
                redirect_uri=params.redirect_uri,
                redirect_uri_provided_explicitly=params.redirect_uri_provided_explicitly,
                resource=self.resource,
                subject=uid,
            )
            self.store.put(
                "authorization_code",
                digest(code),
                auth_code.model_dump(mode="json"),
                ttl=120,
            )
            query["code"] = code
        else:
            query["error"] = "access_denied"
        url = urlsplit(str(params.redirect_uri))
        return urlunsplit(
            (
                url.scheme,
                url.netloc,
                url.path,
                urlencode(parse_qsl(url.query) + list(query.items())),
                "",
            )
        )

    async def load_authorization_code(self, client, authorization_code):
        value = self.store.get("authorization_code", digest(authorization_code))
        return AuthorizationCode.model_validate(value) if value else None

    async def exchange_authorization_code(self, client, authorization_code):
        # Consume atomically so two simultaneous exchanges cannot issue two grants.
        value = self.store.get(
            "authorization_code", digest(authorization_code.code), consume=True
        )
        if not value or value["client_id"] != client.client_id:
            raise TokenError("invalid_grant", "Authorization code was already used")
        return self.issue(value["subject"], client.client_id, value["scopes"])

    def issue(self, uid, client_id, scopes):
        access, refresh, family = (secrets.token_urlsafe(32) for _ in range(3))
        expires = int(time.time())
        self.store.put(
            "access",
            digest(access),
            {
                "client_id": client_id,
                "scopes": scopes,
                "expires_at": expires + 3600,
                "resource": self.resource,
                "subject": uid,
                "family": family,
            },
            ttl=3600,
        )
        self.store.put(
            "refresh",
            digest(refresh),
            {
                "client_id": client_id,
                "scopes": scopes,
                "expires_at": expires + 2592000,
                "resource": self.resource,
                "subject": uid,
                "family": family,
            },
            ttl=2592000,
        )
        self.store.put(
            "family",
            family,
            {"access": digest(access), "refresh": digest(refresh)},
            ttl=2592000,
        )
        return OAuthToken(
            access_token=access,
            token_type="Bearer",
            expires_in=3600,
            refresh_token=refresh,
            scope=" ".join(scopes),
        )

    async def load_refresh_token(self, client, refresh_token):
        value = self.store.get("refresh", digest(refresh_token))
        if not value or value["client_id"] != client.client_id:
            return None
        return RefreshToken(token=refresh_token, **value)

    async def exchange_refresh_token(self, client, refresh_token, scopes):
        value = self.store.get("refresh", digest(refresh_token.token), consume=True)
        if not value or value["client_id"] != client.client_id:
            raise TokenError("invalid_grant", "Refresh token was already used")
        if not set(scopes).issubset(value["scopes"]):
            raise TokenError("invalid_scope", "Scopes cannot be expanded")
        self.revoke_family(value["family"])
        return self.issue(value["subject"], client.client_id, scopes)

    async def load_access_token(self, token):
        value = self.store.get("access", digest(token))
        return AccessToken(token=token, **value) if value else None

    def revoke_family(self, family):
        pair = self.store.get("family", family, consume=True)
        if pair:
            self.store.delete("access", pair["access"])
            self.store.delete("refresh", pair["refresh"])

    async def revoke_token(self, token):
        kind = "access" if isinstance(token, AccessToken) else "refresh"
        value = self.store.get(kind, digest(token.token))
        if value:
            self.revoke_family(value["family"])
