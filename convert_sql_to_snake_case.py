#!/usr/bin/env python3
"""
Convert DBC SQL files to use snake_case column names.

Builds column name mappings from historical data and applies them to SQL files.
"""

import json
import re
import os
from pathlib import Path
from typing import Dict, Set


# Historical column name mappings (old -> new snake_case)
# Built from analysis of existing SQL files and meta file changes
COLUMN_MAPPINGS = {
    # Achievement
    'ID': 'id',
    'requiredFaction': 'required_faction',
    'mapId': 'map_id',
    'parentAchievement': 'parent_achievement',
    'flags': 'flags',
    'count': 'count',
    'refAchievement': 'ref_achievement',

    # Spell - comprehensive mapping
    'Category': 'category',
    'Dispel': 'dispel',
    'Mechanic': 'mechanic',
    'Attributes': 'attributes',
    'AttributesEx': 'attributes_ex',
    'AttributesEx2': 'attributes_ex_2',
    'AttributesEx3': 'attributes_ex_3',
    'AttributesEx4': 'attributes_ex_4',
    'AttributesEx5': 'attributes_ex_5',
    'AttributesEx6': 'attributes_ex_6',
    'AttributesEx7': 'attributes_ex_7',
    'Stances': 'stances',
    'StancesNot': 'stances_not',
    'Targets': 'targets',
    'TargetCreatureType': 'target_creature_type',
    'RequiresSpellFocus': 'requires_spell_focus',
    'FacingCasterFlags': 'facing_caster_flags',
    'CasterAuraState': 'caster_aura_state',
    'TargetAuraState': 'target_aura_state',
    'CasterAuraStateNot': 'caster_aura_state_not',
    'TargetAuraStateNot': 'target_aura_state_not',
    'CasterAuraSpell': 'caster_aura_spell',
    'TargetAuraSpell': 'target_aura_spell',
    'ExcludeCasterAuraSpell': 'exclude_caster_aura_spell',
    'ExcludeTargetAuraSpell': 'exclude_target_aura_spell',
    'CastingTimeIndex': 'casting_time_index',
    'RecoveryTime': 'recovery_time',
    'CategoryRecoveryTime': 'category_recovery_time',
    'InterruptFlags': 'interrupt_flags',
    'AuraInterruptFlags': 'aura_interrupt_flags',
    'ChannelInterruptFlags': 'channel_interrupt_flags',
    'ProcFlags': 'proc_flags',
    'ProcChance': 'proc_chance',
    'ProcCharges': 'proc_charges',
    'MaximumLevel': 'maximum_level',
    'BaseLevel': 'base_level',
    'SpellLevel': 'spell_level',
    'DurationIndex': 'duration_index',
    'PowerType': 'power_type',
    'ManaCost': 'mana_cost',
    'ManaCostPerLevel': 'mana_cost_per_level',
    'ManaPerSecond': 'mana_per_second',
    'ManaPerSecondPerLevel': 'mana_per_second_per_level',
    'RangeIndex': 'range_index',
    'Speed': 'speed',
    'ModalNextSpell': 'modal_next_spell',
    'StackAmount': 'stack_amount',
    'EquippedItemClass': 'equipped_item_class',
    'EquippedItemSubClassMask': 'equipped_item_sub_class_mask',
    'EquippedItemInventoryTypeMask': 'equipped_item_inventory_type_mask',
    'SpellVisual1': 'spell_visual_1',
    'SpellVisual2': 'spell_visual_2',
    'SpellIconID': 'spell_icon_id',
    'ActiveIconID': 'active_icon_id',
    'SpellPriority': 'spell_priority',
    'ManaCostPercentage': 'mana_cost_percentage',
    'StartRecoveryCategory': 'start_recovery_category',
    'StartRecoveryTime': 'start_recovery_time',
    'MaximumTargetLevel': 'maximum_target_level',
    'SpellFamilyName': 'spell_family_name',
    'SpellFamilyFlags': 'spell_family_flags',
    'SpellFamilyFlags1': 'spell_family_flags_1',
    'SpellFamilyFlags2': 'spell_family_flags_2',
    'MaximumAffectedTargets': 'maximum_affected_targets',
    'DamageClass': 'damage_class',
    'PreventionType': 'prevention_type',
    'StanceBarOrder': 'stance_bar_order',
    'MinimumFactionId': 'minimum_faction_id',
    'MinimumReputation': 'minimum_reputation',
    'RequiredAuraVision': 'required_aura_vision',
    'TotemCategory1': 'totem_category_1',
    'TotemCategory2': 'totem_category_2',
    'AreaGroupID': 'area_group_id',
    'SchoolMask': 'school_mask',
    'RuneCostID': 'run_cost_id',
    'SpellMissileID': 'spell_missile_id',
    'PowerDisplayId': 'power_display_id',
    'SpellDescriptionVariableID': 'spell_description_variable_id',
    'SpellDifficultyID': 'spell_difficulty_id',

    # CreatureFamily
    'minScale': 'min_scale',
    'minScaleLevel': 'min_scale_level',
    'maxScale': 'max_scale',
    'maxScaleLevel': 'max_scale_level',
    'petfoodmask': 'petfoodmask',
    'pettalenttype': 'pettalenttype',
    'categoryenumid': 'categoryenumid',
    'nameFlags': 'name_flags',
    'iconpath': 'iconpath',
    'skillline_1': 'skillline_1',
    'skillline_2': 'skillline_2',
    'skill_line_1': 'skill_line_1',
    'skill_line_2': 'skill_line_2',

    # Map
    'DirectoryName': 'directory',
    'directory': 'directory',
    'InstanceType': 'instance_type',
    'instance_type': 'instance_type',
    'PVP': 'pvp',
    'Flags': 'flags',
    'AreaTableID': 'area_table_id',
    'area_table_id': 'area_table_id',
    'MapDescription0_Lang_enUS': 'map_description_0_enus',
    'MapDescription1_Lang_enUS': 'map_description_1_enus',
    'LoadingScreenID': 'loading_screen_id',
    'MinimapIconScale': 'minimap_icon_scale',
    'CorpseMapID': 'corpse_map_id',
    'TimeOfDayOverride': 'time_of_day_override',
    'ExpansionID': 'expansion_id',
    'RaidOffset': 'raid_offset',
    'MaxPlayers': 'max_players',

    # MapDifficulty
    'map_id': 'map_id',
    'difficulty': 'difficulty',
    'message_flags': 'message_flags',
    'lockout_duration': 'lockout_duration',
    'max_players': 'max_players',
    'difficulty_string': 'difficulty_string',

    # TalentTab
    'iconId': 'spell_icon',
    'spell_icon': 'spell_icon',
    'raceMask': 'race_mask',
    'race_mask': 'race_mask',

    # CharStartOutfit
    'race': 'race',
    'class': 'class',
    'gender': 'gender',
    'outfitId': 'outfit_id',

    # ItemSubClass
    'Class': 'class',
    'subClass': 'sub_class',
    'prerequisiteProficiency': 'prerequisite_proficiency',
    'postrequisiteProficiency': 'postrequisite_proficiency',
    'displayFlags': 'display_flags',
    'weaponParrySeq': 'weapon_parry_seq',
    'weaponReadySeq': 'weapon_ready_seq',
    'weaponAttackSeq': 'weapon_attack_seq',
    'displayName1': 'display_name_1',
    'displayNameFlag': 'display_name_flag',
    'verboseNameFlag': 'verbose_name_flag',

    # ItemExtendedCost
    'honor_points': 'honor_points',
    'arena_points': 'arena_points',

    # CurrencyTypes
    'item': 'item',
    'category': 'category',
    'bit_index': 'bit_index',

    # SkillLine
    'costId': 'cost_id',

    # Generic patterns
    'Unknown1': 'unknown_1',
    'Unknown2': 'unknown_2',
}

