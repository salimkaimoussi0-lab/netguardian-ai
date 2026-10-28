#!/usr/bin/env python3

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import time

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from websockets.asyncio.client import connect


ROOT = Path(__file__).resolve().parents[2]

WS_URL = "ws://127.0.0.1:8765"

LABEL_FILE = (
    ROOT
    / "telemetry"
    / "features"
    / "current_label.json"
)

DATASET_FILE = (
    ROOT
    / "data"
    / "cyber"
    / "datasets"
    / "netguardian_v1.csv"
)


FIELDNAMES = [
    "window_start",
    "window_end",

    "scenario_run_id",
    "label",

    "source_ip",
    "destination_ip",

    "connections",
    "connections_per_sec",

    "tcp_connections",
    "udp_connections",
    "icmp_connections",

    "unique_dst_ports",

    "http_requests",
    "http_4xx",
    "http_5xx",
    "http_error_ratio",

    "orig_bytes",
    "resp_bytes",
    "bytes_total",
    "bytes_per_sec",

    "orig_packets",
    "resp_packets",
    "packets_total",
    "packets_per_sec",

    "avg_duration",
    "max_duration",

    "rst_connections",
    "rst_ratio",

    "failed_connections",

    "throughput_events",
    "max_throughput_mbps",

    "capture_warning_count",

    "weird_events",
]


# ============================================================
# HELPERS
# ============================================================

def iso(
    timestamp: float,
) -> str:

    return (
        datetime
        .fromtimestamp(
            timestamp,
            timezone.utc,
        )
        .isoformat()
    )


def load_label():

    if not LABEL_FILE.exists():

        return {
            "label":
                "UNLABELED",

            "run_id":
                None,
        }


    try:

        with LABEL_FILE.open(
            encoding="utf-8"
        ) as file:

            return json.load(
                file
            )

    except Exception:

        return {
            "label":
                "UNLABELED",

            "run_id":
                None,
        }


# ============================================================
# FEATURE ENGINE
# ============================================================

