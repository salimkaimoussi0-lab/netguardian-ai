#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import uuid

from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

LABEL_FILE = (
    ROOT
    / "telemetry"
    / "features"
    / "current_label.json"
)


ALLOWED_LABELS = {
    "UNLABELED",
    "NORMAL",
    "PORT_SCAN",
    "CONNECTION_BURST",
    "HTTP_ERROR_BURST",
    "HIGH_BANDWIDTH",
}


def load():

    if not LABEL_FILE.exists():

        return {
            "label": "UNLABELED",
            "run_id": None,
        }

    with LABEL_FILE.open(
        encoding="utf-8"
    ) as file:

        return json.load(file)


def save(label: str):

    run_id = str(
        uuid.uuid4()
    )

    data = {
        "label":
            label,

        "run_id":
            run_id,

        "changed_at":
            datetime.now(
                timezone.utc
            ).isoformat(),
    }

    LABEL_FILE.write_text(
        json.dumps(
            data,
            indent=2,
        ),
        encoding="utf-8",
    )

    print()
    print(
        "=============================================="
    )
    print(
        " NETGUARDIAN DATASET LABEL"
    )
    print(
        "=============================================="
    )
    print(
        "Label  :",
        label,
    )
    print(
        "Run ID :",
        run_id,
    )
    print(
        "=============================================="
    )


def main():

    parser = argparse.ArgumentParser()

    sub = parser.add_subparsers(
        dest="command",
        required=True,
    )


    set_parser = sub.add_parser(
        "set"
    )

    set_parser.add_argument(
        "label",
    )


    sub.add_parser(
        "show"
    )

    sub.add_parser(
        "clear"
    )


    args = parser.parse_args()


    if args.command == "show":

        print(
            json.dumps(
                load(),
                indent=2,
            )
        )

        return


    if args.command == "clear":

        save(
            "UNLABELED"
        )

        return


    label = (
        args.label
        .strip()
        .upper()
    )


    if label not in ALLOWED_LABELS:

        raise SystemExit(
            "Label invalide.\n"
            "Valeurs: "
            + ", ".join(
                sorted(
                    ALLOWED_LABELS
                )
            )
        )


    save(
        label
    )


if __name__ == "__main__":
    main()
