#!/usr/bin/env python3
"""
Normalize DBCTool meta files and WoW Spell Editor bindings to snake_case.

This script converts all column/field names to consistent snake_case format.
"""

import json
import re
import os
from pathlib import Path


def to_snake_case(name: str) -> str:
    """Convert any naming convention to snake_case.

    Handles:
    - PascalCase -> pascal_case
    - camelCase -> camel_case
    - Already snake_case -> snake_case (unchanged)
    - MixedCase123 -> mixed_case_123
    - ID -> id (special case for common abbreviations)
    - SoundID -> sound_id
    - Name1 -> name_1
    """
    if not name:
        return name

    # Already snake_case? Return as-is
    if '_' in name and name.islower():
        return name

    result = name

    # First, handle the special case of standalone "ID" or names ending in "ID"
    # We want SoundID -> sound_id, not sound_i_d
    # And ID alone -> id
    if result == 'ID':
        return 'id'

    # Replace trailing ID with _id marker (we'll clean up later)
    result = re.sub(r'ID$', '_id', result)
    # Replace ID in middle followed by capital (like IDSomething -> id_something)
    result = re.sub(r'ID([A-Z])', r'_id_\1', result)

    # Same for other common abbreviations
    for abbr in ['UI', 'PVP', 'NPC', 'LFG', 'WMO', 'HP', 'MP', 'XP']:
        if result == abbr:
            return abbr.lower()
        result = re.sub(rf'{abbr}$', f'_{abbr.lower()}', result)
        result = re.sub(rf'{abbr}([A-Z])', rf'_{abbr.lower()}_\1', result)

    # Insert underscore before uppercase letters that follow lowercase
    result = re.sub(r'([a-z])([A-Z])', r'\1_\2', result)

    # Insert underscore before numbers that follow letters
    result = re.sub(r'([a-zA-Z])(\d)', r'\1_\2', result)

    # Insert underscore after numbers that are followed by letters
    result = re.sub(r'(\d)([a-zA-Z])', r'\1_\2', result)

    # Convert to lowercase
    result = result.lower()

    # Clean up any double underscores
    result = re.sub(r'_+', '_', result)

    # Remove leading/trailing underscores
    result = result.strip('_')

    return result


def convert_meta_file(meta_path: Path) -> dict:
    """Convert a DBCTool meta.json file to snake_case."""
    with open(meta_path) as f:
        meta = json.load(f)

    # Convert field names
    if 'fields' in meta:
        for field in meta['fields']:
            if 'name' in field:
                field['name'] = to_snake_case(field['name'])

    # Convert primary keys
    if 'primaryKeys' in meta:
        meta['primaryKeys'] = [to_snake_case(k) for k in meta['primaryKeys']]

    # Convert unique keys
    if 'uniqueKeys' in meta:
        meta['uniqueKeys'] = [[to_snake_case(k) for k in uk] for uk in meta['uniqueKeys']]

    # Convert sort order
    if 'sortOrder' in meta:
        for sort in meta['sortOrder']:
            if 'name' in sort:
                sort['name'] = to_snake_case(sort['name'])

    return meta


def convert_binding_file(binding_path: Path) -> str:
    """Convert a WoW Spell Editor binding file to snake_case."""
    with open(binding_path) as f:
        lines = f.readlines()

    converted_lines = []
    for line in lines:
        # Preserve comments and empty lines
        if line.startswith('#') or not line.strip():
            converted_lines.append(line)
            continue

        parts = line.split()
        if len(parts) >= 2:
            # Format: type fieldName [string]
            field_type = parts[0]
            field_name = parts[1]
            rest = parts[2:] if len(parts) > 2 else []

            converted_name = to_snake_case(field_name)

            if rest:
                converted_lines.append(f"{field_type} {converted_name} {' '.join(rest)}\n")
            else:
                converted_lines.append(f"{field_type} {converted_name}\n")
        else:
            converted_lines.append(line)

    return ''.join(converted_lines)


