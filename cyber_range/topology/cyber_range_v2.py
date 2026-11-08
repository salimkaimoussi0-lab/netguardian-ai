#!/usr/bin/env python3

from __future__ import annotations

from mininet.cli import CLI
from mininet.link import TCLink
from mininet.log import (
    info,
    setLogLevel,
)
from mininet.net import Mininet
from mininet.node import OVSSwitch

from cyber_range.control.scenario_control import (
    ScenarioControlServer,
)

from cyber_range.topology.cyber_range_v1 import (
    CyberRangeTopo,
    SWITCH,
    cleanup_monitor,
    configure_monitor,
)


def main():

    setLogLevel(
        "info"
    )

    cleanup_monitor()

    topo = CyberRangeTopo()

    net = Mininet(
        topo=topo,
        controller=None,
        switch=OVSSwitch,
        link=TCLink,
        autoSetMacs=True,
        autoStaticArp=False,
    )

    control = None


    try:

        info(
            "\n*** Starting NetGuardian Cyber Range v2\n"
        )

        net.start()


        switch = net.get(
            SWITCH
        )

        switch.cmd(
            "ovs-vsctl "
            "set-fail-mode s1 standalone"
        )

        switch.cmd(
            "ovs-vsctl "
            "set Bridge s1 "
            "protocols=OpenFlow13"
        )


        configure_monitor()


        control = (
            ScenarioControlServer(
                net
            )
        )

        control.start()


        info(
            "\n"
            "==============================================\n"
            "       NETGUARDIAN CYBER RANGE v2\n"
            "==============================================\n"
            " h1  Client        10.10.0.11\n"
            " h2  Server        10.10.0.20\n"
            " h3  Test Host     10.10.0.30\n"
            "\n"
            " HTTP Server       h2:8080\n"
            " iperf3 Server     h2:5201\n"
            "\n"
            " OVS Mirror        zeek0\n"
            " Control API       127.0.0.1:8780\n"
            "==============================================\n"
        )


        info(
            "\n*** Connectivity test\n"
        )

        net.pingAll()


        info(
            "\n*** Browser scenarios are now enabled\n"
        )

        info(
            "*** Mininet CLI remains available for debugging\n\n"
        )


        CLI(
            net
        )


    finally:

        if control:

            control.stop()


        net.stop()

        cleanup_monitor()


        info(
            "\n*** Cyber Range v2 stopped\n"
        )


if __name__ == "__main__":
    main()
