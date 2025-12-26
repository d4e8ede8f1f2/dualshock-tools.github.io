#!/usr/bin/env python3

# (C) 2025 dualshock-tools
#
# This script analyzes the source files to find translation strings and compares
# them with the language files to identify:
# - Strings that are used in code but missing from translation files
# - Strings that are in translation files but no longer used in code
#
# The script extracts translation strings from:
# - HTML files: elements with ds-i18n class
# - JavaScript files: l() function calls
# - JavaScript files: HTML embedded in strings with ds-i18n class
#
# The script automatically ignores commented-out code:
# - HTML comments (<!-- ... -->)
# - JavaScript single-line comments (// ...)
# - JavaScript multi-line comments (/* ... */)
#
# Usage:
#   python3 scripts/check_translations.py           # Normal output
#   python3 scripts/check_translations.py --verbose # Show excluded strings
#   python3 scripts/check_translations.py --compact # Compact output (no language details)
#   python3 scripts/check_translations.py --json    # Output in JSON format
#   python3 scripts/check_translations.py --export-base  # Export found strings to lang/base.json

import os
import re
import json
import sys
from pathlib import Path

# Check for flags
VERBOSE = '--verbose' in sys.argv or '-v' in sys.argv
JSON_OUTPUT = '--json' in sys.argv
COMPACT = '--compact' in sys.argv
EXPORT_BASE = '--export-base' in sys.argv or '-e' in sys.argv

# Directories to scan
ROOT_DIR = Path(".")
LANG_DIR = ROOT_DIR / "lang"
JS_DIR = ROOT_DIR / "js"
TEMPLATES_DIR = ROOT_DIR / "templates"

# Special keys that are not in source code
SPECIAL_KEYS = {".authorMsg", ".title"}

# Patterns to exclude from translation checks (CSS selectors, technical strings, etc.)
EXCLUDE_PATTERNS = [
    r'^\.[\w-]+$',  # CSS class selectors like .alert, .hide
    r'^#[\w-]+$',  # CSS ID selectors
    r'^[\w-]+\.[\w-]+$',  # CSS compound selectors like circle.ds-touch
    r'^path,rect,circle',  # SVG element lists
    r'^\\x[0-9a-fA-F]+$',  # Hex escape sequences
]

# Whitelist of strings that are in language files but should be ignored by unused check
# These strings may be used dynamically, in comments, or reserved for future use
WHITELIST_UNUSED = {
    "(beta)",
    "30th Anniversary",
    "Astro Bot",
    "Chroma Indigo",
    "Chroma Pearl",
    "Chroma Teal",
    "Cobalt Blue",
    "Cosmic Red",
    "Fortnite",
    "Galactic Purple",
    "God of War Ragnarok",
    "Grey Camouflage",
    "Midnight Black",
    "Nova Pink",
    "Spider-Man 2",
    "Starlight Blue",
    "Sterling Silver",
    "The Last of Us",
    "Volcanic Red",
    "White",

    "Sony DualSense",
    "Sony DualSense Edge",
    "Sony DualShock 4 V1",
    "Sony DualShock 4 V2",

    "Calibration in progress",
    "Continue",
    "Start",
    "Initializing...",
    "Sampling...",
    "left module",
    "right module",
    "Your device might not be a genuine Sony controller. If it is not a clone then please report this issue.",

    "Adaptive Trigger",
    "Buttons",
    "Haptic Vibration",
    "Headphone Jack",
    "Lights",
    "Microphone",
    "Speaker",
    "USB Connector",
}

def export_to_base_json(used_strings):
    """Export all found strings to lang/base.json in specified format."""
    base_file = LANG_DIR / "base.json"

    # Read existing base.json if it exists
    existing_data = {}
    if base_file.exists():
        try:
            with open(base_file, 'r', encoding='utf-8') as f:
                existing_data = json.load(f)
        except Exception as e:
            print(f"Error reading {base_file}: {e}")
            existing_data = {}

    # Create new data structure with special keys first, then used strings
    new_data = {}

    # Add special keys first
    for key in sorted(SPECIAL_KEYS):
        new_data[key] = existing_data.get(key, "")

    # Add all used strings (sorted alphabetically)
    for string in sorted(used_strings):
        new_data[string] = existing_data.get(string, "")

    # Add empty key at the end (for compatibility with existing format)
    new_data[""] = existing_data.get("", "")

    # Write to file
    try:
        with open(base_file, 'w', encoding='utf-8') as f:
            json.dump(new_data, f, indent=2, ensure_ascii=False)
        print(f"✅ Exported {len(used_strings)} strings + {len(SPECIAL_KEYS)} special keys to {base_file}")
        print(f"   Total keys in file: {len(new_data)} (including empty key)")

        # Show added strings
        added_count = 0
        for key in new_data:
            if key not in existing_data and key != "":
                added_count += 1
                if VERBOSE:
                    print(f"   + Added: \"{key}\"")

        if added_count > 0 and not VERBOSE:
            print(f"   Added {added_count} new strings")

    except Exception as e:
        print(f"Error writing {base_file}: {e}")
        return False

    return True

