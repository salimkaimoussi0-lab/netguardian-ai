#!/usr/bin/env python3

from __future__ import annotations

import csv
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]

DATA = ROOT / "data/processed"

OUTPUT_GRAPH = (
    DATA
    / "netguardian_graph.json"
)

OUTPUT_NODES = (
    ROOT
    / "exports/csv/graph/nodes.csv"
)

OUTPUT_EDGES = (
    ROOT
    / "exports/csv/graph/edges.csv"
)

OUTPUT_SUMMARY = (
    ROOT
    / "exports/csv/graph/summary.csv"
)


# ============================================================
# FILES
# ============================================================

WIFI = (
    DATA
    / "paris_wifi_sites.geojson"
)

ANFR = (
    DATA
    / "anfr_paris_sites.geojson"
)

ARCEP = (
    DATA
    / "arcep_mobile_sites.geojson"
)

RIPE = (
    DATA
    / "ripe_atlas_paris_probes.geojson"
)

PEERINGDB = (
    DATA
    / "peeringdb_paris_facilities.geojson"
)

FRANCEIX_POPS = (
    DATA
    / "france_ix_paris_pops.geojson"
)

FRANCEIX_GRAPH = (
    DATA
    / "france_ix_paris_graph.json"
)

BGP_GRAPH = (
    DATA
    / "bgp_franceix_graph.json"
)


def now_iso():
    return datetime.now(
        timezone.utc
    ).isoformat()


def load_json(path: Path):

    if not path.exists():
        print(
            f"[WARNING] fichier absent : "
            f"{path.relative_to(ROOT)}"
        )

        return None

    with path.open(
        encoding="utf-8"
    ) as f:
        return json.load(f)


def clean(value):

    if isinstance(
        value,
        (str, int, float, bool)
    ):
        return value

    if value is None:
        return None

    return value


def first(
    mapping,
    *names,
    default=None,
):

    for name in names:

        value = mapping.get(
            name
        )

        if value not in (
            None,
            "",
            [],
        ):
            return value

    return default


def coordinates(feature):

    geometry = (
        feature.get(
            "geometry"
        )
        or {}
    )

    coords = geometry.get(
        "coordinates"
    )

    if (
        geometry.get("type") == "Point"
        and
        isinstance(coords, list)
        and
        len(coords) >= 2
    ):

        try:
            return (
                float(coords[1]),
                float(coords[0]),
            )

        except (
            TypeError,
            ValueError,
        ):
            pass

    return (
        None,
        None,
    )


# ============================================================
# GRAPH STORAGE
# ============================================================

nodes = {}

edges = {}

observations = []


def add_node(
    node_id: str,
    node_type: str,
    *,
    name=None,
    latitude=None,
    longitude=None,
    source=None,
    evidence_type=None,
    properties=None,
):

    if not node_id:
        return

    existing = nodes.get(
        node_id
    )

    data = {
        "id":
            node_id,

        "type":
            node_type,

        "name":
            name,

        "latitude":
            latitude,

        "longitude":
            longitude,

        "source":
            source,

        "evidence_type":
            evidence_type,

        "properties":
            properties or {},
    }

    if existing is None:

        nodes[node_id] = data

    else:

        # enrichissement non destructif

        for field in [
            "name",
            "latitude",
            "longitude",
            "source",
            "evidence_type",
        ]:

            if (
                existing.get(field)
                in (
                    None,
                    "",
                )
                and
                data.get(field)
                not in (
                    None,
                    "",
                )
            ):
                existing[field] = (
                    data[field]
                )

        existing[
            "properties"
        ].update(
            {
                k: v
                for k, v
                in data[
                    "properties"
                ].items()
                if v not in (
                    None,
                    "",
                    [],
                )
            }
        )


def add_edge(
    source: str,
    target: str,
    relation: str,
    *,
    evidence_type=None,
    source_name=None,
    properties=None,
):

    if not source or not target:
        return

    if source == target:
        return

    edge_id = (
        f"{source}|"
        f"{relation}|"
        f"{target}"
    )

    if edge_id in edges:
        return

    edges[
        edge_id
    ] = {
        "id":
            edge_id,

        "source":
            source,

        "target":
            target,

        "relation":
            relation,

        "evidence_type":
            evidence_type,

        "source_name":
            source_name,

        "properties":
            properties or {},
    }


