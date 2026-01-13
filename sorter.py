from datetime import datetime

import pandas as pd
import re

# 1. Load the Consolidated Master Sheet
file_path = 'Consolidated_Master_Sheet_2026-01-06.xlsx'
df = pd.read_excel(file_path)

# 2. Define the sorting logic
days = ['D1', 'D2', 'D3', 'D4']
sessions = ['Morning', 'Afternoon', 'Night']
day_map = {
    '19 January': 'D1',
    '20 January': 'D2',
    '21 January': 'D3',
    '22 January': 'D4'
}

# Initialize all 12 tabs as empty lists
tabs_data = {f"{d} {s}": [] for d in days for s in sessions}


# 3. Define the Time and Day logic
def get_session(timeslot_str):
    """Sorts time into Morning (0800-1300), Afternoon (1300-1700), or Night (1700-2100)"""
    if pd.isna(timeslot_str) or str(timeslot_str).upper() == 'N/A':
        return None

    # IMPROVED REGEX: Find 4-digit numbers but EXCLUDE '2026'
    all_numbers = re.findall(r'(\d{4})', str(timeslot_str))
    times = [t for t in all_numbers if t != '2026']

    if not times:
        return None

    start_time = int(times[0])

    # Logic: 1300 and later is Afternoon; 1700 and later is Night
    if 800 <= start_time < 1300:
        return "Morning"
    elif 1300 <= start_time < 1700:
        return "Afternoon"
    elif 1700 <= start_time <= 2100:
        return "Night"
    return None


def get_day_code(timeslot_str, column_name):
    """Maps date text to Day codes; Defaults Beginner Climb to D1"""
    # Force Day 1 for Beginner Climb column
    if column_name == 'Beginner Climb Time slot' and pd.notna(timeslot_str) and str(timeslot_str).upper() != 'N/A':
        return 'D1'

    for date_key, day_code in day_map.items():
        if date_key in str(timeslot_str):
            return day_code
    return None


# 4. Sort every row into its respective tabs
slot_columns = ['Time Slot 1', 'Time Slot 2', 'Beginner Climb Time slot', 'Night time slot']

for _, row in df.iterrows():
    assigned_tabs = set()

    for col in slot_columns:
        if col in df.columns:
            val = row[col]
            day = get_day_code(val, col)
            session = get_session(val)

            if day and session:
                tab_name = f"{day} {session}"
                if tab_name not in assigned_tabs:
                    tabs_data[tab_name].append(row)
                    assigned_tabs.add(tab_name)

# 5. Export to one Excel file with 12 tabs
current_date = datetime.now().strftime('%Y-%m-%d')
output_file = f'ClimbNUS_2026_Schedule_Split_{current_date}.xlsx'
with pd.ExcelWriter(output_file) as writer:
    for d in days:
        for s in sessions:
            tab_name = f"{d} {s}"
            tab_df = pd.DataFrame(tabs_data[tab_name])

            if tab_df.empty:
                tab_df = pd.DataFrame(columns=df.columns)

            tab_df.to_excel(writer, sheet_name=tab_name, index=False)

print(f"Successfully generated {output_file} with all 12 session tabs.")