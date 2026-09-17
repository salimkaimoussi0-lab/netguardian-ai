#!/usr/bin/env python3

import csv
import re
import subprocess
import time
from datetime import datetime
from pathlib import Path


SWITCH = "s1"
INTERVAL = 1.0
OUTPUT_FILE = Path("telemetry/data/ovs_port_stats.csv")


def run_command(command):
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def get_port_map():
    """
    Construit une correspondance :
    OpenFlow port number -> interface name

    Exemple :
    1 -> s1-eth1
    2 -> s1-eth2
    3 -> s1-eth3
    """

    output = run_command([
        "sudo",
        "ovs-vsctl",
        "list-ports",
        SWITCH,
    ])

    mapping = {}

    for interface in output.splitlines():
        interface = interface.strip()

        if not interface:
            continue

        try:
            ofport = run_command([
                "sudo",
                "ovs-vsctl",
                "get",
                "Interface",
                interface,
                "ofport",
            ])

            mapping[int(ofport)] = interface

        except Exception as exc:
            print(
                f"[WARNING] Impossible de mapper "
                f"{interface}: {exc}"
            )

    return mapping


def get_port_stats():
    return run_command([
        "sudo",
        "ovs-ofctl",
        "-O",
        "OpenFlow13",
        "dump-ports",
        SWITCH,
    ])


def parse_stats(output, port_map):
    ports = {}
    current_port = None

    for line in output.splitlines():

        # Cas 1 :
        # port 1: rx pkts=...

        numeric_match = re.search(
            r'port\s+(\d+):\s+'
            r'rx pkts=(\d+), bytes=(\d+), '
            r'drop=(\d+), errs=(\d+)',
            line
        )

        # Cas 2 :
        # port "s1-eth1": rx pkts=...

        named_match = re.search(
            r'port\s+"([^"]+)":\s+'
            r'rx pkts=(\d+), bytes=(\d+), '
            r'drop=(\d+), errs=(\d+)',
            line
        )

        if numeric_match:

            port_number = int(
                numeric_match.group(1)
            )

            current_port = port_map.get(
                port_number,
                f"ofport-{port_number}"
            )

            ports[current_port] = {
                "rx_packets": int(
                    numeric_match.group(2)
                ),
                "rx_bytes": int(
                    numeric_match.group(3)
                ),
                "rx_drops": int(
                    numeric_match.group(4)
                ),
                "rx_errors": int(
                    numeric_match.group(5)
                ),
            }

            continue

        if named_match:

            current_port = named_match.group(1)

            ports[current_port] = {
                "rx_packets": int(
                    named_match.group(2)
                ),
                "rx_bytes": int(
                    named_match.group(3)
                ),
                "rx_drops": int(
                    named_match.group(4)
                ),
                "rx_errors": int(
                    named_match.group(5)
                ),
            }

            continue

        if current_port is not None:

            tx_match = re.search(
                r'tx pkts=(\d+), bytes=(\d+), '
                r'drop=(\d+), errs=(\d+)',
                line
            )

            if tx_match:

                ports[current_port].update({
                    "tx_packets": int(
                        tx_match.group(1)
                    ),
                    "tx_bytes": int(
                        tx_match.group(2)
                    ),
                    "tx_drops": int(
                        tx_match.group(3)
                    ),
                    "tx_errors": int(
                        tx_match.group(4)
                    ),
                })

                current_port = None

    required = {
        "rx_packets",
        "rx_bytes",
        "rx_drops",
        "rx_errors",
        "tx_packets",
        "tx_bytes",
        "tx_drops",
        "tx_errors",
    }

    valid_ports = {}

    for port, stats in ports.items():
        if required.issubset(stats):
            valid_ports[port] = stats

    return valid_ports


