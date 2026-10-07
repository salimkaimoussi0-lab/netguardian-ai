#!/usr/bin/env python3

from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]

WIFI_GEOJSON = (
    ROOT / "data/processed/paris_wifi_sites.geojson"
)

ANFR_GEOJSON = (
    ROOT / "data/processed/anfr_paris_sites.geojson"
)

ANFR_RAW = (
    ROOT / "data/raw/anfr/paris_mobile_systems.json"
)

RIPE_GEOJSON = (
    ROOT / "data/processed/ripe_atlas_paris_probes.geojson"
)

RIPE_RAW = (
    ROOT / "data/raw/ripe_atlas/paris_probes.json"
)


OUTPUT = ROOT / "exports/csv"

WIFI_DIR = OUTPUT / "wifi"
ANFR_DIR = OUTPUT / "anfr"
RIPE_DIR = OUTPUT / "ripe_atlas"


def load_json(path: Path) -> Any:
    if not path.exists():
        raise FileNotFoundError(
            f"Fichier introuvable : {path}"
        )

    with path.open(
        "r",
        encoding="utf-8",
    ) as f:
        return json.load(f)


def flatten_value(value: Any) -> str | int | float | bool:
    """
    Rend les listes/dictionnaires lisibles dans CSV.
    """

    if value is None:
        return ""

    if isinstance(value, list):
        return " | ".join(
            str(item)
            for item in value
        )

    if isinstance(value, dict):
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
        )

    return value


def write_csv(
    path: Path,
    rows: list[dict[str, Any]],
    fieldnames: list[str] | None = None,
) -> None:
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    if not rows:
        print(
            f"[WARNING] Pas de données : {path}"
        )
        return

    if fieldnames is None:
        fields = []

        seen = set()

        for row in rows:
            for key in row:
                if key not in seen:
                    seen.add(key)
                    fields.append(key)

        fieldnames = fields

    # utf-8-sig = compatible Excel / LibreOffice avec accents
    with path.open(
        "w",
        newline="",
        encoding="utf-8-sig",
    ) as f:
        writer = csv.DictWriter(
            f,
            fieldnames=fieldnames,
            extrasaction="ignore",
        )

        writer.writeheader()

        for row in rows:
            writer.writerow(
                {
                    key: flatten_value(
                        row.get(key)
                    )
                    for key in fieldnames
                }
            )

    print(
        f"[CSV] {path.relative_to(ROOT)} "
        f"({len(rows)} lignes)"
    )


# ============================================================
# WIFI
# ============================================================

def export_wifi():
    data = load_json(
        WIFI_GEOJSON
    )

    rows = []

    statuses = Counter()
    postal_codes = Counter()

    total_bornes = 0

    for feature in data.get(
        "features",
        [],
    ):
        p = feature.get(
            "properties",
            {},
        )

        geometry = feature.get(
            "geometry",
            {},
        )

        coordinates = geometry.get(
            "coordinates",
            [],
        )

        longitude = (
            coordinates[0]
            if len(coordinates) >= 2
            else ""
        )

        latitude = (
            coordinates[1]
            if len(coordinates) >= 2
            else ""
        )

        row = {
            "id": p.get("id"),
            "name": p.get("name"),
            "address": p.get("address"),
            "postal_code": p.get(
                "postal_code"
            ),
            "wifi_access_points": p.get(
                "wifi_access_points"
            ),
            "status": p.get("status"),
            "latitude": latitude,
            "longitude": longitude,
            "node_type": p.get(
                "node_type"
            ),
            "provider": p.get(
                "provider"
            ),
            "source": p.get("source"),
            "source_dataset": p.get(
                "source_dataset"
            ),
            "evidence_type": p.get(
                "evidence_type"
            ),
        }

        rows.append(row)

        status = p.get("status")

        if status:
            statuses[
                str(status)
            ] += 1

        postal = p.get(
            "postal_code"
        )

        if postal:
            postal_codes[
                str(postal)
            ] += 1

        try:
            total_bornes += int(
                p.get(
                    "wifi_access_points",
                    0,
                )
                or 0
            )
        except (
            ValueError,
            TypeError,
        ):
            pass

    write_csv(
        WIFI_DIR / "wifi_sites.csv",
        rows,
    )

    summary = [
        {
            "metric":
                "total_sites",

            "value":
                len(rows),
        },

        {
            "metric":
                "total_wifi_access_points",

            "value":
                total_bornes,
        },

        {
            "metric":
                "distinct_postal_codes",

            "value":
                len(postal_codes),
        },
    ]

    for status, count in sorted(
        statuses.items()
    ):
        summary.append(
            {
                "metric":
                    f"status_{status}",

                "value":
                    count,
            }
        )

    write_csv(
        WIFI_DIR / "wifi_summary.csv",
        summary,
        [
            "metric",
            "value",
        ],
    )


