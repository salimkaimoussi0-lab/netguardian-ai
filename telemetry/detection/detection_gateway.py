#!/usr/bin/env python3

from __future__ import annotations

import asyncio
import json
import uuid

from collections import deque
from datetime import datetime, timezone

from websockets.asyncio.client import connect
from websockets.asyncio.server import serve

from telemetry.detection.detection_engine import (
    DetectionEngine,
)


UPSTREAM = (
    "ws://127.0.0.1:8765"
)

HOST = "127.0.0.1"
PORT = 8766


class DetectionGateway:

    def __init__(self):

        self.detector = (
            DetectionEngine()
        )

        self.clients = set()

        self.history = deque(
            maxlen=250
        )


    # ========================================================
    # DOWNSTREAM
    # ========================================================

    async def broadcast(
        self,
        event,
    ):

        if (
            "event_id"
            not in event
        ):

            event["event_id"] = (
                str(
                    uuid.uuid4()
                )
            )

        event[
            "gateway_emitted_at"
        ] = (
            datetime.now(
                timezone.utc
            ).isoformat()
        )

        self.history.append(
            event
        )


        if event.get(
            "type"
        ) == "SECURITY_ALERT":

            print()
            print(
                "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
            )

            print(
                " SECURITY ALERT"
            )

            print(
                " Type:",
                event.get(
                    "alert_type"
                )
            )

            print(
                " Source:",
                (
                    event.get(
                        "source",
                        {}
                    )
                    .get(
                        "ip"
                    )
                )
            )

            print(
                " Target:",
                (
                    event.get(
                        "destination",
                        {}
                    )
                    .get(
                        "ip"
                    )
                )
            )

            print(
                " Unique ports:",
                event.get(
                    "unique_ports"
                )
            )

            print(
                "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
            )
            print()


        if not self.clients:

            return


        payload = json.dumps(
            event,
            ensure_ascii=False,
        )


        dead = []

        for websocket in list(
            self.clients
        ):

            try:

                await websocket.send(
                    payload
                )

            except Exception:

                dead.append(
                    websocket
                )


        for websocket in dead:

            self.clients.discard(
                websocket
            )


    async def client_handler(
        self,
        websocket,
    ):

        self.clients.add(
            websocket
        )

        print(
            "[GATEWAY] dashboard connected:",
            websocket.remote_address,
        )


        await websocket.send(
            json.dumps(
                {
                    "type":
                        "SNAPSHOT",

                    "events":
                        list(
                            self.history
                        ),
                },
                ensure_ascii=False,
            )
        )


        try:

            async for message in websocket:

                try:

                    request = json.loads(
                        message
                    )

                except Exception:

                    continue


                if request.get(
                    "type"
                ) == "PING":

                    await websocket.send(
                        json.dumps(
                            {
                                "type":
                                    "PONG",

                                "timestamp":
                                    datetime.now(
                                        timezone.utc
                                    ).isoformat(),
                            }
                        )
                    )


        finally:

            self.clients.discard(
                websocket
            )

            print(
                "[GATEWAY] dashboard disconnected"
            )


    # ========================================================
    # UPSTREAM
    # ========================================================

    async def upstream_loop(
        self,
    ):

        while True:

            try:

                print(
                    "[GATEWAY] connecting upstream:",
                    UPSTREAM,
                )


                async with connect(
                    UPSTREAM
                ) as websocket:

                    print(
                        "[GATEWAY] upstream connected ✅"
                    )


                    async for message in websocket:

                        event = json.loads(
                            message
                        )


                        #
                        # Snapshot from event_stream:
                        # forward history but don't
                        # generate new alerts from
                        # historical traffic.
                        #

                        if (
                            event.get(
                                "type"
                            )
                            == "SNAPSHOT"
                        ):

                            for old_event in (
                                event.get(
                                    "events",
                                    []
                                )
                            ):

                                self.history.append(
                                    old_event
                                )

                            continue


                        #
                        # Forward raw event.
                        #

                        await self.broadcast(
                            event
                        )


                        #
                        # Detection.
                        #

                        alerts = (
                            self.detector.process(
                                event
                            )
                        )


                        for alert in alerts:

                            await self.broadcast(
                                alert
                            )


            except Exception as exc:

                print(
                    "[GATEWAY] upstream unavailable:",
                    exc,
                )

                print(
                    "[GATEWAY] retry in 2 seconds"
                )

                await asyncio.sleep(
                    2
                )


async def main():

    gateway = (
        DetectionGateway()
    )


    print()
    print(
        "=============================================="
    )

    print(
        " NETGUARDIAN DETECTION GATEWAY"
    )

    print(
        "=============================================="
    )

    print(
        "Raw stream :",
        UPSTREAM,
    )

    print(
        f"Secure feed: ws://"
        f"{HOST}:"
        f"{PORT}"
    )

    print(
        "Detector   : PORT_SCAN"
    )

    print(
        "Rule       : NG-PORTSCAN-001"
    )

    print(
        "=============================================="
    )
    print()


    async with serve(
        gateway.client_handler,
        HOST,
        PORT,
        ping_interval=20,
        ping_timeout=20,
    ):

        await gateway.upstream_loop()


if __name__ == "__main__":

    try:

        asyncio.run(
            main()
        )

    except KeyboardInterrupt:

        print()
        print(
            "[NetGuardian] detection gateway stopped"
        )