# Generate numbered column patterns
for i in range(1, 20):
    # Spell effects, reagents, totems
    COLUMN_MAPPINGS[f'Effect{i}'] = f'effect_{i}'
    COLUMN_MAPPINGS[f'EffectDieSides{i}'] = f'effect_die_sides_{i}'
    COLUMN_MAPPINGS[f'EffectRealPointsPerLevel{i}'] = f'effect_real_points_per_level_{i}'
    COLUMN_MAPPINGS[f'EffectBasePoints{i}'] = f'effect_base_points_{i}'
    COLUMN_MAPPINGS[f'EffectMechanic{i}'] = f'effect_mechanic_{i}'
    COLUMN_MAPPINGS[f'EffectImplicitTargetA{i}'] = f'effect_implicit_target_a_{i}'
    COLUMN_MAPPINGS[f'EffectImplicitTargetB{i}'] = f'effect_implicit_target_b_{i}'
    COLUMN_MAPPINGS[f'EffectRadiusIndex{i}'] = f'effect_radius_index_{i}'
    COLUMN_MAPPINGS[f'EffectApplyAuraName{i}'] = f'effect_apply_aura_name_{i}'
    COLUMN_MAPPINGS[f'EffectAmplitude{i}'] = f'effect_amplitude_{i}'
    COLUMN_MAPPINGS[f'EffectMultipleValue{i}'] = f'effect_multiple_value_{i}'
    COLUMN_MAPPINGS[f'EffectChainTarget{i}'] = f'effect_chain_target_{i}'
    COLUMN_MAPPINGS[f'EffectItemType{i}'] = f'effect_item_type_{i}'
    COLUMN_MAPPINGS[f'EffectMiscValue{i}'] = f'effect_misc_value_{i}'
    COLUMN_MAPPINGS[f'EffectMiscValueB{i}'] = f'effect_misc_value_b_{i}'
    COLUMN_MAPPINGS[f'EffectTriggerSpell{i}'] = f'effect_trigger_spell_{i}'
    COLUMN_MAPPINGS[f'EffectPointsPerComboPoint{i}'] = f'effect_points_per_combo_point_{i}'
    COLUMN_MAPPINGS[f'EffectSpellClassMaskA{i}'] = f'effect_spell_class_mask_a_{i}'
    COLUMN_MAPPINGS[f'EffectSpellClassMaskB{i}'] = f'effect_spell_class_mask_b_{i}'
    COLUMN_MAPPINGS[f'EffectSpellClassMaskC{i}'] = f'effect_spell_class_mask_c_{i}'
    COLUMN_MAPPINGS[f'EffectDamageMultiplier{i}'] = f'effect_damage_multiplier_{i}'
    COLUMN_MAPPINGS[f'EffectBonusMultiplier{i}'] = f'effect_bonus_multiplier_{i}'
    COLUMN_MAPPINGS[f'Reagent{i}'] = f'reagent_{i}'
    COLUMN_MAPPINGS[f'ReagentCount{i}'] = f'reagent_count_{i}'
    COLUMN_MAPPINGS[f'Totem{i}'] = f'totem_{i}'

    # Spell name/rank/description localization
    COLUMN_MAPPINGS[f'SpellName{i}'] = f'spell_name_{i}'
    COLUMN_MAPPINGS[f'SpellNameFlag{i}'] = f'spell_name_flag_{i}'
    COLUMN_MAPPINGS[f'SpellRank{i}'] = f'spell_rank_{i}'
    COLUMN_MAPPINGS[f'SpellRankFlags{i}'] = f'spell_rank_flags_{i}'
    COLUMN_MAPPINGS[f'SpellDescription{i}'] = f'spell_description_{i}'
    COLUMN_MAPPINGS[f'SpellDescriptionFlags{i}'] = f'spell_description_flags_{i}'
    COLUMN_MAPPINGS[f'SpellToolTip{i}'] = f'spell_tool_tip_{i}'
    COLUMN_MAPPINGS[f'SpellToolTipFlags{i}'] = f'spell_tool_tip_flags_{i}'

    # Generic name patterns
    COLUMN_MAPPINGS[f'Name{i}'] = f'name_{i}'
    COLUMN_MAPPINGS[f'name{i}'] = f'name_{i}'

    # CharStartOutfit item patterns
    COLUMN_MAPPINGS[f'itemId{i}'] = f'item_id_{i}'
    COLUMN_MAPPINGS[f'displayInfo{i}'] = f'display_info_{i}'
    COLUMN_MAPPINGS[f'invType{i}'] = f'inv_type_{i}'

