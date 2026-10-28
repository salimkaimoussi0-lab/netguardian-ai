#!/usr/bin/env python3

from __future__ import annotations

import argparse
import asyncio
import json
import os
import uuid

from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from websockets.asyncio.server import serve


ROOT = Path(__file__).resolve().parents[2]

LOG_DIR = (
    ROOT
    / "telemetry"
    / "zeek"
    / "current"
)


HOSTS = {
    "10.10.0.11": {
        "id": "h1",
        "name": "Client",
    },

    "10.10.0.20": {
        "id": "h2",
        "name": "Server",
    },

    "10.10.0.30": {
        "id": "h3",
        "name": "Test Host",
    },
}


# ============================================================
# HELPERS
# ============================================================

def host_info(ip: str | None) -> dict[str, Any]:

    if not ip:
        return {
            "ip": None,
            "id": None,
            "name": "Unknown",
        }

    known = HOSTS.get(ip)

    if known:

        return {
            "ip": ip,
            "id": known["id"],
            "name": known["name"],
        }

    return {
        "ip": ip,
        "id": None,
        "name": ip,
    }


def timestamp_iso(value: Any) -> str:

    try:
        value = float(value)

        return datetime.fromtimestamp(
            value,
            timezone.utc,
        ).isoformat()

    except (
        TypeError,
        ValueError,
        OSError,
    ):

        return datetime.now(
            timezone.utc
        ).isoformat()


def as_int(
    value: Any,
    default: int = 0,
) -> int:

    try:
        return int(value)

    except (
        TypeError,
        ValueError,
    ):
        return default


def as_float(
    value: Any,
    default: float = 0.0,
) -> float:

    try:
        return float(value)

    except (
        TypeError,
        ValueError,
    ):
        return default


# ============================================================
# NORMALIZATION
# ============================================================

def normalize_conn(
    row: dict[str, Any]
) -> dict[str, Any]:

    source_ip = row.get(
        "id.orig_h"
    )

    destination_ip = row.get(
        "id.resp_h"
    )

    source_port = as_int(
        row.get("id.orig_p")
    )

    destination_port = as_int(
        row.get("id.resp_p")
    )

    proto = (
        row.get("proto")
        or "unknown"
    )

    service = (
        row.get("service")
        or None
    )

    duration = as_float(
        row.get("duration")
    )

    orig_bytes = as_int(
        row.get("orig_bytes")
    )

    resp_bytes = as_int(
        row.get("resp_bytes")
    )

    missed_bytes = as_int(
        row.get("missed_bytes")
    )

    orig_pkts = as_int(
        row.get("orig_pkts")
    )

    resp_pkts = as_int(
        row.get("resp_pkts")
    )

    conn_state = (
        row.get("conn_state")
        or "UNKNOWN"
    )


    event_type = "CONNECTION"

    if proto == "icmp":

        event_type = "ICMP"

    elif destination_port == 5201:

        event_type = "THROUGHPUT"


    throughput_mbps = None

    if (
        event_type == "THROUGHPUT"
        and duration > 0
    ):

        throughput_mbps = round(
            (
                orig_bytes
                * 8
                / duration
                / 1_000_000
            ),
            2,
        )


    severity = "info"

    if (
        conn_state
        not in {
            "SF",
            "OTH",
        }
    ):

        severity = "warning"


    return {
        "type":
            event_type,

        "timestamp":
            timestamp_iso(
                row.get("ts")
            ),

        "uid":
            row.get("uid"),

        "source":
            host_info(
                source_ip
            ),

        "destination":
            host_info(
                destination_ip
            ),

        "source_port":
            source_port,

        "destination_port":
            destination_port,

        "protocol":
            proto,

        "service":
            service,

        "duration":
            duration,

        "orig_bytes":
            orig_bytes,

        "resp_bytes":
            resp_bytes,

        "bytes_total":
            (
                orig_bytes
                + resp_bytes
            ),

        "orig_packets":
            orig_pkts,

        "resp_packets":
            resp_pkts,

        "connection_state":
            conn_state,

        "throughput_mbps":
            throughput_mbps,

        "missed_bytes":
            missed_bytes,

        "capture_warning":
            missed_bytes > 0,

        "severity":
            severity,

        "source_log":
            "conn.log",
    }


