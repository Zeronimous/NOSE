import os
import json
import csv
import re

def load_manifest(manifest_path):
    """Loads the manifest file."""
    with open(manifest_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def load_translations(csv_path):
    """Loads the translated text from the CSV file into a dictionary."""
    translations = {}
    with open(csv_path, 'r', newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            translations[row['id']] = row['text']
    return translations

def reconstruct_string(reconstruction_plan, translations):
    """Reconstructs a string based on the manifest plan and translations."""
    full_string = []
    for segment in reconstruction_plan:
        if segment['type'] == 'text':
            entry_id = segment['entry_id']
            translated_text = translations.get(entry_id)
            if translated_text is None:
                # This case should ideally not happen if the CSV is complete.
                # We can either raise an error or use a placeholder.
                print(f"Warning: No translation found for ID '{entry_id}'. Using empty string.")
                full_string.append('')
            else:
                full_string.append(translated_text)
        elif segment['type'] in ['tag', 'placeholder']:
            full_string.append(segment['value'])
    return "".join(full_string)

def escape_for_csharp(text):
    """Escapes a string for C# style string literals."""
    return text.replace('\\', '\\\\').replace('"', '\\"').replace('\r', '\\r').replace('\n', '\\n')

def main():
    """Main function to run the reinjector."""
    manifest_path = "textos/manifest.json"
    translated_csv_path = "textos/textos_traducidos.csv"
    output_dir = "espanol" # Using 'espanol' to avoid issues with special characters
    input_dir_base = "ingles" # To read original files

    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    manifest = load_manifest(manifest_path)
    translations = load_translations(translated_csv_path)

    for original_rel_path, file_manifest in manifest.items():
        # Construct the full path to the original file
        original_file_path = os.path.join(original_rel_path) # relpath is enough

        if not os.path.exists(original_file_path):
            print(f"Error: Original file not found at '{original_file_path}'. Skipping.")
            continue

        print(f"Processing {original_file_path}...")

        with open(original_file_path, 'r', encoding='utf-8') as f:
            original_content = f.read()

        # We need to modify the m_Script part.
        # It's safer to parse, modify, and then re-serialize.
        from extractor import parse_file_content # Reuse the parser

        json_data = parse_file_content(original_content)
        if not json_data:
            print(f"Could not parse data from {original_file_path} for reinjection. Skipping.")
            continue

        # Modify the json_data in memory
        for item in json_data['Data']:
            item_id = item.get('ID')
            if item_id in file_manifest:
                reconstruction_plan = file_manifest[item_id]['reconstruction']
                new_english_text = reconstruct_string(reconstruction_plan, translations)
                item['English'] = new_english_text

        # Now, we need to serialize json_data back into the C#-escaped string format.
        # This is the reverse of what the extractor's parser does.
        # json.dumps will create a standard JSON string.
        new_script_json = json.dumps(json_data, ensure_ascii=False)

        # The original format has escaped quotes and no newlines between elements.
        # json.dumps produces: {"Data": [{"ID": ...}]}
        # We need: {\"Data\":[{\"ID\":...}]}
        # So we need to escape the quotes.

        # Let's get the raw json string, then escape it.
        # The compact separator is important to avoid extra whitespace.
        new_script_raw_json = json.dumps(json_data, ensure_ascii=False, separators=(',', ':'))

        # Now, escape it for the game file format.
        escaped_script_str = new_script_raw_json.replace('"', '\\"')

        # Finally, substitute this new script string back into the original content.
        # We can use regex for this.
        # The original content has the m_Script part. We replace its value.

        # Be careful to handle the BOM (﻿) if it was present
        bom = '\ufeff' if 'm_Script = "﻿{' in original_content else ''

        # The final string to be put inside m_Script = "..."
        final_script_content = bom + escaped_script_str

        new_file_content = re.sub(
            r'(m_Script\s*=\s*").*(")',
            lambda m: m.group(1) + final_script_content + m.group(2),
            original_content,
            count=1,
            flags=re.DOTALL
        )

        # Write the modified content to the new file
        output_filename = os.path.basename(original_rel_path)
        output_filepath = os.path.join(output_dir, output_filename)

        # For debugging unicode issues:
        # print("Content to be written:", new_file_content)

        with open(output_filepath, 'w', encoding='utf-8') as f:
            f.write(new_file_content)

        print(f"Created translated file: {output_filepath}")


if __name__ == "__main__":
    main()
