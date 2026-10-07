#!/usr/bin/env python3

from __future__ import annotations

import csv
import json
import math
import os
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


# ============================================================
# CONFIGURATION
# ============================================================

BASE_URL = "https://www.peeringdb.com/api"

PARIS_LAT = 48.8566
PARIS_LON = 2.3522

# Paris + petite/grande couronne proche
RADIUS_KM = 40.0

TIMEOUT = 60

ROOT = Path(__file__).resolve().parents[2]

RAW_DIR = ROOT / "data/raw/peeringdb"
PROCESSED_DIR = ROOT / "data/processed"
CSV_DIR = ROOT / "exports/csv/peeringdb"

FACILITIES_GEOJSON = (
    PROCESSED_DIR /
    "peeringdb_paris_facilities.geojson"
)

RAW_FACILITIES = (
    RAW_DIR /
    "facilities_france.json"
)

RAW_NETFAC = (
    RAW_DIR /
    "paris_netfac.json"
)

RAW_IXFAC = (
    RAW_DIR /
    "paris_ixfac.json"
)

RAW_NETWORKS = (
    RAW_DIR /
    "paris_networks.json"
)

RAW_IX = (
    RAW_DIR /
    "paris_exchanges.json"
)

API_KEY = os.getenv(
    "PEERINGDB_API_KEY"
)

USER_AGENT = (
    "NetGuardian-Paris/0.4 "
    "(academic network research)"
)


# ============================================================
# HELPERS
# ============================================================

def now_iso() -> str:
    return datetime.now(
        timezone.utc
    ).isoformat()


def safe_float(
    value: Any,
) -> float | None:
    try:
        return float(value)

    except (
        ValueError,
        TypeError,
    ):
        return None


def haversine_km(
    lat1: float,
    lon1: float,
    lat2: float,
    lon2: float,
) -> float:
    radius = 6371.0088

    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)

    dphi = math.radians(
        lat2 - lat1
    )

    dlambda = math.radians(
        lon2 - lon1
    )

    a = (
        math.sin(dphi / 2) ** 2
        +
        math.cos(phi1)
        *
        math.cos(phi2)
        *
        math.sin(dlambda / 2) ** 2
    )

    return (
        2
        *
        radius
        *
        math.asin(
            math.sqrt(a)
        )
    )


