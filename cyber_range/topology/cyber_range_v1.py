#!/usr/bin/env python3

from __future__ import annotations

import subprocess

from mininet.cli import CLI
from mininet.link import TCLink
from mininet.log import info, setLogLevel
from mininet.net import Mininet
from mininet.node import OVSSwitch
from mininet.topo import Topo


SWITCH = "s1"

MONITOR_IFACE = "zeek0"
OVS_MONITOR_IFACE = "ovs-zeek0"


# ============================================================
# COMMAND HELPER
# ============================================================

def run(*args: str):

    result = subprocess.run(
        list(args),
        text=True,
        capture_output=True,
    )

    if result.returncode != 0:

        raise RuntimeError(
            "\nCommande échouée:\n"
            + " ".join(args)
            + "\n\nSTDOUT:\n"
            + result.stdout
            + "\nSTDERR:\n"
            + result.stderr
        )

    return result


# ============================================================
# CLEANUP MONITOR
# ============================================================

def cleanup_monitor():

    subprocess.run(
        [
            "ovs-vsctl",
            "--if-exists",
            "clear",
            "Bridge",
            SWITCH,
            "mirrors",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    subprocess.run(
        [
            "ovs-vsctl",
            "--if-exists",
            "del-port",
            SWITCH,
            OVS_MONITOR_IFACE,
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    subprocess.run(
        [
            "ip",
            "link",
            "del",
            MONITOR_IFACE,
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


# ============================================================
# ZEEK MIRROR
# ============================================================

def configure_monitor():

    info(
        "\n*** Configuration du miroir OVS pour Zeek\n"
    )

    cleanup_monitor()

    #
    # Création d'une paire veth :
    #
    # s1 -> ovs-zeek0 === zeek0 -> Zeek
    #

    run(
        "ip",
        "link",
        "add",
        MONITOR_IFACE,
        "type",
        "veth",
        "peer",
        "name",
        OVS_MONITOR_IFACE,
    )

    run(
        "ip",
        "link",
        "set",
        MONITOR_IFACE,
        "up",
    )

    run(
        "ip",
        "link",
        "set",
        OVS_MONITOR_IFACE,
        "up",
    )

    run(
        "ovs-vsctl",
        "add-port",
        SWITCH,
        OVS_MONITOR_IFACE,
    )

    #
    # Copie de tout le trafic traversant s1
    # vers ovs-zeek0.
    #

    run(
        "ovs-vsctl",
        "--",
        "--id=@monitor",
        "get",
        "Port",
        OVS_MONITOR_IFACE,
        "--",
        "--id=@mirror",
        "create",
        "Mirror",
        "name=netguardian-zeek",
        "select-all=true",
        "output-port=@monitor",
        "--",
        "set",
        "Bridge",
        SWITCH,
        "mirrors=@mirror",
    )

    info(
        "*** Miroir actif : "
        "s1 -> ovs-zeek0 -> zeek0\n"
    )


# ============================================================
# TOPOLOGY
# ============================================================

class CyberRangeTopo(Topo):

    def build(self):

        s1 = self.addSwitch(
            SWITCH,
            protocols="OpenFlow13",
            failMode="standalone",
        )

        #
        # h1 = client légitime
        #

        h1 = self.addHost(
            "h1",
            ip="10.10.0.11/24",
        )

        #
        # h2 = serveur du laboratoire
        #

        h2 = self.addHost(
            "h2",
            ip="10.10.0.20/24",
        )

        #
        # h3 = machine de test cyber
        #

        h3 = self.addHost(
            "h3",
            ip="10.10.0.30/24",
        )

        self.addLink(
            h1,
            s1,
            cls=TCLink,
            bw=100,
            delay="2ms",
        )

        self.addLink(
            h2,
            s1,
            cls=TCLink,
            bw=100,
            delay="2ms",
        )

        self.addLink(
            h3,
            s1,
            cls=TCLink,
            bw=100,
            delay="2ms",
        )


# ============================================================
# MAIN
# ============================================================

def main():

    setLogLevel("info")

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

    try:

        info(
            "\n*** Démarrage NetGuardian Cyber Range\n"
        )

        net.start()

        s1 = net.get(
            SWITCH
        )

        #
        # Switch L2 autonome pour Cyber Range v1.
        # Le contrôleur SDN viendra plus tard.
        #

        s1.cmd(
            "ovs-vsctl "
            "set-fail-mode s1 standalone"
        )

        s1.cmd(
            "ovs-vsctl "
            "set Bridge s1 "
            "protocols=OpenFlow13"
        )

        configure_monitor()

        info(
            "\n"
            "==============================================\n"
            "       NETGUARDIAN CYBER RANGE v1\n"
            "==============================================\n"
            "\n"
            " h1  Client        10.10.0.11\n"
            " h2  Server        10.10.0.20\n"
            " h3  Test Host     10.10.0.30\n"
            "\n"
            " s1  Open vSwitch  OpenFlow 1.3\n"
            "\n"
            " zeek0             Monitoring interface\n"
            "\n"
            " Links             100 Mbit/s / 2 ms\n"
            "\n"
            "==============================================\n"
        )

        info(
            "\n*** Test automatique de connectivité\n"
        )

        net.pingAll()

        info(
            "\n*** Ouverture CLI Mininet\n"
        )

        info(
            "*** Tape 'exit' pour quitter.\n\n"
        )

        CLI(net)

    finally:

        info(
            "\n*** Arrêt Cyber Range\n"
        )

        net.stop()

        cleanup_monitor()

        info(
            "*** Nettoyage terminé\n"
        )


if __name__ == "__main__":
    main()
