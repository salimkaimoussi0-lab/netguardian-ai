#!/usr/bin/env python3

from __future__ import annotations

import csv
import json
import math
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urljoin
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[2]

INDEX_URL = "https://data.arcep.fr/mobile/sites/last/"

PARIS_LAT = 48.8566
PARIS_LON = 2.3522

# Paris + proche couronne
RADIUS_KM = 25.0

TIMEOUT = 120

RAW_FILE = (
    ROOT
    / "data/raw/arcep_mobile/sites_metropole_latest.csv"
)

GEOJSON_FILE = (
    ROOT
    / "data/processed/arcep_mobile_sites.geojson"
)

CSV_RECORDS = (
    ROOT
    / "exports/csv/arcep_mobile/arcep_mobile_records.csv"
)

CSV_SITES = (
    ROOT
    / "exports/csv/arcep_mobile/arcep_mobile_sites.csv"
)

CSV_SUMMARY = (
    ROOT
    / "exports/csv/arcep_mobile/arcep_mobile_summary.csv"
)

ANFR_GEOJSON = (
    ROOT
    / "data/processed/anfr_paris_sites.geojson"
)

USER_AGENT = (
    "NetGuardian-Paris/0.7 "
    "(academic network research)"
)


def now_iso():
    return datetime.now(
        timezone.utc
    ).isoformat()


def request_bytes(url: str) -> bytes:
    request = Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "*/*",
        },
    )

    with urlopen(
        request,
        timeout=TIMEOUT,
    ) as response:
        return response.read()


def discover_latest_csv() -> str:
    print(
        "[ARCEP] Recherche du dernier millésime..."
    )

    html = request_bytes(
        INDEX_URL
    ).decode(
        "utf-8",
        errors="replace",
    )

    matches = re.findall(
        r'href=["\']([^"\']*sites_Metropole\.csv)["\']',
        html,
        flags=re.IGNORECASE,
    )

    if not matches:
        raise RuntimeError(
            "Impossible de trouver le CSV Métropole "
            "sur la page ARCEP."
        )

    filename = matches[0]

    url = urljoin(
        INDEX_URL,
        filename,
    )

    print(
        f"[ARCEP] Fichier : {filename}"
    )

    return url


def download_csv(url: str):
    print(
        "[ARCEP] Téléchargement..."
    )

    content = request_bytes(
        url
    )

    RAW_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    RAW_FILE.write_bytes(
        content
    )

    print(
        f"[ARCEP] RAW : "
        f"{RAW_FILE.relative_to(ROOT)}"
    )

    print(
        f"[ARCEP] Taille : "
        f"{len(content) / 1024 / 1024:.2f} Mo"
    )


def parse_float(value):
    if value is None:
        return None

    text = str(
        value
    ).strip()

    if not text:
        return None

    text = text.replace(
        ",",
        ".",
    )

    try:
        return float(text)
    except ValueError:
        return None


def as_bool(value):
    if value is None:
        return False

    value = (
        str(value)
        .strip()
        .lower()
    )

    return value in {
        "1",
        "true",
        "vrai",
        "yes",
        "oui",
    }


def haversine_km(
    lat1,
    lon1,
    lat2,
    lon2,
):
    r = 6371.0088

    p1 = math.radians(lat1)
    p2 = math.radians(lat2)

    dp = math.radians(
        lat2 - lat1
    )

    dl = math.radians(
        lon2 - lon1
    )

    a = (
        math.sin(dp / 2) ** 2
        +
        math.cos(p1)
        * math.cos(p2)
        * math.sin(dl / 2) ** 2
    )

    return (
        2
        * r
        * math.asin(
            math.sqrt(a)
        )
    )


def normalize_station(value):
    if value is None:
        return ""

    text = str(
        value
    ).strip()

    if not text:
        return ""

    digits = re.sub(
        r"\D",
        "",
        text,
    )

    if digits:
        return (
            digits.lstrip("0")
            or "0"
        )

    return text.upper()