# ============================================================
# WIFI
# ============================================================

def ingest_wifi():

    data = load_json(
        WIFI
    )

    if not data:
        return

    count = 0

    for feature in data.get(
        "features",
        []
    ):

        p = feature.get(
            "properties",
            {}
        )

        lat, lon = coordinates(
            feature
        )

        object_id = first(
            p,
            "id",
            "object_id",
            default=feature.get(
                "id"
            ),
        )

        if object_id is None:
            object_id = count + 1

        node_id = (
            f"wifi:{object_id}"
        )

        add_node(
            node_id,
            "wifi_site",
            name=first(
                p,
                "name",
                "nom_site",
                default="Paris Wi-Fi",
            ),
            latitude=lat,
            longitude=lon,
            source=first(
                p,
                "source",
                default="Paris Open Data",
            ),
            evidence_type=first(
                p,
                "evidence_type",
                default="PUBLIC_DECLARATION",
            ),
            properties=p,
        )

        count += 1

    print(
        f"[GRAPH] Wi-Fi : "
        f"{count}"
    )


# ============================================================
# ANFR
# ============================================================

def ingest_anfr():

    data = load_json(
        ANFR
    )

    if not data:
        return

    count = 0

    for feature in data.get(
        "features",
        []
    ):

        p = feature.get(
            "properties",
            {}
        )

        lat, lon = coordinates(
            feature
        )

        support_id = first(
            p,
            "sup_id",
            "id",
            "support_id",
            default=feature.get(
                "id"
            ),
        )

        if support_id is None:
            support_id = count + 1

        node_id = (
            f"anfr-support:{support_id}"
        )

        add_node(
            node_id,
            "mobile_support",
            name=first(
                p,
                "name",
                "nom_support",
                default=(
                    f"ANFR Support "
                    f"{support_id}"
                ),
            ),
            latitude=lat,
            longitude=lon,
            source=first(
                p,
                "source",
                default="ANFR",
            ),
            evidence_type=first(
                p,
                "evidence_type",
                default="PUBLIC_DECLARATION",
            ),
            properties=p,
        )

        count += 1

    print(
        f"[GRAPH] ANFR : "
        f"{count}"
    )


# ============================================================
# ARCEP
# ============================================================

def ingest_arcep():

    data = load_json(
        ARCEP
    )

    if not data:
        return

    count = 0
    relations = 0

    for feature in data.get(
        "features",
        []
    ):

        p = feature.get(
            "properties",
            {}
        )

        lat, lon = coordinates(
            feature
        )

        object_id = first(
            p,
            "id",
            default=feature.get(
                "id"
            ),
        )

        if object_id is None:
            object_id = count + 1

        node_id = (
            f"arcep-site:{object_id}"
        )

        operator = first(
            p,
            "operator",
            default="ARCEP mobile site",
        )

        add_node(
            node_id,
            "mobile_operator_site",
            name=operator,
            latitude=lat,
            longitude=lon,
            source=first(
                p,
                "source",
                default=(
                    "ARCEP - "
                    "Mon Réseau Mobile"
                ),
            ),
            evidence_type=first(
                p,
                "evidence_type",
                default=(
                    "OPERATOR_DECLARATION"
                ),
            ),
            properties=p,
        )

        support_ids = p.get(
            "anfr_support_ids",
            []
        )

        if isinstance(
            support_ids,
            str,
        ):
            support_ids = [
                x.strip()
                for x in
                support_ids.split("|")
                if x.strip()
            ]

        if not isinstance(
            support_ids,
            list,
        ):
            support_ids = []

        for support_id in support_ids:

            target = (
                f"anfr-support:"
                f"{support_id}"
            )

            if target not in nodes:
                continue

            add_edge(
                node_id,
                target,
                "DECLARED_ON",
                evidence_type=(
                    "PUBLIC_DECLARATION"
                ),
                source_name=(
                    "ARCEP / ANFR"
                ),
            )

            relations += 1

        count += 1

    print(
        f"[GRAPH] ARCEP : "
        f"{count}"
    )

    print(
        f"[GRAPH] ARCEP → ANFR : "
        f"{relations}"
    )


