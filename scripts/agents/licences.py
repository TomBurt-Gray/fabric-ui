"""Print installed distributions with version and declared licence as JSON."""

import json
import sys
from importlib import metadata


def licence_of(dist: metadata.Distribution) -> str:
    meta = dist.metadata
    expression = meta.get("License-Expression")
    if expression:
        return expression.strip()
    classifiers = [
        c.split(" :: ")[-1] for c in meta.get_all("Classifier") or [] if c.startswith("License ::")
    ]
    if classifiers:
        return ", ".join(classifiers)
    declared = (meta.get("License") or "").strip()
    # Some packages put the full licence text here; only keep short identifiers.
    if declared and len(declared) < 100 and "\n" not in declared:
        return declared
    return "Unknown"


def inventory() -> list[dict[str, str]]:
    rows = {
        dist.metadata["Name"].lower(): {
            "name": dist.metadata["Name"],
            "version": dist.version,
            "licence": licence_of(dist),
        }
        for dist in metadata.distributions()
    }
    return [rows[name] for name in sorted(rows)]


def main() -> int:
    json.dump(inventory(), sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
