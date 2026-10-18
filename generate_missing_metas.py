#!/usr/bin/env python3
"""
Generate missing meta.json files from WoW Spell Editor bindings.

Reads bindings from Bindings_335_wotlk/*.txt and creates corresponding
meta.json files in spelleditor_meta/ for any that are missing.
"""

import json
import re
from pathlib import Path

# Paths
BINDINGS_DIR = Path("/workspace/project/Zeppelin-Tools/WoW Spell Editor/Bindings_335_wotlk")
META_DIR = Path("/workspace/project/Zeppelin-Tools/DBCTool/spelleditor_meta")

# Type mapping from binding format to meta format
TYPE_MAP = {
    'uint': 'uint32',
    'int': 'int32',
    'float': 'float',
    'string': 'string',
}


def parse_binding(binding_path: Path) -> dict:
    """Parse a WoW Spell Editor binding file into meta format."""

    with open(binding_path, 'r') as f:
        lines = f.readlines()

    if not lines:
        return None

    # First line might be: # FileName.dbc wotlk 3.3.5
    # Or it might start directly with columns
    header = lines[0].strip()
    match = re.match(r'#\s*(\S+\.dbc)', header, re.IGNORECASE)
    if match:
        dbc_filename = match.group(1)
        data_lines = lines[1:]
    else:
        # No header - use binding filename
        dbc_filename = binding_path.stem + ".dbc"
        data_lines = lines

    columns = []
    for line in data_lines:
        line = line.strip()
        if not line or line.startswith('#'):
            continue

        parts = line.split()
        if len(parts) < 2:
            continue

        col_type = parts[0]
        col_name = parts[1]

        # Skip directives like IGNORE_ORDER
        if col_type.isupper() and '_' in col_type:
            continue

        # Handle "uint name string" format (type name modifier)
        is_string = len(parts) >= 3 and parts[2] == 'string'

        if is_string:
            meta_type = 'string'
        elif col_type in TYPE_MAP:
            meta_type = TYPE_MAP[col_type]
        else:
            meta_type = col_type

        columns.append({
            "name": col_name,
            "type": meta_type
        })

    if not columns:
        return None

    return {
        "file": dbc_filename,
        "primaryKeys": ["id"] if columns and columns[0]["name"] == "id" else [],
        "fields": columns
    }


def main():
    print("Generating missing meta files from bindings...")
    print(f"  Bindings: {BINDINGS_DIR}")
    print(f"  Meta output: {META_DIR}")
    print()

    created = 0
    skipped = 0
    failed = 0

    for binding_path in sorted(BINDINGS_DIR.glob("*.txt")):
        name = binding_path.stem.lower()
        meta_path = META_DIR / f"{name}.meta.json"

        if meta_path.exists():
            skipped += 1
            continue

        meta_data = parse_binding(binding_path)
        if not meta_data:
            print(f"  FAILED: {binding_path.name}")
            failed += 1
            continue

        with open(meta_path, 'w') as f:
            json.dump(meta_data, f, indent=2)
            f.write('\n')

        print(f"  Created: {meta_path.name} ({len(meta_data['fields'])} fields)")
        created += 1

    print()
    print(f"Done: {created} created, {skipped} skipped (exist), {failed} failed")


if __name__ == "__main__":
    main()
