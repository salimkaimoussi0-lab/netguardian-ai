#!/usr/bin/env python3

"""
NetGuardian Paris
=================

Ingestion des sites Paris Wi-Fi depuis Paris Open Data.

Source officielle:
https://opendata.paris.fr/

Dataset:
sites-disposant-du-service-paris-wi-fi

Sorties:
- data/raw/paris_wifi/sites.json
- data/processed/paris_wifi_sites.geojson

Aucune dépendance Python externe n'est nécessaire.
"""

from __future__ import annotations

import gzip
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


# ============================================================
# CONFIGURATION
# ============================================================

DATASET_ID = "sites-disposant-du-service-paris-wi-fi"

BASE_URL = (
    "https://opendata.paris.fr/"
    "api/explore/v2.1/catalog/datasets/"
    f"{DATASET_ID}/records"
)

PAGE_SIZE = 100
TIMEOUT_SECONDS = 30
MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 2

RAW_OUTPUT = Path(
    "data/raw/paris_wifi/sites.json"
)

GEOJSON_OUTPUT = Path(
    "data/processed/paris_wifi_sites.geojson"
)

USER_AGENT = (
    "NetGuardian-Paris/0.1 "
    "(public open-data research project)"
)


# ============================================================
# HTTP
# ============================================================

def decode_http_body(raw: bytes, content_encoding: str) -> bytes:
    """
    Décompresse la réponse HTTP lorsque nécessaire.

    Paris Open Data peut retourner du gzip.
    On teste à la fois l'en-tête HTTP et la signature gzip.
    """

    encoding = (content_encoding or "").lower()

    if "gzip" in encoding or raw[:2] == b"\x1f\x8b":
        return gzip.decompress(raw)

    return raw


def fetch_page(offset: int) -> dict[str, Any]:
    """
    Télécharge une page de l'API Paris Open Data.
    """

    params = {
        "limit": PAGE_SIZE,
        "offset": offset,
    }

    url = f"{BASE_URL}?{urlencode(params)}"

    request = Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
            "Accept-Encoding": "gzip, identity",
        },
    )

    last_error: Exception | None = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            with urlopen(
                request,
                timeout=TIMEOUT_SECONDS,
            ) as response:

                raw = response.read()

                raw = decode_http_body(
                    raw,
                    response.headers.get(
                        "Content-Encoding",
                        "",
                    ),
                )

                text = raw.decode("utf-8")

                payload = json.loads(text)

                if not isinstance(payload, dict):
                    raise RuntimeError(
                        "Réponse API inattendue: "
                        "l'objet racine n'est pas un dictionnaire."
                    )

                return payload

        except HTTPError as exc:
            last_error = exc

            print(
                f"[NetGuardian] HTTP {exc.code} "
                f"- tentative {attempt}/{MAX_RETRIES}"
            )

        except URLError as exc:
            last_error = exc

            print(
                f"[NetGuardian] Erreur réseau "
                f"- tentative {attempt}/{MAX_RETRIES}: "
                f"{exc.reason}"
            )

        except (
            UnicodeDecodeError,
            json.JSONDecodeError,
            gzip.BadGzipFile,
        ) as exc:
            last_error = exc

            print(
                f"[NetGuardian] Réponse invalide "
                f"- tentative {attempt}/{MAX_RETRIES}: "
                f"{exc}"
            )

        if attempt < MAX_RETRIES:
            time.sleep(RETRY_DELAY_SECONDS)

    raise RuntimeError(
        f"Impossible de récupérer l'API après "
        f"{MAX_RETRIES} tentatives."
    ) from last_error


# ============================================================
# PAGINATION
# ============================================================