def api_get(
    endpoint: str,
    params: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    url = (
        f"{BASE_URL}/{endpoint}"
    )

    if params:
        url += (
            "?"
            +
            urlencode(
                params,
                doseq=True,
            )
        )

    headers = {
        "User-Agent":
            USER_AGENT,

        "Accept":
            "application/json",
    }

    if API_KEY:
        headers[
            "Authorization"
        ] = (
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

            raw = response.read()

    except HTTPError as exc:
        raise RuntimeError(
            f"PeeringDB HTTP {exc.code}: "
            f"{url}"
        ) from exc

    except URLError as exc:
        raise RuntimeError(
            f"PeeringDB network error: "
            f"{exc.reason}"
        ) from exc

    payload = json.loads(
        raw.decode(
            "utf-8"
        )
    )

    data = payload.get(
        "data",
        []
    )

    if not isinstance(
        data,
        list,
    ):
        raise RuntimeError(
            f"Invalid PeeringDB response "
            f"for {endpoint}"
        )

    return data


def save_json(
    path: Path,
    data: Any,
) -> None:
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    path.write_text(
        json.dumps(
            data,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def flatten(
    value: Any,
) -> str:
    if value is None:
        return ""

    if isinstance(
        value,
        list,
    ):
        return " | ".join(
            str(v)
            for v in value
        )

    if isinstance(
        value,
        dict,
    ):
        return json.dumps(
            value,
            ensure_ascii=False,
        )

    return str(value)


def write_csv(
    path: Path,
    rows: list[dict[str, Any]],
) -> None:
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    if not rows:
        print(
            f"[CSV] no rows: {path}"
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
    ) as f:

        writer = csv.DictWriter(
            f,
            fieldnames=fields,
        )

        writer.writeheader()

        for row in rows:
            writer.writerow(
                {
                    key:
                        flatten(
                            row.get(key)
                        )
                    for key in fields
                }
            )

    print(
        f"[CSV] "
        f"{path.relative_to(ROOT)} "
        f"({len(rows)} rows)"
    )


def chunked(
    values: list[int],
    size: int = 100,
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
# 1. FACILITIES
# ============================================================

def fetch_france_facilities():
    print()
    print(
        "[PDB] Fetching French facilities..."
    )

    facilities = api_get(
        "fac",
        {
            "country": "FR",
        },
    )

    print(
        f"[PDB] Facilities FR: "
        f"{len(facilities)}"
    )

    save_json(
        RAW_FACILITIES,
        {
            "retrieved_at":
                now_iso(),

            "source":
                "PeeringDB",

            "records":
                facilities,
        },
    )

    return facilities


def filter_paris_facilities(
    facilities,
):
    selected = []

    missing_coordinates = 0

    for facility in facilities:
        lat = safe_float(
            facility.get(
                "latitude"
            )
        )

        lon = safe_float(
            facility.get(
                "longitude"
            )
        )

        if (
            lat is None
            or lon is None
        ):
            missing_coordinates += 1
            continue

        distance = haversine_km(
            PARIS_LAT,
            PARIS_LON,
            lat,
            lon,
        )

        if distance <= RADIUS_KM:
            facility = dict(
                facility
            )

            facility[
                "distance_to_paris_km"
            ] = round(
                distance,
                2,
            )

            selected.append(
                facility
            )

    selected.sort(
        key=lambda x:
            x[
                "distance_to_paris_km"
            ]
    )

    print(
        f"[PDB] Facilities <= "
        f"{RADIUS_KM:.0f} km: "
        f"{len(selected)}"
    )

    print(
        f"[PDB] Missing coordinates: "
        f"{missing_coordinates}"
    )

    return selected


# ============================================================
# 2. NETWORK PRESENCE
# ============================================================

def fetch_netfac(
    facility_ids: list[int],
):
    print()
    print(
        "[PDB] Fetching network "
        "presence..."
    )

    result = []

    for index, batch in enumerate(
        chunked(
            facility_ids,
            50,
        ),
        start=1,
    ):
        print(
            f"[PDB] netfac batch "
            f"{index}"
        )

        records = api_get(
            "netfac",
            {
                "fac_id__in":
                    ",".join(
                        str(x)
                        for x in batch
                    )
            },
        )

        result.extend(
            records
        )

        time.sleep(0.3)

    print(
        f"[PDB] Network presences: "
        f"{len(result)}"
    )

    save_json(
        RAW_NETFAC,
        {
            "retrieved_at":
                now_iso(),

            "records":
                result,
        },
    )

    return result


# ============================================================
# 3. IX PRESENCE
# ============================================================

def fetch_ixfac(
    facility_ids: list[int],
):
    print()
    print(
        "[PDB] Fetching IX presence..."
    )

    result = []

    for index, batch in enumerate(
        chunked(
            facility_ids,
            50,
        ),
        start=1,
    ):
        print(
            f"[PDB] ixfac batch "
            f"{index}"
        )

        records = api_get(
            "ixfac",
            {
                "fac_id__in":
                    ",".join(
                        str(x)
                        for x in batch
                    )
            },
        )

        result.extend(
            records
        )

        time.sleep(0.3)

    print(
        f"[PDB] IX presences: "
        f"{len(result)}"
    )

    save_json(
        RAW_IXFAC,
        {
            "retrieved_at":
                now_iso(),

            "records":
                result,
        },
    )

    return result


# ============================================================
# 4. NETWORK DETAILS
# ============================================================

def fetch_networks(
    netfac,
):
    net_ids = sorted(
        {
            int(row["net_id"])
            for row in netfac
            if row.get(
                "net_id"
            )
        }
    )

    print()
    print(
        f"[PDB] Distinct networks: "
        f"{len(net_ids)}"
    )

    result = []

    for index, batch in enumerate(
        chunked(
            net_ids,
            50,
        ),
        start=1,
    ):
        print(
            f"[PDB] network batch "
            f"{index}"
        )

        records = api_get(
            "net",
            {
                "id__in":
                    ",".join(
                        str(x)
                        for x in batch
                    )
            },
        )

        result.extend(
            records
        )

        time.sleep(0.3)

    save_json(
        RAW_NETWORKS,
        {
            "retrieved_at":
                now_iso(),

            "records":
                result,
        },
    )

    return result


# ============================================================
# 5. EXCHANGE DETAILS
# ============================================================

def fetch_exchanges(
    ixfac,
):
    ix_ids = sorted(
        {
            int(row["ix_id"])
            for row in ixfac
            if row.get(
                "ix_id"
            )
        }
    )

    print()
    print(
        f"[PDB] Distinct IX: "
        f"{len(ix_ids)}"
    )

    result = []

    for index, batch in enumerate(
        chunked(
            ix_ids,
            50,
        ),
        start=1,
    ):
        print(
            f"[PDB] IX batch "
            f"{index}"
        )

        records = api_get(
            "ix",
            {
                "id__in":
                    ",".join(
                        str(x)
                        for x in batch
                    )
            },
        )

        result.extend(
            records
        )

        time.sleep(0.3)

    save_json(
        RAW_IX,
        {
            "retrieved_at":
                now_iso(),

            "records":
                result,
        },
    )

    return result


# ============================================================
# 6. ENRICH FACILITIES
# ============================================================

def enrich_facilities(
    facilities,
    netfac,
    ixfac,
    networks,
    exchanges,
):
    networks_by_id = {
        int(n["id"]): n
        for n in networks
        if n.get("id")
    }

    exchanges_by_id = {
        int(ix["id"]): ix
        for ix in exchanges
        if ix.get("id")
    }

    net_ids_by_fac = {}

    for relation in netfac:
        fac_id = relation.get(
            "fac_id"
        )

        net_id = relation.get(
            "net_id"
        )

        if not fac_id or not net_id:
            continue

        net_ids_by_fac.setdefault(
            int(fac_id),
            set(),
        ).add(
            int(net_id)
        )

    ix_ids_by_fac = {}

    for relation in ixfac:
        fac_id = relation.get(
            "fac_id"
        )

        ix_id = relation.get(
            "ix_id"
        )

        if not fac_id or not ix_id:
            continue

        ix_ids_by_fac.setdefault(
            int(fac_id),
            set(),
        ).add(
            int(ix_id)
        )

    enriched = []

    for facility in facilities:
        facility_id = int(
            facility["id"]
        )

        net_ids = sorted(
            net_ids_by_fac.get(
                facility_id,
                set(),
            )
        )

        ix_ids = sorted(
            ix_ids_by_fac.get(
                facility_id,
                set(),
            )
        )

        asns = []

        network_names = []

        for net_id in net_ids:
            network = (
                networks_by_id.get(
                    net_id
                )
            )

            if not network:
                continue

            if network.get("asn"):
                asns.append(
                    network["asn"]
                )

            if network.get("name"):
                network_names.append(
                    network["name"]
                )

        ix_names = []

        for ix_id in ix_ids:
            ix = exchanges_by_id.get(
                ix_id
            )

            if (
                ix
                and ix.get("name")
            ):
                ix_names.append(
                    ix["name"]
                )

        row = dict(
            facility
        )

        row[
            "network_count"
        ] = len(net_ids)

        row[
            "ix_count"
        ] = len(ix_ids)

        row[
            "network_ids"
        ] = net_ids

        row[
            "network_asns"
        ] = sorted(
            set(asns)
        )

        row[
            "network_names"
        ] = sorted(
            set(network_names)
        )

        row[
            "ix_ids"
        ] = ix_ids

        row[
            "ix_names"
        ] = sorted(
            set(ix_names)
        )

        enriched.append(
            row
        )

    return enriched


# ============================================================
# 7. GEOJSON
# ============================================================

def build_geojson(
    facilities,
):
    features = []

    for facility in facilities:
        lat = safe_float(
            facility.get(
                "latitude"
            )
        )

        lon = safe_float(
            facility.get(
                "longitude"
            )
        )

        if (
            lat is None
            or lon is None
        ):
            continue

        properties = {
            "id":
                facility.get("id"),

            "node_type":
                "peering_facility",

            "name":
                facility.get("name"),

            "org_id":
                facility.get("org_id"),

            "org_name":
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
                facility.get("city"),

            "state":
                facility.get("state"),

            "zipcode":
                facility.get(
                    "zipcode"
                ),

            "country":
                facility.get(
                    "country"
                ),

            "website":
                facility.get(
                    "website"
                ),

            "status":
                facility.get(
                    "status"
                ),

            "distance_to_paris_km":
                facility.get(
                    "distance_to_paris_km"
                ),

            "network_count":
                facility.get(
                    "network_count",
                    0,
                ),

            "ix_count":
                facility.get(
                    "ix_count",
                    0,
                ),

            "network_asns":
                facility.get(
                    "network_asns",
                    [],
                ),

            "network_names":
                facility.get(
                    "network_names",
                    [],
                ),

            "ix_names":
                facility.get(
                    "ix_names",
                    [],
                ),

            "source":
                "PeeringDB",

            "evidence_type":
                "PUBLIC_DECLARATION",
        }

        features.append(
            {
                "type":
                    "Feature",

                "id":
                    (
                        f"peeringdb-fac-"
                        f"{facility['id']}"
                    ),

                "geometry": {
                    "type":
                        "Point",

                    "coordinates": [
                        lon,
                        lat,
                    ],
                },

                "properties":
                    properties,
            }
        )

    return {
        "type":
            "FeatureCollection",

        "name":
            "NetGuardian Paris PeeringDB Facilities",

        "metadata": {
            "source":
                "PeeringDB",

            "retrieved_at":
                now_iso(),

            "radius_km":
                RADIUS_KM,

            "feature_count":
                len(features),
        },

        "features":
            features,
    }


# ============================================================
# 8. CSV EXPORT
# ============================================================

def export_csv(
    facilities,
    netfac,
    ixfac,
    networks,
    exchanges,
):
    facility_rows = []

    for f in facilities:
        facility_rows.append(
            {
                "facility_id":
                    f.get("id"),

                "name":
                    f.get("name"),

                "organization":
                    f.get(
                        "org_name"
                    ),

                "address1":
                    f.get(
                        "address1"
                    ),

                "address2":
                    f.get(
                        "address2"
                    ),

                "city":
                    f.get("city"),

                "postal_code":
                    f.get(
                        "zipcode"
                    ),

                "country":
                    f.get(
                        "country"
                    ),

                "latitude":
                    f.get(
                        "latitude"
                    ),

                "longitude":
                    f.get(
                        "longitude"
                    ),

                "distance_to_paris_km":
                    f.get(
                        "distance_to_paris_km"
                    ),

                "network_count":
                    f.get(
                        "network_count"
                    ),

                "ix_count":
                    f.get(
                        "ix_count"
                    ),

                "asns":
                    f.get(
                        "network_asns"
                    ),

                "networks":
                    f.get(
                        "network_names"
                    ),

                "internet_exchanges":
                    f.get(
                        "ix_names"
                    ),

                "website":
                    f.get(
                        "website"
                    ),

                "status":
                    f.get(
                        "status"
                    ),

                "source":
                    "PeeringDB",
            }
        )

    write_csv(
        CSV_DIR /
        "peeringdb_facilities.csv",

        facility_rows,
    )

    write_csv(
        CSV_DIR /
        "peeringdb_network_presence.csv",

        netfac,
    )

    write_csv(
        CSV_DIR /
        "peeringdb_ix_presence.csv",

        ixfac,
    )

    network_rows = []

    for n in networks:
        network_rows.append(
            {
                "network_id":
                    n.get("id"),

                "name":
                    n.get("name"),

                "asn":
                    n.get("asn"),

                "website":
                    n.get(
                        "website"
                    ),

                "info_type":
                    n.get(
                        "info_type"
                    ),

                "info_scope":
                    n.get(
                        "info_scope"
                    ),

                "info_traffic":
                    n.get(
                        "info_traffic"
                    ),

                "info_ratio":
                    n.get(
                        "info_ratio"
                    ),

                "policy_general":
                    n.get(
                        "policy_general"
                    ),

                "irr_as_set":
                    n.get(
                        "irr_as_set"
                    ),

                "status":
                    n.get(
                        "status"
                    ),
            }
        )

    write_csv(
        CSV_DIR /
        "peeringdb_networks.csv",

        network_rows,
    )

    exchange_rows = []

    for ix in exchanges:
        exchange_rows.append(
            {
                "ix_id":
                    ix.get("id"),

                "name":
                    ix.get("name"),

                "name_long":
                    ix.get(
                        "name_long"
                    ),

                "city":
                    ix.get("city"),

                "country":
                    ix.get(
                        "country"
                    ),

                "region_continent":
                    ix.get(
                        "region_continent"
                    ),

                "website":
                    ix.get(
                        "website"
                    ),

                "tech_email":
                    ix.get(
                        "tech_email"
                    ),

                "policy_email":
                    ix.get(
                        "policy_email"
                    ),

                "status":
                    ix.get(
                        "status"
                    ),
            }
        )

    write_csv(
        CSV_DIR /
        "peeringdb_exchanges.csv",

        exchange_rows,
    )


# ============================================================
# SUMMARY
# ============================================================

def print_summary(
    facilities,
    netfac,
    ixfac,
    networks,
    exchanges,
):
    city_counter = Counter(
        f.get(
            "city",
            "Unknown"
        )
        for f in facilities
    )

    print()
    print(
        "=============================================="
    )
    print(
        "       NETGUARDIAN - PEERINGDB ✅"
    )
    print(
        "=============================================="
    )

    print(
        f"Facilities          : "
        f"{len(facilities)}"
    )

    print(
        f"Network presences   : "
        f"{len(netfac)}"
    )

    print(
        f"Distinct networks   : "
        f"{len(networks)}"
    )

    print(
        f"IX presences        : "
        f"{len(ixfac)}"
    )

    print(
        f"Internet Exchanges  : "
        f"{len(exchanges)}"
    )

    print()
    print(
        "Top cities:"
    )

    for city, count in (
        city_counter
        .most_common(10)
    ):
        print(
            f"  {city:25} "
            f"{count}"
        )

    print()
    print(
        f"GeoJSON : "
        f"{FACILITIES_GEOJSON}"
    )

    print(
        f"CSV     : "
        f"{CSV_DIR}"
    )

    print(
        "=============================================="
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
        "    NETGUARDIAN PARIS - PEERINGDB"
    )
    print(
        "=============================================="
    )

    RAW_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    PROCESSED_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    CSV_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    facilities_fr = (
        fetch_france_facilities()
    )

    facilities = (
        filter_paris_facilities(
            facilities_fr
        )
    )

    if not facilities:
        raise RuntimeError(
            "No PeeringDB facilities "
            "found around Paris."
        )

    facility_ids = [
        int(f["id"])
        for f in facilities
    ]

    netfac = fetch_netfac(
        facility_ids
    )

    ixfac = fetch_ixfac(
        facility_ids
    )

    networks = fetch_networks(
        netfac
    )

    exchanges = fetch_exchanges(
        ixfac
    )

    enriched = (
        enrich_facilities(
            facilities,
            netfac,
            ixfac,
            networks,
            exchanges,
        )
    )

    geojson = build_geojson(
        enriched
    )

    save_json(
        FACILITIES_GEOJSON,
        geojson,
    )

    export_csv(
        enriched,
        netfac,
        ixfac,
        networks,
        exchanges,
    )

    print_summary(
        enriched,
        netfac,
        ixfac,
        networks,
        exchanges,
    )


if __name__ == "__main__":
    main()
