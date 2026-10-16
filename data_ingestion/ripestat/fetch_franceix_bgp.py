#!/usr/bin/env python3

"""
NetGuardian Paris
RIPEstat / BGP intelligence for France-IX members.

Sources:
- RIPEstat announced-prefixes
- RIPEstat asn-neighbours

Outputs:
- exports/csv/bgp/bgp_asns.csv
- exports/csv/bgp/bgp_prefixes.csv
- exports/csv/bgp/bgp_neighbours.csv
- exports/csv/bgp/bgp_edges.csv
- exports/csv/bgp/bgp_franceix_internal_edges.csv
- exports/csv/bgp/bgp_summary.csv
- data/processed/bgp_franceix_graph.json

The collector uses a local cache to avoid repeating RIPEstat
requests every time the script is executed.
"""

from __future__ import annotations

import csv
import json
import os
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


# ============================================================
# CONFIGURATION
# ============================================================

ROOT = Path(__file__).resolve().parents[2]

RIPESTAT_BASE = (
    "https://stat.ripe.net/data"
)

MEMBERS_CSV = (
    ROOT
    / "exports/csv/france_ix/"
    / "france_ix_members.csv"
)

RAW_DIR = (
    ROOT
    / "data/raw/ripestat"
)

CSV_DIR = (
    ROOT
    / "exports/csv/bgp"
)

GRAPH_OUTPUT = (
    ROOT
    / "data/processed/"
    / "bgp_franceix_graph.json"
)

TIMEOUT = 60

MAX_RETRIES = 6

SLEEP_BETWEEN_REQUESTS = 0.25

USER_AGENT = (
    "NetGuardian-Paris/0.6 "
    "(academic network research)"
)

# Pour tester seulement quelques ASN :
#
# BGP_LIMIT=5 python3 ...
#
# 0 = tous les ASN.
ASN_LIMIT = int(
    os.getenv(
        "BGP_LIMIT",
        "0",
    )
)


# ============================================================
# GENERAL HELPERS
# ============================================================

def now_iso() -> str:
    return datetime.now(
        timezone.utc
    ).isoformat()


def load_json(
    path: Path,
) -> Any:

    with path.open(
        "r",
        encoding="utf-8",
    ) as file:

        return json.load(
            file
        )


