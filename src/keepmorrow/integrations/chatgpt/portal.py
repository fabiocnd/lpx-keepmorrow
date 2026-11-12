"""Trusted human interaction routes for the private preservation application.

Browser sessions, exact-origin requests, CSRF challenges, and deliberate human
gestures are independent of every MCP tool argument and bearer-only request.
Copyright 2026 Lopix Neural Inc. All rights reserved.
"""

from __future__ import annotations

import asyncio
import base64
from collections.abc import Awaitable, Callable
from dataclasses import asdict, dataclass, fields
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import secrets
import stat
import threading
import time
from typing import Any
from urllib.parse import unquote, urlencode, urlsplit

import httpx
from mcp.server.auth.provider import TokenVerifier
from starlette.applications import Starlette
from starlette.concurrency import run_in_threadpool
from starlette.middleware import Middleware
from starlette.requests import Request
from starlette.responses import JSONResponse, RedirectResponse, Response
from starlette.routing import Route
from starlette.types import ASGIApp, Receive, Scope, Send

from ...access import AccessDenied, AccessError, Grant, Principal
from ...application.configuration import ConfigurationError
from ...application.service import PreservationService, workspace_id
from ...archive.filesystem import open_regular
from ...archive.model import ArchiveError
from ...catalog import query as catalog_query
from ...catalog.model import CatalogError, collection_summary
from ...formats import check_json_budget
from ...operations import (
    AssociationParameters, ImportParameters, OperationBusy, OperationError,
    PackageParameters, RecoveryParameters, UnpackParameters,
)
from ...persistence import PersistenceError
from ...transfers import TransferLimitExceeded
from .authentication import AuthenticationConfig, ConfiguredTokenVerifier
from .human_sessions import HumanSession, HumanSessions
from .server import MAX_RESULT_BYTES, _browse, _optional_identifier, _page
from .streaming import VerifiedDownloadResponse, receive_stream

_SESSION_COOKIE = "lpx_keepmorrow_session"
_STATE_COOKIE = "lpx_keepmorrow_oauth_state"
_MAX_JSON_BYTES = 64 * 1024
_ELIGIBILITY_VERSION = "eligible-content-v1"
ELIGIBILITY_STATEMENT = (
    "I own or am authorized to process this selected content, confirm that it is eligible "
    "for the configured service, and authorize the displayed processing scope and recipients."
)


class _RequestError(ValueError):
    pass


class _AuthenticationRequired(AccessDenied):
    pass


def _error(code: str, message: str, status: int) -> JSONResponse:
    return JSONResponse({"error_code": code, "message": message}, status_code=status)


def _json(value: Any, *, status: int = 200) -> Response:
    encoded = json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")
    if len(encoded) > MAX_RESULT_BYTES:
        return _error("result_too_large", "Reduce the page size or narrow the selection.", 413)
    return Response(encoded, status_code=status, media_type="application/json")


def _fields(value: dict[str, Any], required: set[str], optional: set[str] | None = None) -> None:
    if not required <= value.keys() or value.keys() - required - (optional or set()):
        raise _RequestError()


def _single_header(request: Request, name: str) -> str | None:
    values = request.headers.getlist(name)
    if len(values) > 1:
        raise _RequestError()
    return values[0] if values else None


def _decode_json(data: bytes) -> dict[str, Any]:
    try:
        check_json_budget(data, max_bytes=_MAX_JSON_BYTES, max_depth=24, max_tokens=10_000)

        def unique(pairs):
            result = {}
            for key, value in pairs:
                if key in result:
                    raise _RequestError()
                result[key] = value
            return result

        def reject_constant(value):
            raise _RequestError()

        result = json.loads(data.decode("utf-8"), object_pairs_hook=unique, parse_constant=reject_constant)
        if not isinstance(result, dict):
            raise _RequestError()
        return result
    except (ValueError, UnicodeError, RecursionError, ArchiveError) as error:
        raise _RequestError() from error