# ============================================================
# ANFR
# ============================================================

def export_anfr():
    geojson = load_json(
        ANFR_GEOJSON
    )

    site_rows = []

    technology_counter = Counter()
    operator_counter = Counter()

    for feature in geojson.get(
        "features",
        [],
    ):
        p = feature.get(
            "properties",
            {},
        )

        geometry = feature.get(
            "geometry",
            {},
        )

        coordinates = geometry.get(
            "coordinates",
            [],
        )

        longitude = (
            coordinates[0]
            if len(coordinates) >= 2
            else ""
        )

        latitude = (
            coordinates[1]
            if len(coordinates) >= 2
            else ""
        )

        generations = p.get(
            "generations",
            [],
        )

        operators = p.get(
            "operators",
            [],
        )

        systems = p.get(
            "systems",
            [],
        )

        statuses = p.get(
            "statuses",
            [],
        )

        stations = p.get(
            "stations",
            [],
        )

        for tech in generations:
            technology_counter[
                str(tech)
            ] += 1

        for operator in operators:
            operator_counter[
                str(operator)
            ] += 1

        site_rows.append(
            {
                "id":
                    p.get("id"),

                "sup_id":
                    p.get("sup_id"),

                "latitude":
                    latitude,

                "longitude":
                    longitude,

                "address":
                    p.get("address"),

                "address_1":
                    p.get("address_1"),

                "address_2":
                    p.get("address_2"),

                "address_3":
                    p.get("address_3"),

                "postal_code":
                    p.get(
                        "postal_code"
                    ),

                "insee_code":
                    p.get(
                        "insee_code"
                    ),

                "support_height_m":
                    p.get(
                        "support_height_m"
                    ),

                "operators":
                    operators,

                "generations":
                    generations,

                "systems":
                    systems,

                "statuses":
                    statuses,

                "stations":
                    stations,

                "system_count":
                    p.get(
                        "system_count"
                    ),

                "node_type":
                    p.get(
                        "node_type"
                    ),

                "source":
                    p.get("source"),

                "evidence_type":
                    p.get(
                        "evidence_type"
                    ),
            }
        )

    write_csv(
        ANFR_DIR / "anfr_sites.csv",
        site_rows,
    )

    # --------------------------------------------------------
    # RAW ANFR : tous les systèmes radio
    # --------------------------------------------------------

    raw_data = load_json(
        ANFR_RAW
    )

    raw_records = raw_data.get(
        "records",
        [],
    )

    write_csv(
        ANFR_DIR / "anfr_systems.csv",
        raw_records,
    )

    # --------------------------------------------------------
    # Les statistiques du terminal sont calculées
    # directement depuis les systèmes radio RAW.
    # --------------------------------------------------------

    raw_technology_counter = Counter()
    raw_operator_counter = Counter()

    for row in raw_records:
        generation = row.get(
            "generation"
        )

        operator = row.get(
            "adm_lb_nom"
        )

        if generation:
            raw_technology_counter[
                str(generation)
            ] += 1

        if operator:
            raw_operator_counter[
                str(operator)
            ] += 1

    technology_rows = [
        {
            "technology": tech,
            "radio_systems": count,
        }
        for tech, count
        in sorted(
            raw_technology_counter.items()
        )
    ]

    write_csv(
        ANFR_DIR /
        "anfr_technologies.csv",

        technology_rows,

        [
            "technology",
            "radio_systems",
        ],
    )

    operator_rows = [
        {
            "operator": operator,
            "radio_systems": count,
        }
        for operator, count
        in raw_operator_counter.most_common()
    ]

    write_csv(
        ANFR_DIR /
        "anfr_operators.csv",

        operator_rows,

        [
            "operator",
            "radio_systems",
        ],
    )

    summary_rows = [
        {
            "metric":
                "radio_systems",

            "value":
                len(raw_records),
        },

        {
            "metric":
                "physical_supports",

            "value":
                len(site_rows),
        },
    ]

    write_csv(
        ANFR_DIR /
        "anfr_summary.csv",

        summary_rows,

        [
            "metric",
            "value",
        ],
    )