def load_anfr_index():
    """
    station ANFR -> support IDs NetGuardian
    """

    index = defaultdict(
        set
    )

    if not ANFR_GEOJSON.exists():
        print(
            "[ARCEP] ANFR GeoJSON absent : "
            "cross-match désactivé."
        )

        return index

    with ANFR_GEOJSON.open(
        encoding="utf-8",
    ) as f:
        data = json.load(f)

    for feature in data.get(
        "features",
        [],
    ):
        p = feature.get(
            "properties",
            {},
        )

        support = (
            p.get("sup_id")
            or p.get("id")
        )

        stations = p.get(
            "stations",
            []
        )

        if isinstance(
            stations,
            str,
        ):
            try:
                parsed = json.loads(
                    stations
                )

                if isinstance(
                    parsed,
                    list,
                ):
                    stations = parsed
                else:
                    stations = [
                        stations
                    ]

            except Exception:
                stations = [
                    stations
                ]

        if not isinstance(
            stations,
            list,
        ):
            stations = []

        for station in stations:
            key = normalize_station(
                station
            )

            if key and support:
                index[key].add(
                    str(support)
                )

    print(
        f"[ARCEP] Stations ANFR indexées : "
        f"{len(index)}"
    )

    return index


def read_paris_records():
    records = []

    operator_counter = Counter()

    tech_counter = Counter()

    with RAW_FILE.open(
        "r",
        encoding="cp1252",
        newline="",
    ) as f:

        reader = csv.DictReader(
            f,
            delimiter=";",
        )

        print()
        print(
            "[ARCEP] Colonnes détectées :"
        )

        print(
            ", ".join(
                reader.fieldnames or []
            )
        )

        for raw in reader:
            lat = parse_float(
                raw.get("latitude")
            )

            lon = parse_float(
                raw.get("longitude")
            )

            if (
                lat is None
                or lon is None
            ):
                continue

            distance = haversine_km(
                PARIS_LAT,
                PARIS_LON,
                lat,
                lon,
            )

            if distance > RADIUS_KM:
                continue

            technologies = []

            for field, name in [
                ("site_2g", "2G"),
                ("site_3g", "3G"),
                ("site_4g", "4G"),
                ("site_5g", "5G"),
            ]:
                if as_bool(
                    raw.get(field)
                ):
                    technologies.append(
                        name
                    )

                    tech_counter[
                        name
                    ] += 1

            bands_5g = []

            for field, band in [
                (
                    "site_5g_700_m_hz",
                    "700 MHz",
                ),
                (
                    "site_5g_800_m_hz",
                    "800 MHz",
                ),
                (
                    "site_5g_1800_m_hz",
                    "1800 MHz",
                ),
                (
                    "site_5g_2100_m_hz",
                    "2100 MHz",
                ),
                (
                    "site_5g_3500_m_hz",
                    "3500 MHz",
                ),
            ]:
                if as_bool(
                    raw.get(field)
                ):
                    bands_5g.append(
                        band
                    )

            operator = (
                raw.get("nom_op")
                or "Inconnu"
            ).strip()

            operator_counter[
                operator
            ] += 1

            record = {
                "operator_code":
                    raw.get("code_op"),

                "operator":
                    operator,

                "operator_site_id":
                    raw.get("num_site"),

                "shared_site_id":
                    raw.get(
                        "id_site_partage"
                    ),

                "anfr_station_id":
                    raw.get(
                        "id_station_anfr"
                    ),

                "latitude":
                    lat,

                "longitude":
                    lon,

                "region":
                    raw.get("nom_reg"),

                "department":
                    raw.get("nom_dep"),

                "department_code":
                    raw.get("insee_dep"),

                "city":
                    raw.get("nom_com"),

                "insee_code":
                    raw.get("insee_com"),

                "technologies":
                    technologies,

                "site_2g":
                    "2G"
                    in technologies,

                "site_3g":
                    "3G"
                    in technologies,

                "site_4g":
                    "4G"
                    in technologies,

                "site_5g":
                    "5G"
                    in technologies,

                "5g_bands":
                    bands_5g,

                "5g_opening_date":
                    raw.get(
                        "date_ouverturecommerciale_5g"
                    ),

                "capacity_240mbps":
                    as_bool(
                        raw.get(
                            "site_capa_240mbps"
                        )
                    ),

                "distance_to_paris_km":
                    round(
                        distance,
                        3,
                    ),

                "source":
                    "ARCEP - Mon Réseau Mobile",

                "evidence_type":
                    "OPERATOR_DECLARATION",
            }

            records.append(
                record
            )

    print()
    print(
        f"[ARCEP] Enregistrements dans "
        f"{RADIUS_KM:.0f} km : "
        f"{len(records)}"
    )

    print()
    print(
        "[ARCEP] Opérateurs :"
    )

    for name, count in (
        operator_counter
        .most_common()
    ):
        print(
            f"  {name:25} "
            f"{count}"
        )

    print()
    print(
        "[ARCEP] Technologies :"
    )

    for name in [
        "2G",
        "3G",
        "4G",
        "5G",
    ]:
        print(
            f"  {name:5} "
            f"{tech_counter[name]}"
        )

    return records


