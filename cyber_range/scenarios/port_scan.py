#!/usr/bin/env python3

"""
NetGuardian Cyber Range
Controlled PORT_SCAN scenario.

IMPORTANT:
This scenario is intentionally restricted to the
Mininet laboratory server 10.10.0.20.
"""

import socket
import time
from datetime import datetime


TARGET = "10.10.0.20"

PORTS = [
    20,
    21,
    22,
    23,
    25,
    53,
    67,
    68,
    80,
    110,
    111,
    123,
    135,
    139,
    143,
    161,
    389,
    443,
    445,
    993,
    995,
    1433,
    1521,
    3306,
    3389,
    5432,
    5201,
    6379,
    8080,
    8443,
    9200,
    27017,
]


def scan_port(port: int) -> int:

    sock = socket.socket(
        socket.AF_INET,
        socket.SOCK_STREAM,
    )

    sock.settimeout(
        0.20
    )

    try:

        return sock.connect_ex(
            (
                TARGET,
                port,
            )
        )

    finally:

        sock.close()


def main():

    print()
    print(
        "=============================================="
    )
    print(
        " NETGUARDIAN CONTROLLED PORT SCAN"
    )
    print(
        "=============================================="
    )

    print(
        "Source  : h3 / 10.10.0.30"
    )

    print(
        f"Target  : {TARGET}"
    )

    print(
        f"Ports   : {len(PORTS)}"
    )

    print(
        "Scope   : Cyber Range only"
    )

    print(
        "=============================================="
    )
    print()

    started = time.monotonic()

    open_ports = []

    for port in PORTS:

        result = scan_port(
            port
        )

        if result == 0:

            state = "OPEN"

            open_ports.append(
                port
            )

        else:

            state = "CLOSED/FILTERED"

        print(
            f"{TARGET}:{port:<5} "
            f"{state}"
        )

        #
        # Slow enough for clean telemetry,
        # fast enough to remain in our
        # detection window.
        #

        time.sleep(
            0.08
        )

    duration = (
        time.monotonic()
        - started
    )

    print()
    print(
        "=============================================="
    )

    print(
        f"Duration : {duration:.2f}s"
    )

    print(
        "Open     :",
        open_ports
        if open_ports
        else "none"
    )

    print(
        "Timestamp:",
        datetime.now().isoformat()
    )

    print(
        "=============================================="
    )


if __name__ == "__main__":
    main()
