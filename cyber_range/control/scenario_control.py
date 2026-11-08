#!/usr/bin/env python3

from __future__ import annotations

import json
import shlex
import threading
import time
import traceback

from datetime import datetime, timezone
from http.server import (
    BaseHTTPRequestHandler,
    ThreadingHTTPServer,
)
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]

SCENARIO_DIR = (
    ROOT
    / "cyber_range"
    / "scenarios"
)


HOST = "127.0.0.1"
PORT = 8780


SCENARIOS = {
    "normal": {
        "name": "Normal Traffic",
        "description": (
            "Legitimate ICMP and HTTP traffic "
            "from h1 to h2."
        ),
    },

    "port_scan": {
        "name": "Port Scan",
        "description": (
            "Controlled reconnaissance from "
            "h3 to h2."
        ),
    },

    "http_error_burst": {
        "name": "HTTP Error Burst",
        "description": (
            "Several HTTP 404 requests "
            "from h3 to h2."
        ),
    },

    "connection_burst": {
        "name": "Connection Burst",
        "description": (
            "Rapid TCP/HTTP connections "
            "from h3 to h2."
        ),
    },

    "high_bandwidth": {
        "name": "High Bandwidth",
        "description": (
            "Controlled iperf3 traffic "
            "from h3 to h2."
        ),
    },
}


def now_iso() -> str:

    return datetime.now(
        timezone.utc
    ).isoformat()