async def _body(request: Request) -> dict[str, Any]:
    """Read bounded JSON metadata and reject ambiguous framing or duplicate fields.

    The streaming byte cap applies even without Content-Length. Binary uploads
    use a separate reader and must not pass through this buffered JSON path.
    """
    content_type = _single_header(request, "content-type")
    if content_type is None or content_type.split(";", 1)[0].lower() != "application/json":
        raise _RequestError()
    length = _single_header(request, "content-length")
    if length is not None and (not length.isascii() or not length.isdigit() or int(length) > _MAX_JSON_BYTES):
        raise _RequestError()
    chunks = bytearray()
    async for chunk in request.stream():
        if len(chunks) + len(chunk) > _MAX_JSON_BYTES:
            raise _RequestError()
        chunks.extend(chunk)
    if length is not None and len(chunks) != int(length):
        raise _RequestError()
    return _decode_json(bytes(chunks))


def _safe(endpoint: Callable[[Request], Awaitable[Response]]) -> Callable[[Request], Awaitable[Response]]:
    async def guarded(request: Request) -> Response:
        try:
            return await endpoint(request)
        except _AuthenticationRequired:
            return _error("authentication_required", "Sign in through the secure portal to continue.", 401)
        except AccessDenied:
            return _error("access_denied", "The requested access or human interaction is unavailable.", 403)
        except (OperationBusy, TransferLimitExceeded):
            return _error("busy", "A resource limit or active operation prevents admission.", 429)
        except (_RequestError, AccessError, OperationError):
            return _error("invalid_request", "The request does not satisfy the supported input or operation state.", 400)
        except (ArchiveError, CatalogError):
            return _error("validation_failed", "The selected material could not satisfy its preservation contract.", 422)
        except (ValueError, TypeError, KeyError):
            return _error("invalid_request", "The request does not satisfy the supported input or operation state.", 400)
        except (PersistenceError, OSError):
            return _error("unavailable", "The service could not complete the request.", 503)
        except Exception:
            # An HTTP error must not serialize exception causes, credentials,
            # submitted content, query text, source names, or filesystem paths.
            return _error("unavailable", "The service could not complete the request.", 503)
    return guarded


class _PortalSecurity:
    """Enforce the configured public authority before any mounted HTTP route.

    A reverse proxy or tunnel must preserve the configured Host value. Browser
    mutation routes additionally require an exact Origin and session-bound CSRF;
    this outer middleware does not establish a user's identity or resource grant.
    """

    def __init__(self, app: ASGIApp, *, origin: str) -> None:
        self.app, self.origin = app, origin
        self.host = urlsplit(origin).netloc

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        headers = scope.get("headers", [])
        hosts = [value.decode("latin-1") for name, value in headers if name.lower() == b"host"]
        origins = [value.decode("latin-1") for name, value in headers if name.lower() == b"origin"]
        if hosts != [self.host] or len(origins) > 1 or (origins and origins != [self.origin]):
            await _error("access_denied", "The request origin is unavailable.", 403)(scope, receive, send)
            return

        async def secured(message):
            if message["type"] == "http.response.start":
                message["headers"] = list(message.get("headers", [])) + [
                    (b"cache-control", b"no-store"), (b"x-content-type-options", b"nosniff"),
                    (b"referrer-policy", b"no-referrer"), (b"x-frame-options", b"DENY"),
                    (b"content-security-policy", b"default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"),
                ]
                if self.origin.startswith("https:"):
                    message["headers"].append((b"strict-transport-security", b"max-age=31536000"))
            await send(message)
        await self.app(scope, receive, secured)


@dataclass(frozen=True, slots=True)
class _OAuthAttempt:
    verifier: str
    expires_at: int


