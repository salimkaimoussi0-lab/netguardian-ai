#!/usr/bin/env python3

"""
NetGuardian Paris - RIPE Atlas probes ingestion

Récupère les sondes RIPE Atlas actuellement connectées
autour de Paris.

Source:
https://atlas.ripe.net/api/v2/probes/

Outputs:
- data/raw/ripe_atlas/paris_probes.json
- data/processed/ripe_atlas_paris_probes.geojson
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


API_URL = "https://atlas.ripe.net/api/v2/probes/"

PARIS_LAT = 48.8566
PARIS_LON = 2.3522

# Paris + proche couronne
RADIUS_KM = 20

PAGE_SIZE = 500
TIMEOUT = 60

RAW_OUTPUT = Path(
    "data/raw/ripe_atlas/paris_probes.json"
)

GEOJSON_OUTPUT = Path(
    "data/processed/ripe_atlas_paris_probes.geojson"
)

USER_AGENT = (
    "NetGuardian-Paris/0.3 "
    "(academic network research project)"
)


def fetch_json(url: str) -> dict[str, Any]:
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
            f"RIPE Atlas HTTP error {exc.code}"
        ) from exc

    except URLError as exc:
        raise RuntimeError(
            f"RIPE Atlas network error: {exc.reason}"
        ) from exc

    return json.loads(
        raw.decode("utf-8")
    )


def fetch_all_probes() -> list[dict[str, Any]]:
    params = {
        "radius": (
            f"{PARIS_LAT},"
            f"{PARIS_LON}:"
            f"{RADIUS_KM}"
        ),

        # RIPE Atlas API:
        # 1 = Connected
        "status": 1,

        "page_size": PAGE_SIZE,

        "sort": "id",
    }

    url = (
        f"{API_URL}?"
        f"{urlencode(params)}"
    )

    probes = []

    print()
    print(
        "=============================================="
    )
    print(
        "    NETGUARDIAN PARIS - RIPE ATLAS"
    )
    print(
        "=============================================="
    )

    print(
        f"[RIPE] Centre : "
        f"{PARIS_LAT}, {PARIS_LON}"
    )

    print(
        f"[RIPE] Rayon  : {RADIUS_KM} km"
    )

    print(
        "[RIPE] Statut : Connected"
    )

    while url:
        payload = fetch_json(url)

        results = payload.get(
            "results",
            [],
        )

        if not isinstance(results, list):
            raise RuntimeError(
                "Champ RIPE Atlas 'results' invalide."
            )

        probes.extend(results)

        total = payload.get(
            "count",
            len(probes),
        )

        print(
            f"[RIPE] {len(probes)}/{total} sondes"
        )

        url = payload.get("next")

    return probes


def get_coordinates(
    probe: dict[str, Any],
) -> tuple[float | None, float | None]:
    geometry = probe.get("geometry")

    if not isinstance(geometry, dict):
        return None, None

    if geometry.get("type") != "Point":
        return None, None

    coordinates = geometry.get(
        "coordinates"
    )

    if (
        not isinstance(coordinates, list)
        or len(coordinates) < 2
    ):
        return None, None

    try:
        longitude = float(
            coordinates[0]
        )

        latitude = float(
            coordinates[1]
        )

    except (
        TypeError,
        ValueError,
    ):
        return None, None

    return longitude, latitude


def get_status(
    probe: dict[str, Any],
) -> tuple[int | None, str]:
    status = probe.get("status")

    if isinstance(status, dict):
        return (
            status.get("id"),
            str(
                status.get(
                    "name",
                    "Unknown",
                )
            ),
        )

    return None, "Unknown"


def get_tags(
    probe: dict[str, Any],
) -> list[str]:
    result = []

    tags = probe.get(
        "tags",
        [],
    )

    if not isinstance(tags, list):
        return result

    for tag in tags:
        if not isinstance(tag, dict):
            continue

        name = tag.get(
            "name"
        )

        if name:
            result.append(
                str(name)
            )

    return sorted(
        set(result)
    )


def save_raw(
    probes: list[dict[str, Any]],
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
                "RIPE Atlas",

            "retrieved_at":
                datetime.now(
                    timezone.utc
                ).isoformat(),

            "radius_km":
                RADIUS_KM,

            "centre": {
                "latitude":
                    PARIS_LAT,

                "longitude":
                    PARIS_LON,
            },

            "probe_count":
                len(probes),
        },

        "records":
            probes,
    }

    RAW_OUTPUT.write_text(
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def build_geojson(
    probes: list[dict[str, Any]],
) -> dict[str, Any]:
    features = []

    skipped = 0

    public_count = 0
    anchor_count = 0

    for probe in probes:
        longitude, latitude = (
            get_coordinates(probe)
        )

        if (
            longitude is None
            or latitude is None
        ):
            skipped += 1
            continue

        status_id, status_name = (
            get_status(probe)
        )

        probe_id = probe.get("id")

        is_public = bool(
            probe.get("is_public")
        )

        is_anchor = bool(
            probe.get("is_anchor")
        )

        if is_public:
            public_count += 1

        if is_anchor:
            anchor_count += 1

        properties = {
            "id":
                f"ripe-probe-{probe_id}",

            "probe_id":
                probe_id,

            "node_type":
                "ripe_atlas_probe",

            "description":
                probe.get("description"),

            "country_code":
                probe.get("country_code"),

            "asn_v4":
                probe.get("asn_v4"),

            "asn_v6":
                probe.get("asn_v6"),

            "prefix_v4":
                probe.get("prefix_v4"),

            "prefix_v6":
                probe.get("prefix_v6"),

            "status_id":
                status_id,

            "status":
                status_name,

            "is_public":
                is_public,

            "is_anchor":
                is_anchor,

            "tags":
                get_tags(probe),

            "first_connected":
                probe.get(
                    "first_connected"
                ),

            "last_connected":
                probe.get(
                    "last_connected"
                ),

            "source":
                "RIPE Atlas",

            "evidence_type":
                "OBSERVED",

            "location_accuracy":
                "OBFUSCATED",
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
                        longitude,
                        latitude,
                    ],
                },

                "properties":
                    properties,
            }
        )

    print()
    print(
        f"[RIPE] Sondes géolocalisées : "
        f"{len(features)}"
    )

    print(
        f"[RIPE] Sondes publiques     : "
        f"{public_count}"
    )

    print(
        f"[RIPE] Anchors              : "
        f"{anchor_count}"
    )

    print(
        f"[RIPE] Sans coordonnées     : "
        f"{skipped}"
    )

    return {
        "type":
            "FeatureCollection",

        "name":
            "NetGuardian Paris RIPE Atlas",

        "metadata": {
            "project":
                "NetGuardian Paris",

            "source":
                "RIPE Atlas",

            "retrieved_at":
                datetime.now(
                    timezone.utc
                ).isoformat(),

            "radius_km":
                RADIUS_KM,

            "feature_count":
                len(features),

            "note":
                (
                    "RIPE Atlas probe locations "
                    "are intentionally obfuscated."
                ),
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
    probes: list[dict[str, Any]],
    geojson: dict[str, Any],
) -> None:
    asns = set()

    ipv4_count = 0
    ipv6_count = 0
    anchor_count = 0

    for probe in probes:
        asn = probe.get(
            "asn_v4"
        )

        if asn:
            asns.add(asn)

        if probe.get(
            "address_v4"
        ):
            ipv4_count += 1

        if probe.get(
            "address_v6"
        ):
            ipv6_count += 1

        if probe.get(
            "is_anchor"
        ):
            anchor_count += 1

    print()
    print(
        "=============================================="
    )
    print(
        "      NETGUARDIAN - RIPE ATLAS ✅"
    )
    print(
        "=============================================="
    )

    print(
        f"Sondes connectées : "
        f"{len(probes)}"
    )

    print(
        f"Points GeoJSON     : "
        f"{len(geojson['features'])}"
    )

    print(
        f"ASN distincts      : "
        f"{len(asns)}"
    )

    print(
        f"IPv4               : "
        f"{ipv4_count}"
    )

    print(
        f"IPv6               : "
        f"{ipv6_count}"
    )

    print(
        f"Anchors             : "
        f"{anchor_count}"
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
    probes = fetch_all_probes()

    if not probes:
        raise RuntimeError(
            "Aucune sonde RIPE Atlas "
            "trouvée autour de Paris."
        )

    save_raw(probes)

    geojson = build_geojson(
        probes
    )

    if not geojson["features"]:
        raise RuntimeError(
            "Aucune sonde RIPE Atlas "
            "géolocalisable."
        )

    save_geojson(
        geojson
    )

    print_summary(
        probes,
        geojson,
    )


if __name__ == "__main__":
    main()
