"""Shared by the tests: stand-ins for database rows and a way to call the app
without a server."""

import asyncio
import json
from types import SimpleNamespace

from app.services import foxhole_data


class Row(SimpleNamespace):
    """A stand-in for an ORM row that can be a dict key (the report takes
    {building: [entries]})."""

    __hash__ = object.__hash__


def resource(resource_id: int, key: str, **flags) -> Row:
    definition = foxhole_data.get_resource_def(key)
    values = {"farmable": definition.get("farmable", False), "imported": False, "unlimited": False}
    values.update(flags)
    return Row(id=resource_id, name=definition["name"]["en"], icon="", resource_def_key=key, nickname=None, **values)


def building(building_id: int, type_key: str, slots=(), name: str | None = None) -> Row:
    return Row(
        id=building_id,
        name=name or type_key,
        role="",
        building_type_key=type_key,
        production_slots=[{"recipe_key": key, "queue_count": count} for key, count in slots],
    )


def entry(res: Row, quantity: float, storage: str = "normal") -> Row:
    return Row(resource=res, resource_id=res.id, quantity=quantity, storage=storage)


def call(app, method: str, path: str, headers: dict | None = None, body=None, client=("127.0.0.1", 50000)):
    """One request straight into the ASGI app. Returns (status, headers, body
    bytes). `body`: bytes, or anything else is sent as JSON."""
    path, _, query = path.partition("?")
    all_headers = {"host": "localhost:8000", **(headers or {})}
    if body is not None and not isinstance(body, bytes):
        body = json.dumps(body).encode()
        all_headers.setdefault("content-type", "application/json")
    body = body or b""
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": method,
        "scheme": "http",
        "path": path,
        "raw_path": path.encode(),
        "query_string": query.encode(),
        "headers": [(k.lower().encode(), v.encode()) for k, v in all_headers.items()],
        "client": client,
        "server": ("127.0.0.1", 8000),
        "root_path": "",
    }
    result = {"status": None, "headers": {}, "body": b""}
    requested = False

    async def receive():
        nonlocal requested
        if requested:
            return {"type": "http.disconnect"}
        requested = True
        return {"type": "http.request", "body": body, "more_body": False}

    async def send(message):
        if message["type"] == "http.response.start":
            result["status"] = message["status"]
            result["headers"] = {k.decode().lower(): v.decode() for k, v in message["headers"]}
        elif message["type"] == "http.response.body":
            result["body"] += message.get("body", b"")

    asyncio.run(app(scope, receive, send))
    return result["status"], result["headers"], result["body"]