# ============================================================
# RIPE ATLAS
# ============================================================

def ingest_ripe():

    data = load_json(
        RIPE
    )

    if not data:
        return

    count = 0
    asn_edges = 0

    for feature in data.get(
        "features",
        []
    ):

        p = feature.get(
            "properties",
            {}
        )

        lat, lon = coordinates(
            feature
        )

        probe_id = first(
            p,
            "id",
            "probe_id",
            default=feature.get(
                "id"
            ),
        )

        if probe_id is None:
            continue

        node_id = (
            f"ripe-probe:"
            f"{probe_id}"
        )

        add_node(
            node_id,
            "ripe_probe",
            name=(
                f"RIPE Atlas "
                f"Probe {probe_id}"
            ),
            latitude=lat,
            longitude=lon,
            source=first(
                p,
                "source",
                default="RIPE Atlas",
            ),
            evidence_type=first(
                p,
                "evidence_type",
                default="OBSERVED",
            ),
            properties=p,
        )

        asns = set()

        for field in [
            "asn_v4",
            "asn_v6",
            "asn4",
            "asn6",
            "asn",
        ]:

            value = p.get(
                field
            )

            if value in (
                None,
                "",
            ):
                continue

            try:
                asns.add(
                    int(
                        str(value)
                        .upper()
                        .replace(
                            "AS",
                            "",
                        )
                    )
                )

            except ValueError:
                pass

        for asn in asns:

            asn_id = (
                f"asn:{asn}"
            )

            add_node(
                asn_id,
                "autonomous_system",
                name=f"AS{asn}",
                source="RIPE Atlas",
                evidence_type="OBSERVED",
                properties={
                    "asn":
                        asn
                },
            )

            add_edge(
                node_id,
                asn_id,
                "ORIGIN_AS",
                evidence_type=(
                    "OBSERVED"
                ),
                source_name=(
                    "RIPE Atlas"
                ),
            )

            asn_edges += 1

        count += 1

    print(
        f"[GRAPH] RIPE probes : "
        f"{count}"
    )

    print(
        f"[GRAPH] Probe → ASN : "
        f"{asn_edges}"
    )


# ============================================================
# PEERINGDB
# ============================================================

def ingest_peeringdb():

    data = load_json(
        PEERINGDB
    )

    if not data:
        return

    count = 0

    for feature in data.get(
        "features",
        []
    ):

        p = feature.get(
            "properties",
            {}
        )

        lat, lon = coordinates(
            feature
        )

        facility_id = first(
            p,
            "id",
            "facility_id",
            default=feature.get(
                "id"
            ),
        )

        if facility_id is None:
            continue

        node_id = (
            f"facility:"
            f"{facility_id}"
        )

        add_node(
            node_id,
            "facility",
            name=first(
                p,
                "name",
                default=(
                    f"Facility "
                    f"{facility_id}"
                ),
            ),
            latitude=lat,
            longitude=lon,
            source=first(
                p,
                "source",
                default="PeeringDB",
            ),
            evidence_type=first(
                p,
                "evidence_type",
                default=(
                    "PUBLIC_DECLARATION"
                ),
            ),
            properties=p,
        )

        count += 1

    print(
        f"[GRAPH] PeeringDB : "
        f"{count}"
    )


# ============================================================
# FRANCE-IX POPS
# ============================================================

def ingest_franceix_pops():

    data = load_json(
        FRANCEIX_POPS
    )

    if not data:
        return

    ix_id = (
        "ix:france-ix-paris"
    )

    add_node(
        ix_id,
        "internet_exchange",
        name="France-IX Paris",
        source=(
            "France-IX / PeeringDB"
        ),
        evidence_type=(
            "PUBLIC_DECLARATION"
        ),
    )

    count = 0

    for feature in data.get(
        "features",
        []
    ):

        p = feature.get(
            "properties",
            {}
        )

        facility_id = first(
            p,
            "facility_id",
        )

        if facility_id is None:
            continue

        facility_node = (
            f"facility:"
            f"{facility_id}"
        )

        add_edge(
            ix_id,
            facility_node,
            "PRESENT_AT",
            evidence_type=(
                "PUBLIC_DECLARATION"
            ),
            source_name=(
                "France-IX / PeeringDB"
            ),
        )

        count += 1

    print(
        f"[GRAPH] France-IX PoPs : "
        f"{count}"
    )