# ============================================================
# RIPE ATLAS
# ============================================================

def export_ripe():
    geojson = load_json(
        RIPE_GEOJSON
    )

    rows = []

    asn_counter = Counter()

    public_count = 0
    anchor_count = 0
    ipv4_count = 0
    ipv6_count = 0

    for feature in geojson.get(
        "features",
        [],
    ):
        p = feature.get(
            "properties",
            {},
        )

        geometry = feature.get(
            "geometry",
            {},
        )

        coordinates = geometry.get(
            "coordinates",
            [],
        )

        longitude = (
            coordinates[0]
            if len(coordinates) >= 2
            else ""
        )

        latitude = (
            coordinates[1]
            if len(coordinates) >= 2
            else ""
        )

        asn_v4 = p.get(
            "asn_v4"
        )

        asn_v6 = p.get(
            "asn_v6"
        )

        if asn_v4:
            asn_counter[
                f"AS{asn_v4}"
            ] += 1

        if p.get(
            "is_public"
        ):
            public_count += 1

        if p.get(
            "is_anchor"
        ):
            anchor_count += 1

        if asn_v4:
            ipv4_count += 1

        if asn_v6:
            ipv6_count += 1

        rows.append(
            {
                "id":
                    p.get("id"),

                "probe_id":
                    p.get("probe_id"),

                "description":
                    p.get(
                        "description"
                    ),

                "latitude":
                    latitude,

                "longitude":
                    longitude,

                "country_code":
                    p.get(
                        "country_code"
                    ),

                "asn_v4":
                    asn_v4,

                "asn_v6":
                    asn_v6,

                "prefix_v4":
                    p.get(
                        "prefix_v4"
                    ),

                "prefix_v6":
                    p.get(
                        "prefix_v6"
                    ),

                "status_id":
                    p.get(
                        "status_id"
                    ),

                "status":
                    p.get("status"),

                "is_public":
                    p.get(
                        "is_public"
                    ),

                "is_anchor":
                    p.get(
                        "is_anchor"
                    ),

                "tags":
                    p.get(
                        "tags"
                    ),

                "first_connected":
                    p.get(
                        "first_connected"
                    ),

                "last_connected":
                    p.get(
                        "last_connected"
                    ),

                "node_type":
                    p.get(
                        "node_type"
                    ),

                "source":
                    p.get("source"),

                "evidence_type":
                    p.get(
                        "evidence_type"
                    ),

                "location_accuracy":
                    p.get(
                        "location_accuracy"
                    ),
            }
        )

    write_csv(
        RIPE_DIR /
        "ripe_probes.csv",

        rows,
    )

    asn_rows = [
        {
            "asn": asn,
            "probe_count": count,
        }
        for asn, count
        in asn_counter.most_common()
    ]

    write_csv(
        RIPE_DIR /
        "ripe_asn.csv",

        asn_rows,

        [
            "asn",
            "probe_count",
        ],
    )

    summary = [
        {
            "metric":
                "connected_probes",

            "value":
                len(rows),
        },

        {
            "metric":
                "public_probes",

            "value":
                public_count,
        },

        {
            "metric":
                "anchors",

            "value":
                anchor_count,
        },

        {
            "metric":
                "ipv4_probes",

            "value":
                ipv4_count,
        },

        {
            "metric":
                "ipv6_probes",

            "value":
                ipv6_count,
        },

        {
            "metric":
                "distinct_asn_ipv4",

            "value":
                len(asn_counter),
        },
    ]

    write_csv(
        RIPE_DIR /
        "ripe_summary.csv",

        summary,

        [
            "metric",
            "value",
        ],
    )