class FeatureEngine:

    def __init__(
        self,
        window_seconds: float,
    ):

        self.window_seconds = (
            window_seconds
        )

        self.windows = {}


    # ========================================================
    # WINDOW
    # ========================================================

    def make_window(
        self,
        *,
        bucket: float,
        label: str,
        run_id: str | None,
        source_ip: str,
        destination_ip: str,
    ):

        return {
            "window_start":
                bucket,

            "window_end":
                (
                    bucket
                    + self.window_seconds
                ),

            "scenario_run_id":
                run_id,

            "label":
                label,

            "source_ip":
                source_ip,

            "destination_ip":
                destination_ip,

            "connections":
                0,

            "tcp_connections":
                0,

            "udp_connections":
                0,

            "icmp_connections":
                0,

            "dst_ports":
                set(),

            "http_requests":
                0,

            "http_4xx":
                0,

            "http_5xx":
                0,

            "orig_bytes":
                0,

            "resp_bytes":
                0,

            "orig_packets":
                0,

            "resp_packets":
                0,

            "duration_sum":
                0.0,

            "max_duration":
                0.0,

            "rst_connections":
                0,

            "failed_connections":
                0,

            "throughput_events":
                0,

            "max_throughput_mbps":
                0.0,

            "capture_warning_count":
                0,

            "weird_events":
                0,
        }


    # ========================================================
    # EVENT PROCESSING
    # ========================================================

    def process(
        self,
        event: dict[str, Any],
    ):

        event_type = event.get(
            "type"
        )


        if event_type in {
            "SNAPSHOT",
            "PONG",
        }:

            return


        source = (
            event.get(
                "source"
            )
            or {}
        )

        destination = (
            event.get(
                "destination"
            )
            or {}
        )


        source_ip = source.get(
            "ip"
        )

        destination_ip = (
            destination.get(
                "ip"
            )
        )


        if (
            not source_ip
            or
            not destination_ip
        ):

            return


        label_state = load_label()

        label = (
            label_state.get(
                "label"
            )
            or "UNLABELED"
        )

        run_id = (
            label_state.get(
                "run_id"
            )
        )


        #
        # Don't pollute the supervised dataset
        # when no explicit scenario is selected.
        #

        if label == "UNLABELED":

            return


        now = time.time()

        bucket = (
            int(
                now
                // self.window_seconds
            )
            * self.window_seconds
        )


        key = (
            bucket,
            run_id,
            label,
            source_ip,
            destination_ip,
        )


        if key not in self.windows:

            self.windows[
                key
            ] = self.make_window(
                bucket=bucket,
                label=label,
                run_id=run_id,
                source_ip=source_ip,
                destination_ip=destination_ip,
            )


        window = self.windows[
            key
        ]


        # ----------------------------------------------------
        # ZEEK CONNECTION
        # ----------------------------------------------------

        if event_type in {
            "CONNECTION",
            "THROUGHPUT",
            "ICMP",
        }:

            window[
                "connections"
            ] += 1


            protocol = (
                event.get(
                    "protocol"
                )
                or ""
            )


            if protocol == "tcp":

                window[
                    "tcp_connections"
                ] += 1


            elif protocol == "udp":

                window[
                    "udp_connections"
                ] += 1


            elif protocol == "icmp":

                window[
                    "icmp_connections"
                ] += 1


            port = event.get(
                "destination_port"
            )


            if (
                isinstance(
                    port,
                    int,
                )
                and
                port > 0
            ):

                window[
                    "dst_ports"
                ].add(
                    port
                )


            orig_bytes = int(
                event.get(
                    "orig_bytes"
                )
                or 0
            )

            resp_bytes = int(
                event.get(
                    "resp_bytes"
                )
                or 0
            )


            window[
                "orig_bytes"
            ] += orig_bytes

            window[
                "resp_bytes"
            ] += resp_bytes


            orig_packets = int(
                event.get(
                    "orig_packets"
                )
                or 0
            )

            resp_packets = int(
                event.get(
                    "resp_packets"
                )
                or 0
            )


            window[
                "orig_packets"
            ] += orig_packets

            window[
                "resp_packets"
            ] += resp_packets


            duration = float(
                event.get(
                    "duration"
                )
                or 0.0
            )


            window[
                "duration_sum"
            ] += duration


            window[
                "max_duration"
            ] = max(
                window[
                    "max_duration"
                ],
                duration,
            )


            state = (
                event.get(
                    "connection_state"
                )
                or ""
            )


            if (
                "RST"
                in state
            ):

                window[
                    "rst_connections"
                ] += 1


            if (
                protocol == "tcp"
                and
                state
                not in {
                    "SF",
                    "OTH",
                }
            ):

                window[
                    "failed_connections"
                ] += 1


            if event.get(
                "capture_warning"
            ):

                window[
                    "capture_warning_count"
                ] += 1


        # ----------------------------------------------------
        # THROUGHPUT
        # ----------------------------------------------------

        if (
            event_type
            == "THROUGHPUT"
        ):

            window[
                "throughput_events"
            ] += 1


            throughput = float(
                event.get(
                    "throughput_mbps"
                )
                or 0.0
            )


            window[
                "max_throughput_mbps"
            ] = max(
                window[
                    "max_throughput_mbps"
                ],
                throughput,
            )


        # ----------------------------------------------------
        # HTTP
        # ----------------------------------------------------

        if (
            event_type
            == "HTTP_REQUEST"
        ):

            window[
                "http_requests"
            ] += 1


            status = int(
                event.get(
                    "status_code"
                )
                or 0
            )


            if (
                400
                <= status
                < 500
            ):

                window[
                    "http_4xx"
                ] += 1


            elif status >= 500:

                window[
                    "http_5xx"
                ] += 1


        # ----------------------------------------------------
        # WEIRD
        # ----------------------------------------------------

        if (
            event_type
            == "NETWORK_WEIRD"
        ):

            window[
                "weird_events"
            ] += 1


    # ========================================================
    # ROW
    # ========================================================

    def build_row(
        self,
        window,
    ):

        connections = (
            window[
                "connections"
            ]
        )

        tcp_connections = (
            window[
                "tcp_connections"
            ]
        )

        http_requests = (
            window[
                "http_requests"
            ]
        )


        orig_bytes = (
            window[
                "orig_bytes"
            ]
        )

        resp_bytes = (
            window[
                "resp_bytes"
            ]
        )

        bytes_total = (
            orig_bytes
            + resp_bytes
        )


        orig_packets = (
            window[
                "orig_packets"
            ]
        )

        resp_packets = (
            window[
                "resp_packets"
            ]
        )

        packets_total = (
            orig_packets
            + resp_packets
        )


        duration_sum = (
            window[
                "duration_sum"
            ]
        )


        rst_connections = (
            window[
                "rst_connections"
            ]
        )


        http_errors = (
            window[
                "http_4xx"
            ]
            +
            window[
                "http_5xx"
            ]
        )


        return {
            "window_start":
                iso(
                    window[
                        "window_start"
                    ]
                ),

            "window_end":
                iso(
                    window[
                        "window_end"
                    ]
                ),

            "scenario_run_id":
                window[
                    "scenario_run_id"
                ],

            "label":
                window[
                    "label"
                ],

            "source_ip":
                window[
                    "source_ip"
                ],

            "destination_ip":
                window[
                    "destination_ip"
                ],

            "connections":
                connections,

            "connections_per_sec":
                round(
                    connections
                    / self.window_seconds,
                    4,
                ),

            "tcp_connections":
                tcp_connections,

            "udp_connections":
                window[
                    "udp_connections"
                ],

            "icmp_connections":
                window[
                    "icmp_connections"
                ],

            "unique_dst_ports":
                len(
                    window[
                        "dst_ports"
                    ]
                ),

            "http_requests":
                http_requests,

            "http_4xx":
                window[
                    "http_4xx"
                ],

            "http_5xx":
                window[
                    "http_5xx"
                ],

            "http_error_ratio":
                round(
                    (
                        http_errors
                        / http_requests
                    )
                    if http_requests
                    else 0.0,
                    4,
                ),

            "orig_bytes":
                orig_bytes,

            "resp_bytes":
                resp_bytes,

            "bytes_total":
                bytes_total,

            "bytes_per_sec":
                round(
                    bytes_total
                    / self.window_seconds,
                    2,
                ),

            "orig_packets":
                orig_packets,

            "resp_packets":
                resp_packets,

            "packets_total":
                packets_total,

            "packets_per_sec":
                round(
                    packets_total
                    / self.window_seconds,
                    2,
                ),

            "avg_duration":
                round(
                    (
                        duration_sum
                        / connections
                    )
                    if connections
                    else 0.0,
                    6,
                ),

            "max_duration":
                round(
                    window[
                        "max_duration"
                    ],
                    6,
                ),

            "rst_connections":
                rst_connections,

            "rst_ratio":
                round(
                    (
                        rst_connections
                        / tcp_connections
                    )
                    if tcp_connections
                    else 0.0,
                    4,
                ),

            "failed_connections":
                window[
                    "failed_connections"
                ],

            "throughput_events":
                window[
                    "throughput_events"
                ],

            "max_throughput_mbps":
                round(
                    window[
                        "max_throughput_mbps"
                    ],
                    2,
                ),

            "capture_warning_count":
                window[
                    "capture_warning_count"
                ],

            "weird_events":
                window[
                    "weird_events"
                ],
        }


    # ========================================================
    # CSV
    # ========================================================

    def write_row(
        self,
        row,
    ):

        DATASET_FILE.parent.mkdir(
            parents=True,
            exist_ok=True,
        )


        new_file = (
            not DATASET_FILE.exists()
            or
            DATASET_FILE.stat().st_size
            == 0
        )


        with DATASET_FILE.open(
            "a",
            encoding="utf-8",
            newline="",
        ) as file:

            writer = csv.DictWriter(
                file,
                fieldnames=FIELDNAMES,
            )


            if new_file:

                writer.writeheader()


            writer.writerow(
                row
            )


        print(
            "[FEATURE]",
            row["label"],
            row["source_ip"],
            "->",
            row["destination_ip"],
            "| conn:",
            row["connections"],
            "| ports:",
            row[
                "unique_dst_ports"
            ],
            "| HTTP:",
            row[
                "http_requests"
            ],
            "| Mbps:",
            row[
                "max_throughput_mbps"
            ],
        )


    # ========================================================
    # FLUSH
    # ========================================================

    def flush_ready(
        self,
    ):

        now = time.time()


        ready = [
            key
            for key, window
            in self.windows.items()
            if (
                window[
                    "window_end"
                ]
                <= now
            )
        ]


        for key in ready:

            window = (
                self.windows.pop(
                    key
                )
            )

            row = self.build_row(
                window
            )

            self.write_row(
                row
            )


    def flush_all(
        self,
    ):

        keys = list(
            self.windows.keys()
        )


        for key in keys:

            window = (
                self.windows.pop(
                    key
                )
            )

            self.write_row(
                self.build_row(
                    window
                )
            )