def normalize_http(
    row: dict[str, Any]
) -> dict[str, Any]:

    status = as_int(
        row.get("status_code")
    )

    severity = "info"

    if status >= 500:
        severity = "high"

    elif status >= 400:
        severity = "warning"


    return {
        "type":
            "HTTP_REQUEST",

        "timestamp":
            timestamp_iso(
                row.get("ts")
            ),

        "uid":
            row.get("uid"),

        "source":
            host_info(
                row.get(
                    "id.orig_h"
                )
            ),

        "destination":
            host_info(
                row.get(
                    "id.resp_h"
                )
            ),

        "source_port":
            as_int(
                row.get(
                    "id.orig_p"
                )
            ),

        "destination_port":
            as_int(
                row.get(
                    "id.resp_p"
                )
            ),

        "method":
            row.get("method"),

        "host":
            row.get("host"),

        "uri":
            row.get("uri"),

        "status_code":
            status,

        "user_agent":
            row.get(
                "user_agent"
            ),

        "severity":
            severity,

        "source_log":
            "http.log",
    }


def normalize_weird(
    row: dict[str, Any]
) -> dict[str, Any]:

    return {
        "type":
            "NETWORK_WEIRD",

        "timestamp":
            timestamp_iso(
                row.get("ts")
            ),

        "uid":
            row.get("uid"),

        "source":
            host_info(
                row.get(
                    "id.orig_h"
                )
            ),

        "destination":
            host_info(
                row.get(
                    "id.resp_h"
                )
            ),

        "name":
            row.get("name"),

        "additional":
            row.get("addl"),

        "severity":
            "warning",

        "source_log":
            "weird.log",
    }


NORMALIZERS = {
    "conn.log":
        normalize_conn,

    "http.log":
        normalize_http,

    "weird.log":
        normalize_weird,
}


# ============================================================
# EVENT HUB
# ============================================================

