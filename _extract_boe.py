"""Extract BoE millennium dataset into CSV files."""
import pandas as pd
import numpy as np
import calendar
import os

BOE_DIR = "data/historical/boe"
xl_path = os.path.join(BOE_DIR, "boe_millennium.xlsx")

xl = pd.ExcelFile(xl_path, engine="openpyxl")

# ===== GBP/USD =====
gbp_sheet = [s for s in xl.sheet_names if "1791" in str(s)][0]
print(f"GBP/USD sheet: {gbp_sheet}")
df = pd.read_excel(
    xl_path, sheet_name=gbp_sheet,
    engine="openpyxl", header=None, skiprows=6,
)
df.columns = ["year", "month_name", "rate"]  # type: ignore[assignment]

month_map = {m: i for i, m in enumerate(calendar.month_abbr) if m}
rows = []
for _, row in df.iterrows():
    try:
        year = int(row["year"])
        month_str = str(row["month_name"]).strip()[:3]
        month = month_map.get(month_str)
        rate = float(row["rate"])
        if month and not np.isnan(rate):
            rows.append({"date": f"{year}-{month:02d}-01", "rate": rate})
    except (ValueError, TypeError):
        continue

out = pd.DataFrame(rows)
out.to_csv(os.path.join(BOE_DIR, "boe_gbpusd.csv"), index=False)
first = out["date"].iloc[0]
last = out["date"].iloc[-1]
print(f"GBP/USD: {len(out)} obs ({first} to {last})")

# ===== Bank Rate (D1 sheet) =====
rate_sheet = [s for s in xl.sheet_names if "D1" in str(s)][0]
print(f"\nBank Rate sheet: {rate_sheet}")
df2 = pd.read_excel(
    xl_path, sheet_name=rate_sheet,
    engine="openpyxl", header=None,
)
# Show first 20 rows to understand structure
print("First 20 rows:")
for i in range(min(20, len(df2))):
    vals = [str(v)[:30] for v in df2.iloc[i].values[:5]]
    print(f"  [{i}] {vals}")

# Try to parse: usually date + rate columns
# Skip header rows
data_start = None
for i in range(len(df2)):
    val = df2.iloc[i, 0]
    if isinstance(val, pd.Timestamp) or (isinstance(val, str) and "-" in val):
        data_start = i
        break
    try:
        y = int(float(str(val)))
        if 1600 < y < 2100:
            data_start = i
            break
    except (ValueError, TypeError):
        continue

if data_start is not None:
    print(f"\nData starts at row {data_start}")
    df3 = df2.iloc[data_start:].copy()
    bank_rows = []
    for _, row in df3.iterrows():
        try:
            dt = pd.Timestamp(row.iloc[0])
            rate = float(row.iloc[1])
            if not np.isnan(rate):
                bank_rows.append({
                    "date": dt.strftime("%Y-%m-%d"),
                    "rate": rate,
                })
        except (ValueError, TypeError):
            continue
    if bank_rows:
        br = pd.DataFrame(bank_rows)
        br.to_csv(os.path.join(BOE_DIR, "boe_bankrate.csv"), index=False)
        first_br = br["date"].iloc[0]
        last_br = br["date"].iloc[-1]
        print(f"Bank Rate: {len(br)} obs ({first_br} to {last_br})")
    else:
        print("No bank rate data parsed")
else:
    print("Could not find data start row")
