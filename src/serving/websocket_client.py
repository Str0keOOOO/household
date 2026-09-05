"""A persistent synchronous client exposing ``client.infer(observation)``."""

from __future__ import annotations

from typing import Any

from websockets.sync.client import ClientConnection, connect

from serving.serialization import packb, payload_checksum, unpackb


class PlannerWebSocketClient:
    """Keep one WebSocket connection open across multiple planner calls."""

    def __init__(self, uri: str = "ws://127.0.0.1:8000") -> None:
        self._uri = uri
        self._connection: ClientConnection | None = None

    def connect(self) -> None:
        if self._connection is None:
            self._connection = connect(self._uri, compression=None, max_size=None)
            print("Connected to planner server", flush=True)

    def close(self) -> None:
        if self._connection is not None:
            self._connection.close()
            self._connection = None

    def infer(self, observation: dict[str, Any]) -> dict[str, Any]:
        """Send one planner observation and return the planner result dict."""
        self.connect()
        assert self._connection is not None
        request = {
            "type": "infer",
            "observation": observation,
            "checksum": payload_checksum(observation),
        }
        self._connection.send(packb(request))
        response = self._connection.recv()
        if isinstance(response, str):
            raise RuntimeError(f"planner server returned a text error: {response}")
        result = unpackb(response)
        if not isinstance(result, dict):
            raise RuntimeError(f"planner server returned {type(result).__name__}, expected dict")
        if "error" in result:
            raise RuntimeError(f"planner server rejected observation: {result['error']}")
        return result

    def __enter__(self) -> "PlannerWebSocketClient":
        self.connect()
        return self

    def __exit__(self, exc_type: object, exc_value: object, traceback: object) -> None:
        del exc_type, exc_value, traceback
        self.close()
