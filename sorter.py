import pandas as pd
import re
from datetime import datetime

# ==========================================
# 1. CONFIGURATION & LOADING
# ==========================================

MASTER_FILE = 'ClimbNUS_2026_Registration - Consolidated Master_ Downloaded_13_1.csv'
PRODUCT_FILE = 'Events signup import(PRODUCTS).csv'

print("Loading files...")
try:
    df_master = pd.read_csv(MASTER_FILE, encoding='utf-8-sig')
    df_products = pd.read_csv(PRODUCT_FILE, encoding='utf-8-sig')
except FileNotFoundError:
    print("File not found. Please check the filenames.")
    exit()

# CRITICAL FIX: Forward-fill the Item column
df_products['Item'] = df_products['Item'].ffill()

# ==========================================
# 2. PREPARE PRODUCT LOOKUP
# ==========================================

product_map = {}
available_product_names = set()

for _, row in df_products.iterrows():
    p_item = str(row['Item']).strip()
    p_size = str(row['Shirt Size']).strip().upper()

    available_product_names.add(p_item)

    product_map[(p_item, p_size)] = {
        'product_id': row['Product ID'],
        'price_id': row['Price ID'],
        'item_name': p_item
    }

print("\n--- DEBUG: Loaded Product Names (First 15) ---")
for name in sorted(list(available_product_names))[:15]:
    print(f"  [FOUND]: {name}")
print("-----------------------------------\n")

# ==========================================
# 3. INITIALIZE TABS & HELPERS
# ==========================================

days = ['D1', 'D2', 'D3', 'D4']
sessions = ['Morning', 'Afternoon', 'Night']
day_map = {
    '19 January': 'D1',
    '20 January': 'D2',
    '21 January': 'D3',
    '22 January': 'D4'
}

tabs_data = {}
for d in days:
    for s in sessions:
        if d == 'D4' and s == 'Night': continue
        tabs_data[f"{d} {s}"] = []

summary_entries = []
error_log = []


def normalize_size(size_str):
    """
    Converts Master Sheet sizes (2XL, 2XS) to Product Sheet format (XXL, XXS).
    """
    if pd.isna(size_str): return ""
    s = str(size_str).strip().upper()

    # MAPPING FIX
    if s == "2XL": return "XXL"
    if s == "2XS": return "XXS"
    if s == "3XL": return "XXXL"  # Added just in case

    return s


def get_session(timeslot_str):
    if pd.isna(timeslot_str) or str(timeslot_str).upper() == 'N/A': return None
    all_numbers = re.findall(r'(\d{4})', str(timeslot_str))
    times = [t for t in all_numbers if t != '2026']
    if not times: return None
    start_time = int(times[0])
    if 800 <= start_time < 1300:
        return "Morning"
    elif 1300 <= start_time < 1700:
        return "Afternoon"
    elif 1700 <= start_time <= 2100:
        return "Night"
    return None


def get_day_code(timeslot_str, column_name):
    # Force D1 for Beginner
    if column_name == 'Beginner Climb Time slot' and pd.notna(timeslot_str) and str(timeslot_str).upper() != 'N/A':
        return 'D1'
    for date_key, day_code in day_map.items():
        if date_key in str(timeslot_str): return day_code
    return None


def split_name(full_name):
    if pd.isna(full_name): return "", ""
    parts = str(full_name).strip().split(' ', 1)
    if len(parts) == 1: return parts[0], ""
    return parts[0], parts[1]


# ==========================================
# 4. PASS 1: STANDARD SLOTS (Individual, Team, Beginner)
# ==========================================
print("Starting Pass 1: Standard Slots...")

standard_cols = ['Time Slot 1', 'Time Slot 2', 'Beginner Climb Time slot']

