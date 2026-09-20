"""Reject oversized requests while streaming, before multipart parsing fills disk."""

from starlette.exceptions import HTTPException
from starlette.responses import JSONResponse


class RequestLimit:
    def __init__(self, app, upload_limit):
        self.app = app
        self.upload_limit = upload_limit

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        path = scope.get("path", "")
        limit = (
            self.upload_limit + 1024 * 1024
            if path.endswith("/media")
            else 4 * 1024 * 1024
        )
        headers = dict(scope.get("headers", []))
        try:
            declared = int(headers.get(b"content-length", b"0"))
        except ValueError:
            declared = limit + 1
        if declared > limit:
            return await JSONResponse(
                {"detail": "Request exceeds the upload limit"}, status_code=413
            )(scope, receive, send)
        total = 0
        exceeded = False
        limit_sent = False

        async def reject():
            nonlocal limit_sent
            if not limit_sent:
                limit_sent = True
                await JSONResponse(
                    {"detail": "Request exceeds the upload limit"}, status_code=413
                )(scope, receive, send)

        async def bounded_receive():
            nonlocal total, exceeded
            message = await receive()
            if message["type"] == "http.request":
                total += len(message.get("body", b""))
                if total > limit:
                    exceeded = True
                    raise HTTPException(413, "Request exceeds the upload limit")
            return message

        async def bounded_send(message):
            # FastAPI may translate a body-reading exception to HTTP 400. Keep
            # the size-limit response explicit even across that parser boundary.
            if exceeded:
                await reject()
            else:
                await send(message)

        try:
            await self.app(scope, bounded_receive, bounded_send)
        except HTTPException:
            if not exceeded:
                raise
            await reject()
