#!/usr/bin/env python3

"""
NetGuardian Paris - ANFR mobile network ingestion

Récupère les systèmes radio mobiles ANFR pour les
20 arrondissements de Paris.

Puis agrège les systèmes radio par support physique SUP_ID.

Outputs:
- data/raw/anfr/paris_mobile_systems.json
- data/processed/anfr_paris_sites.geojson
"""

from __future__ import annotations

import json
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


RESOURCE_ID = (
    "88ef0887-6b0f-4d3f-8545-6d64c8f597da"
)

API_URL = (
    "https://data-backoffice.anfr.fr/"
    "fr/api/action/datastore_search"
)

PAGE_SIZE = 1000
TIMEOUT = 60

PARIS_INSEE_CODES = [
    f"751{i:02d}"
    for i in range(1, 21)
]

RAW_OUTPUT = Path(
    "data/raw/anfr/paris_mobile_systems.json"
)

GEOJSON_OUTPUT = Path(
    "data/processed/anfr_paris_sites.geojson"
)

USER_AGENT = (
    "NetGuardian-Paris/0.2 "
    "(academic-open-data-project)"
)


def api_request(
    code_insee: str,
    offset: int,
) -> dict[str, Any]:
    """
    Interroge l'API CKAN ANFR pour un arrondissement.
    """

    filters = json.dumps(
        {
            "com_cd_insee": code_insee,
        },
        ensure_ascii=False,
    )

    params = {
        "resource_id": RESOURCE_ID,
        "limit": PAGE_SIZE,
        "offset": offset,
        "filters": filters,
    }

    url = (
        f"{API_URL}?"
        f"{urlencode(params)}"
    )

    request = Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
        },
    )

    try:
        with urlopen(
            request,
            timeout=TIMEOUT,
        ) as response:
            raw = response.read()

    except HTTPError as exc:
        raise RuntimeError(
            f"ANFR HTTP {exc.code} "
            f"pour {code_insee}"
        ) from exc

    except URLError as exc:
        raise RuntimeError(
            f"Erreur réseau ANFR: "
            f"{exc.reason}"
        ) from exc

    payload = json.loads(
        raw.decode("utf-8")
    )

    if not payload.get("success"):
        raise RuntimeError(
            f"ANFR API success=false "
            f"pour {code_insee}: {payload}"
        )

    result = payload.get("result")

    if not isinstance(result, dict):
        raise RuntimeError(
            "Réponse ANFR invalide: "
            "'result' absent."
        )

    return result


def fetch_arrondissement(
    code_insee: str,
) -> list[dict[str, Any]]:
    """
    Récupère toutes les lignes d'un arrondissement,
    avec pagination.
    """

    all_records = []

    offset = 0
    total = None

    while True:
        result = api_request(
            code_insee,
            offset,
        )

        records = result.get(
            "records",
            [],
        )

        if not isinstance(records, list):
            raise RuntimeError(
                "ANFR 'records' n'est pas une liste."
            )

        if total is None:
            total = result.get(
                "total",
                len(records),
            )

            print(
                f"[ANFR]   total annoncé: {total}"
            )

        all_records.extend(records)

        print(
            f"[ANFR]   "
            f"{len(all_records)}/{total}"
        )

        if not records:
            break

        offset += len(records)

        if total is not None:
            try:
                if len(all_records) >= int(total):
                    break
            except (TypeError, ValueError):
                pass

        if len(records) < PAGE_SIZE:
            break

        time.sleep(0.15)

    return all_records


def fetch_all_paris() -> list[dict[str, Any]]:
    """
    Récupère les 20 arrondissements.
    """

    all_records = []

    print()
    print(
        "=============================================="
    )
    print(
        "       NETGUARDIAN PARIS - ANFR"
    )
    print(
        "=============================================="
    )
    print(
        "[ANFR] Source: ANFR Open Data"
    )
    print(
        "[ANFR] Dataset: réseaux mobiles"
    )
    print()

    for index, code in enumerate(
        PARIS_INSEE_CODES,
        start=1,
    ):
        print(
            f"[ANFR] Paris {index:02d}/20 "
            f"- INSEE {code}"
        )

        rows = fetch_arrondissement(
            code
        )

        print(
            f"[ANFR]   récupérés: "
            f"{len(rows)} systèmes"
        )

        all_records.extend(rows)

        time.sleep(0.2)

    print()
    print(
        f"[ANFR] TOTAL PARIS: "
        f"{len(all_records)} systèmes"
    )

    return all_records