class ScenarioManager:

    def __init__(self, net):

        self.net = net

        self.h1 = net.get("h1")
        self.h2 = net.get("h2")
        self.h3 = net.get("h3")

        self.lock = threading.Lock()

        self.running = False

        self.current_scenario = None

        self.started_at = None

        self.finished_at = None

        self.last_scenario = None

        self.last_status = None

        self.last_output = None

        self.run_counter = 0

        # Public demo protection
        self.last_finished_monotonic = 0.0
        self.cooldown_seconds = 5.0

        self.rate_window_seconds = 60.0
        self.rate_max_runs = 6
        self.client_runs = {}


    # ========================================================
    # LAB SERVICES
    # ========================================================

    def start_services(self):

        print(
            "[CONTROL] starting h2 services"
        )

        self.h2.cmd(
            "python3 -m http.server 8080 "
            ">/tmp/netguardian-http.log 2>&1 &"
        )

        self.h2.cmd(
            "iperf3 -s -D"
        )


    # ========================================================
    # STATUS
    # ========================================================

    def status(self) -> dict[str, Any]:

        with self.lock:

            return {
                "online":
                    True,

                "state":
                    (
                        "RUNNING"
                        if self.running
                        else "IDLE"
                    ),

                "current_scenario":
                    self.current_scenario,

                "started_at":
                    self.started_at,

                "finished_at":
                    self.finished_at,

                "last_scenario":
                    self.last_scenario,

                "last_status":
                    self.last_status,

                "last_output":
                    self.last_output,

                "run_counter":
                    self.run_counter,

                "hosts": {
                    "h1": {
                        "name":
                            "Client",

                        "ip":
                            "10.10.0.11",
                    },

                    "h2": {
                        "name":
                            "Server",

                        "ip":
                            "10.10.0.20",
                    },

                    "h3": {
                        "name":
                            "Test Host",

                        "ip":
                            "10.10.0.30",
                    },
                },
            }


    # ========================================================
    # FIXED SCENARIOS
    # ========================================================

    def scenario_normal(self):

        ping = self.h1.cmd(
            "ping -c 3 10.10.0.20"
        )

        http = self.h1.cmd(
            "curl -s "
            "-o /dev/null "
            "-w 'HTTP %{http_code}\\n' "
            "http://10.10.0.20:8080/"
        )

        return (
            ping[-1200:]
            + "\n"
            + http[-500:]
        )


    def scenario_script(
        self,
        filename: str,
    ):

        path = (
            SCENARIO_DIR
            / filename
        )

        if not path.exists():

            raise RuntimeError(
                f"Scenario missing: {path}"
            )

        command = (
            "python3 "
            + shlex.quote(
                str(path)
            )
        )

        return self.h3.cmd(
            command
        )


    def scenario_port_scan(self):

        return self.scenario_script(
            "port_scan.py"
        )


    def scenario_http_error_burst(self):

        return self.scenario_script(
            "http_error_burst.py"
        )


    def scenario_connection_burst(self):

        return self.scenario_script(
            "connection_burst.py"
        )


    def scenario_high_bandwidth(self):

        #
        # Ensure server is available.
        #

        self.h2.cmd(
            "iperf3 -s -D "
            "2>/dev/null || true"
        )

        return self.h3.cmd(
            "iperf3 "
            "-c 10.10.0.20 "
            "-t 5"
        )


    # ========================================================
    # EXECUTION
    # ========================================================

    def execute(
        self,
        scenario: str,
    ):

        handlers = {
            "normal":
                self.scenario_normal,

            "port_scan":
                self.scenario_port_scan,

            "http_error_burst":
                self.scenario_http_error_burst,

            "connection_burst":
                self.scenario_connection_burst,

            "high_bandwidth":
                self.scenario_high_bandwidth,
        }


        try:

            print()
            print(
                "=============================================="
            )

            print(
                "[CONTROL] scenario:",
                scenario,
            )

            print(
                "=============================================="
            )


            output = handlers[
                scenario
            ]()


            with self.lock:

                self.last_status = (
                    "SUCCESS"
                )

                self.last_output = (
                    output[-2000:]
                )


            print(
                "[CONTROL] completed:",
                scenario,
            )


        except Exception as exc:

            traceback.print_exc()

            with self.lock:

                self.last_status = (
                    "FAILED"
                )

                self.last_output = (
                    str(exc)
                )


        finally:

            with self.lock:

                self.running = False

                self.last_finished_monotonic = (
                    time.monotonic()
                )

                self.finished_at = (
                    now_iso()
                )

                self.last_scenario = (
                    scenario
                )

                self.current_scenario = (
                    None
                )


    def launch(
        self,
        scenario: str,
        client_id: str = "unknown",
    ) -> tuple[
        bool,
        dict[str, Any],
    ]:

        if scenario not in SCENARIOS:

            return (
                False,
                {
                    "error":
                        "UNKNOWN_SCENARIO"
                },
            )


        with self.lock:

            now = time.monotonic()

            # Remove old requests from this client.
            recent = [
                ts
                for ts in self.client_runs.get(
                    client_id,
                    []
                )
                if (
                    now - ts
                    < self.rate_window_seconds
                )
            ]

            if len(recent) >= self.rate_max_runs:

                self.client_runs[
                    client_id
                ] = recent

                return (
                    False,
                    {
                        "error": "RATE_LIMITED",
                        "retry_after": 60,
                    },
                )

            # Global cooldown between scenarios.
            remaining = (
                self.cooldown_seconds
                - (
                    now
                    - self.last_finished_monotonic
                )
            )

            if (
                self.last_finished_monotonic > 0
                and remaining > 0
            ):

                return (
                    False,
                    {
                        "error": "COOLDOWN",
                        "retry_after": round(
                            remaining,
                            1,
                        ),
                    },
                )

            if self.running:

                return (
                    False,
                    {
                        "error":
                            "LAB_BUSY",

                        "current_scenario":
                            self.current_scenario,
                    },
                )


            recent.append(
                now
            )

            self.client_runs[
                client_id
            ] = recent

            self.running = True

            self.current_scenario = (
                scenario
            )

            self.started_at = (
                now_iso()
            )

            self.finished_at = None

            self.last_status = None

            self.last_output = None

            self.run_counter += 1


        thread = threading.Thread(
            target=self.execute,
            args=(
                scenario,
            ),
            daemon=True,
        )

        thread.start()


        return (
            True,
            {
                "accepted":
                    True,

                "scenario":
                    scenario,

                "state":
                    "RUNNING",

                "started_at":
                    self.started_at,
            },
        )


# ============================================================
# HTTP API
# ============================================================