def should_exclude_string(text):
    """Check if a string should be excluded from translation checks."""
    for pattern in EXCLUDE_PATTERNS:
        if re.match(pattern, text):
            return True
    return False

def find_html_files():
    """Find all HTML files in the project."""
    html_files = []
    # Root HTML files
    html_files.extend(ROOT_DIR.glob("*.html"))
    # Template HTML files
    html_files.extend(TEMPLATES_DIR.glob("*.html"))
    return html_files

def find_js_files():
    """Find all JavaScript files in the js directory."""
    js_files = []
    js_files.extend(JS_DIR.glob("**/*.js"))
    return js_files

def extract_ds_i18n_strings(html_files):
    """Extract strings from elements with ds-i18n class in HTML files.
    Automatically ignores HTML comments (<!-- ... -->) before extraction.
    """
    strings = {}
    pattern = r'<(\w+)[^>]*class="[^"]*ds-i18n[^"]*"[^>]*>(.*?)</\1>'

    for html_file in html_files:
        try:
            with open(html_file, 'r', encoding='utf-8') as f:
                content = f.read()

                # Remove HTML comments before processing
                content = re.sub(r'<!--.*?-->', '', content, flags=re.DOTALL)

                # Find all matches
                matches = re.finditer(pattern, content, re.DOTALL)
                for match in matches:
                    text = match.group(2)

                    # Skip if contains complex nested HTML tags
                    if '<' in text and '>' in text:
                        text_without_simple_tags = re.sub(r'</?(?:b|i|em|strong|span)>', '', text)
                        if '<' in text_without_simple_tags:
                            continue

                    if text:
                        line_num = content[:match.start()].count('\n') + 1
                        col_num = match.start() - content[:match.start()].rfind('\n')
                        
                        if text not in strings:
                            strings[text] = []
                        strings[text].append({
                            'file': str(html_file),
                            'line': line_num,
                            'col': col_num
                        })
        except Exception as e:
            print(f"Error reading {html_file}: {e}")

    return strings

def extract_l_function_strings(js_files):
    """Extract strings passed to l() function in JavaScript files.
    Automatically ignores JavaScript comments (// and /* ... */) before extraction.
    """
    strings = {}
    pattern = r'''(?:this\.)?\bl\s*\(\s*(["'`])((?:\\.|[^\\])*?)(?<!\\)\1\s*\)'''

    for js_file in js_files:
        try:
            with open(js_file, 'r', encoding='utf-8') as f:
                content = f.read()

                # Remove JavaScript comments before processing
                content = re.sub(r'//.*?$', '', content, flags=re.MULTILINE)
                content = re.sub(r'/\*.*?\*/', '', content, flags=re.DOTALL)

                # Find all matches
                matches = re.finditer(pattern, content, re.DOTALL)
                for match in matches:
                    text = match.group(2)
                    if text:
                        text = text.replace("\\'", "'").replace('\\"', '"').replace('\\\\', '\\')

                        line_num = content[:match.start()].count('\n') + 1
                        col_num = match.start() - content[:match.start()].rfind('\n')

                        if text not in strings:
                            strings[text] = []
                        strings[text].append({
                            'file': str(js_file),
                            'line': line_num,
                            'col': col_num
                        })
        except Exception as e:
            print(f"Error reading {js_file}: {e}")

    return strings