def clean_text(
    value: Any,
) -> str | None:
    if value is None:
        return None

    value = str(value).strip()

    return value or None


def parse_coordinate_string(
    value: str,
) -> tuple[float | None, float | None]:
    """
    Parse une coordonnée type:
    '48.8566, 2.3522'

    Le dataset ANFR utilise latitude, longitude.
    """

    try:
        parts = [
            part.strip()
            for part in value.split(",")
        ]

        if len(parts) < 2:
            return None, None

        latitude = float(parts[0])
        longitude = float(parts[1])

        return longitude, latitude

    except (
        TypeError,
        ValueError,
    ):
        return None, None


def extract_lon_lat(
    row: dict[str, Any],
) -> tuple[float | None, float | None]:
    """
    Supporte plusieurs représentations possibles
    du champ geo_point_2d.
    """

    value = row.get(
        "coordonnees"
    )

    # Exemple:
    # {"lat": 48.8, "lon": 2.3}
    if isinstance(value, dict):
        latitude = value.get("lat")
        longitude = value.get("lon")

        try:
            return (
                float(longitude),
                float(latitude),
            )
        except (
            TypeError,
            ValueError,
        ):
            pass

    # Exemple:
    # [48.8, 2.3]
    if (
        isinstance(value, list)
        and len(value) >= 2
    ):
        try:
            latitude = float(
                value[0]
            )

            longitude = float(
                value[1]
            )

            return (
                longitude,
                latitude,
            )

        except (
            TypeError,
            ValueError,
        ):
            pass

    # Exemple:
    # "48.8566, 2.3522"
    if isinstance(value, str):
        longitude, latitude = (
            parse_coordinate_string(
                value
            )
        )

        if (
            longitude is not None
            and latitude is not None
        ):
            return (
                longitude,
                latitude,
            )

    return None, None


