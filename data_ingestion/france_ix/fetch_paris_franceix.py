#!/usr/bin/env python3

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
# CONFIG
# ============================================================

ROOT = Path(__file__).resolve().parents[2]

BASE_URL = "https://www.peeringdb.com/api"

FRANCE_IX_EXCHANGES = [
    {
        "ix_id": 359,
        "name": "France-IX Paris",
        "service": "Plus",
    },
    {
        "ix_id": 5040,
        "name": "France-IX Paris Essentiel",
        "service": "Essentiel",
    },
]

TIMEOUT = 60
PAGE_SIZE = 250

API_KEY = os.getenv("PEERINGDB_API_KEY")

USER_AGENT = (
    "NetGuardian-Paris/0.5 "
    "(academic network research project)"
)

RAW_DIR = ROOT / "data/raw/france_ix"

PROCESSED_DIR = ROOT / "data/processed"

CSV_DIR = ROOT / "exports/csv/france_ix"

PEERINGDB_LOCAL = (
    ROOT
    / "data/processed/"
    / "peeringdb_paris_facilities.geojson"
)

POPS_GEOJSON = (
    PROCESSED_DIR
    / "france_ix_paris_pops.geojson"
)

GRAPH_JSON = (
    PROCESSED_DIR
    / "france_ix_paris_graph.json"
)


# ============================================================
# HELPERS
# ============================================================

def now_iso() -> str:
    return datetime.now(
        timezone.utc
    ).isoformat()


def request_json(
    url: str,
) -> dict[str, Any]:

    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json",
    }

    if API_KEY:
        headers["Authorization"] = (
            f"Api-Key {API_KEY}"
        )

    request = Request(
        url,
        headers=headers,
    )

    try:
        with urlopen(
            request,
            timeout=TIMEOUT,
        ) as response:

            return json.loads(
                response
                .read()
                .decode("utf-8")
            )

    except HTTPError as exc:
        body = ""

        try:
            body = (
                exc.read()
                .decode(
                    "utf-8",
                    errors="replace",
                )
            )
        except Exception:
            pass

        raise RuntimeError(
            f"HTTP {exc.code}: {url}\n"
            f"{body[:500]}"
        ) from exc

    except URLError as exc:
        raise RuntimeError(
            f"Network error: "
            f"{exc.reason}"
        ) from exc


