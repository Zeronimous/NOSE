import os
import re
import json
import csv

def find_text_files(directory):
    """Finds all .txt files in a directory."""
    txt_files = []
    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith(".txt"):
                txt_files.append(os.path.join(root, file))
    return txt_files

def parse_file_content(content):
    """Extracts and cleans the JSON string from the file content."""
    match = re.search(r'm_Script\s*=\s*"(.*)"', content, re.DOTALL)
    if not match:
        return None

    json_str = match.group(1)

    # 1. Remove BOM character
    if json_str.startswith('\ufeff'):
        json_str = json_str[1:]

    # 2. The file format uses C#-style escaping for quotes (`\"`) and has
    # newlines (`\r\n`) between array elements, making it invalid JSON.
    # In Python's view of the raw string, these are `\\"` and `\\r\\n`.

    # Replace `\` followed by `r` or `n` with nothing.
    # This is safer than a blanket replace of `\r\n`.
    json_str = re.sub(r'\\r|\\n', '', json_str)

    # Replace `\"` with `"`. This is the key to making it valid JSON
    # without corrupting unicode characters.
    json_str = json_str.replace('\\"', '"')

    try:
        return json.loads(json_str)
    except json.JSONDecodeError as e:
        print(f"Failed to parse JSON from content. Error: {e}")
        print(f"Problematic string: {json_str[:200]}")
        return None


def process_english_text(text, original_id):
    """
    Processes the English text to split it according to markers and placeholders.
    Returns a list of segments and a list of text parts for the CSV.
    """
    # Rule: ignore text that is only a placeholder
    if re.fullmatch(r'\{[^{}]+\}', text):
        return [], []

    # Regex to find all markers and placeholders
    tag_regex = r'(<[a-zA-Z0-9_=\#\/]+>|\{[^{}]+\})'

    parts = re.split(tag_regex, text)
    # Filter out empty strings from the split result
    parts = [p for p in parts if p]

    # Count how many actual text parts we will have
    text_parts_count = sum(1 for p in parts if not re.fullmatch(tag_regex, p) and p.strip())

    reconstruction_segments = []
    csv_rows = []
    text_segment_counter = 1

    for part in parts:
        # Check if the part is a tag or placeholder
        if re.fullmatch(tag_regex, part):
            if re.fullmatch(r'\{[^{}]+\}', part):
                reconstruction_segments.append({"type": "placeholder", "value": part})
            else:
                reconstruction_segments.append({"type": "tag", "value": part})
        # Otherwise, it's a text segment
        elif part.strip():
            if text_parts_count > 1:
                entry_id = f"{original_id}_{text_segment_counter}"
                text_segment_counter += 1
            else:
                entry_id = original_id

            reconstruction_segments.append({"type": "text", "entry_id": entry_id})
            csv_rows.append({"id": entry_id, "text": part})

    # If the text was empty or only whitespace to begin with
    if not parts and text.strip():
        entry_id = original_id
        reconstruction_segments.append({"type": "text", "entry_id": entry_id})
        csv_rows.append({"id": entry_id, "text": text})

    return reconstruction_segments, csv_rows


def main():
    """Main function to run the extractor."""
    input_dir = "ingles"
    output_dir = "textos"

    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    txt_files = find_text_files(input_dir)
    if not txt_files:
        print(f"No .txt files found in '{input_dir}' directory.")
        return

    all_csv_rows = []
    manifest = {}

    for filepath in txt_files:
        print(f"Processing {filepath}...")
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        # The file content is not pure JSON, we need to extract the script part.
        # The provided example is: 0 TextAsset Base  1 string m_Name = "..."  1 string m_Script = "..."
        # We need to extract the content of m_Script.
        json_data = parse_file_content(content)

        if not json_data or 'Data' not in json_data:
            print(f"Could not parse valid data from {filepath}. Skipping.")
            continue

        relative_path = os.path.relpath(filepath)
        manifest[relative_path] = {}

        for item in json_data['Data']:
            item_id = item.get('ID')
            english_text = item.get('English')

            if not item_id or not english_text:
                continue

            reconstruction_segments, csv_rows = process_english_text(english_text, item_id)

            if reconstruction_segments:
                manifest[relative_path][item_id] = {"reconstruction": reconstruction_segments}
                all_csv_rows.extend(csv_rows)

    # Write the CSV file
    csv_filepath = os.path.join(output_dir, "textos_a_traducir.csv")
    with open(csv_filepath, 'w', newline='', encoding='utf-8') as f:
        if all_csv_rows:
            writer = csv.DictWriter(f, fieldnames=["id", "text"])
            writer.writeheader()
            writer.writerows(all_csv_rows)
    print(f"CSV file created at {csv_filepath}")

    # Write the manifest file
    manifest_filepath = os.path.join(output_dir, "manifest.json")
    with open(manifest_filepath, 'w', encoding='utf-8') as f:
        json.dump(manifest, f, indent=4)
    print(f"Manifest file created at {manifest_filepath}")


if __name__ == "__main__":
    main()