def extract_html_strings_from_js(js_files):
    """Extract strings from HTML embedded in JavaScript files.
    This function looks for HTML strings in JavaScript that contain elements with ds-i18n class.
    Automatically ignores JavaScript comments (// and /* ... */) before extraction.
    """
    strings = {}
    pattern = r'<(\w+)[^>]*class=["\'`][^"\'`]*ds-i18n[^"\'`]*["\'`][^>]*>(.*?)</\1>'
    template_literal_pattern = r'''\$\{l\s*\(\s*(["'`])((?:\\.|[^\\])*?)(?<!\\)\1\s*\)\}'''

    for js_file in js_files:
        try:
            with open(js_file, 'r', encoding='utf-8') as f:
                content = f.read()
                original_content = content

                # Remove JavaScript comments before processing
                content = re.sub(r'//.*?$', '', content, flags=re.MULTILINE)
                content = re.sub(r'/\*.*?\*/', '', content, flags=re.DOTALL)

                # Find all matches
                matches = re.finditer(pattern, content, re.DOTALL)
                for match in matches:
                    text = match.group(2)

                    if '<' in text and '>' in text:
                        text_without_simple_tags = re.sub(r'</?(?:b|i|em|strong|span)>', '', text)
                        if '<' in text_without_simple_tags:
                            continue

                    if text:
                        # Extract template literal function calls
                        template_matches = re.finditer(template_literal_pattern, text, re.DOTALL)
                        for template_match in template_matches:
                            extracted_string = template_match.group(2)
                            if extracted_string:
                                extracted_string = extracted_string.replace("\\'", "'").replace('\\"', '"').replace('\\\\', '\\')
                                line_num = original_content[:match.start()].count('\n') + 1
                                col_num = match.start() - original_content[:match.start()].rfind('\n')

                                if extracted_string not in strings:
                                    strings[extracted_string] = []
                                strings[extracted_string].append({
                                    'file': str(js_file),
                                    'line': line_num,
                                    'col': col_num
                                })

                        # Handle non-template literal strings
                        if not re.search(template_literal_pattern, text, re.DOTALL):
                            line_num = original_content[:match.start()].count('\n') + 1
                            col_num = match.start() - original_content[:match.start()].rfind('\n')
                            
                            if text not in strings:
                                strings[text] = []
                            strings[text].append({
                                'file': str(js_file),
                                'line': line_num,
                                'col': col_num
                            })
        except Exception as e:
            print(f"Error reading {js_file}: {e}")

    return strings