def aggregate_sites(
    records,
    anfr_index,
):
    groups = {}

    for record in records:
        station = normalize_station(
            record[
                "anfr_station_id"
            ]
        )

        if station:
            key = (
                "ANFR",
                station,
            )
        else:
            key = (
                "COORD",
                round(
                    record["latitude"],
                    5,
                ),
                round(
                    record["longitude"],
                    5,
                ),
            )

        if key not in groups:
            groups[key] = {
                "latitude":
                    record["latitude"],

                "longitude":
                    record["longitude"],

                "anfr_station_ids":
                    set(),

                "operators":
                    set(),

                "operator_site_ids":
                    set(),

                "shared_site_ids":
                    set(),

                "technologies":
                    set(),

                "5g_bands":
                    set(),

                "cities":
                    set(),

                "departments":
                    set(),

                "insee_codes":
                    set(),

                "opening_dates_5g":
                    set(),

                "capacity_240mbps":
                    False,

                "distance_to_paris_km":
                    record[
                        "distance_to_paris_km"
                    ],

                "record_count":
                    0,
            }

        g = groups[key]

        g[
            "record_count"
        ] += 1

        g["operators"].add(
            record["operator"]
        )

        if record[
            "operator_site_id"
        ]:
            g[
                "operator_site_ids"
            ].add(
                str(
                    record[
                        "operator_site_id"
                    ]
                )
            )

        if record[
            "shared_site_id"
        ]:
            g[
                "shared_site_ids"
            ].add(
                str(
                    record[
                        "shared_site_id"
                    ]
                )
            )

        if record[
            "anfr_station_id"
        ]:
            g[
                "anfr_station_ids"
            ].add(
                str(
                    record[
                        "anfr_station_id"
                    ]
                )
            )

        g[
            "technologies"
        ].update(
            record[
                "technologies"
            ]
        )

        g[
            "5g_bands"
        ].update(
            record[
                "5g_bands"
            ]
        )

        if record["city"]:
            g["cities"].add(
                record["city"]
            )

        if record["department"]:
            g[
                "departments"
            ].add(
                record[
                    "department"
                ]
            )

        if record["insee_code"]:
            g[
                "insee_codes"
            ].add(
                record[
                    "insee_code"
                ]
            )

        if record[
            "5g_opening_date"
        ]:
            g[
                "opening_dates_5g"
            ].add(
                record[
                    "5g_opening_date"
                ]
            )

        if record[
            "capacity_240mbps"
        ]:
            g[
                "capacity_240mbps"
            ] = True

    sites = []

    for index, (
        key,
        group,
    ) in enumerate(
        groups.items(),
        start=1,
    ):
        normalized_station_ids = {
            normalize_station(
                station
            )
            for station
            in group[
                "anfr_station_ids"
            ]
            if normalize_station(
                station
            )
        }

        anfr_support_ids = set()

        for station in (
            normalized_station_ids
        ):
            anfr_support_ids.update(
                anfr_index.get(
                    station,
                    set(),
                )
            )

        opening_dates = sorted(
            group[
                "opening_dates_5g"
            ]
        )

        site = {
            "id":
                f"arcep-mobile-{index}",

            "node_type":
                "commercial_mobile_site",

            "latitude":
                group["latitude"],

            "longitude":
                group["longitude"],

            "operators":
                sorted(
                    group["operators"]
                ),

            "operator_count":
                len(
                    group["operators"]
                ),

            "operator_site_ids":
                sorted(
                    group[
                        "operator_site_ids"
                    ]
                ),

            "shared_site_ids":
                sorted(
                    group[
                        "shared_site_ids"
                    ]
                ),

            "anfr_station_ids":
                sorted(
                    group[
                        "anfr_station_ids"
                    ]
                ),

            "technologies":
                sorted(
                    group["technologies"]
                ),

            "5g_bands":
                sorted(
                    group["5g_bands"]
                ),

            "has_2g":
                "2G"
                in group[
                    "technologies"
                ],

            "has_3g":
                "3G"
                in group[
                    "technologies"
                ],

            "has_4g":
                "4G"
                in group[
                    "technologies"
                ],

            "has_5g":
                "5G"
                in group[
                    "technologies"
                ],

            "first_5g_opening_date":
                (
                    opening_dates[0]
                    if opening_dates
                    else None
                ),

            "capacity_240mbps":
                group[
                    "capacity_240mbps"
                ],

            "cities":
                sorted(
                    group["cities"]
                ),

            "departments":
                sorted(
                    group["departments"]
                ),

            "insee_codes":
                sorted(
                    group[
                        "insee_codes"
                    ]
                ),

            "distance_to_paris_km":
                group[
                    "distance_to_paris_km"
                ],

            "arcep_record_count":
                group[
                    "record_count"
                ],

            "anfr_match":
                bool(
                    anfr_support_ids
                ),

            "anfr_support_ids":
                sorted(
                    anfr_support_ids
                ),

            "source":
                "ARCEP - Mon Réseau Mobile",

            "evidence_type":
                "OPERATOR_DECLARATION",
        }

        sites.append(
            site
        )

    sites.sort(
        key=lambda x:
            x[
                "distance_to_paris_km"
            ]
    )

    return sites


