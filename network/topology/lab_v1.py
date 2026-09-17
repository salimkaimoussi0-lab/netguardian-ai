

from mininet.net import Mininet
from mininet.node import OVSController, OVSSwitch
from mininet.link import TCLink
from mininet.cli import CLI
from mininet.log import setLogLevel, info


def create_lab():
    info("\n")
    info("=====================================\n")
    info("      NetGuardian AI - LAB v1       \n")
    info("=====================================\n\n")

    net = Mininet(
        controller=OVSController,
        switch=OVSSwitch,
        link=TCLink,
        autoSetMacs=True
    )

    info("*** Adding OpenFlow controller\n")
    net.addController("c0")

    info("*** Adding Open vSwitch\n")
    s1 = net.addSwitch(
        "s1",
        protocols="OpenFlow13"
    )

    info("*** Adding hosts\n")

    h1 = net.addHost(
        "h1",
        ip="10.0.0.1/24"
    )

    h2 = net.addHost(
        "h2",
        ip="10.0.0.2/24"
    )

    h3 = net.addHost(
        "h3",
        ip="10.0.0.3/24"
    )

    info("*** Creating links\n")

    net.addLink(
        h1,
        s1,
        bw=100,
        delay="2ms"
    )

    net.addLink(
        h2,
        s1,
        bw=100,
        delay="2ms"
    )

    net.addLink(
        h3,
        s1,
        bw=100,
        delay="2ms"
    )

    info("*** Starting network\n")
    net.start()

    info("*** Testing connectivity\n")
    net.pingAll()

    info("\n")
    info("*** NetGuardian LAB v1 READY\n")
    info("*** Hosts      : h1 h2 h3\n")
    info("*** Switch     : s1\n")
    info("*** Controller : c0\n")
    info("*** Network    : 10.0.0.0/24\n\n")

    CLI(net)

    info("*** Stopping network\n")
    net.stop()


if __name__ == "__main__":
    setLogLevel("info")
    create_lab()