def load_translation_keys():
    """Load all translation keys from language files."""
    all_keys = set()
    keys_by_language = {}
    lang_files = list(LANG_DIR.glob("*.json"))

    if not lang_files:
        print(f"Warning: No language files found in {LANG_DIR}")
        return all_keys, keys_by_language

    # Load keys from all language files
    for lang_file in lang_files:
        try:
            lang_code = lang_file.stem

            with open(lang_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                keys = set(data.keys())
                keys.discard("")

                keys_by_language[lang_code] = keys
                all_keys.update(keys)
        except Exception as e:
            print(f"Error reading {lang_file}: {e}")

    all_keys.discard("")
    return all_keys, keys_by_language

def main():
    if not JSON_OUTPUT:
        print("=" * 80)
        print("Translation String Checker")
        print("=" * 80)
        print()

    # Find all source files
    if not JSON_OUTPUT:
        print("Scanning source files...")
    html_files = find_html_files()
    js_files = find_js_files()

    if not JSON_OUTPUT:
        print(f"Found {len(html_files)} HTML files")
        print(f"Found {len(js_files)} JavaScript files")
        print()

    # Extract strings from source files
    if not JSON_OUTPUT:
        print("Extracting translation strings from source files...")
    ds_i18n_strings = extract_ds_i18n_strings(html_files)
    l_function_strings = extract_l_function_strings(js_files)
    html_in_js_strings = extract_html_strings_from_js(js_files)

    if not JSON_OUTPUT:
        print(f"Found {len(ds_i18n_strings)} strings with ds-i18n class in HTML files")
        print(f"Found {len(l_function_strings)} strings in l() function calls")
        print(f"Found {len(html_in_js_strings)} strings with ds-i18n class in JavaScript files")
        print()

    # Combine all used strings and filter out excluded patterns
    all_used_strings_with_locations = {}
    for text, locations in ds_i18n_strings.items():
        all_used_strings_with_locations[text] = locations.copy()
    for text, locations in l_function_strings.items():
        if text in all_used_strings_with_locations:
            all_used_strings_with_locations[text].extend(locations)
        else:
            all_used_strings_with_locations[text] = locations.copy()
    for text, locations in html_in_js_strings.items():
        if text in all_used_strings_with_locations:
            all_used_strings_with_locations[text].extend(locations)
        else:
            all_used_strings_with_locations[text] = locations.copy()

    excluded_strings = {s for s in all_used_strings_with_locations.keys() if should_exclude_string(s)}
    used_strings_with_locations = {k: v for k, v in all_used_strings_with_locations.items() if k not in excluded_strings}
    used_strings = set(used_strings_with_locations.keys())

    if not JSON_OUTPUT and excluded_strings:
        print(f"Excluded {len(excluded_strings)} non-translatable strings (CSS selectors, etc.)")
        if VERBOSE:
            for s in sorted(excluded_strings):
                print(f"  - \"{s}\"")
        print()

    # Check if we need to export to base.json
    if EXPORT_BASE:
        success = export_to_base_json(used_strings)
        return 0 if success else 1

    # Load translation keys
    if not JSON_OUTPUT:
        print("Loading translation keys from language files...")
    translation_keys, keys_by_language = load_translation_keys()
    if not JSON_OUTPUT:
        print(f"Found {len(translation_keys)} keys in translation files")
        print(f"Found {len(keys_by_language)} language files")
        print()

    # Remove special keys from comparison
    translation_keys_for_comparison = translation_keys - SPECIAL_KEYS

    # Remove special keys from each language's key set
    keys_by_language_filtered = {}
    for lang_code, keys in keys_by_language.items():
        keys_by_language_filtered[lang_code] = keys - SPECIAL_KEYS

    # Find missing translations (used in code but not in translation files)
    missing_translations = used_strings - translation_keys_for_comparison

    # For each missing translation, find which languages are missing it
    missing_by_language = {}
    for string in missing_translations:
        missing_langs = []
        for lang_code, keys in keys_by_language_filtered.items():
            if string not in keys:
                missing_langs.append(lang_code)
        missing_by_language[string] = sorted(missing_langs)

    # Find unused translations (in translation files but not used in code)
    unused_translations = (translation_keys_for_comparison - used_strings) - WHITELIST_UNUSED

    # Output results
    if JSON_OUTPUT:
        missing_with_locations = []
        for string in sorted(missing_translations):
            entry = {
                "string": string,
                "missing_from_languages": missing_by_language.get(string, [])
            }
            if string in used_strings_with_locations:
                entry["locations"] = used_strings_with_locations[string]
            missing_with_locations.append(entry)

        result = {
            "summary": {
                "total_strings_used": len(used_strings),
                "total_translation_keys": len(translation_keys_for_comparison),
                "total_languages": len(keys_by_language),
                "missing_count": len(missing_translations),
                "unused_count": len(unused_translations),
                "excluded_count": len(excluded_strings),
                "whitelisted_count": len(WHITELIST_UNUSED)
            },
            "missing_translations": missing_with_locations,
            "unused_translations": sorted(unused_translations),
            "excluded_strings": sorted(excluded_strings),
            "whitelisted_strings": sorted(WHITELIST_UNUSED)
        }
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 1 if (missing_translations or unused_translations) else 0

    # Print results (text format)
    print("=" * 80)
    print("RESULTS")
    print("=" * 80)
    print()

    if missing_translations:
        print(f"⚠️  MISSING TRANSLATIONS ({len(missing_translations)} strings)")
        print("These strings are used in code but not found in translation files:")
        print("-" * 80)
        for string in sorted(missing_translations):
            print(f"  - \"{string}\"")
            if not COMPACT and string in used_strings_with_locations:
                locations = used_strings_with_locations[string]
                if locations:
                    loc = locations[0]
                    print(f"    → {loc['file']}:{loc['line']}:{loc['col']}")
                    if len(locations) > 1:
                        print(f"    (and {len(locations) - 1} more location{'s' if len(locations) > 2 else ''})")
            if not COMPACT and string in missing_by_language:
                missing_langs = missing_by_language[string]
                if len(missing_langs) == len(keys_by_language):
                    print(f"    Missing from: ALL languages ({len(missing_langs)})")
                else:
                    if len(missing_langs) <= 5:
                        print(f"    Missing from: {', '.join(missing_langs)}")
                    else:
                        print(f"    Missing from: {', '.join(missing_langs[:5])} (and {len(missing_langs) - 5} more)")
        print()
    else:
        print("✅ No missing translations found!")
        print()

    if unused_translations:
        print(f"ℹ️  UNUSED TRANSLATIONS ({len(unused_translations)} strings)")
        print("These strings are in translation files but not used in code:")
        print("-" * 80)
        for string in sorted(unused_translations):
            print(f"  - \"{string}\"")
        print()
    else:
        print("✅ No unused translations found!")
        print()

    # Summary
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Total strings used in code: {len(used_strings)}")
    print(f"Total keys in translation files: {len(translation_keys_for_comparison)}")
    print(f"Missing translations: {len(missing_translations)}")
    print(f"Unused translations: {len(unused_translations)}")
    print(f"Whitelisted strings: {len(WHITELIST_UNUSED)}")
    print()

    if missing_translations or unused_translations:
        print("⚠️  Translation files need updates!")
        return 1
    else:
        print("✅ All translations are in sync!")
        return 0

if __name__ == "__main__":
    exit(main())