def save_geojson(sites):
    features = []

    for site in sites:
        properties = dict(
            site
        )

        latitude = properties.pop(
            "latitude"
        )

        longitude = properties.pop(
            "longitude"
        )

        features.append(
            {
                "type":
                    "Feature",

                "id":
                    site["id"],

                "geometry": {
                    "type":
                        "Point",

                    "coordinates": [
                        longitude,
                        latitude,
                    ],
                },

                "properties":
                    properties,
            }
        )

    geojson = {
        "type":
            "FeatureCollection",

        "name":
            "NetGuardian Paris ARCEP Mobile",

        "metadata": {
            "source":
                "ARCEP - Mon Réseau Mobile",

            "retrieved_at":
                now_iso(),

            "radius_km":
                RADIUS_KM,

            "feature_count":
                len(features),

            "description":
                (
                    "Commercially opened "
                    "2G/3G/4G/5G mobile sites "
                    "declared by operators."
                ),
        },

        "features":
            features,
    }

    GEOJSON_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    GEOJSON_FILE.write_text(
        json.dumps(
            geojson,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def csv_value(value):
    if isinstance(
        value,
        list,
    ):
        return " | ".join(
            str(v)
            for v in value
        )

    if value is None:
        return ""

    return value


def write_csv(
    path,
    rows,
):
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    if not rows:
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
                        csv_value(
                            row.get(key)
                        )
                    for key in fields
                }
            )

    print(
        f"[CSV] "
        f"{path.relative_to(ROOT)} "
        f"({len(rows)} lignes)"
    )