# Special handling for 0-indexed names (SpellName0, etc.)
for i in range(17):  # 0-16 for localization
    COLUMN_MAPPINGS[f'SpellName{i}'] = f'spell_name_{i}'
    COLUMN_MAPPINGS[f'SpellRank{i}'] = f'spell_rank_{i}'
    COLUMN_MAPPINGS[f'SpellDescription{i}'] = f'spell_description_{i}'
    COLUMN_MAPPINGS[f'SpellToolTip{i}'] = f'spell_tool_tip_{i}'
    COLUMN_MAPPINGS[f'Description{i}'] = f'description_{i}'


def load_meta_mappings(meta_dir: Path) -> Dict[str, Dict[str, str]]:
    """Load column mappings from meta files.

    Returns dict of table_name -> {old_name: new_name}
    """
    mappings = {}

    for meta_file in meta_dir.glob('*.meta.json'):
        try:
            with open(meta_file) as f:
                meta = json.load(f)

            table_name = meta.get('tableName', meta_file.stem)

            # Build mapping from field names
            for field in meta.get('fields', []):
                name = field.get('name', '')
                # The meta files are already converted to snake_case,
                # so we can use them as targets
                mappings.setdefault(table_name, {})[name] = name

        except Exception as e:
            print(f"Warning: Could not load {meta_file}: {e}")

    return mappings