def save_raw(
    rows: list[dict[str, Any]],
) -> None:
    RAW_OUTPUT.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    payload = {
        "metadata": {
            "project":
                "NetGuardian Paris",

            "source":
                "ANFR Open Data",

            "resource_id":
                RESOURCE_ID,

            "retrieved_at":
                datetime.now(
                    timezone.utc
                ).isoformat(),

            "record_count":
                len(rows),
        },

        "records":
            rows,
    }

    RAW_OUTPUT.write_text(
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def aggregate_sites(
    rows: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """
    Plusieurs systèmes radio peuvent être installés
    sur le même support physique.

    On regroupe donc par SUP_ID.
    """

    sites = {}

    skipped = 0

    for row in rows:
        sup_id = row.get(
            "sup_id"
        )

        if sup_id is None:
            continue

        longitude, latitude = (
            extract_lon_lat(row)
        )

        if (
            longitude is None
            or latitude is None
        ):
            skipped += 1
            continue

        # Sécurité géographique:
        # on ne garde que des points cohérents
        # avec Paris / proche couronne.
        if not (
            2.0 <= longitude <= 2.7
            and
            48.7 <= latitude <= 49.1
        ):
            skipped += 1
            continue

        key = str(
            sup_id
        )

        if key not in sites:
            sites[key] = {
                "sup_id":
                    key,

                "longitude":
                    longitude,

                "latitude":
                    latitude,

                "address":
                    clean_text(
                        row.get(
                            "adr_lb_lieu"
                        )
                    ),

                "address_1":
                    clean_text(
                        row.get(
                            "adr_lb_add1"
                        )
                    ),

                "address_2":
                    clean_text(
                        row.get(
                            "adr_lb_add2"
                        )
                    ),

                "address_3":
                    clean_text(
                        row.get(
                            "adr_lb_add3"
                        )
                    ),

                "postal_code":
                    clean_text(
                        row.get(
                            "adr_nm_cp"
                        )
                    ),

                "insee_code":
                    clean_text(
                        row.get(
                            "com_cd_insee"
                        )
                    ),

                "support_height_m":
                    clean_text(
                        row.get(
                            "sup_nm_haut"
                        )
                    ),

                "operators":
                    set(),

                "generations":
                    set(),

                "systems":
                    set(),

                "statuses":
                    set(),

                "stations":
                    set(),

                "system_count":
                    0,
            }

        site = sites[key]

        site["system_count"] += 1

        operator = clean_text(
            row.get(
                "adm_lb_nom"
            )
        )

        generation = clean_text(
            row.get(
                "generation"
            )
        )

        system = clean_text(
            row.get(
                "emr_lb_systeme"
            )
        )

        status = clean_text(
            row.get(
                "statut"
            )
        )

        station = clean_text(
            row.get(
                "sta_nm_anfr"
            )
        )

        if operator:
            site[
                "operators"
            ].add(
                operator
            )

        if generation:
            site[
                "generations"
            ].add(
                generation
            )

        if system:
            site[
                "systems"
            ].add(
                system
            )

        if status:
            site[
                "statuses"
            ].add(
                status
            )

        if station:
            site[
                "stations"
            ].add(
                station
            )

    print()
    print(
        f"[ANFR] Supports physiques: "
        f"{len(sites)}"
    )

    print(
        f"[ANFR] Lignes sans "
        f"coordonnées exploitables: {skipped}"
    )

    return sites


def build_geojson(
    sites: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    features = []

    for site in sites.values():
        properties = {
            "id":
                f"anfr-{site['sup_id']}",

            "sup_id":
                site["sup_id"],

            "node_type":
                "mobile_radio_site",

            "address":
                site["address"],

            "address_1":
                site["address_1"],

            "address_2":
                site["address_2"],

            "address_3":
                site["address_3"],

            "postal_code":
                site["postal_code"],

            "insee_code":
                site["insee_code"],

            "support_height_m":
                site["support_height_m"],

            "operators":
                sorted(
                    site["operators"]
                ),

            "generations":
                sorted(
                    site["generations"]
                ),

            "systems":
                sorted(
                    site["systems"]
                ),

            "statuses":
                sorted(
                    site["statuses"]
                ),

            "stations":
                sorted(
                    site["stations"]
                ),

            "system_count":
                site["system_count"],

            "source":
                "ANFR Open Data",

            "evidence_type":
                "PUBLIC_DECLARATION",
        }

        features.append(
            {
                "type":
                    "Feature",

                "id":
                    properties["id"],

                "geometry": {
                    "type":
                        "Point",

                    "coordinates": [
                        site[
                            "longitude"
                        ],
                        site[
                            "latitude"
                        ],
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
            "NetGuardian Paris ANFR",

        "metadata": {
            "project":
                "NetGuardian Paris",

            "source":
                "ANFR Open Data",

            "retrieved_at":
                datetime.now(
                    timezone.utc
                ).isoformat(),

            "feature_count":
                len(features),
        },

        "features":
            features,
    }


def save_geojson(
    geojson: dict[str, Any],
) -> None:
    GEOJSON_OUTPUT.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    GEOJSON_OUTPUT.write_text(
        json.dumps(
            geojson,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def print_summary(
    rows: list[dict[str, Any]],
    sites: dict[str, dict[str, Any]],
) -> None:
    generations = Counter()
    operators = Counter()

    for row in rows:
        generation = clean_text(
            row.get(
                "generation"
            )
        )

        operator = clean_text(
            row.get(
                "adm_lb_nom"
            )
        )

        if generation:
            generations[
                generation
            ] += 1

        if operator:
            operators[
                operator
            ] += 1

    print()
    print(
        "=============================================="
    )
    print(
        "        NETGUARDIAN PARIS - ANFR ✅"
    )
    print(
        "=============================================="
    )

    print(
        f"Systèmes radio      : {len(rows)}"
    )

    print(
        f"Supports physiques  : {len(sites)}"
    )

    print()
    print(
        "Technologies:"
    )

    for generation, count in sorted(
        generations.items()
    ):
        print(
            f"  {generation:5} : {count}"
        )

    print()
    print(
        "Opérateurs:"
    )

    for operator, count in (
        operators.most_common()
    ):
        print(
            f"  {operator:25} : {count}"
        )

    print()
    print(
        f"RAW     : {RAW_OUTPUT}"
    )

    print(
        f"GeoJSON : {GEOJSON_OUTPUT}"
    )

    print(
        "=============================================="
    )


def main() -> None:
    rows = fetch_all_paris()

    if not rows:
        raise RuntimeError(
            "Aucune donnée ANFR récupérée."
        )

    save_raw(
        rows
    )

    sites = aggregate_sites(
        rows
    )

    if not sites:
        raise RuntimeError(
            "Aucun support ANFR "
            "géolocalisé trouvé."
        )

    geojson = build_geojson(
        sites
    )

    save_geojson(
        geojson
    )

    print_summary(
        rows,
        sites,
    )


if __name__ == "__main__":
    main()