def export_summary(
    records,
    sites,
):
    operator_counter = Counter()

    for row in records:
        operator_counter[
            row["operator"]
        ] += 1

    rows = [
        {
            "metric":
                "operator_site_records",

            "value":
                len(records),
        },

        {
            "metric":
                "aggregated_physical_sites",

            "value":
                len(sites),
        },

        {
            "metric":
                "2g_sites",

            "value":
                sum(
                    site["has_2g"]
                    for site in sites
                ),
        },

        {
            "metric":
                "3g_sites",

            "value":
                sum(
                    site["has_3g"]
                    for site in sites
                ),
        },

        {
            "metric":
                "4g_sites",

            "value":
                sum(
                    site["has_4g"]
                    for site in sites
                ),
        },

        {
            "metric":
                "5g_sites",

            "value":
                sum(
                    site["has_5g"]
                    for site in sites
                ),
        },

        {
            "metric":
                "5g_3500mhz_sites",

            "value":
                sum(
                    "3500 MHz"
                    in site[
                        "5g_bands"
                    ]
                    for site in sites
                ),
        },

        {
            "metric":
                "matched_with_anfr",

            "value":
                sum(
                    site[
                        "anfr_match"
                    ]
                    for site in sites
                ),
        },

        {
            "metric":
                "multi_operator_sites",

            "value":
                sum(
                    site[
                        "operator_count"
                    ] > 1
                    for site in sites
                ),
        },
    ]

    for operator, count in (
        operator_counter
        .most_common()
    ):
        rows.append(
            {
                "metric":
                    (
                        "operator_records_"
                        + operator
                    ),

                "value":
                    count,
            }
        )

    write_csv(
        CSV_SUMMARY,
        rows,
    )


def main():
    print()
    print(
        "=============================================="
    )
    print(
        "   NETGUARDIAN PARIS - ARCEP MOBILE"
    )
    print(
        "=============================================="
    )

    url = discover_latest_csv()

    print(
        f"[ARCEP] URL : {url}"
    )

    download_csv(
        url
    )

    anfr_index = (
        load_anfr_index()
    )

    records = (
        read_paris_records()
    )

    if not records:
        raise RuntimeError(
            "Aucun site ARCEP trouvé "
            "autour de Paris."
        )

    sites = aggregate_sites(
        records,
        anfr_index,
    )

    save_geojson(
        sites
    )

    write_csv(
        CSV_RECORDS,
        records,
    )

    write_csv(
        CSV_SITES,
        sites,
    )

    export_summary(
        records,
        sites,
    )

    matched = sum(
        site["anfr_match"]
        for site in sites
    )

    print()
    print(
        "=============================================="
    )
    print(
        "          ARCEP MOBILE ✅"
    )
    print(
        "=============================================="
    )

    print(
        f"Enregistrements opérateurs : "
        f"{len(records)}"
    )

    print(
        f"Sites agrégés              : "
        f"{len(sites)}"
    )

    print(
        f"Sites 2G                   : "
        f"{sum(s['has_2g'] for s in sites)}"
    )

    print(
        f"Sites 3G                   : "
        f"{sum(s['has_3g'] for s in sites)}"
    )

    print(
        f"Sites 4G                   : "
        f"{sum(s['has_4g'] for s in sites)}"
    )

    print(
        f"Sites 5G                   : "
        f"{sum(s['has_5g'] for s in sites)}"
    )

    print(
        f"5G 3500 MHz                : "
        f"{sum('3500 MHz' in s['5g_bands'] for s in sites)}"
    )

    print(
        f"Correspondances ANFR       : "
        f"{matched}"
    )

    print()
    print(
        "GeoJSON : "
        "data/processed/"
        "arcep_mobile_sites.geojson"
    )

    print(
        "CSV     : "
        "exports/csv/arcep_mobile/"
    )

    print(
        "=============================================="
    )


if __name__ == "__main__":
    main()
