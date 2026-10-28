from __future__ import annotations

import time

from collections import defaultdict, deque
from datetime import datetime
from typing import Any


class DetectionEngine:

    # ========================================================
    # PORT SCAN
    # ========================================================

    PORT_SCAN_WINDOW = 6.0
    PORT_SCAN_THRESHOLD = 12
    PORT_SCAN_COOLDOWN = 15.0

    # ========================================================
    # CONNECTION BURST
    # ========================================================

    CONNECTION_BURST_WINDOW = 5.0
    CONNECTION_BURST_THRESHOLD = 20
    CONNECTION_BURST_COOLDOWN = 15.0

    # ========================================================
    # HTTP ERROR BURST
    # ========================================================

    HTTP_ERROR_WINDOW = 10.0
    HTTP_ERROR_THRESHOLD = 5
    HTTP_ERROR_COOLDOWN = 20.0

    # ========================================================
    # HIGH BANDWIDTH
    # ========================================================

    HIGH_BANDWIDTH_THRESHOLD_MBPS = 70.0
    HIGH_BANDWIDTH_COOLDOWN = 10.0


    def __init__(self):

        self.port_activity = defaultdict(
            deque
        )

        self.connection_activity = defaultdict(
            deque
        )

        self.http_error_activity = defaultdict(
            deque
        )

        self.last_alert = {}


    # ========================================================
    # HELPERS
    # ========================================================

    @staticmethod
    def event_time(
        event: dict[str, Any],
    ) -> float:

        value = event.get(
            "timestamp"
        )

        if value:

            try:

                return (
                    datetime
                    .fromisoformat(
                        value.replace(
                            "Z",
                            "+00:00",
                        )
                    )
                    .timestamp()
                )

            except Exception:
                pass

        return time.time()


    @staticmethod
    def lab_pair(
        event: dict[str, Any],
    ) -> tuple[
        str | None,
        str | None,
    ]:

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

        return (
            source.get("ip"),
            destination.get("ip"),
        )


    @staticmethod
    def is_test_host_to_server(
        event: dict[str, Any],
    ) -> bool:

        source_ip, destination_ip = (
            DetectionEngine.lab_pair(
                event
            )
        )

        return (
            source_ip == "10.10.0.30"
            and
            destination_ip == "10.10.0.20"
        )


    @staticmethod
    def clean_window(
        history: deque,
        cutoff: float,
    ) -> None:

        while (
            history
            and
            history[0][0]
            < cutoff
        ):

            history.popleft()


    def allow_alert(
        self,
        key,
        now: float,
        cooldown: float,
    ) -> bool:

        last = self.last_alert.get(
            key,
            0.0,
        )

        if (
            now - last
            < cooldown
        ):

            return False

        self.last_alert[
            key
        ] = now

        return True


    @staticmethod
    def source(
        event,
    ):

        return (
            event.get(
                "source"
            )
            or {}
        )


    @staticmethod
    def destination(
        event,
    ):

        return (
            event.get(
                "destination"
            )
            or {}
        )


    # ========================================================
    # PORT SCAN
    # ========================================================

    def detect_port_scan(
        self,
        event: dict[str, Any],
    ) -> list[dict[str, Any]]:

        if (
            event.get("type")
            != "CONNECTION"
        ):

            return []

        if (
            event.get("protocol")
            != "tcp"
        ):

            return []

        if not self.is_test_host_to_server(
            event
        ):

            return []


        port = event.get(
            "destination_port"
        )

        if (
            not isinstance(
                port,
                int,
            )
            or
            port <= 0
        ):

            return []


        now = self.event_time(
            event
        )

        source_ip, destination_ip = (
            self.lab_pair(
                event
            )
        )

        key = (
            source_ip,
            destination_ip,
        )

        history = (
            self.port_activity[
                key
            ]
        )

        history.append(
            (
                now,
                port,
            )
        )

        self.clean_window(
            history,
            now
            - self.PORT_SCAN_WINDOW,
        )


        ports = sorted(
            {
                item[1]
                for item
                in history
            }
        )


        if (
            len(ports)
            <
            self.PORT_SCAN_THRESHOLD
        ):

            return []


        cooldown_key = (
            "PORT_SCAN",
            source_ip,
            destination_ip,
        )

        if not self.allow_alert(
            cooldown_key,
            now,
            self.PORT_SCAN_COOLDOWN,
        ):

            return []


        return [
            {
                "type":
                    "SECURITY_ALERT",

                "alert_type":
                    "PORT_SCAN",

                "severity":
                    "high",

                "timestamp":
                    event.get(
                        "timestamp"
                    ),

                "source":
                    self.source(
                        event
                    ),

                "destination":
                    self.destination(
                        event
                    ),

                "detection_method":
                    "RULE_BASED",

                "rule":
                    "NG-PORTSCAN-001",

                "window_seconds":
                    self.PORT_SCAN_WINDOW,

                "unique_ports":
                    len(
                        ports
                    ),

                "ports":
                    ports,

                "threshold":
                    self.PORT_SCAN_THRESHOLD,

                "message":
                    (
                        f"{len(ports)} distinct "
                        "destination ports contacted"
                    ),
            }
        ]


    # ========================================================
    # CONNECTION BURST
    # ========================================================

    def detect_connection_burst(
        self,
        event: dict[str, Any],
    ) -> list[dict[str, Any]]:

        if (
            event.get("type")
            != "CONNECTION"
        ):

            return []

        if (
            event.get("protocol")
            != "tcp"
        ):

            return []

        if not self.is_test_host_to_server(
            event
        ):

            return []


        port = event.get(
            "destination_port"
        )

        if (
            not isinstance(
                port,
                int,
            )
            or
            port <= 0
        ):

            return []


        now = self.event_time(
            event
        )

        source_ip, destination_ip = (
            self.lab_pair(
                event
            )
        )


        #
        # Important:
        # même port uniquement.
        #
        # Ainsi un port scan n'est pas
        # automatiquement considéré comme
        # un connection burst.
        #

        key = (
            source_ip,
            destination_ip,
            port,
        )


        history = (
            self.connection_activity[
                key
            ]
        )

        history.append(
            (
                now,
                port,
            )
        )

        self.clean_window(
            history,
            now
            - self.CONNECTION_BURST_WINDOW,
        )


        count = len(
            history
        )


        if (
            count
            <
            self.CONNECTION_BURST_THRESHOLD
        ):

            return []


        cooldown_key = (
            "CONNECTION_BURST",
            source_ip,
            destination_ip,
            port,
        )


        if not self.allow_alert(
            cooldown_key,
            now,
            self.CONNECTION_BURST_COOLDOWN,
        ):

            return []


        return [
            {
                "type":
                    "SECURITY_ALERT",

                "alert_type":
                    "CONNECTION_BURST",

                "severity":
                    "high",

                "timestamp":
                    event.get(
                        "timestamp"
                    ),

                "source":
                    self.source(
                        event
                    ),

                "destination":
                    self.destination(
                        event
                    ),

                "destination_port":
                    port,

                "connections":
                    count,

                "window_seconds":
                    self.CONNECTION_BURST_WINDOW,

                "threshold":
                    self.CONNECTION_BURST_THRESHOLD,

                "detection_method":
                    "RULE_BASED",

                "rule":
                    "NG-CONNBURST-001",

                "message":
                    (
                        f"{count} TCP connections "
                        f"to port {port}"
                    ),
            }
        ]


    # ========================================================
    # HTTP ERROR BURST
    # ========================================================

    def detect_http_error_burst(
        self,
        event: dict[str, Any],
    ) -> list[dict[str, Any]]:

        if (
            event.get("type")
            != "HTTP_REQUEST"
        ):

            return []


        if not self.is_test_host_to_server(
            event
        ):

            return []


        status = event.get(
            "status_code"
        )

        if (
            not isinstance(
                status,
                int,
            )
            or
            status < 400
        ):

            return []


        now = self.event_time(
            event
        )

        source_ip, destination_ip = (
            self.lab_pair(
                event
            )
        )


        key = (
            source_ip,
            destination_ip,
        )


        history = (
            self.http_error_activity[
                key
            ]
        )


        history.append(
            (
                now,
                status,
            )
        )


        self.clean_window(
            history,
            now
            - self.HTTP_ERROR_WINDOW,
        )


        count = len(
            history
        )


        if (
            count
            <
            self.HTTP_ERROR_THRESHOLD
        ):

            return []


        cooldown_key = (
            "HTTP_ERROR_BURST",
            source_ip,
            destination_ip,
        )


        if not self.allow_alert(
            cooldown_key,
            now,
            self.HTTP_ERROR_COOLDOWN,
        ):

            return []


        return [
            {
                "type":
                    "SECURITY_ALERT",

                "alert_type":
                    "HTTP_ERROR_BURST",

                "severity":
                    "warning",

                "timestamp":
                    event.get(
                        "timestamp"
                    ),

                "source":
                    self.source(
                        event
                    ),

                "destination":
                    self.destination(
                        event
                    ),

                "errors":
                    count,

                "window_seconds":
                    self.HTTP_ERROR_WINDOW,

                "threshold":
                    self.HTTP_ERROR_THRESHOLD,

                "last_status":
                    status,

                "detection_method":
                    "RULE_BASED",

                "rule":
                    "NG-HTTPERR-001",

                "message":
                    (
                        f"{count} HTTP errors "
                        "observed"
                    ),
            }
        ]


    # ========================================================
    # HIGH BANDWIDTH
    # ========================================================

    def detect_high_bandwidth(
        self,
        event: dict[str, Any],
    ) -> list[dict[str, Any]]:

        if (
            event.get("type")
            != "THROUGHPUT"
        ):

            return []


        if not self.is_test_host_to_server(
            event
        ):

            return []


        value = event.get(
            "throughput_mbps"
        )

        if not isinstance(
            value,
            (
                int,
                float,
            ),
        ):

            return []


        if (
            value
            <
            self.HIGH_BANDWIDTH_THRESHOLD_MBPS
        ):

            return []


        now = self.event_time(
            event
        )

        source_ip, destination_ip = (
            self.lab_pair(
                event
            )
        )


        cooldown_key = (
            "HIGH_BANDWIDTH",
            source_ip,
            destination_ip,
        )


        if not self.allow_alert(
            cooldown_key,
            now,
            self.HIGH_BANDWIDTH_COOLDOWN,
        ):

            return []


        return [
            {
                "type":
                    "SECURITY_ALERT",

                "alert_type":
                    "HIGH_BANDWIDTH",

                "severity":
                    "warning",

                "timestamp":
                    event.get(
                        "timestamp"
                    ),

                "source":
                    self.source(
                        event
                    ),

                "destination":
                    self.destination(
                        event
                    ),

                "throughput_mbps":
                    round(
                        float(value),
                        2,
                    ),

                "threshold_mbps":
                    self.HIGH_BANDWIDTH_THRESHOLD_MBPS,

                "capture_warning":
                    event.get(
                        "capture_warning",
                        False,
                    ),

                "detection_method":
                    "RULE_BASED",

                "rule":
                    "NG-BANDWIDTH-001",

                "message":
                    (
                        f"High traffic rate: "
                        f"{value:.2f} Mbps"
                    ),
            }
        ]


    # ========================================================
    # PROCESS EVENT
    # ========================================================

    def process(
        self,
        event: dict[str, Any],
    ) -> list[dict[str, Any]]:

        alerts = []


        alerts.extend(
            self.detect_port_scan(
                event
            )
        )


        alerts.extend(
            self.detect_connection_burst(
                event
            )
        )


        alerts.extend(
            self.detect_http_error_burst(
                event
            )
        )


        alerts.extend(
            self.detect_high_bandwidth(
                event
            )
        )


        return alerts