def create_portal(service: PreservationService, verifier: TokenVerifier | None = None) -> Starlette:
    """Build the trusted portal; the caller owns worker and maintenance lifespan.

    OAuth mode requires a registered browser authorization-code client with
    PKCE and the configured resource audience. Operator mode requires the CLI's
    owner-only local key file and is restricted by configuration to loopback.
    """
    configuration = service.configuration
    origin = configuration.public_origin
    secure = configuration.mode == "oauth"
    sessions = HumanSessions(service.database)
    # Authorization attempts are bounded, process-local state. A restart
    # invalidates unfinished browser sign-ins instead of persisting PKCE secrets.
    pending_oauth: dict[str, _OAuthAttempt] = {}
    upload_slots = threading.BoundedSemaphore(2)
    operator_digest: bytes | None = None
    oauth_secret: str | None = None
    if secure:
        if verifier is None:
            verifier = ConfiguredTokenVerifier(AuthenticationConfig(
                issuer=configuration.oauth_issuer, audience=configuration.resource_url,
                jwks_uri=configuration.oauth_jwks_uri,
            ))
        if configuration.browser_oauth.client_secret_env:
            oauth_secret = os.environ.get(configuration.browser_oauth.client_secret_env)
            if not isinstance(oauth_secret, str) or not 1 <= len(oauth_secret) <= 4096:
                raise ConfigurationError("The registered browser client secret is unavailable.")
    else:
        key_path = service.root / "operator.key"
        try:
            info = key_path.lstat()
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or (os.name == "posix" and info.st_mode & 0o077):
                raise ConfigurationError("The local operator key must be an owner-only ordinary file.")
            with open_regular(key_path) as key_file:
                key_bytes = key_file.read(66)
            if re.fullmatch(b"[0-9a-f]{64}\n?", key_bytes) is None:
                raise ConfigurationError("The local operator key is unavailable.")
            operator_digest = hashlib.sha256(key_bytes.rstrip(b"\n")).digest()
        except (OSError, ArchiveError) as error:
            raise ConfigurationError("The local operator key is unavailable.") from error

    def require_origin(request: Request) -> None:
        if _single_header(request, "origin") != origin:
            raise AccessDenied()

    def identity(request: Request, *, mutate: bool = False) -> tuple[Principal, HumanSession, str]:
        """Require a live browser session; bearer-only requests cannot act here."""
        if mutate:
            require_origin(request)
        token = request.cookies.get(_SESSION_COOKIE)
        if token is None:
            raise _AuthenticationRequired()
        csrf = _single_header(request, "x-csrf-token") if mutate else None
        if mutate and csrf is None:
            raise AccessDenied()
        session = sessions.require(token, csrf=csrf)
        return service.principal(session.principal_id), session, token

    def set_session(response: Response, token: str) -> None:
        response.set_cookie(_SESSION_COOKIE, token, max_age=900, secure=secure, httponly=True, samesite="lax", path="/")

    def policy_scope(grant: Grant) -> dict[str, Any]:
        # Presentation and challenge hashing share this declaration, so the
        # accepted actions, recipient, policy digests, and eligibility text cannot
        # silently diverge from the values returned for human review.
        return {
            "grant_id": grant.grant_id, "grant_version": grant.grant_version,
            "resource_id": grant.resource_id, "generation": grant.generation,
            "actions": sorted(grant.actions), "policies": service.policies.as_dict(),
            "purpose": grant.purpose, "recipient": grant.recipient,
            "eligibility_version": _ELIGIBILITY_VERSION, "eligibility_statement": ELIGIBILITY_STATEMENT,
        }

    def scope_digest(grant: Grant) -> str:
        return hashlib.sha256(json.dumps(policy_scope(grant), sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()

    async def public_config(request: Request) -> Response:
        return _json({"mode": configuration.mode, "login_url": "/auth/login" if secure else None,
                      "operator_login_url": None if secure else "/auth/operator", "portal_url": origin + "/portal"})

    async def local_login(request: Request) -> Response:
        require_origin(request)
        if secure or operator_digest is None:
            raise AccessDenied()
        body = await _body(request)
        _fields(body, {"key"})
        key = body["key"]
        if not isinstance(key, str) or re.fullmatch(r"[0-9a-f]{64}", key) is None:
            raise AccessDenied()
        if not hmac.compare_digest(hashlib.sha256(key.encode("ascii")).digest(), operator_digest):
            raise AccessDenied()
        token = await run_in_threadpool(sessions.create, configuration.principals[0].principal_id, expires_at=int(time.time()) + 900)
        response = _json({"authenticated": True})
        set_session(response, token)
        return response

    async def oauth_login(request: Request) -> Response:
        if not secure:
            raise AccessDenied()
        now = int(time.time())
        for key, attempt in tuple(pending_oauth.items()):
            if attempt.expires_at <= now:
                del pending_oauth[key]
        if len(pending_oauth) >= 100:
            raise OperationBusy("The browser sign-in queue is full.")
        state = secrets.token_hex(32)
        proof = secrets.token_urlsafe(64)
        pending_oauth[state] = _OAuthAttempt(proof, now + 300)
        challenge = base64.urlsafe_b64encode(hashlib.sha256(proof.encode("ascii")).digest()).rstrip(b"=").decode("ascii")
        oauth = configuration.browser_oauth
        query = urlencode({
            "response_type": "code", "client_id": oauth.client_id,
            "redirect_uri": origin + "/auth/callback", "scope": "keepmorrow:access",
            "resource": configuration.resource_url, "state": state,
            "code_challenge": challenge, "code_challenge_method": "S256",
        })
        response = RedirectResponse(oauth.authorization_endpoint + "?" + query, status_code=303)
        response.set_cookie(_STATE_COOKIE, state, max_age=300, secure=True, httponly=True, samesite="lax", path="/auth")
        return response

    async def exchange_code(code: str, proof: str) -> str:
        oauth = configuration.browser_oauth
        data = {"grant_type": "authorization_code", "code": code, "code_verifier": proof,
                "redirect_uri": origin + "/auth/callback", "resource": configuration.resource_url}
        authentication = None
        if oauth_secret is None:
            data["client_id"] = oauth.client_id
        else:
            authentication = (oauth.client_id, oauth_secret)
        async with asyncio.timeout(10):
            async with httpx.AsyncClient(follow_redirects=False, trust_env=False, timeout=10) as client:
                async with client.stream("POST", oauth.token_endpoint, data=data, auth=authentication,
                                         headers={"Accept": "application/json", "Accept-Encoding": "identity"}) as response:
                    if response.status_code != 200 or response.headers.get("content-encoding", "identity") != "identity":
                        raise AccessDenied()
                    encoded = bytearray()
                    async for chunk in response.aiter_raw(chunk_size=16_384):
                        if len(encoded) + len(chunk) > _MAX_JSON_BYTES:
                            raise AccessDenied()
                        encoded.extend(chunk)
        result = _decode_json(bytes(encoded))
        token = result.get("access_token")
        if (not isinstance(token, str) or not token.isascii() or not 1 <= len(token) <= 16_384
                or not isinstance(result.get("token_type"), str) or result["token_type"].lower() != "bearer"):
            raise AccessDenied()
        return token

    async def oauth_callback(request: Request) -> Response:
        if not secure:
            raise AccessDenied()
        state, cookie, code = request.query_params.get("state"), request.cookies.get(_STATE_COOKIE), request.query_params.get("code")
        if (not isinstance(state, str) or re.fullmatch(r"[0-9a-f]{64}", state) is None
                or not isinstance(cookie, str) or not hmac.compare_digest(state, cookie)
                or len(request.query_params.getlist("state")) != 1 or len(request.query_params.getlist("code")) != 1
                or not isinstance(code, str) or not 1 <= len(code) <= 4096
                or any(ord(char) < 33 or ord(char) > 126 for char in code)):
            raise AccessDenied()
        # Consume the browser-bound attempt before awaiting the token exchange.
        # A duplicate callback cannot redeem the same local proof concurrently.
        attempt = pending_oauth.pop(state, None)
        if attempt is None or attempt.expires_at <= int(time.time()) or "error" in request.query_params:
            raise AccessDenied()
        access_token = await verifier.verify_token(await exchange_code(code, attempt.verifier))
        if (access_token is None or access_token.subject is None or not access_token.claims
                or access_token.client_id != configuration.browser_oauth.client_id
                or type(access_token.expires_at) is not int or access_token.expires_at <= int(time.time())
                or attempt.expires_at <= int(time.time())):
            raise AccessDenied()
        principal = configuration.principal(access_token.claims.get("iss"), access_token.subject)
        token = await run_in_threadpool(sessions.create, principal.principal_id, expires_at=access_token.expires_at)
        response = RedirectResponse(origin + "/portal", status_code=303)
        set_session(response, token)
        response.delete_cookie(_STATE_COOKIE, path="/auth", secure=True, httponly=True, samesite="lax")
        return response

    async def logout(request: Request) -> Response:
        _, _, token = await run_in_threadpool(identity, request, mutate=True)
        await run_in_threadpool(sessions.end, token)
        response = _json({"authenticated": False})
        response.delete_cookie(_SESSION_COOKIE, path="/", secure=secure, httponly=True, samesite="lax")
        return response

    async def session_status(request: Request) -> Response:
        principal, session, token = await run_in_threadpool(identity, request)
        options = await run_in_threadpool(service.consent_options, principal)
        grants = await run_in_threadpool(service.access.list_grants, principal)
        return _json({"csrf": sessions.csrf(token), "mode": configuration.mode,
                      "expires_at": session.expires_at, "options": options,
                      "grants": [{**asdict(grant), "actions": sorted(grant.actions)} for grant in grants],
                      "portal_url": origin + "/portal"})

    async def options(request: Request) -> Response:
        principal, _, _ = await run_in_threadpool(identity, request)
        if set(request.query_params) - {"offset"} or len(request.query_params.getlist("offset")) > 1:
            raise _RequestError()
        offset = int(request.query_params.get("offset", "0"))
        _page(offset, 50)
        return _json(await run_in_threadpool(service.consent_options, principal, offset=offset))

    async def consent_prepare(request: Request) -> Response:
        principal, session, _ = await run_in_threadpool(identity, request, mutate=True)
        body = await _body(request)
        _fields(body, {"resource_id", "generation", "actions"})

        def prepare():
            grant = service.prepare_consent(principal, **body)
            challenge = sessions.challenge(session, kind="consent", object_id=grant.grant_id, document_digest=scope_digest(grant))
            return {**policy_scope(grant), "challenge": challenge}
        return _json(await run_in_threadpool(prepare))

    async def consent_accept(request: Request) -> Response:
        principal, session, _ = await run_in_threadpool(identity, request, mutate=True)
        body = await _body(request)
        checks = {"accepted_terms", "acknowledged_privacy", "authorized_scope", "eligible_content"}
        required = {"grant_id", "grant_version", "resource_id", "generation", "actions", "policies", "challenge"} | checks
        _fields(body, required, {"purpose", "recipient", "eligibility_version", "eligibility_statement"})
        if any(body[name] is not True for name in checks):
            raise AccessDenied()

        def accept():
            # Challenge consumption, scoped acceptance, and its retained context
            # commit together. A rejected receipt leaves no partial acceptance.
            with service.database.transaction() as connection:
                grant = service.access.get_grant(principal, grant_id=body["grant_id"], connection=connection)
                expected = policy_scope(grant)
                if (type(body["grant_version"]) is not int
                        or any(body[key] != expected[key] for key in required - checks - {"challenge"})
                        or any(body[key] != expected[key] for key in body.keys() - required)):
                    raise AccessDenied()
                interaction = sessions.consume(session, body["challenge"], kind="consent", object_id=grant.grant_id,
                                               document_digest=scope_digest(grant), connection=connection)
                receipt = service.access.accept_grant(
                    principal, grant_id=grant.grant_id, expected_grant_version=grant.grant_version,
                    policies=service.policies, actions=body["actions"], interaction_id=interaction,
                    connection=connection,
                )
                sessions.record_acceptance_context(
                    session, acceptance_id=receipt.acceptance_id, interaction_id=interaction,
                    scope_sha256=scope_digest(grant), eligibility_version=_ELIGIBILITY_VERSION,
                    connection=connection,
                )
                return {"accepted": True, "acceptance_id": receipt.acceptance_id,
                        "grant_id": receipt.grant_id, "expires_at": receipt.expires_at}
        return _json(await run_in_threadpool(accept))

    async def revoke(request: Request) -> Response:
        principal, _, _ = await run_in_threadpool(identity, request, mutate=True)
        body = await _body(request)
        _fields(body, {"grant_id", "grant_version"})
        grant = await run_in_threadpool(service.access.revoke_grant, principal, grant_id=body["grant_id"],
                                        expected_grant_version=body["grant_version"])
        return _json({"revoked": True, "grant_id": grant.grant_id, "grant_version": grant.grant_version})

    async def prepare_operation(request: Request) -> Response:
        principal, _, _ = await run_in_threadpool(identity, request, mutate=True)
        body = await _body(request)
        _fields(body, {"kind", "resource_id", "generation", "parameters"})
        classes = {"import": ImportParameters, "recovery": RecoveryParameters, "association": AssociationParameters,
                   "package": PackageParameters, "unpack": UnpackParameters}
        kind, parameters = body["kind"], body["parameters"]
        if not isinstance(kind, str) or kind not in classes or not isinstance(parameters, dict):
            raise _RequestError()
        cls = classes[kind]
        if parameters.keys() - {field.name for field in fields(cls)}:
            raise _RequestError()
        parameters = dict(parameters)
        if kind == "recovery" and "conversation_keys" in parameters:
            if not isinstance(parameters["conversation_keys"], list):
                raise _RequestError()
            parameters["conversation_keys"] = tuple(parameters["conversation_keys"])
        plan = await run_in_threadpool(service.prepare, principal, resource_id=body["resource_id"],
                                      generation=body["generation"], parameters=cls(**parameters))
        return _json(plan.as_dict())

    def current_plan(principal: Principal, plan_id: str):
        plan = service.operations.get_plan(principal.principal_id, plan_id)
        with service.database.transaction(immediate=False) as connection:
            service._authorize(connection, plan)
        if plan.expires_at <= time.time():
            raise AccessDenied()
        return plan

    async def plan_detail(request: Request) -> Response:
        principal, session, _ = await run_in_threadpool(identity, request)

        def detail():
            plan = current_plan(principal, request.path_params["plan_id"])
            challenge = sessions.challenge(session, kind="operation_review", object_id=plan.plan_id, document_digest=plan.parameter_digest)
            return {"plan": plan.as_dict(), "challenge": challenge}
        return _json(await run_in_threadpool(detail))

    async def review_plan(request: Request) -> Response:
        principal, session, _ = await run_in_threadpool(identity, request, mutate=True)
        body = await _body(request)
        _fields(body, {"parameter_digest", "challenge", "approved"})
        if body["approved"] is not True:
            raise AccessDenied()

        def review():
            plan = current_plan(principal, request.path_params["plan_id"])
            if body["parameter_digest"] != plan.parameter_digest:
                raise AccessDenied()
            # Review recording is separate from challenge consumption. If its
            # write fails, the UI must fetch a fresh challenge for the same plan;
            # starting work still independently rechecks current authorization.
            interaction = sessions.consume(session, body["challenge"], kind="operation_review",
                                           object_id=plan.plan_id, document_digest=plan.parameter_digest)
            result = service.operations.record_human_review(principal.principal_id, plan.plan_id,
                                                           parameter_digest=plan.parameter_digest, interaction_id=interaction)
            return {"reviewed": True, "review_id": result.review_id, "plan_id": result.plan_id, "expires_at": result.expires_at}
        return _json(await run_in_threadpool(review))

    async def start_operation(request: Request) -> Response:
        principal, _, _ = await run_in_threadpool(identity, request, mutate=True)
        body = await _body(request)
        _fields(body, {"plan_id", "idempotency_key"})
        return _json(await run_in_threadpool(service.start, principal, body["plan_id"], body["idempotency_key"]))

    async def operations(request: Request) -> Response:
        principal, _, _ = await run_in_threadpool(identity, request)
        if set(request.query_params) - {"limit", "before_operation_id"}:
            raise _RequestError()
        limit = int(request.query_params.get("limit", "20"))
        cursor = request.query_params.get("before_operation_id")

        def listed():
            snapshots = service.operations.list(principal.principal_id, limit=limit, before_operation_id=cursor)
            return {"items": [service.status(principal, item.operation_id) for item in snapshots],
                    "next_before_operation_id": snapshots[-1].operation_id if len(snapshots) == limit else None}
        return _json(await run_in_threadpool(listed))

    async def cancel_operation(request: Request) -> Response:
        principal, _, _ = await run_in_threadpool(identity, request, mutate=True)
        body = await _body(request)
        _fields(body, set())

        def cancel():
            receipt = service.operations.request_cancel(principal.principal_id, request.path_params["operation_id"])
            return {"disposition": receipt.disposition, "operation": service.status(principal, receipt.operation.operation_id)}
        return _json(await run_in_threadpool(cancel))

    async def query(request: Request) -> Response:
        # Reads use a CSRF-protected POST so selected identifiers and search text
        # remain outside URLs and follow the same browser-origin boundary.
        principal, _, _ = await run_in_threadpool(identity, request, mutate=True)
        body = await _body(request)
        required = {"kind", "collection_id", "generation"}
        kind = body.get("kind")
        allowed = {
            "browse": {"offset", "limit", "project_id", "association_state", "revision_offset", "revision_limit"},
            "search": {"query", "limit", "conversation_key"},
            "read": {"conversation_key", "revision_id", "offset", "limit"}, "verify": set(),
        }
        if not isinstance(kind, str) or kind not in allowed:
            raise _RequestError()
        _fields(body, required | ({"query"} if kind == "search" else {"conversation_key"} if kind == "read" else set()), allowed[kind])
        offset, limit = body.get("offset", 0), body.get("limit", 20)
        _page(offset, limit)
        if kind == "browse":
            revision_offset, revision_limit = body.get("revision_offset", 0), body.get("revision_limit", 10)
            _page(revision_offset, revision_limit, 20)
            _optional_identifier(body.get("project_id"))
            state = body.get("association_state")
            if state not in {None, "project_confirmed", "standalone_confirmed", "association_unknown"}:
                raise _RequestError()
            execute = lambda collection: _browse(collection, offset=offset, limit=limit,
                project_id=body.get("project_id"), association_state=state,
                revision_offset=revision_offset, revision_limit=revision_limit)
        elif kind == "search":
            term = body["query"]
            if not isinstance(term, str) or not term.strip() or len(term) > 1024:
                raise _RequestError()
            _optional_identifier(body.get("conversation_key"), digest=True)
            execute = lambda collection: catalog_query.search_catalog(collection.document, term, limit=limit,
                                                                       conversation_key=body.get("conversation_key"))
        elif kind == "read":
            if body["conversation_key"] is None:
                raise _RequestError()
            _optional_identifier(body["conversation_key"], digest=True)
            _optional_identifier(body.get("revision_id"), digest=True)
            execute = lambda collection: catalog_query.read_revision(collection.document, body["conversation_key"],
                revision_id=body.get("revision_id"), offset=offset, limit=limit)
        else:
            execute = lambda collection: {"verified": True, "stage": "local_collection_validation",
                "generation": body["generation"], "summary": collection_summary(collection.document),
                "account_completeness": "not_asserted"}
        return _json(await run_in_threadpool(service.query, principal, body["collection_id"], body["generation"], kind, execute))

    async def upload(request: Request) -> Response:
        principal, _, cookie = await run_in_threadpool(identity, request, mutate=True)
        length = _single_header(request, "content-length")
        media = _single_header(request, "content-type")
        encoded_name = _single_header(request, "x-file-name")
        if (length is None or not length.isascii() or not length.isdigit()
                or not 0 <= int(length) <= configuration.max_upload_bytes
                or media != "application/octet-stream" or encoded_name is None or len(encoded_name) > 2048
                or _single_header(request, "transfer-encoding") is not None):
            raise _RequestError()
        name = unquote(encoded_name, encoding="utf-8", errors="strict")
        decision = await run_in_threadpool(service._require, principal, workspace_id(principal), "workspace_v1", "upload")
        if not upload_slots.acquire(blocking=False):
            raise OperationBusy("The upload intake slots are occupied.")

        def check():
            sessions.require(cookie)
            service._require(principal, workspace_id(principal), "workspace_v1", "upload", grant_id=decision.grant_id,
                             expected_grant_version=decision.grant_version, expected_acceptance_id=decision.acceptance_id)

        try:
            result = await receive_stream(request, lambda source: service.receive_upload(
                principal, source, display_name=name, expected_size_bytes=int(length)),
                expected_size_bytes=int(length), checkpoint=check)
            return _json(result, status=201)
        finally:
            # receive_stream waits for its synchronous receiver to unwind even
            # after disconnect; only then may another request reuse this slot.
            upload_slots.release()

    async def download(request: Request) -> Response:
        principal, _, cookie = await run_in_threadpool(identity, request)
        if set(request.query_params) != {"generation"} or len(request.query_params.getlist("generation")) != 1:
            raise _RequestError()
        if request.headers.get("sec-fetch-site") == "cross-site":
            raise AccessDenied()
        resource, generation = request.path_params["resource_id"], request.query_params["generation"]
        decision = await run_in_threadpool(service._require, principal, resource, generation, "download")

        def check():
            sessions.require(cookie)
            service._require(principal, resource, generation, "download", grant_id=decision.grant_id,
                             expected_grant_version=decision.grant_version, expected_acceptance_id=decision.acceptance_id)
            service.resources.resolve(principal, resource, generation)
            service._require_origin(principal, resource)

        context = service.download(principal, resource, generation)
        stream, size = await run_in_threadpool(context.__enter__)
        try:
            # Transfer the entered context to the response. Construction failure
            # leaves ownership here; the response closes it after transmission.
            return VerifiedDownloadResponse(context, stream, size, check)
        except BaseException:
            await run_in_threadpool(context.__exit__, None, None, None)
            raise

    async def policy(request: Request) -> Response:
        name = request.path_params["name"]
        if name not in {"terms", "privacy"}:
            raise _RequestError()
        return Response(service.policy_documents[name], media_type="text/plain; charset=utf-8")

    assets = Path(__file__).with_name("portal_assets")

    async def static(request: Request) -> Response:
        name = request.path_params.get("name", "index.html")
        types = {"index.html": "text/html", "portal.js": "text/javascript", "portal.css": "text/css"}
        if name not in types:
            raise _RequestError()
        with open_regular(assets / name) as source:
            data = source.read(1024 * 1024 + 1)
        if len(data) > 1024 * 1024:
            raise _RequestError()
        return Response(data, media_type=types[name])

    routes = [
        Route("/api/config", _safe(public_config)), Route("/auth/operator", _safe(local_login), methods=["POST"]),
        Route("/auth/login", _safe(oauth_login)), Route("/auth/callback", _safe(oauth_callback)),
        Route("/auth/logout", _safe(logout), methods=["POST"]), Route("/api/session", _safe(session_status)),
        Route("/api/options", _safe(options)), Route("/api/consent/prepare", _safe(consent_prepare), methods=["POST"]),
        Route("/api/consent/accept", _safe(consent_accept), methods=["POST"]),
        Route("/api/grants/revoke", _safe(revoke), methods=["POST"]),
        Route("/api/operations/prepare", _safe(prepare_operation), methods=["POST"]),
        Route("/api/plans/{plan_id}", _safe(plan_detail)), Route("/api/plans/{plan_id}/review", _safe(review_plan), methods=["POST"]),
        Route("/api/operations/start", _safe(start_operation), methods=["POST"]), Route("/api/operations", _safe(operations)),
        Route("/api/operations/{operation_id}/cancel", _safe(cancel_operation), methods=["POST"]),
        Route("/api/query", _safe(query), methods=["POST"]), Route("/api/uploads", _safe(upload), methods=["POST"]),
        Route("/api/downloads/{resource_id}", _safe(download)), Route("/policies/{name}", _safe(policy)),
        Route("/assets/{name}", _safe(static)), Route("/portal", _safe(static)), Route("/", _safe(static)),
    ]
    app = Starlette(routes=routes, middleware=[Middleware(_PortalSecurity, origin=origin)])
    app.state.human_sessions = sessions
    return app