class EventHub:

    def __init__(self):

        self.clients = set()

        self.history = deque(
            maxlen=250
        )


    async def publish(
        self,
        event: dict[str, Any],
    ) -> None:

        event = dict(event)

        event["event_id"] = (
            str(
                uuid.uuid4()
            )
        )

        event["emitted_at"] = (
            datetime.now(
                timezone.utc
            ).isoformat()
        )

        self.history.append(
            event
        )

        print(
            "[EVENT]",
            event.get("type"),
            (
                event
                .get(
                    "source",
                    {}
                )
                .get(
                    "ip"
                )
            ),
            "->",
            (
                event
                .get(
                    "destination",
                    {}
                )
                .get(
                    "ip"
                )
            ),
        )

        if not self.clients:
            return

        payload = json.dumps(
            event,
            ensure_ascii=False,
        )

        disconnected = []

        for client in list(
            self.clients
        ):

            try:

                await client.send(
                    payload
                )

            except Exception:

                disconnected.append(
                    client
                )


        for client in disconnected:

            self.clients.discard(
                client
            )


    async def handler(
        self,
        websocket,
    ) -> None:

        self.clients.add(
            websocket
        )

        print(
            "[WS] client connecté:",
            websocket.remote_address,
        )

        snapshot = {
            "type":
                "SNAPSHOT",

            "events":
                list(
                    self.history
                ),
        }

        await websocket.send(
            json.dumps(
                snapshot,
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

                if (
                    request.get("type")
                    == "PING"
                ):

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
                "[WS] client déconnecté"
            )


# ============================================================
# FILE TAILER
# ============================================================

class LogTailer:

    def __init__(
        self,
        path: Path,
        *,
        replay_existing: bool,
    ):

        self.path = path

        self.replay_existing = (
            replay_existing
        )

        self.position = 0

        self.inode = None

        self.initialized = False

        self.buffer = ""


    def read_new_lines(
        self,
    ) -> list[str]:

        if not self.path.exists():
            return []

        try:

            stat = self.path.stat()

        except FileNotFoundError:

            return []


        if not self.initialized:

            self.inode = stat.st_ino

            if self.replay_existing:
                self.position = 0
            else:
                self.position = (
                    stat.st_size
                )

            self.initialized = True


        elif (
            self.inode
            != stat.st_ino
            or
            stat.st_size
            < self.position
        ):

            print(
                "[TAIL] rotation/troncature:",
                self.path.name,
            )

            self.inode = stat.st_ino

            self.position = 0

            self.buffer = ""


        with self.path.open(
            "rb"
        ) as file:

            file.seek(
                self.position
            )

            data = file.read()

            self.position = (
                file.tell()
            )


        if not data:
            return []


        text = (
            self.buffer
            + data.decode(
                "utf-8",
                errors="replace",
            )
        )

        if text.endswith("\n"):

            lines = text.splitlines()

            self.buffer = ""

        else:

            parts = text.split("\n")

            self.buffer = parts.pop()

            lines = parts


        return [
            line
            for line in lines
            if line.strip()
        ]


# ============================================================
# WATCHER
# ============================================================

async def watch_log(
    filename: str,
    hub: EventHub,
    *,
    replay_existing: bool,
):

    path = (
        LOG_DIR
        / filename
    )

    tailer = LogTailer(
        path,
        replay_existing=(
            replay_existing
        ),
    )

    normalizer = (
        NORMALIZERS[
            filename
        ]
    )

    print(
        "[TAIL] surveillance:",
        path,
    )


    while True:

        lines = (
            tailer
            .read_new_lines()
        )

        for line in lines:

            try:

                row = json.loads(
                    line
                )

            except json.JSONDecodeError:

                print(
                    "[TAIL] JSON invalide:",
                    filename,
                )

                continue


            try:

                event = normalizer(
                    row
                )

            except Exception as exc:

                print(
                    "[TAIL] erreur normalisation:",
                    filename,
                    exc,
                )

                continue


            await hub.publish(
                event
            )


        await asyncio.sleep(
            0.20
        )


# ============================================================
# MAIN
# ============================================================

async def async_main(
    args,
):

    hub = EventHub()

    print()
    print(
        "=============================================="
    )
    print(
        " NETGUARDIAN ZEEK LIVE EVENT STREAM"
    )
    print(
        "=============================================="
    )
    print(
        "Log directory:",
        LOG_DIR,
    )
    print(
        f"WebSocket: ws://"
        f"{args.host}:"
        f"{args.port}"
    )
    print(
        "Replay existing:",
        args.replay_existing,
    )
    print(
        "=============================================="
    )
    print()


    async with serve(
        hub.handler,
        args.host,
        args.port,
        ping_interval=20,
        ping_timeout=20,
    ):

        tasks = [
            asyncio.create_task(
                watch_log(
                    filename,
                    hub,
                    replay_existing=(
                        args.replay_existing
                    ),
                )
            )
            for filename
            in NORMALIZERS
        ]

        await asyncio.gather(
            *tasks
        )


def main():

    parser = argparse.ArgumentParser(
        description=(
            "NetGuardian Zeek "
            "live WebSocket stream"
        )
    )

    parser.add_argument(
        "--host",
        default="127.0.0.1",
    )

    parser.add_argument(
        "--port",
        type=int,
        default=8765,
    )

    parser.add_argument(
        "--replay-existing",
        action="store_true",
    )

    args = parser.parse_args()

    try:

        asyncio.run(
            async_main(
                args
            )
        )

    except KeyboardInterrupt:

        print()
        print(
            "[NetGuardian] arrêt event stream"
        )


if __name__ == "__main__":
    main()
