import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, timezone
import gspread
from google.oauth2.service_account import Credentials

# --- BACK BUTTON ---
if st.button("⬅️ Back to Money Manager", type="secondary"):
    st.switch_page("money_app.py") 
st.write("---") 
# -------------------

# ==========================================
# 1. SETUP & HELPER FUNCTIONS
# ==========================================
st.set_page_config(page_title="Money Manager: Backlog", page_icon="💰", layout="centered")
st.title("💰 Money Manager: Incomplete Backlog")
st.markdown("Use this dedicated tool to rapidly clear your backlog of incomplete quick entries and UNPAID dues.")

def get_ist_now():
    return datetime.now(timezone.utc) + timedelta(hours=5, minutes=30)

@st.cache_resource
def init_connection():
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scopes)
    client = gspread.authorize(creds)
    return client.open("sk_money_location")

try:
    sh = init_connection()
except Exception as e:
    st.error(f"Could not connect to Google Sheets. Error: {e}")
    st.stop()

# --- SMART CACHING ENGINE ---
@st.cache_data(ttl=600)
def load_config():
    try: return pd.DataFrame(sh.worksheet("CONFIG").get_all_records())
    except: return pd.DataFrame()

@st.cache_data(ttl=60)
def load_money_data():
    try: return pd.DataFrame(sh.worksheet("MONEY_DATA").get_all_records())
    except: return pd.DataFrame()

config_df = load_config()

ACCOUNT_HEADERS = ["A. Cash:", "B. Bank Accounts:", "C. Credit Cards:", "D. Digital Wallet:", "E. Loan:", "F. Members:"]

def get_list(column_name):
    if column_name in config_df.columns:
        raw_list = [str(val).strip() for val in config_df[column_name].dropna().tolist() if str(val).strip() != ""]
        return list(dict.fromkeys(raw_list))
    return []

def get_clean_accounts():
    raw = get_list("Accounts")
    return [a for a in raw if a not in ACCOUNT_HEADERS]

# ==========================================
# 2. INCOMPLETE LIST UI
# ==========================================
df_money = load_money_data()

