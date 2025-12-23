import pandas as pd
from datetime import datetime

# 1. Load files with latin1
reg_file = 'ClimbNUS 2026 Registration(Sheet1).csv'
pay_file = 'ClimbNUS 2026 FastPay Report(FastPay RAW).csv'

df_reg = pd.read_csv(reg_file, encoding='latin1')
df_pay = pd.read_csv(pay_file, encoding='latin1')

# 2. Identify Receipt column
reg_rcpt_col = [c for c in df_reg.columns if "RECEIPT NUMBER" in c][0]
df_reg['R_Clean'] = df_reg[reg_rcpt_col].astype(str).str.strip()
df_pay['R_Clean'] = df_pay['Receipt'].astype(str).str.strip()

# 3. Pricing Logic
PRICES = {
    'Individual': {'NUS Student': 28, 'Public': 35},
    'Learn To Climb': {'NUS Student': 22, 'Public': 30},
    'Team': {'NUS Student': 112, 'Public': 140},
    'Addon_Night': {'NUS Student': 8, 'Public': 10},
    'Addon_Extra': 15
}


def calculate_expected(row):
    total = 0
    cat = 'NUS Student' if 'NUS' in str(row['I am a...']) else 'Public'
    reg_type = str(row['I am signing up as...'])

    if "Individual" in reg_type:
        total += PRICES['Individual'][cat]
    elif "Learn To Climb" in reg_type:
        total += PRICES['Learn To Climb'][cat]
    elif "Team" in reg_type:
        total += PRICES['Team'][cat]

    night_flag = 'I am interested in paying additional $8/$10 (NUS/Public) per pax for add-on Night Climb'
    night_pax = 'How many pax need the Night Climb Add-On? (Required for Team Sign-ups, otherwise 1)'
    if row[night_flag] == 'Yes':
        n = pd.to_numeric(row[night_pax], errors='coerce')
        total += PRICES['Addon_Night'][cat] * (1 if pd.isna(n) else int(n))

    extra_flag = 'I am interested in paying additional $15 per pax for add-on Extra Day Climb'
    extra_pax = 'How many pax need the Extra Day Add-On? (Required for Team Sign-ups, otherwise 1)'
    if row[extra_flag] == 'Yes':
        e = pd.to_numeric(row[extra_pax], errors='coerce')
        total += 15 * (1 if pd.isna(e) else int(e))
    return total


# 4. Group pay data
pay_summary = df_pay.groupby('R_Clean').agg({'Amount': 'sum', 'Booking Status': lambda x: list(x)}).to_dict('index')


# 5. Build Master Data with Split Slots
def build_master(df_reg, df_pay):
    master_rows = []

    for _, row in df_reg.iterrows():
        is_team = "Team" in str(row['I am signing up as...'])
        team_name = row['Team Name'] if is_team and pd.notna(row['Team Name']) else "N/A"

        # --- LOGIC UPDATE: SPLIT TIME SLOTS ---
        raw_slots = str(row['Time Slot Selection (Individual / Team)']).split(';')
        ts1 = raw_slots[0].strip() if len(raw_slots) > 0 and raw_slots[0] != 'nan' else "N/A"
        ts2 = raw_slots[1].strip() if len(raw_slots) > 1 else "N/A"

        # Other slots
        ts_learn = row['Time Slot Selection (Learn To Climb)\n'] if pd.notna(
            row['Time Slot Selection (Learn To Climb)\n']) else "N/A"
        ts_night = row['Time Slot Selection (Night Climb)'] if pd.notna(
            row['Time Slot Selection (Night Climb)']) else "N/A"

        # Payment Audit
        receipt = row['R_Clean']
        p_info = pay_summary.get(receipt, {'Amount': 0, 'Booking Status': []})
        paid_val = "Yes" if any(s == 'Paid' for s in p_info['Booking Status']) else "No"
        expected = calculate_expected(row)
        finalised = "Yes" if (paid_val == "Yes" and p_info['Amount'] >= expected) else "No"

        def add_person(name, email, phone, size, nok, nok_rel, nok_phone):
            if pd.isna(name) or str(name).strip() == "" or str(name).lower() == 'nan': return
            master_rows.append({
                'Name': name, 'Email': email, 'Contact Number': str(phone),
                'Attendee Type': row['I am a...'], 'Category': row['I am signing up as...'],
                'Team Name': team_name,
                'Time Slot 1': ts1,
                'Time Slot 2': ts2,
                'Beginner Climb Time slot': ts_learn, 'Night time slot': ts_night,
                'Paid': paid_val, 'Form Done': "Yes", 'Shirt Size': size,
                'Next of kin': nok, 'next of kin relationship': nok_rel,
                'Next of kin Contact Number': nok_phone, 'Finalised': finalised
            })

        add_person(row['Name1'], row['E-mail address'], row['Contact number'], row['Shirt size'],
                   row['Name of next of kin'], row['Relationship with next of kin'],
                   row['Contact number of next of kin'])
        if is_team:
            add_person(row['Member 2 Details'], row['Member 2 Details1'], row['Member 2 Details2'],
                       row['Member 2 Details3'], row['Member 2 Details5'], row['Member 2 Details6'],
                       row['Member 2 Details7'])
            add_person(row['Member 3 Details'], row['Member 3 Details1'], row['Member 3 Details2'],
                       row['Member 3 Details3'], row['Member 3 Details5'], row['Member 3 Details6'],
                       row['Member 3 Details7'])
            add_person(row['Member 4 Details, if applicable'], row['Member 4 Details, if applicable1'],
                       row['Member 4 Details, if applicable2'], row['Member 4 Details, if applicable3'],
                       row['Member 4 Details, if applicable5'], row['Member 4 Details, if applicable6'],
                       row['Member 4 Details, if applicable7'])

    # Add Ghost Payers
    reg_receipts = set(df_reg['R_Clean'])
    for r_id, info in pay_summary.items():
        if r_id not in reg_receipts and r_id != 'nan':
            p_rows = df_pay[df_pay['R_Clean'] == r_id]
            lead = p_rows.iloc[0]
            master_rows.append({
                'Name': f"{lead['First Name']} {lead['Surname']}", 'Email': lead['Email'],
                'Contact Number': lead['Contact Phone Number'],
                'Attendee Type': lead['Attendee Type'], 'Category': "Unknown (Form Missing)",
                'Team Name': "N/A", 'Time Slot 1': "N/A", 'Time Slot 2': "N/A", 'Beginner Climb Time slot': "N/A",
                'Night time slot': "N/A",
                'Paid': "Yes" if any(s == 'Paid' for s in info['Booking Status']) else "No",
                'Form Done': "No", 'Shirt Size': "N/A", 'Next of kin': "N/A", 'next of kin relationship': "N/A",
                'Next of kin Contact Number': "N/A",
                'Finalised': "No (Form Missing)"
            })
    return pd.DataFrame(master_rows)


df_master = build_master(df_reg, df_pay)
current_date = datetime.now().strftime('%Y-%m-%d')
df_master.to_excel(f'Consolidated_Master_Sheet_{current_date}.xlsx', index=False)
print("Updated Master Sheet with split time slots generated.")