def convert_sql_column_names(sql: str, mappings: Dict[str, str] = None) -> str:
    """Convert column names in SQL to snake_case.

    Args:
        sql: SQL string to convert
        mappings: Optional additional mappings

    Returns:
        Converted SQL string
    """
    if mappings is None:
        mappings = COLUMN_MAPPINGS
    else:
        mappings = {**COLUMN_MAPPINGS, **mappings}

    result = sql

    # Sort by length (longest first) to avoid partial replacements
    sorted_mappings = sorted(mappings.items(), key=lambda x: -len(x[0]))

    for old_name, new_name in sorted_mappings:
        if old_name == new_name:
            continue

        # Replace in backtick-quoted identifiers
        result = re.sub(
            rf'`{re.escape(old_name)}`',
            f'`{new_name}`',
            result,
            flags=re.IGNORECASE
        )

        # Replace as bare identifiers (word boundaries)
        # But be careful not to replace in string literals
        result = re.sub(
            rf"(?<!['\"`a-zA-Z0-9_]){re.escape(old_name)}(?!['\"`a-zA-Z0-9_])",
            new_name,
            result
        )

    return result


def convert_sql_file(input_path: Path, output_path: Path = None) -> bool:
    """Convert a SQL file to use snake_case column names.

    Args:
        input_path: Path to input SQL file
        output_path: Path to output file (default: same as input)

    Returns:
        True if file was modified
    """
    if output_path is None:
        output_path = input_path

    with open(input_path) as f:
        original = f.read()

    converted = convert_sql_column_names(original)

    if converted != original or output_path != input_path:
        with open(output_path, 'w') as f:
            f.write(converted)
        return True

    return False


def main():
    script_dir = Path(__file__).parent
    craft_root = Path('/workspace/project/Zeppelin-Craft')

    # Directories to process
    directories = [
        craft_root / 'Scripts' / 'Patch Builder' / 'Updates',
        craft_root / 'zpaks' / 'worgoblin' / 'dbc',
        craft_root / 'zpaks' / 'clan-centaur' / 'dbc',
        craft_root / 'zpaks' / 'hd-creatures-mounts' / 'dbc',
    ]

    print("=" * 60)
    print("Converting SQL files to snake_case column names")
    print("=" * 60)

    for directory in directories:
        if not directory.exists():
            print(f"\nSkipping {directory} (not found)")
            continue

        print(f"\nProcessing {directory}/")

        for sql_file in sorted(directory.glob('*.sql')):
            # Skip _fixed files (will overwrite originals)
            if '_fixed' in sql_file.name:
                continue

            try:
                modified = convert_sql_file(sql_file)
                status = "converted" if modified else "unchanged"
                print(f"  {sql_file.name}: {status}")
            except Exception as e:
                print(f"  {sql_file.name}: ERROR - {e}")

    print("\n" + "=" * 60)
    print("Conversion complete!")
    print("=" * 60)


if __name__ == '__main__':
    main()