for idx, row in df_master.iterrows():
    full_name = row['Name']
    first, last = split_name(full_name)
    email = row['Email']
    category = str(row['Category']).strip()

    # --- SIZE FIX APPLIED HERE ---
    shirt_size = normalize_size(row['Shirt Size'])

    for col in standard_cols:
        if col not in df_master.columns: continue

        val = row[col]
        if pd.isna(val) or str(val).upper() == 'N/A': continue

        day = get_day_code(val, col)
        session = get_session(val)

        if day and session:
            # Add to Tab
            tab_name = f"{day} {session}"
            if tab_name in tabs_data:
                tabs_data[tab_name].append(row)

            # --- MAPPING LOGIC (Standard) ---
            item_name = None

            if col == 'Beginner Climb Time slot':
                sess_num = "1"
                if '1300' in val or '13:00' in val: sess_num = "2"
                if '1600' in val or '16:00' in val: sess_num = "3"
                item_name = f"Learn to Climb - Session {sess_num}"
            else:
                # Individual or Team
                prefix = "Team" if "Team" in category else "Individual"
                day_str = day.replace("D", "Day ")
                item_name = f"{prefix} - {day_str} {session}"

            # Lookup
            if item_name and (item_name, shirt_size) in product_map:
                p_info = product_map[(item_name, shirt_size)]
                summary_entries.append({
                    'first_name': first, 'last_name': last, 'email': email,
                    'product_name': p_info['item_name'],
                    'product_id': p_info['product_id'],
                    'price_id': p_info['price_id'],
                    'original_slot': val
                })
            else:
                error_log.append({
                    'Name': full_name, 'Slot': val, 'Type': 'Standard',
                    'Reason': f"Mapping Failed. Computed: '{item_name}' Size: '{shirt_size}'"
                })

# ==========================================
# 5. PASS 2: NIGHT SLOTS ONLY
# ==========================================
print("Starting Pass 2: Night Slots...")

night_col = 'Night time slot'

for idx, row in df_master.iterrows():
    if night_col not in df_master.columns: break

    val = row[night_col]

    # 1. Validation
    if pd.isna(val) or str(val).upper() == 'N/A': continue

    # 2. Determine Day/Session
    day = None
    if "19 January" in str(val):
        day = "D1"
    elif "20 January" in str(val):
        day = "D2"
    elif "21 January" in str(val):
        day = "D3"

    session = "Night"

    if day:
        # Sort into Tab
        tab_name = f"{day} {session}"
        if tab_name in tabs_data:
            tabs_data[tab_name].append(row)

        # --- MAPPING LOGIC (Night Specific) ---
        night_item_name = None

        if "Night 1" in str(val):
            night_item_name = "Night - Day 1"
        elif "Night 2" in str(val):
            night_item_name = "Night - Day 2"
        elif "Night 3" in str(val):
            night_item_name = "Night - Day 3"

        # --- SIZE FIX APPLIED HERE ---
        shirt_size = normalize_size(row['Shirt Size'])

        match_found = False

        # Try exact match
        if night_item_name and (night_item_name, shirt_size) in product_map:
            p_info = product_map[(night_item_name, shirt_size)]
            match_found = True
        # Try alternative match
        elif night_item_name:
            alt_name = f"Night Climb - {night_item_name}"
            if (alt_name, shirt_size) in product_map:
                p_info = product_map[(alt_name, shirt_size)]
                match_found = True

        if match_found:
            full_name = row['Name']
            first, last = split_name(full_name)
            email = row['Email']

            summary_entries.append({
                'first_name': first, 'last_name': last, 'email': email,
                'product_name': p_info['item_name'],
                'product_id': p_info['product_id'],
                'price_id': p_info['price_id'],
                'original_slot': val
            })
        else:
            error_log.append({
                'Name': row['Name'], 'Slot': val, 'Type': 'Night',
                'Reason': f"Night Map Failed. Computed: '{night_item_name}' Size: '{shirt_size}'"
            })

    else:
        error_log.append({
            'Name': row['Name'], 'Slot': val, 'Type': 'Night',
            'Reason': "Could not determine Date from Night slot string"
        })

# ==========================================
# 6. EXPORT
# ==========================================

current_date = datetime.now().strftime('%Y-%m-%d')
output_file = f'ClimbNUS_2026_Processed_{current_date}.xlsx'

with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
    pd.DataFrame(summary_entries).to_excel(writer, sheet_name='Summary_All_Entries', index=False)

    if error_log:
        pd.DataFrame(error_log).to_excel(writer, sheet_name='Unmapped_Log', index=False)

    for tab_name, rows in tabs_data.items():
        tab_df = pd.DataFrame(rows)
        if tab_df.empty: tab_df = pd.DataFrame(columns=df_master.columns)
        tab_df.to_excel(writer, sheet_name=tab_name, index=False)

print(f"Successfully generated {output_file}")
print(f"Total mapped: {len(summary_entries)}")
print(f"Total unmapped: {len(error_log)}")