def fetch_all_records() -> list[dict[str, Any]]:
    """
    Récupère tous les sites Paris Wi-Fi via pagination.
    """

    records: list[dict[str, Any]] = []

    offset = 0
    total_count: int | None = None

    print()
    print(
        "=============================================="
    )
    print(
        "     NETGUARDIAN PARIS - DATA INGESTION"
    )
    print(
        "=============================================="
    )
    print(
        "[NetGuardian] Source : Paris Open Data"
    )
    print(
        f"[NetGuardian] Dataset: {DATASET_ID}"
    )
    print()
    print(
        "[NetGuardian] Téléchargement des sites "
        "Paris Wi-Fi..."
    )

    while True:
        payload = fetch_page(offset)

        if total_count is None:
            total_count_raw = payload.get(
                "total_count",
                0,
            )

            try:
                total_count = int(total_count_raw)
            except (TypeError, ValueError):
                total_count = 0

            print(
                f"[NetGuardian] Nombre annoncé par API: "
                f"{total_count}"
            )

        page = payload.get(
            "results",
            [],
        )

        if not isinstance(page, list):
            raise RuntimeError(
                "Le champ 'results' de l'API "
                "n'est pas une liste."
            )

        if not page:
            break

        valid_page = [
            item
            for item in page
            if isinstance(item, dict)
        ]

        records.extend(valid_page)

        if total_count:
            print(
                f"[NetGuardian] "
                f"{len(records)}/{total_count} "
                f"enregistrements"
            )
        else:
            print(
                f"[NetGuardian] "
                f"{len(records)} enregistrements"
            )

        offset += len(page)

        if total_count and len(records) >= total_count:
            break

        if len(page) < PAGE_SIZE:
            break

        time.sleep(0.15)

    print(
        f"[NetGuardian] Téléchargement terminé: "
        f"{len(records)} sites."
    )

    return records


# ============================================================
# GÉOMÉTRIE
# ============================================================

def geometry_from_geo_shape(
    record: dict[str, Any],
) -> dict[str, Any] | None:
    """
    Extrait la géométrie depuis geo_shape.

    L'API peut fournir:
    {
        "type": "Feature",
        "geometry": {
            "type": "Point",
            "coordinates": [lon, lat]
        }
    }

    ou directement une géométrie GeoJSON.
    """

    geo_shape = record.get("geo_shape")

    if not isinstance(geo_shape, dict):
        return None

    shape_type = geo_shape.get("type")

    if shape_type == "Feature":
        geometry = geo_shape.get("geometry")

        if isinstance(geometry, dict):
            return geometry

    if (
        shape_type == "Point"
        and isinstance(
            geo_shape.get("coordinates"),
            list,
        )
    ):
        return geo_shape

    return None


def geometry_from_geo_point(
    record: dict[str, Any],
) -> dict[str, Any] | None:
    """
    Fallback utilisant geo_point_2d.

    Selon la représentation API, geo_point_2d peut
    être un dictionnaire:
        {"lon": 2.35, "lat": 48.85}

    ou une liste:
        [48.85, 2.35]
    """

    geo_point = record.get("geo_point_2d")

    if isinstance(geo_point, dict):
        latitude = geo_point.get("lat")
        longitude = geo_point.get("lon")

        if (
            isinstance(latitude, (int, float))
            and isinstance(
                longitude,
                (int, float),
            )
        ):
            return {
                "type": "Point",
                "coordinates": [
                    float(longitude),
                    float(latitude),
                ],
            }

    if (
        isinstance(geo_point, list)
        and len(geo_point) >= 2
    ):
        latitude = geo_point[0]
        longitude = geo_point[1]

        if (
            isinstance(latitude, (int, float))
            and isinstance(
                longitude,
                (int, float),
            )
        ):
            return {
                "type": "Point",
                "coordinates": [
                    float(longitude),
                    float(latitude),
                ],
            }

    return None


def extract_geometry(
    record: dict[str, Any],
) -> dict[str, Any] | None:
    """
    Extrait la meilleure géométrie disponible.
    """

    geometry = geometry_from_geo_shape(record)

    if geometry is not None:
        return geometry

    return geometry_from_geo_point(record)


def get_lon_lat(
    geometry: dict[str, Any] | None,
) -> tuple[float | None, float | None]:
    """
    Récupère longitude et latitude d'un Point GeoJSON.
    """

    if not isinstance(geometry, dict):
        return None, None

    if geometry.get("type") != "Point":
        return None, None

    coordinates = geometry.get("coordinates")

    if (
        not isinstance(coordinates, list)
        or len(coordinates) < 2
    ):
        return None, None

    longitude = coordinates[0]
    latitude = coordinates[1]

    if not isinstance(longitude, (int, float)):
        return None, None

    if not isinstance(latitude, (int, float)):
        return None, None

    return float(longitude), float(latitude)


# ============================================================
# NORMALISATION
# ============================================================

def normalize_record(
    record: dict[str, Any],
) -> dict[str, Any]:
    """
    Transforme le schéma Paris Open Data
    vers le schéma commun NetGuardian.
    """

    geometry = extract_geometry(record)

    longitude, latitude = get_lon_lat(
        geometry
    )

    access_points = record.get(
        "nombre_de_borne_wifi"
    )

    if isinstance(access_points, str):
        try:
            access_points = int(access_points)
        except ValueError:
            access_points = None

    return {
        "id": record.get("idpw"),
        "name": record.get("nom_site"),
        "address": record.get(
            "arc_adresse"
        ),
        "postal_code": record.get("cp"),
        "wifi_access_points": access_points,
        "status": record.get("etat2"),
        "latitude": latitude,
        "longitude": longitude,
        "node_type": "public_wifi",
        "provider": "Ville de Paris",
        "source": "Paris Open Data",
        "source_dataset": DATASET_ID,
        "evidence_type": "PUBLIC_DECLARATION",
    }


