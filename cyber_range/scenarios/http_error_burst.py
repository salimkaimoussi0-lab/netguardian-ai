#!/usr/bin/env python3

import socket
import time


TARGET = "10.10.0.20"
PORT = 8080

REQUESTS = 8


def request(index):

    path = (
        f"/netguardian-missing-{index}"
    )

    sock = socket.create_connection(
        (
            TARGET,
            PORT,
        ),
        timeout=1,
    )

    request_data = (
        f"GET {path} HTTP/1.0\r\n"
        f"Host: {TARGET}:{PORT}\r\n"
        "User-Agent: NetGuardian-CyberRange\r\n"
        "\r\n"
    )

    sock.sendall(
        request_data.encode()
    )

    response = sock.recv(
        1024
    )

    sock.close()

    first_line = (
        response
        .split(
            b"\r\n",
            1,
        )[0]
        .decode(
            errors="replace"
        )
    )

    print(
        f"{index:02d} "
        f"{path:<32} "
        f"{first_line}"
    )


def main():

    print()
    print(
        "=============================================="
    )

    print(
        " NETGUARDIAN HTTP ERROR BURST"
    )

    print(
        "=============================================="
    )

    print(
        "Source : h3 / 10.10.0.30"
    )

    print(
        "Target : h2 / 10.10.0.20:8080"
    )

    print(
        f"Requests: {REQUESTS}"
    )

    print()


    for index in range(
        1,
        REQUESTS + 1,
    ):

        request(
            index
        )

        time.sleep(
            0.25
        )


if __name__ == "__main__":
    main()
