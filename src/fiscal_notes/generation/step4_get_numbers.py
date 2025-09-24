import os
import re
import json

def extract_number_context(input_dir="./documents", output_file="number_context.json", window=50):
    """
    Scans all .txt files in input_dir, finds dollar amounts (handles both $5,000 and 5,000 $),
    and extracts +/- window tokens of context.
    Saves results to output_file in JSON format.
    """

    number_pattern = re.compile(
        r"""
        (?:\$|USD\s*)                   # leading $ or USD (required)
        \s*
        [0-9]{1,3}(?:,[0-9]{3})*        # digits with optional commas (thousands)
        (?:\.\d{1,2})?                  # optional decimal part
        |                               # OR
        [0-9]{1,3}(?:,[0-9]{3})*        # digits with optional commas (thousands)
        (?:\.\d{1,2})?                  # optional decimal part
        \s*(?:\$|USD)                   # trailing $ or USD (required)
        """,
        re.VERBOSE
    )

    results = []

    for filename in os.listdir(input_dir):
        if filename.endswith(".txt"):
            file_path = os.path.join(input_dir, filename)
            with open(file_path, "r", encoding="utf-8") as f:
                text = f.read()

            tokens = text.split()
            for i, token in enumerate(tokens):
                # candidate groups to test
                candidates = [token]
                if i + 1 < len(tokens):
                    candidates.append(token + tokens[i + 1])  # e.g. "5000" + "$"
                if i > 0:
                    candidates.append(tokens[i - 1] + token)  # e.g. "$" + "5000"

                for candidate in candidates:
                    if number_pattern.fullmatch(candidate):
                        # context window
                        start = max(0, i - window)
                        end = min(len(tokens), i + window + 1)
                        context_text = " ".join(tokens[start:end])

                        # normalize number
                        cleaned = re.sub(r"[^\d.]", "", candidate.replace(",", ""))
                        try:
                            number_val = float(cleaned)
                        except ValueError:
                            continue

                        results.append({
                            "text": context_text,
                            "number": number_val,
                            "filename": filename
                        })
                        break  # stop after first match for this token

    # Save as JSON
    with open(output_file, "w", encoding="utf-8") as out:
        json.dump(results, out, indent=2, ensure_ascii=False)

    return results
