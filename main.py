import pandas as pd
from datetime import datetime

# 1. Load files with latin1
reg_file = 'ClimbNUS 2026 Registration(Sheet1)_13_1.csv'
pay_file = 'ClimbNUS 2026 FastPay Report(FastPay RAW)_13_1.csv'

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
    'Team': {'NUS Student': 104, 'Public': 140},
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
        qty = 1 if pd.isna(n) else int(n)
        total += PRICES['Addon_Night'][cat] * qty

    extra_flag = 'I am interested in paying additional $15 per pax for add-on Extra Day Climb'
    extra_pax = 'How many pax need the Extra Day Add-On? (Required for Team Sign-ups, otherwise 1)'
    if row[extra_flag] == 'Yes':
        e = pd.to_numeric(row[extra_pax], errors='coerce')
        qty = 1 if pd.isna(e) else int(e)
        total += 15 * qty

    return total


# 4. Group pay data
pay_summary = df_pay.groupby('R_Clean').agg({'Amount': 'sum', 'Booking Status': lambda x: list(x)}).to_dict('index')


# 5. Build Master Data with Split Slots
def build_master(df_reg, df_pay):
    master_rows = []

    print("--- STARTING VALIDATION LOG ---")

    for index, row in df_reg.iterrows():
        is_team = "Team" in str(row['I am signing up as...'])
        team_name = row['Team Name'] if is_team and pd.notna(row['Team Name']) else "N/A"

        # Split time slots
        raw_slots = str(row['Time Slot Selection (Individual / Team)']).split(';')
        ts1 = raw_slots[0].strip() if len(raw_slots) > 0 and raw_slots[0] != 'nan' else "N/A"
        ts2 = raw_slots[1].strip() if len(raw_slots) > 1 else "N/A"

        ts_learn = row.get('Time Slot Selection (Learn To Climb)\n', "N/A")
        ts_learn = "N/A" if pd.isna(ts_learn) else ts_learn

        ts_night = row.get('Time Slot Selection (Night Climb)', "N/A")
        ts_night = "N/A" if pd.isna(ts_night) else ts_night

        # --- PAYMENT AUDIT & LOGGING ---
        receipt = row['R_Clean']
        p_info = pay_summary.get(receipt, {'Amount': 0, 'Booking Status': []})

        # Check 1: Is there a valid payment record?
        paid_val = "Yes" if any(s == 'Paid' for s in p_info['Booking Status']) else "No"

        # Check 2: Is the amount correct?
        expected = calculate_expected(row)
        paid_amount = p_info['Amount']

        finalised = "Yes"
        status_reason = "OK"

        if paid_val == "No":
            finalised = "No"
            status_reason = f"Missing Payment (Receipt: {receipt})"
        elif paid_amount < expected:
            finalised = "No"
            status_reason = f"Underpaid (Paid: ${paid_amount}, Expected: ${expected})"

        # PRINT LOG TO CONSOLE
        if finalised == "No":
            print(f"[Row {row.get('Id', index)}] {row['Name']} - Finalised: NO. Reason: {status_reason}")

        def add_person(name, email, phone, size, nok, nok_rel, nok_phone):
            if pd.isna(name) or str(name).strip() == "" or str(name).lower() == 'nan': return
            master_rows.append({
                'Name': name,
                'Email': email,
                'Contact Number': str(phone),
                'Attendee Type': row['I am a...'],
                'Category': row['I am signing up as...'],
                'Team Name': team_name,
                'Time Slot 1': ts1,
                'Time Slot 2': ts2,
                'Beginner Climb Time slot': ts_learn,
                'Night time slot': ts_night,
                'Paid': paid_val,
                'Form Done': "Yes",
                'Shirt Size': size,
                'Next of kin': nok,
                'next of kin relationship': nok_rel,
                'Next of kin Contact Number': nok_phone,
                'Finalised': finalised,
                'Status Reason': status_reason  # Added column to Excel
            })

        # Add Main Applicant
        add_person(row['Name1'], row['E-mail address'], row['Contact number'], row['Shirt size'],
                   row['Name of next of kin'], row['Relationship with next of kin'],
                   row['Contact number of next of kin'])

        # Add Team Members (Using Corrected Indices)
        if is_team:
            add_person(row['Member 2 Details'], row['Member 2 Details2'], row['Member 2 Details4'],
                       row['Member 2 Details3'], row['Member 2 Details6'], row['Member 2 Details7'],
                       row['Member 2 Details8'])

            add_person(row['Member 3 Details'], row['Member 3 Details2'], row['Member 3 Details4'],
                       row['Member 3 Details3'], row['Member 3 Details6'], row['Member 3 Details7'],
                       row['Member 3 Details8'])

            add_person(row['Member 4 Details, if applicable'], row['Member 4 Details, if applicable2'],
                       row['Member 4 Details, if applicable4'], row['Member 4 Details, if applicable3'],
                       row['Member 4 Details, if applicable6'], row['Member 4 Details, if applicable7'],
                       row['Member 4 Details, if applicable8'])

    # Add Ghost Payers
    reg_receipts = set(df_reg['R_Clean'])
    for r_id, info in pay_summary.items():
        if r_id not in reg_receipts and r_id != 'nan':
            p_rows = df_pay[df_pay['R_Clean'] == r_id]
            lead = p_rows.iloc[0]
            master_rows.append({
                'Name': f"{lead['First Name']} {lead['Surname']}",
                'Email': lead['Email'],
                'Contact Number': lead['Contact Phone Number'],
                'Attendee Type': lead['Attendee Type'],
                'Category': "Unknown (Form Missing)",
                'Team Name': "N/A", 'Time Slot 1': "N/A", 'Time Slot 2': "N/A",
                'Beginner Climb Time slot': "N/A", 'Night time slot': "N/A",
                'Paid': "Yes" if any(s == 'Paid' for s in info['Booking Status']) else "No",
                'Form Done': "No", 'Shirt Size': "N/A",
                'Next of kin': "N/A", 'next of kin relationship': "N/A",
                'Next of kin Contact Number': "N/A",
                'Finalised': "No (Form Missing)",
                'Status Reason': "No Registration Form Found"
            })

    print("--- VALIDATION COMPLETE ---")
    return pd.DataFrame(master_rows)


df_master = build_master(df_reg, df_pay)
current_date = datetime.now().strftime('%Y-%m-%d')
# df_master.to_excel(f'Consolidated_Master_Sheet_{current_date}.xlsx', index=False)
df_master.to_excel(f'Consolidated_Master_Sheet_special_13_1.xlsx', index=False)
print(f"File saved: Consolidated_Master_Sheet_{current_date}.xlsx")