if not df_money.empty and 'Remark' in df_money.columns:
    incomplete_df = df_money[df_money['Remark'] == '⚠️ INCOMPLETE'].copy()
    
    if not incomplete_df.empty:
        st.error(f"⚠️ You currently have **{len(incomplete_df)}** incomplete entries waiting to be cleared!")
        
        # Sort toggle
        sort_desc = st.toggle("⬇️ Sort Newest First", value=True)
        
        # Parse dates safely to allow mathematical sorting and month grouping
        incomplete_df['Date_Parsed'] = pd.to_datetime(incomplete_df['Date'], format='%d-%m-%Y', errors='coerce')
        incomplete_df['Time_Parsed'] = pd.to_datetime(incomplete_df['Time'], format='%H:%M', errors='coerce').dt.time
        
        # Sort the dataframe based on the toggle
        incomplete_df = incomplete_df.sort_values(
            by=['Date_Parsed', 'Time_Parsed'], 
            ascending=[not sort_desc, not sort_desc]
        )
        
        current_month = ""
        
        # Iterate through the correctly sorted items
        for idx, row in incomplete_df.iterrows():
            sheet_row = idx + 2 # Google Sheet rows are 1-indexed, and row 1 is header
            
            # Check and display Month Headings
            row_month = row['Date_Parsed'].strftime('%B %Y') if pd.notna(row['Date_Parsed']) else "Unknown Date"
            if row_month != current_month:
                st.markdown(f"#### 📅 {row_month}")
                current_month = row_month
            
            amt_display = f"₹{row['Out']} (OUT)" if float(row.get('Out', 0) or 0) > 0 else f"₹{row['In']} (IN)"
            is_unpaid = str(row.get('Account', '')).strip() == 'UNPAID'
            icon = "🔴" if is_unpaid else "🔸"
            due_label = " | **(DUE)**" if is_unpaid else ""
            
            expander_title = f"{icon} {row['Date']} at {row.get('Time', '')} | {amt_display} | Loc: {row.get('Location', '')}{due_label}"
            
            # Render each incomplete form inside its own collapse menu
            with st.expander(expander_title):
                c_r1_1, c_r1_2, c_r1_3 = st.columns(3)
                with c_r1_1: 
                    acc_opts = get_clean_accounts()
                    row_acc = str(row.get('Account', '')).strip()
                    if row_acc and row_acc not in acc_opts: acc_opts.insert(0, row_acc)
                    i_acc = st.selectbox("Account", acc_opts, index=acc_opts.index(row_acc) if row_acc in acc_opts else 0, key=f"ac_{idx}")
                with c_r1_2: i_fund = st.selectbox("Fund", get_list("Funds"), key=f"fu_{idx}")
                with c_r1_3:
                    mapped_entities = list(dict.fromkeys([str(e).strip() for e in config_df['Map_Entity'].dropna() if str(e).strip() != ""])) if 'Map_Entity' in config_df.columns else []
                    ent_opts = mapped_entities if mapped_entities else get_list("Entities")
                    curr_ent = str(row.get('Entity', '')).strip()
                    if curr_ent and curr_ent not in ent_opts: ent_opts.insert(0, curr_ent)
                    i_ent = st.selectbox("Entity", ent_opts, index=ent_opts.index(curr_ent) if curr_ent in ent_opts else 0, key=f"en_{idx}")

                c_r2_1, c_r2_2, c_r2_3 = st.columns(3)
                with c_r2_1:
                    if 'Map_Entity' in config_df.columns:
                        ent_df = config_df[config_df['Map_Entity'].astype(str).str.strip() == i_ent]
                        cat_opts = list(dict.fromkeys([str(c).strip() for c in ent_df['Map_Category'].dropna() if str(c).strip() != ""]))
                        i_cat_sel = st.selectbox("Category", cat_opts + ["-- Type New --", "-None-"], key=f"ca_{idx}")
                        i_cat = st.text_input("Type New Category", key=f"ca_new_{idx}") if i_cat_sel == "-- Type New --" else i_cat_sel
                        cat_df = pd.DataFrame() if i_cat_sel == "-- Type New --" else ent_df[ent_df['Map_Category'].astype(str).str.strip() == i_cat]
                    else:
                        i_cat_sel = st.selectbox("Category", get_list("Categories") + ["-- Type New --", "-None-"], key=f"ca_{idx}")
                        i_cat = st.text_input("Type New Category", key=f"ca_new_{idx}") if i_cat_sel == "-- Type New --" else i_cat_sel
                        cat_df = pd.DataFrame()
                        
                with c_r2_2:
                    if not cat_df.empty and 'Map_SubCat' in cat_df.columns:
                        sub_opts = list(dict.fromkeys([str(s).strip() for s in cat_df['Map_SubCat'].dropna() if str(s).strip() != ""]))
                        i_sub_sel = st.selectbox("Sub Category", sub_opts + ["-- Type New --", "-None-"], key=f"su_{idx}")
                        i_sub = st.text_input("Type New Sub Category", key=f"su_new_{idx}") if i_sub_sel == "-- Type New --" else i_sub_sel
                        sub_df = pd.DataFrame() if i_sub_sel == "-- Type New --" else cat_df[cat_df['Map_SubCat'].astype(str).str.strip() == i_sub]
                    else:
                        i_sub_sel = st.selectbox("Sub Category", get_list("Sub-Categories") + ["-- Type New --", "-None-"], key=f"su_{idx}")
                        i_sub = st.text_input("Type New Sub Category", key=f"su_new_{idx}") if i_sub_sel == "-- Type New --" else i_sub_sel
                        sub_df = pd.DataFrame()
                        
                with c_r2_3:
                    if not sub_df.empty and 'Map_Particular' in sub_df.columns:
                        part_opts = list(dict.fromkeys([str(p).strip() for p in sub_df['Map_Particular'].dropna() if str(p).strip() != ""]))
                        i_part_sel = st.selectbox("Particulars", part_opts + ["-- Type New --", "-None-"], key=f"pa_{idx}")
                        i_part = st.text_input("Type New Particulars", key=f"pa_new_{idx}") if i_part_sel == "-- Type New --" else i_part_sel
                    else:
                        i_part_sel = st.selectbox("Particulars", get_list("Particulars") + ["-- Type New --", "-None-"], key=f"pa_{idx}")
                        i_part = st.text_input("Type New Particulars", key=f"pa_new_{idx}") if i_part_sel == "-- Type New --" else i_part_sel

                c_r3_1, c_r3_2, c_r3_3 = st.columns([1.5, 1.5, 1])
                with c_r3_1:
                    tf_opts = get_list("TO_FROM")
                    curr_tf = str(row.get('TO_FROM', '')).strip()
                    if curr_tf and curr_tf not in tf_opts: tf_opts.insert(0, curr_tf)
                    tf_opts_with_none = tf_opts + ["-None-"]
                    i_tofrom = st.selectbox("TO / FROM", tf_opts_with_none, index=tf_opts_with_none.index(curr_tf) if curr_tf in tf_opts_with_none else (len(tf_opts_with_none)-1), key=f"tf_{idx}")
                
                with c_r3_2: i_rem = st.text_input("Remark", key=f"re_{idx}")
                    
                with c_r3_3:
                    st.markdown("<br>", unsafe_allow_html=True)
                    if st.button("💾 Complete & Clear", key=f"sv_{idx}", type="primary", use_container_width=True):
                        try:
                            cells = sh.worksheet("MONEY_DATA").range(f"A{sheet_row}:M{sheet_row}")
                            row_data = [row['Date'], row.get('Time', ''), row['In'], row['Out'], i_acc, i_fund, i_ent, "" if i_cat == "-None-" else i_cat, "" if i_sub == "-None-" else i_sub, "" if i_part == "-None-" else i_part, "" if i_tofrom == "-None-" else i_tofrom, row.get('Location', ''), i_rem]
                            for i, val in enumerate(row_data): cells[i].value = str(val)
                            sh.worksheet("MONEY_DATA").update_cells(cells)
                            load_money_data.clear()
                            st.success("Record Completed!")
                            st.rerun()
                        except Exception as e: st.error(f"Error: {e}")
    else:
        st.success("🎉 Congratulations! You have zero incomplete entries!")
else:
    st.info("No transaction history found.")