# ============================================================
# FRANCE-IX MEMBER GRAPH
# ============================================================

def ingest_franceix_graph():

    data = load_json(
        FRANCEIX_GRAPH
    )

    if not data:
        return

    ix_id = (
        "ix:france-ix-paris"
    )

    member_edges = 0

    for node in data.get(
        "nodes",
        []
    ):

        if (
            node.get("type")
            != "autonomous_system"
        ):
            continue

        asn = node.get(
            "asn"
        )

        if asn is None:
            continue

        asn_id = (
            f"asn:{asn}"
        )

        add_node(
            asn_id,
            "autonomous_system",
            name=first(
                node,
                "name",
                default=f"AS{asn}",
            ),
            source=(
                "PeeringDB / "
                "France-IX"
            ),
            evidence_type=(
                "PUBLIC_DECLARATION"
            ),
            properties={
                "asn":
                    asn,

                "franceix_member":
                    True,
            },
        )

        add_edge(
            asn_id,
            ix_id,
            "MEMBER_OF",
            evidence_type=(
                "PUBLIC_DECLARATION"
            ),
            source_name=(
                "PeeringDB / "
                "France-IX"
            ),
        )

        member_edges += 1

    print(
        f"[GRAPH] ASN → France-IX : "
        f"{member_edges}"
    )


# ============================================================
# BGP
# ============================================================

def ingest_bgp():

    data = load_json(
        BGP_GRAPH
    )

    if not data:
        return

    node_count = 0
    edge_count = 0

    for node in data.get(
        "nodes",
        []
    ):

        asn = node.get(
            "asn"
        )

        if asn is None:
            continue

        asn_id = (
            f"asn:{asn}"
        )

        add_node(
            asn_id,
            "autonomous_system",
            name=first(
                node,
                "name",
                default=f"AS{asn}",
            ),
            source=(
                "RIPEstat / RIPE RIS"
            ),
            evidence_type=(
                "OBSERVED"
            ),
            properties=node,
        )

        node_count += 1

    for edge in data.get(
        "edges",
        []
    ):

        source = str(
            edge.get(
                "source",
                ""
            )
        )

        target = str(
            edge.get(
                "target",
                ""
            )
        )

        if source.startswith(
            "asn-"
        ):
            source = (
                "asn:"
                + source[4:]
            )

        if target.startswith(
            "asn-"
        ):
            target = (
                "asn:"
                + target[4:]
            )

        if (
            not source
            or not target
        ):
            continue

        add_edge(
            source,
            target,
            "OBSERVED_BGP_ADJACENCY",
            evidence_type="OBSERVED",
            source_name=(
                "RIPEstat / RIPE RIS"
            ),
            properties={
                k: v
                for k, v
                in edge.items()
                if k not in {
                    "source",
                    "target",
                }
            },
        )

        edge_count += 1

    print(
        f"[GRAPH] BGP ASN nodes : "
        f"{node_count}"
    )

    print(
        f"[GRAPH] BGP edges : "
        f"{edge_count}"
    )


# ============================================================
# CSV
# ============================================================

def write_nodes_csv():

    OUTPUT_NODES.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    fields = [
        "id",
        "type",
        "name",
        "latitude",
        "longitude",
        "source",
        "evidence_type",
        "properties",
    ]

    with OUTPUT_NODES.open(
        "w",
        encoding="utf-8-sig",
        newline="",
    ) as f:

        writer = csv.DictWriter(
            f,
            fieldnames=fields,
        )

        writer.writeheader()

        for node in nodes.values():

            row = dict(
                node
            )

            row["properties"] = (
                json.dumps(
                    node.get(
                        "properties",
                        {},
                    ),
                    ensure_ascii=False,
                )
            )

            writer.writerow(
                row
            )


