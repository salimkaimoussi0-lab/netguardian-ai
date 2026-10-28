#!/usr/bin/env python3

import socket
import time


TARGET = "10.10.0.20"
PORT = 8080

CONNECTIONS = 25


def create_connection(index):

    sock = socket.create_connection(
        (
            TARGET,
            PORT,
        ),
        timeout=1,
    )

    request = (
        "GET / HTTP/1.0\r\n"
        f"Host: {TARGET}:{PORT}\r\n"
        "User-Agent: NetGuardian-Burst\r\n"
        "\r\n"
    )

    sock.sendall(
        request.encode()
    )

    while True:

        data = sock.recv(
            4096
        )

        if not data:
            break

    sock.close()

    print(
        f"Connection {index:02d} ✅"
    )


def main():

    print()
    print(
        "=============================================="
    )

    print(
        " NETGUARDIAN CONNECTION BURST"
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
        f"Connections: {CONNECTIONS}"
    )

    print()


    for index in range(
        1,
        CONNECTIONS + 1,
    ):

        create_connection(
            index
        )

        time.sleep(
            0.08
        )


if __name__ == "__main__":
    main()