# ============================================================
# GLOBAL NETWORK OBJECTS
# ============================================================

def export_all_network_objects():
    rows = []

    # Wi-Fi
    wifi = load_json(
        WIFI_GEOJSON
    )

    for feature in wifi.get(
        "features",
        [],
    ):
        p = feature.get(
            "properties",
            {},
        )

        coords = (
            feature
            .get("geometry", {})
            .get("coordinates", [])
        )

        if len(coords) < 2:
            continue

        rows.append(
            {
                "layer":
                    "PARIS_WIFI",

                "object_id":
                    p.get("id"),

                "object_type":
                    "public_wifi",

                "name":
                    p.get("name"),

                "latitude":
                    coords[1],

                "longitude":
                    coords[0],

                "operator_or_asn":
                    p.get(
                        "provider"
                    ),

                "technologies":
                    "",

                "status":
                    p.get(
                        "status"
                    ),

                "source":
                    p.get(
                        "source"
                    ),
            }
        )

    # ANFR
    anfr = load_json(
        ANFR_GEOJSON
    )

    for feature in anfr.get(
        "features",
        [],
    ):
        p = feature.get(
            "properties",
            {},
        )

        coords = (
            feature
            .get("geometry", {})
            .get("coordinates", [])
        )

        if len(coords) < 2:
            continue

        rows.append(
            {
                "layer":
                    "ANFR",

                "object_id":
                    p.get(
                        "sup_id"
                    ),

                "object_type":
                    "mobile_radio_site",

                "name":
                    f"ANFR Support {p.get('sup_id')}",

                "latitude":
                    coords[1],

                "longitude":
                    coords[0],

                "operator_or_asn":
                    flatten_value(
                        p.get(
                            "operators"
                        )
                    ),

                "technologies":
                    flatten_value(
                        p.get(
                            "generations"
                        )
                    ),

                "status":
                    flatten_value(
                        p.get(
                            "statuses"
                        )
                    ),

                "source":
                    p.get(
                        "source"
                    ),
            }
        )

    # RIPE Atlas
    ripe = load_json(
        RIPE_GEOJSON
    )

    for feature in ripe.get(
        "features",
        [],
    ):
        p = feature.get(
            "properties",
            {},
        )

        coords = (
            feature
            .get("geometry", {})
            .get("coordinates", [])
        )

        if len(coords) < 2:
            continue

        rows.append(
            {
                "layer":
                    "RIPE_ATLAS",

                "object_id":
                    p.get(
                        "probe_id"
                    ),

                "object_type":
                    (
                        "ripe_anchor"
                        if p.get(
                            "is_anchor"
                        )
                        else
                        "ripe_probe"
                    ),

                "name":
                    f"RIPE Probe {p.get('probe_id')}",

                "latitude":
                    coords[1],

                "longitude":
                    coords[0],

                "operator_or_asn":
                    p.get(
                        "asn_v4"
                    ),

                "technologies":
                    "IPv4 | IPv6",

                "status":
                    p.get(
                        "status"
                    ),

                "source":
                    "RIPE Atlas",
            }
        )

    write_csv(
        OUTPUT /
        "all_network_objects.csv",

        rows,

        [
            "layer",
            "object_id",
            "object_type",
            "name",
            "latitude",
            "longitude",
            "operator_or_asn",
            "technologies",
            "status",
            "source",
        ],
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
        "       NETGUARDIAN CSV EXPORT"
    )
    print(
        "=============================================="
    )

    WIFI_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    ANFR_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    RIPE_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    print()
    print("[1/4] Paris Wi-Fi")
    export_wifi()

    print()
    print("[2/4] ANFR")
    export_anfr()

    print()
    print("[3/4] RIPE Atlas")
    export_ripe()

    print()
    print("[4/4] Global Network Objects")
    export_all_network_objects()

    print()
    print(
        "=============================================="
    )
    print(
        "             EXPORT TERMINÉ ✅"
    )
    print(
        "=============================================="
    )

    print(
        f"Dossier : {OUTPUT}"
    )


if __name__ == "__main__":
    main()
