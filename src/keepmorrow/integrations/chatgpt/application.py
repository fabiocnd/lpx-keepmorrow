"""Compose the authenticated MCP endpoint and trusted human portal.

Copyright 2026 Lopix Neural Inc. All rights reserved.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import AsyncExitStack, asynccontextmanager
from importlib.resources import files
import logging
from typing import TYPE_CHECKING

from ...application.configuration import ServiceConfiguration
from ...application.service import PreservationService

_LOGGER = logging.getLogger(__name__)

if TYPE_CHECKING:
    from starlette.applications import Starlette


def create_application(configuration: ServiceConfiguration) -> "Starlette":
    """Initialize configured local stores and compose the ASGI application.

    Construction creates or validates service state without starting a worker.
    The ASGI lifespan owns worker startup, maintenance, and shutdown. The CLI
    binds loopback; OAuth deployments additionally require a selected HTTPS
    transport or supported private tunnel. A local operator key never enables
    remote MCP authentication.
    """
    import anyio
    from starlette.routing import Mount
    from .authentication import AuthenticationConfig, ConfiguredTokenVerifier
    from .pilot_server import create_pilot_server
    from .portal import create_portal

    service = PreservationService(configuration)
    verifier = None
    server = None
    if configuration.mode == "oauth":
        verifier = ConfiguredTokenVerifier(AuthenticationConfig(
            issuer=configuration.oauth_issuer, audience=configuration.resource_url,
            jwks_uri=configuration.oauth_jwks_uri,
        ))
    portal = create_portal(service, verifier=verifier)
    if verifier is not None:
        html = files("keepmorrow.integrations.chatgpt").joinpath("assets/keepmorrow.html").read_text(encoding="utf-8")
        server = create_pilot_server(service, verifier, ui_html=html)
        # Keep the SDK authentication and token-context middleware around its
        # own routes. Copying routes alone would silently discard that boundary.
        portal.routes.append(Mount("/", app=server.streamable_http_app()))

    async def maintenance_loop() -> None:
        while True:
            await anyio.sleep(60)
            try:
                await anyio.to_thread.run_sync(service.maintenance, abandon_on_cancel=False)
            except Exception:
                _LOGGER.error("Keepmorrow retention maintenance requires operator review.")

    @asynccontextmanager
    async def lifespan(app: "Starlette") -> AsyncIterator[None]:
        async with AsyncExitStack() as stack:
            try:
                try:
                    # Startup includes maintenance after the worker acquires its
                    # process lock. Its failure still requires ownership cleanup.
                    await anyio.to_thread.run_sync(service.start_worker, abandon_on_cancel=False)
                    if server is not None:
                        await stack.enter_async_context(server.session_manager.run())
                except Exception:
                    # ASGI servers log startup tracebacks. Suppress the original
                    # chain because filesystem errors can contain private paths.
                    raise RuntimeError("Keepmorrow could not start safely. Operator review is required.") from None
                async with anyio.create_task_group() as tasks:
                    tasks.start_soon(maintenance_loop)
                    try:
                        yield
                    finally:
                        tasks.cancel_scope.cancel()
            finally:
                # Request cancellation cannot transfer ownership of a live
                # executor. Finish the bounded shutdown attempt under shielding.
                with anyio.CancelScope(shield=True):
                    stopped = await anyio.to_thread.run_sync(service.stop_worker, abandon_on_cancel=False)
                if not stopped:
                    _LOGGER.error("Keepmorrow is waiting for its active worker to retain and release ownership safely.")

    portal.router.lifespan_context = lifespan
    portal.state.preservation_service = service
    return portal
