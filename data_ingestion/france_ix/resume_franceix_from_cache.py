#!/usr/bin/env python3

"""
NetGuardian Paris
Reprise France-IX depuis les données déjà téléchargées.

Aucun nouvel appel PeeringDB n'est nécessaire pour reconstruire :
- membres France-IX
- ASN
- PoPs
- relations ASN <-> Facility
- graphe
- CSV
- GeoJSON
"""

from __future__ import annotations

import json
from pathlib import Path

import fetch_paris_franceix as fx


ROOT = Path(__file__).resolve().parents[2]

FRANCEIX_NETIXLAN = (
    ROOT
    / "data/raw/france_ix/france_ix_netixlan.json"
)

FRANCEIX_IXFAC = (
    ROOT
    / "data/raw/france_ix/france_ix_ixfac.json"
)

LOCAL_NETFAC = (
    ROOT
    / "data/raw/peeringdb/paris_netfac.json"
)

LOCAL_NETWORKS = (
    ROOT
    / "data/raw/peeringdb/paris_networks.json"
)

LOCAL_FACILITIES = (
    ROOT
    / "data/processed/peeringdb_paris_facilities.geojson"
)


def load_json(path: Path):
    if not path.exists():
        raise FileNotFoundError(
            f"Fichier manquant : {path}"
        )

    with path.open(
        "r",
        encoding="utf-8",
    ) as f:
        return json.load(f)


def load_records(path: Path):
    data = load_json(path)

    if isinstance(data, dict):
        records = data.get(
            "records",
            []
        )

        if isinstance(records, list):
            return records

    if isinstance(data, list):
        return data

    return []


def build_networks_from_cache(
    connections,
):
    """
    Utilise d'abord les détails PeeringDB déjà présents
    dans paris_networks.json.

    Complète les réseaux manquants à partir de netixlan.
    """

    network_map = {}

    if LOCAL_NETWORKS.exists():

        for network in load_records(
            LOCAL_NETWORKS
        ):
            net_id = network.get("id")

            if not net_id:
                continue

            network_map[
                int(net_id)
            ] = dict(network)

    for connection in connections:

        net_id = connection.get(
            "net_id"
        )

        if not net_id:
            continue

        net_id = int(net_id)

        if net_id not in network_map:

            asn = connection.get(
                "asn"
            )

            name = (
                connection.get("name")
                or connection.get(
                    "net_name"
                )
                or (
                    f"AS{asn}"
                    if asn
                    else
                    f"Network {net_id}"
                )
            )

            network_map[
                net_id
            ] = {
                "id":
                    net_id,

                "asn":
                    asn,

                "name":
                    name,

                "org_id":
                    None,

                "info_type":
                    None,

                "info_scope":
                    None,

                "info_traffic":
                    None,

                "policy_general":
                    None,

                "website":
                    None,

                "status":
                    "ok",
            }

    member_ids = {
        int(c["net_id"])
        for c in connections
        if c.get("net_id")
    }

    networks = [
        network_map[net_id]
        for net_id in sorted(
            member_ids
        )
        if net_id in network_map
    ]

    return networks


def load_franceix_facilities(
    ix_facilities,
):
    """
    Croise les facility IDs France-IX avec notre
    GeoJSON PeeringDB local.
    """

    data = load_json(
        LOCAL_FACILITIES
    )

    franceix_facility_ids = {
        int(row["fac_id"])
        for row in ix_facilities
        if row.get("fac_id")
    }

    facilities = []

    found_ids = set()

    for feature in data.get(
        "features",
        [],
    ):

        p = feature.get(
            "properties",
            {}
        )

        facility_id = p.get(
            "id"
        )

        if facility_id is None:
            continue

        try:
            facility_id = int(
                facility_id
            )
        except (
            ValueError,
            TypeError,
        ):
            continue

        if (
            facility_id
            not in franceix_facility_ids
        ):
            continue

        coordinates = (
            feature
            .get("geometry", {})
            .get("coordinates", [])
        )

        longitude = (
            coordinates[0]
            if len(coordinates) >= 2
            else None
        )

        latitude = (
            coordinates[1]
            if len(coordinates) >= 2
            else None
        )

        facility = dict(p)

        facility["id"] = (
            facility_id
        )

        facility["latitude"] = (
            latitude
        )

        facility["longitude"] = (
            longitude
        )

        facilities.append(
            facility
        )

        found_ids.add(
            facility_id
        )

    missing = (
        franceix_facility_ids
        -
        found_ids
    )

    if missing:
        print()
        print(
            "[WARNING] Facilities France-IX "
            "absentes du cache PeeringDB :"
        )

        print(
            "          ",
            sorted(missing),
        )

    return facilities


def load_local_netfac(
    member_net_ids,
    franceix_facility_ids,
):
    """
    Filtre le cache PeeringDB déjà téléchargé.

    On ne garde que :
    - les réseaux membres France-IX
    - dans les facilities France-IX
    """

    records = load_records(
        LOCAL_NETFAC
    )

    result = []

    for row in records:

        net_id = row.get(
            "net_id"
        )

        fac_id = row.get(
            "fac_id"
        )

        if (
            not net_id
            or not fac_id
        ):
            continue

        try:
            net_id = int(net_id)
            fac_id = int(fac_id)

        except (
            TypeError,
            ValueError,
        ):
            continue

        if (
            net_id in member_net_ids
            and
            fac_id in franceix_facility_ids
        ):
            result.append(
                row
            )

    return result