# ============================================================
# LIVE STREAM
# ============================================================

async def flush_loop(
    engine: FeatureEngine,
):

    while True:

        await asyncio.sleep(
            0.5
        )

        engine.flush_ready()


async def consume(
    engine: FeatureEngine,
):

    while True:

        try:

            print(
                "[FEATURE] connecting:",
                WS_URL,
            )


            async with connect(
                WS_URL
            ) as websocket:

                print(
                    "[FEATURE] raw stream connected ✅"
                )


                async for message in websocket:

                    event = json.loads(
                        message
                    )


                    #
                    # Avoid replaying history from
                    # event_stream snapshots.
                    #

                    if (
                        event.get("type")
                        == "SNAPSHOT"
                    ):

                        continue


                    engine.process(
                        event
                    )


        except Exception as exc:

            print(
                "[FEATURE] stream unavailable:",
                exc,
            )

            print(
                "[FEATURE] retry in 2s"
            )

            await asyncio.sleep(
                2
            )


async def async_main(
    args,
):

    engine = FeatureEngine(
        window_seconds=(
            args.window
        )
    )


    print()
    print(
        "=============================================="
    )
    print(
        " NETGUARDIAN FEATURE ENGINE"
    )
    print(
        "=============================================="
    )

    print(
        "Raw stream :",
        WS_URL,
    )

    print(
        "Window     :",
        args.window,
        "seconds",
    )

    print(
        "Dataset    :",
        DATASET_FILE,
    )

    print(
        "=============================================="
    )
    print()


    if args.reset:

        if DATASET_FILE.exists():

            DATASET_FILE.unlink()

            print(
                "[FEATURE] dataset reset ✅"
            )


    tasks = [
        asyncio.create_task(
            consume(
                engine
            )
        ),

        asyncio.create_task(
            flush_loop(
                engine
            )
        ),
    ]


    try:

        await asyncio.gather(
            *tasks
        )

    finally:

        engine.flush_all()


def main():

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--window",
        type=float,
        default=5.0,
    )

    parser.add_argument(
        "--reset",
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
            "[FeatureEngine] stopped"
        )


if __name__ == "__main__":
    main()