def create_handler(
    manager: ScenarioManager,
):

    class Handler(
        BaseHTTPRequestHandler
    ):

        server_version = (
            "NetGuardianControl/1.0"
        )


        def log_message(
            self,
            format,
            *args,
        ):

            return


        # ----------------------------------------------------
        # CORS
        # ----------------------------------------------------

        def cors(self):

            origin = self.headers.get(
                "Origin",
                ""
            )

            allowed = {
                "http://localhost:5173",
                "http://127.0.0.1:5173",
                "http://localhost:4173",
                "http://127.0.0.1:4173",
            }

            if origin in allowed or origin.endswith(".vercel.app"):

                self.send_header(
                    "Access-Control-Allow-Origin",
                    origin,
                )

            self.send_header(
                "Access-Control-Allow-Methods",
                "GET, POST, OPTIONS",
            )

            self.send_header(
                "Access-Control-Allow-Headers",
                "Content-Type",
            )


        def json_response(
            self,
            status: int,
            payload,
        ):

            body = json.dumps(
                payload,
                ensure_ascii=False,
            ).encode(
                "utf-8"
            )

            self.send_response(
                status
            )

            self.cors()

            self.send_header(
                "Content-Type",
                "application/json; charset=utf-8",
            )

            self.send_header(
                "Content-Length",
                str(
                    len(body)
                ),
            )

            self.end_headers()

            self.wfile.write(
                body
            )


        # ----------------------------------------------------
        # OPTIONS
        # ----------------------------------------------------

        def do_OPTIONS(self):

            self.send_response(
                204
            )

            self.cors()

            self.end_headers()


        # ----------------------------------------------------
        # GET
        # ----------------------------------------------------

        def do_GET(self):

            if (
                self.path
                == "/api/lab/status"
            ):

                self.json_response(
                    200,
                    manager.status(),
                )

                return


            if (
                self.path
                == "/api/lab/scenarios"
            ):

                self.json_response(
                    200,
                    {
                        "scenarios":
                            SCENARIOS,
                    },
                )

                return


            if (
                self.path
                == "/health"
            ):

                self.json_response(
                    200,
                    {
                        "status":
                            "ok",

                        "service":
                            "NetGuardian Cyber Range Control",
                    },
                )

                return


            self.json_response(
                404,
                {
                    "error":
                        "NOT_FOUND"
                },
            )


        # ----------------------------------------------------
        # POST
        # ----------------------------------------------------

        def do_POST(self):

            prefix = (
                "/api/lab/scenarios/"
            )


            if not self.path.startswith(
                prefix
            ):

                self.json_response(
                    404,
                    {
                        "error":
                            "NOT_FOUND"
                    },
                )

                return


            scenario = (
                self.path[
                    len(prefix):
                ]
                .strip("/")
            )


            forwarded = self.headers.get(
                "X-Forwarded-For",
                ""
            )

            client_id = (
                forwarded.split(",")[0].strip()
                or self.client_address[0]
            )

            success, response = (
                manager.launch(
                    scenario,
                    client_id=client_id,
                )
            )


            self.json_response(
                202
                if success
                else 409,
                response,
            )


    return Handler


class ScenarioControlServer:

    def __init__(
        self,
        net,
        host=HOST,
        port=PORT,
    ):

        self.manager = (
            ScenarioManager(
                net
            )
        )

        self.host = host

        self.port = port

        self.httpd = None

        self.thread = None


    def start(self):

        self.manager.start_services()

        handler = create_handler(
            self.manager
        )

        self.httpd = (
            ThreadingHTTPServer(
                (
                    self.host,
                    self.port,
                ),
                handler,
            )
        )


        self.thread = threading.Thread(
            target=(
                self.httpd
                .serve_forever
            ),
            daemon=True,
        )

        self.thread.start()


        print()
        print(
            "=============================================="
        )

        print(
            " NETGUARDIAN SCENARIO CONTROL API"
        )

        print(
            "=============================================="
        )

        print(
            f" http://{self.host}:{self.port}"
        )

        print(
            " GET  /api/lab/status"
        )

        print(
            " GET  /api/lab/scenarios"
        )

        print(
            " POST /api/lab/scenarios/<scenario>"
        )

        print(
            "=============================================="
        )
        print()


    def stop(self):

        if self.httpd is None:
            return

        self.httpd.shutdown()

        self.httpd.server_close()

        print(
            "[CONTROL] API stopped"
        )