def main():

    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    fieldnames = [
        "timestamp",
        "switch",
        "port",
        "rx_packets",
        "tx_packets",
        "rx_bytes",
        "tx_bytes",
        "rx_drops",
        "tx_drops",
        "rx_errors",
        "tx_errors",
        "rx_pps",
        "tx_pps",
        "rx_mbps",
        "tx_mbps",
    ]

    print()
    print(
        "=============================================="
    )
    print(
        "       NETGUARDIAN TELEMETRY v0.3"
    )
    print(
        "=============================================="
    )

    port_map = get_port_map()

    print()
    print("[NetGuardian] OpenFlow port mapping:")

    for number, name in sorted(
        port_map.items()
    ):
        print(
            f"  port {number} -> {name}"
        )

    print()
    print(f"Switch   : {SWITCH}")
    print(f"Interval : {INTERVAL} second")
    print(f"Output   : {OUTPUT_FILE}")
    print("Ctrl+C   : stop")
    print(
        "=============================================="
    )
    print()

    previous = {}

    file_exists = OUTPUT_FILE.exists()

    with OUTPUT_FILE.open(
        "a",
        newline=""
    ) as csvfile:

        writer = csv.DictWriter(
            csvfile,
            fieldnames=fieldnames
        )

        if (
            not file_exists
            or OUTPUT_FILE.stat().st_size == 0
        ):
            writer.writeheader()

        try:

            while True:

                sample_time = time.monotonic()
                timestamp = datetime.now().isoformat()

                raw = get_port_stats()

                ports = parse_stats(
                    raw,
                    port_map
                )

                if not ports:
                    print(
                        "[WARNING] Aucun port "
                        "OpenFlow détecté."
                    )

                    time.sleep(INTERVAL)
                    continue

                for port, stats in ports.items():

                    rx_pps = 0.0
                    tx_pps = 0.0

                    rx_mbps = 0.0
                    tx_mbps = 0.0

                    old = previous.get(port)

                    if old:

                        elapsed = (
                            sample_time
                            - old["_sample_time"]
                        )

                        if elapsed > 0:

                            rx_packets_delta = (
                                stats["rx_packets"]
                                - old["rx_packets"]
                            )

                            tx_packets_delta = (
                                stats["tx_packets"]
                                - old["tx_packets"]
                            )

                            rx_bytes_delta = (
                                stats["rx_bytes"]
                                - old["rx_bytes"]
                            )

                            tx_bytes_delta = (
                                stats["tx_bytes"]
                                - old["tx_bytes"]
                            )

                            rx_pps = (
                                rx_packets_delta
                                / elapsed
                            )

                            tx_pps = (
                                tx_packets_delta
                                / elapsed
                            )

                            rx_mbps = (
                                rx_bytes_delta
                                * 8
                                / elapsed
                                / 1_000_000
                            )

                            tx_mbps = (
                                tx_bytes_delta
                                * 8
                                / elapsed
                                / 1_000_000
                            )

                    writer.writerow({
                        "timestamp": timestamp,
                        "switch": SWITCH,
                        "port": port,
                        "rx_packets":
                            stats["rx_packets"],
                        "tx_packets":
                            stats["tx_packets"],
                        "rx_bytes":
                            stats["rx_bytes"],
                        "tx_bytes":
                            stats["tx_bytes"],
                        "rx_drops":
                            stats["rx_drops"],
                        "tx_drops":
                            stats["tx_drops"],
                        "rx_errors":
                            stats["rx_errors"],
                        "tx_errors":
                            stats["tx_errors"],
                        "rx_pps":
                            round(rx_pps, 2),
                        "tx_pps":
                            round(tx_pps, 2),
                        "rx_mbps":
                            round(rx_mbps, 3),
                        "tx_mbps":
                            round(tx_mbps, 3),
                    })

                    print(
                        f"{port:<10} | "
                        f"RX "
                        f"{rx_pps:8.1f} pps "
                        f"{rx_mbps:8.2f} Mbps | "
                        f"TX "
                        f"{tx_pps:8.1f} pps "
                        f"{tx_mbps:8.2f} Mbps"
                    )

                    previous[port] = {
                        **stats,
                        "_sample_time": sample_time
                    }

                csvfile.flush()

                print("-" * 90)

                time.sleep(INTERVAL)

        except KeyboardInterrupt:

            print()
            print(
                "[NetGuardian] "
                "Telemetry collector stopped."
            )


if __name__ == "__main__":
    main()