def main():

    print()
    print(
        "=============================================="
    )
    print(
        " NETGUARDIAN - FRANCE-IX CACHE RESUME"
    )
    print(
        "=============================================="
    )

    print()
    print(
        "[1/6] Chargement des connexions France-IX..."
    )

    connections = load_records(
        FRANCEIX_NETIXLAN
    )

    print(
        f"      {len(connections)} "
        f"connexions chargées"
    )

    print()
    print(
        "[2/6] Chargement des PoPs France-IX..."
    )

    ix_facilities = load_records(
        FRANCEIX_IXFAC
    )

    franceix_facility_ids = {
        int(row["fac_id"])
        for row in ix_facilities
        if row.get("fac_id")
    }

    print(
        f"      {len(franceix_facility_ids)} "
        f"PoPs distincts"
    )

    print()
    print(
        "[3/6] Reconstruction des réseaux / ASN..."
    )

    networks = (
        build_networks_from_cache(
            connections
        )
    )

    member_net_ids = {
        int(c["net_id"])
        for c in connections
        if c.get("net_id")
    }

    print(
        f"      {len(member_net_ids)} "
        f"réseaux distincts"
    )

    print()
    print(
        "[4/6] Croisement avec PeeringDB local..."
    )

    facilities = (
        load_franceix_facilities(
            ix_facilities
        )
    )

    netfac = (
        load_local_netfac(
            member_net_ids,
            franceix_facility_ids,
        )
    )

    print(
        f"      {len(facilities)} "
        f"facilities trouvées"
    )

    print(
        f"      {len(netfac)} "
        f"relations réseau/facility"
    )

    print()
    print(
        "[5/6] Construction du graphe..."
    )

    ix_service_by_id = {
        359: "Plus",
        5040: "Essentiel",
    }

    members = fx.build_members(
        connections,
        networks,
        ix_service_by_id,
    )

    local_peeringdb_ids = (
        fx.load_local_peeringdb_ids()
    )

    (
        pops,
        pop_geojson,
        member_fac,
    ) = fx.build_pops(
        facilities,
        ix_facilities,
        netfac,
        member_net_ids,
        local_peeringdb_ids,
    )

    relations = (
        fx.build_member_pop_relations(
            members,
            member_fac,
            facilities,
        )
    )

    graph = fx.build_graph(
        members,
        pops,
        relations,
    )

    print(
        f"      Membres : "
        f"{len(members)}"
    )

    print(
        f"      PoPs : "
        f"{len(pops)}"
    )

    print(
        f"      Relations ASN <-> PoP : "
        f"{len(relations)}"
    )

    print()
    print(
        "[6/6] Export..."
    )

    fx.save_json(
        fx.RAW_DIR
        / "france_ix_networks.json",

        {
            "retrieved_at":
                fx.now_iso(),

            "source":
                "local PeeringDB cache",

            "records":
                networks,
        },
    )

    fx.save_json(
        fx.RAW_DIR
        / "france_ix_facilities.json",

        {
            "retrieved_at":
                fx.now_iso(),

            "source":
                "local PeeringDB cache",

            "records":
                facilities,
        },
    )

    fx.save_json(
        fx.RAW_DIR
        / "france_ix_netfac.json",

        {
            "retrieved_at":
                fx.now_iso(),

            "source":
                "local PeeringDB cache",

            "records":
                netfac,
        },
    )

    fx.save_json(
        fx.POPS_GEOJSON,
        pop_geojson,
    )

    fx.save_json(
        fx.GRAPH_JSON,
        graph,
    )

    fx.write_csv(
        fx.CSV_DIR
        / "france_ix_members.csv",

        members,
    )

    fx.write_csv(
        fx.CSV_DIR
        / "france_ix_pops.csv",

        pops,
    )

    fx.write_csv(
        fx.CSV_DIR
        / "france_ix_member_pop_relations.csv",

        relations,
    )

    summary = [
        {
            "metric":
                "distinct_members",

            "value":
                len(members),
        },
        {
            "metric":
                "netixlan_connections",

            "value":
                len(connections),
        },
        {
            "metric":
                "france_ix_pops",

            "value":
                len(pops),
        },
        {
            "metric":
                "member_pop_colocation_relations",

            "value":
                len(relations),
        },
        {
            "metric":
                "graph_nodes",

            "value":
                len(
                    graph["nodes"]
                ),
        },
        {
            "metric":
                "graph_edges",

            "value":
                len(
                    graph["edges"]
                ),
        },
    ]

    fx.write_csv(
        fx.CSV_DIR
        / "france_ix_summary.csv",

        summary,
    )

    print()
    print(
        "=============================================="
    )
    print(
        "       FRANCE-IX PARIS ✅"
    )
    print(
        "=============================================="
    )

    print(
        f"Connexions IX      : "
        f"{len(connections)}"
    )

    print(
        f"Membres / ASN      : "
        f"{len(members)}"
    )

    print(
        f"PoPs               : "
        f"{len(pops)}"
    )

    print(
        f"Relations ASN↔PoP  : "
        f"{len(relations)}"
    )

    print(
        f"Graph nodes        : "
        f"{len(graph['nodes'])}"
    )

    print(
        f"Graph edges        : "
        f"{len(graph['edges'])}"
    )

    print()
    print(
        "GeoJSON : "
        "data/processed/"
        "france_ix_paris_pops.geojson"
    )

    print(
        "Graph   : "
        "data/processed/"
        "france_ix_paris_graph.json"
    )

    print(
        "CSV     : "
        "exports/csv/france_ix/"
    )

    print()
    print(
        "Aucun nouvel appel PeeringDB effectué."
    )

    print(
        "=============================================="
    )


if __name__ == "__main__":
    main()
