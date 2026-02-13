import streamlit as st
import pandas as pd
from datetime import datetime
import os

# --- INITIAL SETUP ---
st.set_page_config(page_title="Bhagyabantapur PS Management", layout="wide")
date_today = datetime.now().strftime("%Y-%m-%d")

# Student Database Load karein
if os.path.exists('students.csv'):
    students_df = pd.read_csv('students.csv')
else:
    st.error("Error: students.csv nahi mili!")
    st.stop()

# --- SIDEBAR NAVIGATION ---
st.sidebar.title("🏫 Bhagyabantapur PS")
role = st.sidebar.radio("Apna Role Chunnein:", ["Assistant Teacher (MDM)", "Head Teacher (Attendance)"])

# --- ROLE: ASSISTANT TEACHER (MDM) ---
if role == "Assistant Teacher (MDM)":
    st.header("🍱 Student-wise MDM Checklist")
    
    teacher_list = [
        "BIMAL KUMAR PATRA", "TAPAN KUMAR MANDAL", "SUJATA BISWAS ROTHA", 
        "SUSMITA PAUL", "ROHINI SINGH", "UDAY NARAYAN JANA", 
        "TAPASI RANA", "MANJUMA KHATUN"
    ]
    selected_teacher = st.selectbox("Apna Naam Chunnein", teacher_list)
    
    col1, col2 = st.columns(2)
    with col1:
        sel_class = st.selectbox("Class", students_df['Class'].unique())
    with col2:
        sections = students_df[students_df['Class'] == sel_class]['Section'].unique()
        sel_section = st.selectbox("Section", sections)

    class_list = students_df[(students_df['Class'] == sel_class) & 
                             (students_df['Section'] == sel_section)].copy()

    if not class_list.empty:
        st.write(f"### MDM Register: {sel_class} - {sel_section}")
        class_list['Ate_MDM'] = False
        
        edited_mdm = st.data_editor(
            class_list[['Roll', 'Name', 'Ate_MDM']],
            column_config={"Ate_MDM": st.column_config.CheckboxColumn("MDM Liya?", default=False)},
            disabled=["Roll", "Name"],
            hide_index=True,
            use_container_width=True,
            key=f"mdm_{sel_class}_{sel_section}"
        )
        
        total_mdm = edited_mdm['Ate_MDM'].sum()
        st.metric("Aaj ka Total MDM", total_mdm)

        if st.button("MDM Report Submit Karein"):
            mdm_summary = pd.DataFrame([{
                "Date": date_today, "Class": sel_class, "Section": sel_section, 
                "MDM_Count": total_mdm, "Teacher": selected_teacher
            }])
            mdm_summary.to_csv('mdm_log.csv', mode='a', index=False, header=not os.path.exists('mdm_log.csv'))
            st.success("Report submit ho gayi!")
            st.balloons()

# --- ROLE: HEAD TEACHER (ATTENDANCE) ---
elif role == "Head Teacher (Attendance)":
    st.sidebar.markdown(f"**Head Teacher:** SUKHAMAY KISKU")
    tabs = st.tabs(["📋 Attendance", "📊 Daily Summary", "🍱 MDM Data", "📑 Monthly Reports"])

    # 1. MARK ATTENDANCE
    with tabs[0]:
        st.header("Official Attendance Checklist")
        sel_class_ht = st.selectbox("Class Chunnein", students_df['Class'].unique())
        current_list = students_df[students_df['Class'] == sel_class_ht].copy()
        current_list['Present'] = False
        
        edited_att = st.data_editor(
            current_list[['Roll', 'Name', 'Present']],
            column_config={"Present": st.column_config.CheckboxColumn("Present", default=False)},
            disabled=["Roll", "Name"],
            hide_index=True,
            use_container_width=True,
            key=f"ht_att_{sel_class_ht}"
        )
        
        if st.button("Official Attendance Save Karein"):
            att_data = edited_att.copy()
            att_data['Date'] = date_today
            att_data['Class'] = sel_class_ht
            # Hum saara data save karenge (Present aur Absent dono) taaki reports ban sakein
            att_data.to_csv('attendance_log.csv', mode='a', index=False, header=not os.path.exists('attendance_log.csv'))
            st.success("Attendance save ho gayi!")

    # 2. DAILY SUMMARY
    with tabs[1]:
        st.header("School Reporting Summary")
        if os.path.exists('attendance_log.csv'):
            df_att = pd.read_csv('attendance_log.csv')
            today = df_att[(df_att['Date'] == date_today) & (df_att['Present'] == True)]
            
            if not today.empty:
                pp = len(today[today['Class'] == 'PP'])
                c1_4 = len(today[today['Class'].isin(['CLASS I', 'CLASS II', 'CLASS III', 'CLASS IV'])])
                c5 = len(today[today['Class'] == 'CLASS V'])
                grand_total = len(today)
                perc = (grand_total / len(students_df)) * 100

                st.subheader(f"Aaj ki Stithi: {date_today}")
                c1, c2, c3 = st.columns(3)
                c1.metric("Class PP", pp)
                c2.metric("Class 1 to 4", c1_4)
                c3.metric("Class 5", c5)
                st.divider()
                st.write(f"### **GRAND TOTAL:** {grand_total} | **PERCENTAGE:** {perc:.2f}%")
            else: st.info("Aaj ki attendance abhi tak nahi bhari gayi.")

    # 3. MDM VIEW
    with tabs[2]:
        st.header("Assistant Teachers ki MDM Entry")
        if os.path.exists('mdm_log.csv'):
            df_mdm = pd.read_csv('mdm_log.csv')
            st.dataframe(df_mdm[df_mdm['Date'] == date_today], use_container_width=True)

    # 4. MONTHLY REPORTS & ABSENTEE LIST
    with tabs[3]:
        st.header("📑 Monthly Analysis & Absentee List")
        if os.path.exists('attendance_log.csv'):
            full_att = pd.read_csv('attendance_log.csv')
            full_att['Date'] = pd.to_datetime(full_att['Date'])
            full_att['Month_Year'] = full_att['Date'].dt.strftime('%B %Y')
            
            selected_month = st.selectbox("Mahina Chunnein", full_att['Month_Year'].unique())
            monthly_data = full_att[full_att['Month_Year'] == selected_month]

            # --- Absentee List Section ---
            st.subheader(f"🔴 {selected_month} ki Absentee Report")
            
            # Un bacchon ko filter karein jo absent the
            absent_data = monthly_data[monthly_data['Present'] == False]
            
            if not absent_data.empty:
                # Count karein ki kaun kitni baar absent raha
                absent_summary = absent_data.groupby(['Name', 'Class']).size().reset_index(name='Days Absent')
                absent_summary = absent_summary.sort_values(by='Days Absent', ascending=False)
                
                st.warning("Niche un bacchon ki list hai jo is mahine absent rahe hain (Zyada chutti wale upar hain):")
                st.dataframe(absent_summary, use_container_width=True, hide_index=True)
            else:
                st.success("Is mahine koi bhi absent nahi raha!")

            st.divider()
            
            # Download Button
            csv_data = monthly_data.to_csv(index=False).encode('utf-8')
            st.download_button("📥 Download Full Monthly Data", csv_data, f"Report_{selected_month}.csv", "text/csv")
        else:
            st.info("Data available nahi hai.")