def write_edges_csv():

    fields = [
        "id",
        "source",
        "target",
        "relation",
        "evidence_type",
        "source_name",
        "properties",
    ]

    with OUTPUT_EDGES.open(
        "w",
        encoding="utf-8-sig",
        newline="",
    ) as f:

        writer = csv.DictWriter(
            f,
            fieldnames=fields,
        )

        writer.writeheader()

        for edge in edges.values():

            row = dict(
                edge
            )

            row["properties"] = (
                json.dumps(
                    edge.get(
                        "properties",
                        {},
                    ),
                    ensure_ascii=False,
                )
            )

            writer.writerow(
                row
            )


def write_summary():

    node_types = Counter(
        node["type"]
        for node in nodes.values()
    )

    relations = Counter(
        edge["relation"]
        for edge in edges.values()
    )

    rows = [
        {
            "category":
                "global",

            "name":
                "nodes",

            "value":
                len(nodes),
        },

        {
            "category":
                "global",

            "name":
                "edges",

            "value":
                len(edges),
        },
    ]

    for name, count in sorted(
        node_types.items()
    ):

        rows.append(
            {
                "category":
                    "node_type",

                "name":
                    name,

                "value":
                    count,
            }
        )

    for name, count in sorted(
        relations.items()
    ):

        rows.append(
            {
                "category":
                    "relation",

                "name":
                    name,

                "value":
                    count,
            }
        )

    with OUTPUT_SUMMARY.open(
        "w",
        encoding="utf-8-sig",
        newline="",
    ) as f:

        writer = csv.DictWriter(
            f,
            fieldnames=[
                "category",
                "name",
                "value",
            ],
        )

        writer.writeheader()

        writer.writerows(
            rows
        )


# ============================================================
# MAIN
# ============================================================

def main():

    print()
    print(
        "=============================================="
    )
    print(
        "   NETGUARDIAN UNIFIED NETWORK GRAPH"
    )
    print(
        "=============================================="
    )
    print()

    ingest_wifi()

    ingest_anfr()

    ingest_arcep()

    ingest_ripe()

    ingest_peeringdb()

    ingest_franceix_pops()

    ingest_franceix_graph()

    ingest_bgp()

    graph = {
        "metadata": {
            "project":
                "NetGuardian Paris",

            "generated_at":
                now_iso(),

            "node_count":
                len(nodes),

            "edge_count":
                len(edges),

            "model":
                "NetGuardian Unified Graph v1",

            "note":
                (
                    "Physical, declared and "
                    "observed relations are "
                    "distinguished using "
                    "evidence_type."
                ),
        },

        "nodes":
            list(
                nodes.values()
            ),

        "edges":
            list(
                edges.values()
            ),

        "observations":
            observations,
    }

    OUTPUT_GRAPH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with OUTPUT_GRAPH.open(
        "w",
        encoding="utf-8",
    ) as f:

        json.dump(
            graph,
            f,
            ensure_ascii=False,
        )

    write_nodes_csv()

    write_edges_csv()

    write_summary()

    node_types = Counter(
        node["type"]
        for node in nodes.values()
    )

    relations = Counter(
        edge["relation"]
        for edge in edges.values()
    )

    print()
    print(
        "=============================================="
    )
    print(
        "       NETGUARDIAN GRAPH ✅"
    )
    print(
        "=============================================="
    )

    print(
        f"Nodes : "
        f"{len(nodes)}"
    )

    print(
        f"Edges : "
        f"{len(edges)}"
    )

    print()
    print(
        "NODE TYPES"
    )

    for key, value in (
        node_types
        .most_common()
    ):
        print(
            f"  {key:25} "
            f"{value}"
        )

    print()
    print(
        "RELATIONS"
    )

    for key, value in (
        relations
        .most_common()
    ):
        print(
            f"  {key:30} "
            f"{value}"
        )

    print()
    print(
        "Graph : "
        "data/processed/"
        "netguardian_graph.json"
    )

    print(
        "CSV   : "
        "exports/csv/graph/"
    )

    print(
        "=============================================="
    )


if __name__ == "__main__":
    main()