def api_list(
    endpoint: str,
    params: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:

    params = dict(
        params or {}
    )

    params.setdefault(
        "limit",
        PAGE_SIZE,
    )

    params.setdefault(
        "skip",
        0,
    )

    records = []

    while True:
        query = urlencode(
            params,
            doseq=True,
        )

        url = (
            f"{BASE_URL}/{endpoint}"
            f"?{query}"
        )

        payload = request_json(
            url
        )

        data = payload.get(
            "data",
            [],
        )

        if not isinstance(
            data,
            list,
        ):
            raise RuntimeError(
                f"Invalid API response "
                f"for {endpoint}"
            )

        records.extend(data)

        if len(data) < int(
            params["limit"]
        ):
            break

        params["skip"] += int(
            params["limit"]
        )

        time.sleep(0.2)

    return records


def api_list_with_fallback(
    endpoint: str,
    candidates: list[
        dict[str, Any]
    ],
) -> list[dict[str, Any]]:

    last_error = None

    for params in candidates:
        try:
            return api_list(
                endpoint,
                params,
            )

        except RuntimeError as exc:
            last_error = exc

    if last_error:
        raise last_error

    return []


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
    rows: list[
        dict[str, Any]
    ],
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
        )

        writer.writeheader()

        for row in rows:

            cleaned = {}

            for key in fields:
                value = row.get(key)

                if isinstance(
                    value,
                    list,
                ):
                    value = " | ".join(
                        str(x)
                        for x in value
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

                cleaned[key] = value

            writer.writerow(
                cleaned
            )

    print(
        f"[CSV] "
        f"{path.relative_to(ROOT)} "
        f"({len(rows)} lignes)"
    )


def chunks(
    values: list[int],
    size: int = 50,
):
    for start in range(
        0,
        len(values),
        size,
    ):
        yield values[
            start:start + size
        ]


# ============================================================
# EXCHANGE
# ============================================================

def fetch_exchange(
    ix_id: int,
) -> dict[str, Any]:

    records = api_list(
        "ix",
        {
            "id": ix_id,
            "status": "ok",
        },
    )

    if not records:
        raise RuntimeError(
            f"IX {ix_id} introuvable."
        )

    return records[0]


# ============================================================
# NETIXLAN = MEMBERS CONNECTED TO FRANCE-IX
# ============================================================

def fetch_connections(
    ix_id: int,
) -> list[dict[str, Any]]:

    print(
        f"[FRANCE-IX] Connexions "
        f"IX {ix_id}..."
    )

    records = (
        api_list_with_fallback(
            "netixlan",
            [
                {
                    "ixlan_id":
                        ix_id,

                    "status":
                        "ok",
                },
                {
                    "ix_id":
                        ix_id,

                    "status":
                        "ok",
                },
            ],
        )
    )

    # sécurité supplémentaire
    records = [
        row
        for row in records
        if (
            row.get("ix_id")
            in (None, ix_id)
            and
            row.get(
                "ixlan_id"
            )
            in (None, ix_id)
        )
    ]

    return records


# ============================================================
# IX FACILITIES / POP
# ============================================================

def fetch_ixfac(
    ix_id: int,
) -> list[dict[str, Any]]:

    print(
        f"[FRANCE-IX] PoPs "
        f"IX {ix_id}..."
    )

    return api_list(
        "ixfac",
        {
            "ix_id": ix_id,
            "status": "ok",
        },
    )


# ============================================================
# NETWORK DETAILS
# ============================================================

def fetch_networks(
    net_ids: list[int],
) -> list[dict[str, Any]]:

    result = []

    for number, batch in enumerate(
        chunks(
            net_ids,
            50,
        ),
        start=1,
    ):

        print(
            f"[FRANCE-IX] "
            f"Networks batch "
            f"{number}"
        )

        records = api_list(
            "net",
            {
                "id__in":
                    ",".join(
                        str(x)
                        for x in batch
                    ),

                "status":
                    "ok",
            },
        )

        result.extend(
            records
        )

        time.sleep(0.2)

    return result


# ============================================================
# FACILITY DETAILS
# ============================================================

def fetch_facilities(
    facility_ids: list[int],
) -> list[dict[str, Any]]:

    result = []

    for number, batch in enumerate(
        chunks(
            facility_ids,
            50,
        ),
        start=1,
    ):

        print(
            f"[FRANCE-IX] "
            f"Facilities batch "
            f"{number}"
        )

        records = api_list(
            "fac",
            {
                "id__in":
                    ",".join(
                        str(x)
                        for x in batch
                    ),

                "status":
                    "ok",
            },
        )

        result.extend(
            records
        )

        time.sleep(0.2)

    return result


# ============================================================
# NETWORK -> FACILITY
# ============================================================

def fetch_netfac(
    net_ids: list[int],
) -> list[dict[str, Any]]:

    result = []

    for number, batch in enumerate(
        chunks(
            net_ids,
            40,
        ),
        start=1,
    ):

        print(
            f"[FRANCE-IX] "
            f"NetFac batch "
            f"{number}"
        )

        records = api_list(
            "netfac",
            {
                "net_id__in":
                    ",".join(
                        str(x)
                        for x in batch
                    ),

                "status":
                    "ok",
            },
        )

        result.extend(
            records
        )

        time.sleep(0.2)

    return result


# ============================================================
# LOCAL PEERINGDB CROSS-REFERENCE
# ============================================================

def load_local_peeringdb_ids() -> set[int]:

    if not PEERINGDB_LOCAL.exists():
        return set()

    with PEERINGDB_LOCAL.open(
        encoding="utf-8",
    ) as file:

        data = json.load(
            file
        )

    ids = set()

    for feature in data.get(
        "features",
        [],
    ):

        p = feature.get(
            "properties",
            {},
        )

        facility_id = p.get(
            "id"
        )

        try:
            ids.add(
                int(facility_id)
            )
        except (
            TypeError,
            ValueError,
        ):
            pass

    return ids


# ============================================================
# MEMBERS
# ============================================================

def build_members(
    connections,
    networks,
    ix_service_by_id,
):

    networks_by_id = {
        int(n["id"]): n
        for n in networks
        if n.get("id")
    }

    grouped = defaultdict(
        lambda: {
            "connections": [],
            "services": set(),
        }
    )

    for connection in connections:

        net_id = connection.get(
            "net_id"
        )

        asn = connection.get(
            "asn"
        )

        if not net_id:
            continue

        key = int(net_id)

        grouped[key][
            "connections"
        ].append(
            connection
        )

        ix_id = connection.get(
            "ix_id"
        )

        service = (
            ix_service_by_id
            .get(
                int(ix_id)
                if ix_id
                else None
            )
        )

        if service:
            grouped[key][
                "services"
            ].add(
                service
            )

    rows = []

    for net_id, group in grouped.items():

        network = networks_by_id.get(
            net_id,
            {}
        )

        conns = group[
            "connections"
        ]

        asns = {
            c.get("asn")
            for c in conns
            if c.get("asn")
        }

        asn = (
            sorted(asns)[0]
            if asns
            else network.get(
                "asn"
            )
        )

        ips4 = sorted(
            {
                c.get("ipaddr4")
                for c in conns
                if c.get(
                    "ipaddr4"
                )
            }
        )

        ips6 = sorted(
            {
                c.get("ipaddr6")
                for c in conns
                if c.get(
                    "ipaddr6"
                )
            }
        )

        speed_mbps = sum(
            int(
                c.get(
                    "speed",
                    0,
                )
                or 0
            )
            for c in conns
        )

        rs_peer = any(
            bool(
                c.get(
                    "is_rs_peer"
                )
            )
            for c in conns
        )

        operational = any(
            c.get(
                "operational"
            )
            is True
            for c in conns
        )

        rows.append(
            {
                "net_id":
                    net_id,

                "asn":
                    asn,

                "name":
                    network.get(
                        "name"
                    ),

                "organization_id":
                    network.get(
                        "org_id"
                    ),

                "network_type":
                    network.get(
                        "info_type"
                    ),

                "scope":
                    network.get(
                        "info_scope"
                    ),

                "traffic":
                    network.get(
                        "info_traffic"
                    ),

                "peering_policy":
                    network.get(
                        "policy_general"
                    ),

                "website":
                    network.get(
                        "website"
                    ),

                "services":
                    sorted(
                        group[
                            "services"
                        ]
                    ),

                "connection_count":
                    len(conns),

                "capacity_mbps":
                    speed_mbps,

                "capacity_gbps":
                    round(
                        speed_mbps
                        / 1000,
                        3,
                    ),

                "ipv4_addresses":
                    ips4,

                "ipv6_addresses":
                    ips6,

                "route_server_peer":
                    rs_peer,

                "operational":
                    operational,

                "source":
                    "PeeringDB",

                "exchange":
                    "France-IX Paris",
            }
        )

    rows.sort(
        key=lambda x: (
            -int(
                x.get(
                    "capacity_mbps",
                    0,
                )
                or 0
            ),
            str(
                x.get(
                    "name",
                    ""
                )
            ),
        )
    )

    return rows


# ============================================================
# POPS
# ============================================================

def build_pops(
    facilities,
    ix_facilities,
    netfac,
    member_net_ids,
    local_peeringdb_ids,
):

    facilities_by_id = {
        int(f["id"]): f
        for f in facilities
        if f.get("id")
    }

    ix_by_fac = defaultdict(
        set
    )

    for relation in ix_facilities:

        fac_id = relation.get(
            "fac_id"
        )

        ix_id = relation.get(
            "ix_id"
        )

        if not fac_id:
            continue

        ix_by_fac[
            int(fac_id)
        ].add(
            int(ix_id)
            if ix_id
            else 0
        )

    member_fac = defaultdict(
        set
    )

    for relation in netfac:

        net_id = relation.get(
            "net_id"
        )

        fac_id = relation.get(
            "fac_id"
        )

        if (
            not net_id
            or not fac_id
        ):
            continue

        net_id = int(net_id)
        fac_id = int(fac_id)

        if net_id not in (
            member_net_ids
        ):
            continue

        if fac_id not in (
            ix_by_fac
        ):
            continue

        member_fac[
            fac_id
        ].add(
            net_id
        )

    rows = []

    features = []

    for fac_id in sorted(
        ix_by_fac
    ):

        facility = (
            facilities_by_id
            .get(
                fac_id
            )
        )

        if not facility:
            continue

        latitude = facility.get(
            "latitude"
        )

        longitude = facility.get(
            "longitude"
        )

        services = []

        for ix_id in sorted(
            ix_by_fac[
                fac_id
            ]
        ):

            if ix_id == 359:
                services.append(
                    "Plus"
                )

            elif ix_id == 5040:
                services.append(
                    "Essentiel"
                )

            else:
                services.append(
                    f"IX-{ix_id}"
                )

        row = {
            "facility_id":
                fac_id,

            "name":
                facility.get(
                    "name"
                ),

            "organization":
                facility.get(
                    "org_name"
                ),

            "address1":
                facility.get(
                    "address1"
                ),

            "address2":
                facility.get(
                    "address2"
                ),

            "city":
                facility.get(
                    "city"
                ),

            "postal_code":
                facility.get(
                    "zipcode"
                ),

            "country":
                facility.get(
                    "country"
                ),

            "latitude":
                latitude,

            "longitude":
                longitude,

            "services":
                sorted(
                    set(
                        services
                    )
                ),

            "colocated_member_count":
                len(
                    member_fac.get(
                        fac_id,
                        set(),
                    )
                ),

            "matched_netguardian_peeringdb":
                (
                    fac_id
                    in local_peeringdb_ids
                ),

            "relation_type":
                "IX_PRESENT_AT_FACILITY",

            "source":
                "PeeringDB",

            "evidence_type":
                "PUBLIC_DECLARATION",
        }

        rows.append(
            row
        )

        try:
            lat = float(
                latitude
            )

            lon = float(
                longitude
            )

        except (
            TypeError,
            ValueError,
        ):
            continue

        features.append(
            {
                "type":
                    "Feature",

                "id":
                    f"franceix-pop-{fac_id}",

                "geometry": {
                    "type":
                        "Point",

                    "coordinates": [
                        lon,
                        lat,
                    ],
                },

                "properties":
                    row,
            }
        )

    geojson = {
        "type":
            "FeatureCollection",

        "name":
            "NetGuardian France-IX Paris PoPs",

        "metadata": {
            "source":
                "PeeringDB / France-IX",

            "retrieved_at":
                now_iso(),

            "note":
                (
                    "France-IX PoPs are "
                    "PeeringDB facilities "
                    "where France-IX has "
                    "a declared presence."
                ),

            "feature_count":
                len(features),
        },

        "features":
            features,
    }

    return (
        rows,
        geojson,
        member_fac,
    )


# ============================================================
# MEMBER ↔ POP RELATIONS
# ============================================================

def build_member_pop_relations(
    members,
    member_fac,
    facilities,
):

    members_by_net = {
        int(row["net_id"]):
            row
        for row in members
        if row.get(
            "net_id"
        )
    }

    facilities_by_id = {
        int(f["id"]):
            f
        for f in facilities
        if f.get("id")
    }

    rows = []

    for fac_id, net_ids in (
        member_fac.items()
    ):

        facility = (
            facilities_by_id
            .get(
                fac_id,
                {},
            )
        )

        for net_id in sorted(
            net_ids
        ):

            member = (
                members_by_net
                .get(
                    net_id,
                    {},
                )
            )

            rows.append(
                {
                    "facility_id":
                        fac_id,

                    "facility":
                        facility.get(
                            "name"
                        ),

                    "city":
                        facility.get(
                            "city"
                        ),

                    "net_id":
                        net_id,

                    "asn":
                        member.get(
                            "asn"
                        ),

                    "network":
                        member.get(
                            "name"
                        ),

                    "relation":
                        "COLOCATED_PRESENCE",

                    "confidence":
                        "PUBLIC_DECLARATION",

                    "note":
                        (
                            "Network and "
                            "France-IX are both "
                            "declared present at "
                            "this facility. This "
                            "does not necessarily "
                            "prove the member's "
                            "France-IX port "
                            "terminates here."
                        ),
                }
            )

    return rows


# ============================================================
# GRAPH
# ============================================================

def build_graph(
    members,
    pops,
    relations,
):

    nodes = []
    edges = []

    nodes.append(
        {
            "id":
                "ix-franceix-paris",

            "type":
                "internet_exchange",

            "name":
                "France-IX Paris",
        }
    )

    for pop in pops:

        nodes.append(
            {
                "id":
                    (
                        "fac-"
                        f"{pop['facility_id']}"
                    ),

                "type":
                    "facility",

                "name":
                    pop.get(
                        "name"
                    ),

                "latitude":
                    pop.get(
                        "latitude"
                    ),

                "longitude":
                    pop.get(
                        "longitude"
                    ),
            }
        )

        edges.append(
            {
                "source":
                    "ix-franceix-paris",

                "target":
                    (
                        "fac-"
                        f"{pop['facility_id']}"
                    ),

                "type":
                    "IX_PRESENT_AT_FACILITY",
            }
        )

    for member in members:

        nodes.append(
            {
                "id":
                    (
                        "asn-"
                        f"{member['asn']}"
                    ),

                "type":
                    "autonomous_system",

                "asn":
                    member.get(
                        "asn"
                    ),

                "name":
                    member.get(
                        "name"
                    ),
            }
        )

        edges.append(
            {
                "source":
                    (
                        "asn-"
                        f"{member['asn']}"
                    ),

                "target":
                    "ix-franceix-paris",

                "type":
                    "MEMBER_OF_IX",
            }
        )

    for relation in relations:

        edges.append(
            {
                "source":
                    (
                        "asn-"
                        f"{relation['asn']}"
                    ),

                "target":
                    (
                        "fac-"
                        f"{relation['facility_id']}"
                    ),

                "type":
                    "COLOCATED_PRESENCE",
            }
        )

    return {
        "metadata": {
            "project":
                "NetGuardian Paris",

            "retrieved_at":
                now_iso(),

            "source":
                "PeeringDB / France-IX",
        },

        "nodes":
            nodes,

        "edges":
            edges,
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
        "     NETGUARDIAN PARIS - FRANCE-IX"
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

    exchanges = []

    all_connections = []
    all_ixfac = []

    ix_service_by_id = {}

    for config in (
        FRANCE_IX_EXCHANGES
    ):

        ix_id = config[
            "ix_id"
        ]

        print()
        print(
            f"[FRANCE-IX] "
            f"{config['name']}"
        )

        exchange = (
            fetch_exchange(
                ix_id
            )
        )

        exchange[
            "_service"
        ] = config[
            "service"
        ]

        exchanges.append(
            exchange
        )

        ix_service_by_id[
            ix_id
        ] = config[
            "service"
        ]

        connections = (
            fetch_connections(
                ix_id
            )
        )

        for connection in connections:
            connection[
                "_service"
            ] = config[
                "service"
            ]

        all_connections.extend(
            connections
        )

        ix_facilities = (
            fetch_ixfac(
                ix_id
            )
        )

        all_ixfac.extend(
            ix_facilities
        )

        print(
            f"  Connexions : "
            f"{len(connections)}"
        )

        print(
            f"  Facilities : "
            f"{len(ix_facilities)}"
        )

    save_json(
        RAW_DIR /
        "france_ix_exchanges.json",

        {
            "retrieved_at":
                now_iso(),

            "records":
                exchanges,
        },
    )

    save_json(
        RAW_DIR /
        "france_ix_netixlan.json",

        {
            "retrieved_at":
                now_iso(),

            "records":
                all_connections,
        },
    )

    save_json(
        RAW_DIR /
        "france_ix_ixfac.json",

        {
            "retrieved_at":
                now_iso(),

            "records":
                all_ixfac,
        },
    )

    net_ids = sorted(
        {
            int(
                row["net_id"]
            )
            for row
            in all_connections
            if row.get(
                "net_id"
            )
        }
    )

    facility_ids = sorted(
        {
            int(
                row["fac_id"]
            )
            for row
            in all_ixfac
            if row.get(
                "fac_id"
            )
        }
    )

    print()
    print(
        f"[FRANCE-IX] "
        f"Réseaux distincts : "
        f"{len(net_ids)}"
    )

    print(
        f"[FRANCE-IX] "
        f"PoPs distincts    : "
        f"{len(facility_ids)}"
    )

    networks = (
        fetch_networks(
            net_ids
        )
    )

    facilities = (
        fetch_facilities(
            facility_ids
        )
    )

    netfac = (
        fetch_netfac(
            net_ids
        )
    )

    save_json(
        RAW_DIR /
        "france_ix_networks.json",

        {
            "retrieved_at":
                now_iso(),

            "records":
                networks,
        },
    )

    save_json(
        RAW_DIR /
        "france_ix_facilities.json",

        {
            "retrieved_at":
                now_iso(),

            "records":
                facilities,
        },
    )

    save_json(
        RAW_DIR /
        "france_ix_netfac.json",

        {
            "retrieved_at":
                now_iso(),

            "records":
                netfac,
        },
    )

    members = build_members(
        all_connections,
        networks,
        ix_service_by_id,
    )

    local_peeringdb_ids = (
        load_local_peeringdb_ids()
    )

    (
        pops,
        pop_geojson,
        member_fac,
    ) = build_pops(
        facilities,
        all_ixfac,
        netfac,
        set(net_ids),
        local_peeringdb_ids,
    )

    relations = (
        build_member_pop_relations(
            members,
            member_fac,
            facilities,
        )
    )

    graph = build_graph(
        members,
        pops,
        relations,
    )

    save_json(
        POPS_GEOJSON,
        pop_geojson,
    )

    save_json(
        GRAPH_JSON,
        graph,
    )

    write_csv(
        CSV_DIR /
        "france_ix_members.csv",

        members,
    )

    write_csv(
        CSV_DIR /
        "france_ix_pops.csv",

        pops,
    )

    write_csv(
        CSV_DIR /
        "france_ix_member_pop_relations.csv",

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
                len(
                    all_connections
                ),
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
        CSV_DIR /
        "france_ix_summary.csv",

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
        f"Membres / ASN      : "
        f"{len(members)}"
    )

    print(
        f"Connexions IX      : "
        f"{len(all_connections)}"
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

    print(
        "=============================================="
    )


if __name__ == "__main__":
    main()