def save_json(
    path: Path,
    value: Any,
) -> None:

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    path.write_text(
        json.dumps(
            value,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def write_csv(
    path: Path,
    rows: list[dict[str, Any]],
    fields: list[str] | None = None,
) -> None:

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    if not rows:
        print(
            f"[CSV] aucune donnée : "
            f"{path.name}"
        )
        return

    if fields is None:

        fields = []

        seen = set()

        for row in rows:
            for key in row:

                if key not in seen:
                    seen.add(key)
                    fields.append(key)

    with path.open(
        "w",
        encoding="utf-8-sig",
        newline="",
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=fields,
            extrasaction="ignore",
        )

        writer.writeheader()

        for row in rows:

            cleaned = {}

            for key in fields:

                value = row.get(
                    key
                )

                if isinstance(
                    value,
                    list,
                ):
                    value = " | ".join(
                        str(v)
                        for v in value
                    )

                elif isinstance(
                    value,
                    dict,
                ):
                    value = json.dumps(
                        value,
                        ensure_ascii=False,
                    )

                elif value is None:
                    value = ""

                cleaned[
                    key
                ] = value

            writer.writerow(
                cleaned
            )

    print(
        f"[CSV] "
        f"{path.relative_to(ROOT)} "
        f"({len(rows)} lignes)"
    )


def safe_int(
    value: Any,
) -> int | None:

    if value is None:
        return None

    text = str(
        value
    ).strip()

    if not text:
        return None

    text = (
        text
        .upper()
        .removeprefix("AS")
    )

    try:
        return int(text)

    except ValueError:
        return None


# ============================================================
# FRANCE-IX MEMBERS
# ============================================================

def load_members() -> list[dict[str, Any]]:

    if not MEMBERS_CSV.exists():
        raise FileNotFoundError(
            f"Fichier manquant : "
            f"{MEMBERS_CSV}"
        )

    with MEMBERS_CSV.open(
        encoding="utf-8-sig",
    ) as file:

        rows = list(
            csv.DictReader(file)
        )

    members = {}

    for row in rows:

        asn = safe_int(
            row.get("asn")
        )

        if asn is None:
            continue

        if asn not in members:

            members[asn] = {
                "asn":
                    asn,

                "name":
                    row.get(
                        "name"
                    )
                    or f"AS{asn}",

                "net_id":
                    row.get(
                        "net_id"
                    ),

                "network_type":
                    row.get(
                        "network_type"
                    ),

                "scope":
                    row.get(
                        "scope"
                    ),

                "traffic":
                    row.get(
                        "traffic"
                    ),

                "peering_policy":
                    row.get(
                        "peering_policy"
                    ),

                "capacity_gbps":
                    row.get(
                        "capacity_gbps"
                    ),

                "route_server_peer":
                    row.get(
                        "route_server_peer"
                    ),
            }

    result = [
        members[asn]
        for asn in sorted(
            members
        )
    ]

    if ASN_LIMIT > 0:

        result = result[
            :ASN_LIMIT
        ]

    return result


# ============================================================
# RIPESTAT HTTP
# ============================================================

def request_ripestat(
    endpoint: str,
    asn: int,
) -> dict[str, Any]:

    params = {
        "resource":
            f"AS{asn}",
    }

    # Le endpoint prefixes dispose d'un filtre
    # de visibilité. 10 est aussi sa valeur
    # par défaut, mais on l'explicite.
    if endpoint == "announced-prefixes":

        params[
            "min_peers_seeing"
        ] = 10

    url = (
        f"{RIPESTAT_BASE}/"
        f"{endpoint}/data.json?"
        f"{urlencode(params)}"
    )

    headers = {
        "Accept":
            "application/json",

        "User-Agent":
            USER_AGENT,
    }

    last_error = None

    for attempt in range(
        1,
        MAX_RETRIES + 1,
    ):

        request = Request(
            url,
            headers=headers,
        )

        try:

            with urlopen(
                request,
                timeout=TIMEOUT,
            ) as response:

                raw = (
                    response.read()
                )

            payload = json.loads(
                raw.decode(
                    "utf-8"
                )
            )

            return payload

        except HTTPError as exc:

            last_error = exc

            retry_after = (
                exc.headers.get(
                    "Retry-After"
                )
                if exc.headers
                else None
            )

            try:
                wait = float(
                    retry_after
                )

            except (
                TypeError,
                ValueError,
            ):

                wait = min(
                    60,
                    2 ** attempt,
                )

            if exc.code in {
                429,
                500,
                502,
                503,
                504,
            }:

                print(
                    f"\n[RIPEstat] "
                    f"HTTP {exc.code} "
                    f"AS{asn} "
                    f"{endpoint}"
                )

                print(
                    f"[RIPEstat] "
                    f"Nouvel essai dans "
                    f"{wait:.0f}s..."
                )

                time.sleep(
                    wait
                )

                continue

            raise

        except URLError as exc:

            last_error = exc

            wait = min(
                30,
                2 ** attempt,
            )

            print(
                f"\n[RIPEstat] "
                f"Erreur réseau AS{asn}"
            )

            print(
                f"[RIPEstat] "
                f"Nouvel essai dans "
                f"{wait}s..."
            )

            time.sleep(
                wait
            )

    raise RuntimeError(
        f"Impossible de récupérer "
        f"{endpoint} pour AS{asn}: "
        f"{last_error}"
    )


# ============================================================
# CACHE
# ============================================================

def cached_request(
    endpoint: str,
    asn: int,
) -> dict[str, Any]:

    cache_dir = (
        RAW_DIR
        / f"AS{asn}"
    )

    cache_file = (
        cache_dir
        / f"{endpoint}.json"
    )

    if cache_file.exists():

        try:
            return load_json(
                cache_file
            )

        except (
            json.JSONDecodeError,
            OSError,
        ):
            pass

    payload = request_ripestat(
        endpoint,
        asn,
    )

    cache_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    save_json(
        cache_file,
        payload,
    )

    time.sleep(
        SLEEP_BETWEEN_REQUESTS
    )

    return payload


# ============================================================
# PREFIXES
# ============================================================

def parse_prefixes(
    asn: int,
    payload: dict[str, Any],
) -> list[dict[str, Any]]:

    data = payload.get(
        "data",
        {}
    )

    prefixes = data.get(
        "prefixes",
        []
    )

    rows = []

    seen = set()

    for item in prefixes:

        prefix = item.get(
            "prefix"
        )

        if not prefix:
            continue

        key = (
            asn,
            prefix,
        )

        if key in seen:
            continue

        seen.add(
            key
        )

        family = (
            "IPv6"
            if ":" in prefix
            else "IPv4"
        )

        timelines = item.get(
            "timelines",
            []
        )

        first_seen = ""
        last_seen = ""

        if timelines:

            starts = [
                t.get(
                    "starttime"
                )
                for t in timelines
                if t.get(
                    "starttime"
                )
            ]

            ends = [
                t.get(
                    "endtime"
                )
                for t in timelines
                if t.get(
                    "endtime"
                )
            ]

            if starts:
                first_seen = min(
                    starts
                )

            if ends:
                last_seen = max(
                    ends
                )

        rows.append(
            {
                "asn":
                    asn,

                "prefix":
                    prefix,

                "address_family":
                    family,

                "timeline_count":
                    len(
                        timelines
                    ),

                "first_seen":
                    first_seen,

                "last_seen":
                    last_seen,

                "source":
                    "RIPEstat / RIPE RIS",

                "evidence_type":
                    "OBSERVED_BGP",
            }
        )

    return rows


# ============================================================
# ASN NEIGHBOURS
# ============================================================

def peer_count_value(
    value: Any,
) -> tuple[int, int]:

    if isinstance(
        value,
        dict,
    ):

        v4 = (
            value.get("v4")
            or value.get("ipv4")
            or 0
        )

        v6 = (
            value.get("v6")
            or value.get("ipv6")
            or 0
        )

        try:
            v4 = int(v4)
        except (
            TypeError,
            ValueError,
        ):
            v4 = 0

        try:
            v6 = int(v6)
        except (
            TypeError,
            ValueError,
        ):
            v6 = 0

        return (
            v4,
            v6,
        )

    return (
        0,
        0,
    )


def parse_neighbours(
    asn: int,
    payload: dict[str, Any],
) -> list[dict[str, Any]]:

    data = payload.get(
        "data",
        {}
    )

    neighbours = data.get(
        "neighbours",
        []
    )

    rows = []

    for item in neighbours:

        neighbour_asn = safe_int(
            item.get("asn")
        )

        if neighbour_asn is None:
            continue

        position = (
            item.get(
                "position"
            )
            or item.get(
                "type"
            )
            or "unknown"
        )

        path_count = (
            item.get(
                "path_count"
            )
        )

        if path_count is None:

            path_count = (
                item.get(
                    "power",
                    0,
                )
            )

        try:
            path_count = int(
                path_count or 0
            )

        except (
            TypeError,
            ValueError,
        ):
            path_count = 0

        peer_v4 = item.get(
            "v4_peers"
        )

        peer_v6 = item.get(
            "v6_peers"
        )

        structured_v4, structured_v6 = (
            peer_count_value(
                item.get(
                    "peer_count"
                )
            )
        )

        try:
            peer_v4 = int(
                peer_v4
                if peer_v4 is not None
                else structured_v4
            )

        except (
            TypeError,
            ValueError,
        ):
            peer_v4 = (
                structured_v4
            )

        try:
            peer_v6 = int(
                peer_v6
                if peer_v6 is not None
                else structured_v6
            )

        except (
            TypeError,
            ValueError,
        ):
            peer_v6 = (
                structured_v6
            )

        rows.append(
            {
                "asn":
                    asn,

                "neighbour_asn":
                    neighbour_asn,

                "position":
                    position,

                "path_count":
                    path_count,

                "ipv4_visibility":
                    peer_v4,

                "ipv6_visibility":
                    peer_v6,

                "source":
                    "RIPEstat / RIPE RIS",

                "relation":
                    "OBSERVED_BGP_ADJACENCY",

                "evidence_type":
                    "OBSERVED",
            }
        )

    return rows


# ============================================================
# EDGE AGGREGATION
# ============================================================

def build_edges(
    neighbour_rows:
        list[dict[str, Any]],

    member_asns:
        set[int],
) -> list[dict[str, Any]]:

    edge_map = {}

    for row in neighbour_rows:

        a = int(
            row["asn"]
        )

        b = int(
            row[
                "neighbour_asn"
            ]
        )

        if a == b:
            continue

        low = min(
            a,
            b,
        )

        high = max(
            a,
            b,
        )

        key = (
            low,
            high,
        )

        if key not in edge_map:

            edge_map[key] = {
                "source_asn":
                    low,

                "target_asn":
                    high,

                "relation":
                    "OBSERVED_BGP_ADJACENCY",

                "observed_from":
                    set(),

                "positions":
                    set(),

                "path_count":
                    0,

                "ipv4_visibility":
                    0,

                "ipv6_visibility":
                    0,

                "both_franceix_members":
                    (
                        low in member_asns
                        and
                        high in member_asns
                    ),

                "source":
                    "RIPEstat / RIPE RIS",

                "evidence_type":
                    "OBSERVED",
            }

        edge = edge_map[
            key
        ]

        edge[
            "observed_from"
        ].add(
            a
        )

        edge[
            "positions"
        ].add(
            str(
                row.get(
                    "position",
                    "unknown",
                )
            )
        )

        edge[
            "path_count"
        ] += int(
            row.get(
                "path_count",
                0,
            )
            or 0
        )

        edge[
            "ipv4_visibility"
        ] += int(
            row.get(
                "ipv4_visibility",
                0,
            )
            or 0
        )

        edge[
            "ipv6_visibility"
        ] += int(
            row.get(
                "ipv6_visibility",
                0,
            )
            or 0
        )

    rows = []

    for edge in edge_map.values():

        edge[
            "observed_from"
        ] = sorted(
            edge[
                "observed_from"
            ]
        )

        edge[
            "positions"
        ] = sorted(
            edge[
                "positions"
            ]
        )

        rows.append(
            edge
        )

    rows.sort(
        key=lambda row: (
            row[
                "source_asn"
            ],
            row[
                "target_asn"
            ],
        )
    )

    return rows


# ============================================================
# GRAPH
# ============================================================

def build_graph(
    members:
        list[dict[str, Any]],

    asn_rows:
        list[dict[str, Any]],

    edges:
        list[dict[str, Any]],
) -> dict[str, Any]:

    member_names = {
        int(m["asn"]):
            m.get(
                "name"
            )
            or f"AS{m['asn']}"

        for m in members
    }

    stats_by_asn = {
        int(row["asn"]):
            row

        for row in asn_rows
    }

    all_asns = set(
        member_names
    )

    for edge in edges:

        all_asns.add(
            int(
                edge[
                    "source_asn"
                ]
            )
        )

        all_asns.add(
            int(
                edge[
                    "target_asn"
                ]
            )
        )

    nodes = []

    for asn in sorted(
        all_asns
    ):

        stats = (
            stats_by_asn.get(
                asn,
                {}
            )
        )

        is_member = (
            asn in member_names
        )

        nodes.append(
            {
                "id":
                    f"asn-{asn}",

                "type":
                    "autonomous_system",

                "asn":
                    asn,

                "name":
                    (
                        member_names.get(
                            asn
                        )
                        or f"AS{asn}"
                    ),

                "franceix_member":
                    is_member,

                "prefix_count":
                    stats.get(
                        "prefix_count",
                        0,
                    ),

                "ipv4_prefix_count":
                    stats.get(
                        "ipv4_prefix_count",
                        0,
                    ),

                "ipv6_prefix_count":
                    stats.get(
                        "ipv6_prefix_count",
                        0,
                    ),

                "neighbour_count":
                    stats.get(
                        "neighbour_count",
                        0,
                    ),
            }
        )

    graph_edges = []

    for edge in edges:

        graph_edges.append(
            {
                "source":
                    (
                        f"asn-"
                        f"{edge['source_asn']}"
                    ),

                "target":
                    (
                        f"asn-"
                        f"{edge['target_asn']}"
                    ),

                "type":
                    "OBSERVED_BGP_ADJACENCY",

                "path_count":
                    edge.get(
                        "path_count",
                        0,
                    ),

                "both_franceix_members":
                    edge.get(
                        "both_franceix_members",
                        False,
                    ),
            }
        )

    return {
        "metadata": {
            "project":
                "NetGuardian Paris",

            "source":
                "RIPEstat / RIPE RIS",

            "generated_at":
                now_iso(),

            "important_note":
                (
                    "Edges represent BGP adjacency "
                    "observed in RIPE RIS paths. "
                    "They do not prove a physical "
                    "link or commercial peering "
                    "relationship."
                ),

            "member_asn_count":
                len(
                    member_names
                ),

            "node_count":
                len(nodes),

            "edge_count":
                len(
                    graph_edges
                ),
        },

        "nodes":
            nodes,

        "edges":
            graph_edges,
    }


# ============================================================
# MAIN
# ============================================================

def main():

    print()
    print(
        "=============================================="
    )
    print(
        " NETGUARDIAN PARIS - BGP / RIPESTAT"
    )
    print(
        "=============================================="
    )

    RAW_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    CSV_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    members = load_members()

    print()
    print(
        f"[BGP] ASN France-IX à analyser : "
        f"{len(members)}"
    )

    if ASN_LIMIT > 0:

        print(
            f"[BGP] MODE TEST : "
            f"{ASN_LIMIT} ASN maximum"
        )

    prefix_rows = []

    neighbour_rows = []

    asn_rows = []

    total = len(
        members
    )

    for index, member in enumerate(
        members,
        start=1,
    ):

        asn = int(
            member["asn"]
        )

        name = (
            member.get(
                "name"
            )
            or f"AS{asn}"
        )

        print()
        print(
            f"[BGP] "
            f"[{index}/{total}] "
            f"AS{asn} - {name}"
        )

        try:

            prefixes_payload = (
                cached_request(
                    "announced-prefixes",
                    asn,
                )
            )

            prefixes = (
                parse_prefixes(
                    asn,
                    prefixes_payload,
                )
            )

        except Exception as exc:

            print(
                f"[WARNING] Prefixes "
                f"AS{asn}: {exc}"
            )

            prefixes = []

        try:

            neighbours_payload = (
                cached_request(
                    "asn-neighbours",
                    asn,
                )
            )

            neighbours = (
                parse_neighbours(
                    asn,
                    neighbours_payload,
                )
            )

        except Exception as exc:

            print(
                f"[WARNING] Neighbours "
                f"AS{asn}: {exc}"
            )

            neighbours = []

        prefix_rows.extend(
            prefixes
        )

        neighbour_rows.extend(
            neighbours
        )

        ipv4 = sum(
            1
            for row in prefixes
            if row[
                "address_family"
            ] == "IPv4"
        )

        ipv6 = sum(
            1
            for row in prefixes
            if row[
                "address_family"
            ] == "IPv6"
        )

        unique_neighbours = {
            row[
                "neighbour_asn"
            ]
            for row in neighbours
        }

        asn_rows.append(
            {
                "asn":
                    asn,

                "name":
                    name,

                "franceix_member":
                    True,

                "prefix_count":
                    len(
                        prefixes
                    ),

                "ipv4_prefix_count":
                    ipv4,

                "ipv6_prefix_count":
                    ipv6,

                "neighbour_count":
                    len(
                        unique_neighbours
                    ),

                "capacity_gbps":
                    member.get(
                        "capacity_gbps"
                    ),

                "route_server_peer":
                    member.get(
                        "route_server_peer"
                    ),

                "network_type":
                    member.get(
                        "network_type"
                    ),

                "source":
                    "RIPEstat / RIPE RIS",
            }
        )

        print(
            f"      prefixes   : "
            f"{len(prefixes)} "
            f"(IPv4={ipv4}, "
            f"IPv6={ipv6})"
        )

        print(
            f"      neighbours : "
            f"{len(unique_neighbours)}"
        )

    member_asns = {
        int(
            member["asn"]
        )
        for member in members
    }

    edges = build_edges(
        neighbour_rows,
        member_asns,
    )

    internal_edges = [
        edge
        for edge in edges
        if edge[
            "both_franceix_members"
        ]
    ]

    graph = build_graph(
        members,
        asn_rows,
        edges,
    )

    save_json(
        GRAPH_OUTPUT,
        graph,
    )

    write_csv(
        CSV_DIR
        / "bgp_asns.csv",

        asn_rows,
    )

    write_csv(
        CSV_DIR
        / "bgp_prefixes.csv",

        prefix_rows,
    )

    write_csv(
        CSV_DIR
        / "bgp_neighbours.csv",

        neighbour_rows,
    )

    write_csv(
        CSV_DIR
        / "bgp_edges.csv",

        edges,
    )

    write_csv(
        CSV_DIR
        / "bgp_franceix_internal_edges.csv",

        internal_edges,
    )

    distinct_external_asns = set()

    for edge in edges:

        for asn in (
            edge[
                "source_asn"
            ],
            edge[
                "target_asn"
            ],
        ):

            if (
                int(asn)
                not in member_asns
            ):
                distinct_external_asns.add(
                    int(asn)
                )

    summary = [
        {
            "metric":
                "analysed_franceix_asns",

            "value":
                len(
                    members
                ),
        },
        {
            "metric":
                "announced_prefixes",

            "value":
                len(
                    prefix_rows
                ),
        },
        {
            "metric":
                "ipv4_prefixes",

            "value":
                sum(
                    1
                    for row
                    in prefix_rows
                    if row[
                        "address_family"
                    ] == "IPv4"
                ),
        },
        {
            "metric":
                "ipv6_prefixes",

            "value":
                sum(
                    1
                    for row
                    in prefix_rows
                    if row[
                        "address_family"
                    ] == "IPv6"
                ),
        },
        {
            "metric":
                "raw_neighbour_observations",

            "value":
                len(
                    neighbour_rows
                ),
        },
        {
            "metric":
                "unique_bgp_edges",

            "value":
                len(
                    edges
                ),
        },
        {
            "metric":
                "franceix_internal_bgp_edges",

            "value":
                len(
                    internal_edges
                ),
        },
        {
            "metric":
                "external_neighbour_asns",

            "value":
                len(
                    distinct_external_asns
                ),
        },
        {
            "metric":
                "graph_nodes",

            "value":
                len(
                    graph[
                        "nodes"
                    ]
                ),
        },
        {
            "metric":
                "graph_edges",

            "value":
                len(
                    graph[
                        "edges"
                    ]
                ),
        },
    ]

    write_csv(
        CSV_DIR
        / "bgp_summary.csv",

        summary,
        [
            "metric",
            "value",
        ],
    )

    print()
    print(
        "=============================================="
    )
    print(
        "          BGP / RIPESTAT ✅"
    )
    print(
        "=============================================="
    )

    print(
        f"ASN analysés       : "
        f"{len(members)}"
    )

    print(
        f"Préfixes           : "
        f"{len(prefix_rows)}"
    )

    print(
        f"Observations voisin: "
        f"{len(neighbour_rows)}"
    )

    print(
        f"Arêtes BGP uniques : "
        f"{len(edges)}"
    )

    print(
        f"Arêtes internes IX : "
        f"{len(internal_edges)}"
    )

    print(
        f"ASN externes       : "
        f"{len(distinct_external_asns)}"
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
        "Graph : "
        "data/processed/"
        "bgp_franceix_graph.json"
    )

    print(
        "CSV   : "
        "exports/csv/bgp/"
    )

    print(
        "=============================================="
    )


if __name__ == "__main__":
    main()