def convert_binding_loc_suffixes(content: str) -> str:
    """Convert locale-numbered fields in bindings to language code suffixes.

    Detects 16-field locale groups (base_0..base_15 or base_1..base_16)
    followed by a flags field, and rewrites them with language code suffixes
    matching DBCTool's Loc type expansion.

    Language code order (matching DBCTool locLangs):
        0: enus, 1: kokr, 2: frfr, 3: dede, 4: zhcn, 5: zhtw,
        6: eses, 7: esmx, 8: ruru, 9: jajp, 10: ptpt, 11: itit,
        12: unused_1, 13: unused_2, 14: unused_3, 15: unused_4
        flags field keeps _flags suffix
    """
    LOC_LANGS = [
        'enus', 'kokr', 'frfr', 'dede', 'zhcn', 'zhtw',
        'eses', 'esmx', 'ruru', 'jajp', 'ptpt', 'itit',
        'unused_1', 'unused_2', 'unused_3', 'unused_4',
    ]

    lines = content.split('\n')

    # Parse all field lines with their indices
    field_entries = []  # (line_index, field_type, field_name, is_string, rest)
    for idx, line in enumerate(lines):
        if line.startswith('#') or not line.strip():
            continue
        parts = line.split()
        if len(parts) >= 2:
            ftype = parts[0]
            fname = parts[1]
            rest = parts[2:] if len(parts) > 2 else []
            is_string = 'string' in rest
            field_entries.append((idx, ftype, fname, is_string, rest))

    # Find locale groups
    replacements = {}  # line_index -> new_line

    i = 0
    while i < len(field_entries):
        idx, ftype, fname, is_string, rest = field_entries[i]

        if not is_string:
            i += 1
            continue

        # Try to match {base}_{num}
        m = re.match(r'^(.+?)_(\d+)$', fname)
        if not m:
            i += 1
            continue

        base = m.group(1)
        start_num = int(m.group(2))

        if start_num not in (0, 1):
            i += 1
            continue

        # Check for 16 consecutive string fields
        found = True
        for j in range(16):
            entry_idx = i + j
            if entry_idx >= len(field_entries):
                found = False
                break
            _, _, ename, eis_string, _ = field_entries[entry_idx]
            expected = f"{base}_{start_num + j}"
            if ename != expected or not eis_string:
                found = False
                break

        if not found:
            i += 1
            continue

        # Check for flags field after the 16 strings
        has_flags = False
        flags_entry_idx = i + 16
        if flags_entry_idx < len(field_entries):
            _, _, flags_name, _, _ = field_entries[flags_entry_idx]
            if flags_name.endswith('_flags') or flags_name.endswith('_flag'):
                has_flags = True

        # Apply replacements
        for j in range(16):
            entry_idx = i + j
            line_idx, ft, fn, _, r = field_entries[entry_idx]
            new_name = f"{base}_{LOC_LANGS[j]}"
            if r:
                replacements[line_idx] = f"{ft} {new_name} {' '.join(r)}"
            else:
                replacements[line_idx] = f"{ft} {new_name}"

        if has_flags:
            line_idx, ft, fn, _, r = field_entries[flags_entry_idx]
            new_name = f"{base}_flags"
            if r:
                replacements[line_idx] = f"{ft} {new_name} {' '.join(r)}"
            else:
                replacements[line_idx] = f"{ft} {new_name}"
            i += 17
        else:
            i += 16

        continue

    # Apply replacements
    new_lines = []
    for idx, line in enumerate(lines):
        if idx in replacements:
            new_lines.append(replacements[idx])
        else:
            new_lines.append(line)

    return '\n'.join(new_lines)


def main():
    script_dir = Path(__file__).parent

    # Process meta files
    meta_dirs = [
        script_dir / 'meta',
        script_dir / 'spelleditor_meta',
    ]

    print("=" * 60)
    print("Phase 1: Converting DBCTool meta files to snake_case")
    print("=" * 60)

    for meta_dir in meta_dirs:
        if not meta_dir.exists():
            print(f"Skipping {meta_dir} (not found)")
            continue

        print(f"\nProcessing {meta_dir.name}/")

        for meta_file in sorted(meta_dir.glob('*.meta.json')):
            try:
                converted = convert_meta_file(meta_file)

                with open(meta_file, 'w') as f:
                    json.dump(converted, f, indent=2)
                    f.write('\n')

                print(f"  ✓ {meta_file.name}")
            except Exception as e:
                print(f"  ✗ {meta_file.name}: {e}")

    # Process WoW Spell Editor bindings
    bindings_dir = script_dir.parent / 'WoW Spell Editor' / 'Bindings_335_wotlk'

    print("\n" + "=" * 60)
    print("Phase 2: Converting WoW Spell Editor bindings to snake_case")
    print("=" * 60)

    if bindings_dir.exists():
        print(f"\nProcessing {bindings_dir}/")

        for binding_file in sorted(bindings_dir.glob('*.txt')):
            try:
                converted = convert_binding_file(binding_file)

                with open(binding_file, 'w') as f:
                    f.write(converted)

                print(f"  ✓ {binding_file.name}")
            except Exception as e:
                print(f"  ✗ {binding_file.name}: {e}")
    else:
        print(f"Bindings directory not found: {bindings_dir}")

    # Phase 3: Convert locale-numbered fields to language code suffixes in bindings
    print("\n" + "=" * 60)
    print("Phase 3: Converting binding locale fields to language code suffixes")
    print("=" * 60)

    if bindings_dir.exists():
        print(f"\nProcessing {bindings_dir}/")

        for binding_file in sorted(bindings_dir.glob('*.txt')):
            try:
                with open(binding_file) as f:
                    content = f.read()

                converted = convert_binding_loc_suffixes(content)

                if converted != content:
                    with open(binding_file, 'w') as f:
                        f.write(converted)
                    print(f"  ✓ {binding_file.name} (locale suffixes updated)")
                else:
                    print(f"  - {binding_file.name} (no locale fields)")
            except Exception as e:
                print(f"  ✗ {binding_file.name}: {e}")

    print("\n" + "=" * 60)
    print("Conversion complete!")
    print("=" * 60)
    print("\nNext steps:")
    print("1. Run 'zep dbc init-original --force' to rebuild original_dbc")
    print("2. Run 'zep dbc rebuild' to rebuild dbc and expected_dbc")
    print("3. Apply customization SQL files")


if __name__ == '__main__':
    main()
