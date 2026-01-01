
import json
import re
import os

def parse_refkey(file_path):
    ref_map = {}
    with open(file_path, "r") as f:
        lines = [l.strip() for l in f.readlines() if l.strip()]
    
    # Skip header if it exists
    start_idx = 0
    if lines[0] == "Bill Number":
        start_idx = 3 # Bill Number, Referral, Notes

    i = start_idx
    while i < len(lines):
        line = lines[i]
        
        # Check if line is a bill number (HB followed by digits)
        if re.match(r"^HB\d+$", line):
            bill_num = line
            i += 1
            if i >= len(lines):
                break
            
            committees = lines[i]
            # Next line could be notes (starts with *)
            notes = ""
            if i + 1 < len(lines) and lines[i+1].startswith("*"):
                i += 1
                notes = lines[i]
            
            # Combine if needed, or just store committees
            # User asked for "Actual Committee (from refkey)", so let's store the raw referral string
            # If notes provide an alternative, we might include them, but let's stick to the primary referral for now unless it's ambiguous.
            # Actually, "JHA/HLT, CPC, FIN" is one string.
            
            ref_map[bill_num] = {
                "committees": committees,
                "notes": notes
            }
        else:
            # Maybe skip or handle weird lines
            # In the dump provided, it looks cleaner than raw PDF text sometimes, but let's be safe.
            i += 1
    return ref_map

def clean_bill_name(filename):
    # extracts HB1234 from HB1234_.PDF.pdf or similar
    match = re.search(r"(HB\d+)", filename)
    if match:
        return match.group(1)
    return filename

def generate_report():
    results_path = "/Users/rodericktabalba/Documents/GitHub/financial-rag/src/refbot/results_tmp/results.json"
    refkey_path = "/Users/rodericktabalba/Documents/GitHub/financial-rag/src/refbot/results_tmp/refkey_dump.txt"
    output_path = "/Users/rodericktabalba/Documents/GitHub/financial-rag/src/refbot/results_tmp/comparison_report.html"

    # Load Predicted Results
    with open(results_path, "r") as f:
        data = json.load(f)
    
    predictions = data.get("results", [])
    
    # Load RefKey
    ref_map = parse_refkey(refkey_path)
    
    # Build HTML
    html = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Committee Assignment Comparison</title>
        <style>
            body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; padding: 20px; background: #f5f5f7; color: #1d1d1f; }
            h1 { text-align: center; margin-bottom: 30px; }
            .container { max-width: 1000px; margin: 0 auto; background: white; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); overflow: hidden; }
            table { width: 100%; border-collapse: collapse; }
            th, td { padding: 12px 16px; text-align: left; border-bottom: 1px solid #e5e5e5; }
            th { background: #f5f5f7; font-weight: 600; font-size: 14px; text-transform: uppercase; letter-spacing: 0.5px; }
            tr:last-child td { border-bottom: none; }
            tr:hover { background-color: #f9f9fa; }
            .match { color: green; font-weight: bold; }
            .mismatch { color: #d70015; }
            .partial { color: #f5a623; }
            .badge { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 12px; font-weight: 500; margin-right: 4px; background: #e8e8ed; color: #1d1d1f; }
            .notes { font-size: 11px; color: #86868b; display: block; margin-top: 4px; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Committee Assignments Comparison</h1>
            <table>
                <thead>
                    <tr>
                        <th>Bill Name</th>
                        <th>Predicted Committees</th>
                        <th>Actual Committees (RefKey)</th>
                        <th>Status</th>
                    </tr>
                </thead>
                <tbody>
    """

    # Populate rows
    # We iterate through predictions because that's what we processed
    # We can also track which ones in RefMap we didn't predict if needed, but let's focus on validating our results.
    
    total_bills = 0
    perfect_matches = 0

    sorted_results = sorted(predictions, key=lambda x: clean_bill_name(x.get("bill_name", "")))

    for item in sorted_results:
        raw_name = item.get("bill_name", "Unknown")
        bill_id = clean_bill_name(raw_name)
        
        pred_committees = item.get("committees", [])
        # Simplify pred list for display
        pred_str = ", ".join(pred_committees)
        
        actual_data = ref_map.get(bill_id)
        
        actual_str = "N/A"
        notes = ""
        status = "Unknown"
        status_class = ""

        if actual_data:
            actual_raw = actual_data["committees"]
            # Clean up actual raw: "JHA, FIN" -> list logic?
            # RefKey formats: "JHA, FIN", "JHA/HLT, CPC, FIN". 
            # "/" usually means joint or alternative? In HI leg, "/" often means committee referral to one followed by another?
            # Usually comma separated means sequential referral.
            # Let's keep it as string for the "Actual" column as requested, but maybe do loose matching for status.
            actual_str = actual_raw
            if actual_data["notes"]:
                notes = actual_data["notes"]
            
            # Simple check: do all predicted exist in actual string?
            # This is a bit rough properly parsing "JHA/HLT" is tricky.
            # Let's clean actual string: replace '/' with ' ', replace ',' with ' '.
            # This allows substring checking.
            
            normalized_actual = actual_raw.replace("/", " ").replace(",", " ").upper().split()
            # Remove common junk words if any? No, committee codes are 3 chars usually.
            
        # Calculate Recall
        # Denominator: Number of specific codes in the actual string
        # We extract all 3-letter uppercase codes
        actual_codes = set(re.findall(r"\b[A-Z]{3}\b", actual_str))
        
        # Numerator: Number of predicted committees that appear in the actual codes
        pred_set = set(pred_committees)
        matches = pred_set.intersection(actual_codes)
        
        match_count = len(matches)
        total_actual = len(actual_codes)
        
        recall = 0.0
        if total_actual > 0:
            recall = match_count / total_actual
            
        recall_pct = int(recall * 100)
        
        # Color coding based on recall
        if recall_pct == 100:
            status_class = "match"
        elif recall_pct > 0:
            status_class = "partial"
        else:
            status_class = "mismatch"
            
        status_text = f"{recall_pct}% ({match_count}/{total_actual})"
        
        # Highlight matches in the actual column would be fancy, but simple text for now
        
        html += f"""
                    <tr>
                        <td>{bill_id}</td>
                        <td>
                            {''.join([f'<span class="badge">{c}</span>' for c in pred_committees])}
                        </td>
                        <td>
                            {actual_str}
                            {f'<span class="notes">{notes}</span>' if notes else ''}
                        </td>
                        <td class="{status_class}">
                            {status_text}
                        </td>
                    </tr>
        """
        
    html += """
                </tbody>
            </table>
        </div>
    </body>
    </html>
    """
    
    with open(output_path, "w") as f:
        f.write(html)
        
    print(f"Report generated at {output_path}")

if __name__ == "__main__":
    generate_report()
