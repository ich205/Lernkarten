import os, pandas as pd, csv, datetime, pathlib, json

def export_to_excel(rows, out_dir, base_name="export"):
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    xlsx_path = os.path.join(out_dir, f"{base_name}_{ts}.xlsx")
    df = pd.DataFrame(rows, columns=["Original", "Frage", "Antwort", "Labels", "Quelle"])
    with pd.ExcelWriter(xlsx_path, engine="openpyxl") as w:
        df.to_excel(w, index=False, sheet_name="Lernkarten")
    # zusätzlich CSV (z. B. für Anki)
    csv_path = os.path.join(out_dir, f"{base_name}_{ts}.csv")
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        cw = csv.writer(f, delimiter=";")
        cw.writerow(["Front", "Back", "Quelle", "Labels", "Original"])
        for r in rows:
            cw.writerow([r[1], r[2], r[4], r[3], r[0]])
    meta_path = os.path.join(out_dir, f"{base_name}_{ts}.json")
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump({"rows": len(rows)}, f, ensure_ascii=False, indent=2)
    return xlsx_path
