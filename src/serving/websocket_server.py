"""Persistent WebSocket server for a planner with an ``infer`` method."""

from __future__ import annotations

import asyncio
import traceback
from collections.abc import Mapping
from typing import Any

import numpy as np
from websockets.asyncio.server import ServerConnection, serve
from websockets.exceptions import ConnectionClosed

from planner.base import Planner
from protocol import validate_planner_observation
from serving.serialization import packb, payload_checksum, unpackb


class PlannerWebSocketServer:
    """Serve planner inference over a single persistent binary WebSocket stream."""

    def __init__(
        self,
        planner: Planner,
        host: str = "0.0.0.0",
        port: int = 8000,
        on_observation=None,
    ) -> None:
        self._planner = planner
        self._host = host
        self._port = port
        self._on_observation = on_observation

    def serve_forever(self) -> None:
        try:
            asyncio.run(self.run())
        except KeyboardInterrupt:
            print("Planner server stopped", flush=True)

    async def run(self) -> None:
        async with serve(self._handler, self._host, self._port, compression=None, max_size=None):
            print(f"Planner server listening on ws://{self._host}:{self._port}", flush=True)
            await asyncio.Future()

    async def _handler(self, websocket: ServerConnection) -> None:
        print("Client connected", flush=True)
        try:
            async for message in websocket:
                if not isinstance(message, bytes):
                    raise ValueError("planner protocol accepts binary MessagePack frames only")
                request = unpackb(message)
                if not isinstance(request, dict) or set(request) != {"type", "observation", "checksum"}:
                    raise ValueError("invalid planner request envelope")
                if request["type"] != "infer" or not isinstance(request["observation"], dict):
                    raise ValueError("invalid planner request")
                if not isinstance(request["checksum"], str):
                    raise ValueError("planner request checksum must be a string")

                observation = request["observation"]
                if payload_checksum(observation) != request["checksum"]:
                    raise ValueError("planner observation checksum mismatch after MessagePack transport")
                validate_planner_observation(observation)
                print("Received observation", flush=True)
                if self._on_observation is not None:
                    try:
                        self._on_observation(observation)
                    except Exception as exc:
                        print(f"Observation recorder failed: {exc}", flush=True)

                result = self._planner.infer(observation)
                self._validate_result(result)
                actions = result["actions"]
                print(f"Returned actions: shape={actions.shape}, dtype={actions.dtype}", flush=True)
                await websocket.send(packb(result))
        except ConnectionClosed:
            return
        except Exception as exc:
            error = "".join(traceback.format_exception_only(type(exc), exc)).strip()
            print(f"Planner request failed: {error}", flush=True)
            try:
                await websocket.send(packb({"error": error}))
                await websocket.close(code=1011, reason="planner request failed")
            except ConnectionClosed:
                pass

    @staticmethod
    def _validate_result(result: Any) -> None:
        if not isinstance(result, dict) or set(result) != {"actions"}:
            raise ValueError("planner result must be exactly {'actions': np.ndarray}")
        actions = result["actions"]
        if not isinstance(actions, np.ndarray) or actions.ndim != 2 or actions.dtype != np.float32:
            raise ValueError("planner actions must be a rank-2 float32 numpy.ndarray")