# ============================================================
# GEOJSON
# ============================================================

def build_geojson(
    records: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Génère un FeatureCollection GeoJSON.
    """

    features: list[dict[str, Any]] = []

    skipped = 0

    for record in records:
        geometry = extract_geometry(record)

        if geometry is None:
            skipped += 1
            continue

        normalized = normalize_record(
            record
        )

        features.append(
            {
                "type": "Feature",
                "id": normalized.get("id"),
                "geometry": geometry,
                "properties": normalized,
            }
        )

    retrieved_at = (
        datetime.now(timezone.utc)
        .isoformat()
    )

    print(
        f"[NetGuardian] GeoJSON: "
        f"{len(features)} points créés."
    )

    if skipped:
        print(
            f"[NetGuardian] Attention: "
            f"{skipped} enregistrements "
            f"sans coordonnées."
        )

    return {
        "type": "FeatureCollection",
        "name": "NetGuardian Paris Wi-Fi",
        "metadata": {
            "project": "NetGuardian Paris",
            "source": "Paris Open Data",
            "dataset": DATASET_ID,
            "retrieved_at": retrieved_at,
            "feature_count": len(features),
            "skipped_without_geometry": skipped,
            "evidence_type": (
                "PUBLIC_DECLARATION"
            ),
        },
        "features": features,
    }


# ============================================================
# SAUVEGARDE
# ============================================================

def save_raw(
    records: list[dict[str, Any]],
) -> None:
    """
    Sauvegarde les données API originales.
    """

    RAW_OUTPUT.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    payload = {
        "metadata": {
            "project": "NetGuardian Paris",
            "source": "Paris Open Data",
            "dataset": DATASET_ID,
            "retrieved_at": (
                datetime.now(timezone.utc)
                .isoformat()
            ),
            "record_count": len(records),
        },
        "records": records,
    }

    RAW_OUTPUT.write_text(
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def save_geojson(
    geojson: dict[str, Any],
) -> None:
    """
    Sauvegarde le dataset normalisé GeoJSON.
    """

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


# ============================================================
# STATISTIQUES
# ============================================================

def print_summary(
    records: list[dict[str, Any]],
    geojson: dict[str, Any],
) -> None:
    """
    Affiche un résumé des données récupérées.
    """

    operational = 0
    non_operational = 0
    total_access_points = 0

    postal_codes: set[str] = set()

    for record in records:
        status = record.get("etat2")

        if status == "Opérationnel":
            operational += 1
        else:
            non_operational += 1

        access_points = record.get(
            "nombre_de_borne_wifi"
        )

        if isinstance(access_points, int):
            total_access_points += (
                access_points
            )

        postal_code = record.get("cp")

        if postal_code:
            postal_codes.add(
                str(postal_code)
            )

    features = geojson.get(
        "features",
        [],
    )

    print()
    print(
        "=============================================="
    )
    print(
        "       NETGUARDIAN PARIS - WIFI ✅"
    )
    print(
        "=============================================="
    )
    print(
        f"Sites téléchargés       : {len(records)}"
    )
    print(
        f"Sites géolocalisés      : {len(features)}"
    )
    print(
        f"Sites opérationnels     : {operational}"
    )
    print(
        f"Autres états            : {non_operational}"
    )
    print(
        f"Bornes Wi-Fi            : "
        f"{total_access_points}"
    )
    print(
        f"Codes postaux distincts : "
        f"{len(postal_codes)}"
    )
    print()
    print(
        f"RAW                     : "
        f"{RAW_OUTPUT}"
    )
    print(
        f"GEOJSON                 : "
        f"{GEOJSON_OUTPUT}"
    )
    print(
        "=============================================="
    )


# ============================================================
# MAIN
# ============================================================

def main() -> None:
    records = fetch_all_records()

    if not records:
        raise RuntimeError(
            "Paris Open Data n'a retourné "
            "aucun enregistrement."
        )

    save_raw(records)

    geojson = build_geojson(records)

    save_geojson(geojson)

    print_summary(
        records,
        geojson,
    )


if __name__ == "__main__":
    main()
