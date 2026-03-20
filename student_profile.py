# --- SIDEBAR: EASY SEARCH ---
st.sidebar.header("Find Student")

class_list = sorted(df_master['Class'].astype(str).unique().tolist())
selected_class = st.sidebar.selectbox("1. Select Class", class_list)

if selected_class:
    filtered_by_class = df_master[df_master['Class'] == selected_class]
    section_list = sorted(filtered_by_class['Section'].astype(str).unique().tolist())
    selected_section = st.sidebar.selectbox("2. Select Section", section_list)
    
    if selected_section:
        # Use .copy() to safely modify the dataframe
        filtered_by_section = filtered_by_class[filtered_by_class['Section'] == selected_section].copy()
        
        # --- THE FIX: Create a unique display name using Name + Roll Number ---
        filtered_by_section['Display_Name'] = filtered_by_section['Name'].astype(str) + " (Roll: " + filtered_by_section['Roll'].astype(str) + ")"
        
        # Sort and display the new unique names
        student_list = sorted(filtered_by_section['Display_Name'].unique().tolist())
        selected_display_name = st.sidebar.selectbox("3. Select Student", student_list)

        if selected_display_name:
            # Filter the master record using the exact Display Name
            student_record = filtered_by_section[filtered_by_section['Display_Name'] == selected_display_name]
            
            if not student_record.empty:
                student = student_record.iloc[0]
                
                # Extract the actual name and roll to use for filtering the logs
                selected_name = student['Name']
                selected_roll = student['Roll']
                
                # --- PROFILE HEADER ---
                st.divider()
                
                raw_code = str(student.get('Student Code', 'N/A'))
                if raw_code.lower() not in ['n/a', 'nan', 'none', '']:
                    raw_code = raw_code.replace("'", "").split('.')[0]
                    display_code = raw_code.zfill(14) 
                else:
                    display_code = "N/A"
                
                head_col1, head_col2 = st.columns([1, 4]) 

                with head_col1:
                    raw_url = student.get('Photo_URL', '')
                    display_student_photo(raw_url)

                with head_col2:
                    st.subheader(f"Profile: {student['Name']}")
                    st.write(f"**Class:** {student['Class']} '{student['Section']}' | **Roll No:** {student['Roll']} | **Student Code:** {display_code}")
                    st.caption(f"**Parents:** {student.get('Father', 'N/A')} & {student.get('Mother', 'N/A')} | **Mobile:** {student.get('Mobile', 'N/A')}")
                
                st.divider()
                
                # --- MAIN DATA MODULES ---
                col1, col2, col3 = st.columns(3)
                
                # MODULE 1: OVERALL ATTENDANCE (Updated with Roll filter)
                with col1:
                    st.write("### 📅 Master Attendance")
                    student_att = df_attendance[
                        (df_attendance['Class'] == selected_class) & 
                        (df_attendance['Section'] == selected_section) & 
                        (df_attendance['Name'] == selected_name) &
                        (df_attendance['Roll'].astype(str) == str(selected_roll)) # Filters by exact Roll
                    ]
                    
                    if not student_att.empty:
                        student_att['Status_Bool'] = student_att['Status'].astype(str).str.lower() == 'true'
                        days_present = student_att['Status_Bool'].sum()
                        total_recorded_days = len(student_att)
                        att_percentage = (days_present / total_recorded_days) * 100 if total_recorded_days > 0 else 0
                        
                        st.metric("Total Days Present", f"{days_present} / {total_recorded_days}")
                        st.progress(min(att_percentage / 100, 1.0))
                        st.caption(f"Current Attendance Rate: {att_percentage:.1f}%")
                    else:
                        st.info("No master attendance records found.")

                # MODULE 2: MDM LOG (Updated with Roll filter)
                with col2:
                    st.write("### 🍛 MDM Participation")
                    student_mdm = df_mdm[
                        (df_mdm['Class'] == selected_class) & 
                        (df_mdm['Section'] == selected_section) & 
                        (df_mdm['Name'] == selected_name) &
                        (df_mdm['Roll'].astype(str) == str(selected_roll)) # Filters by exact Roll
                    ]
                    
                    mdm_days = len(student_mdm)
                    st.metric("Mid-Day Meals Taken", f"{mdm_days} Days")
                    
                    if not student_mdm.empty:
                        st.write("**Recent MDM Activity:**")
                        recent_mdm = student_mdm.tail(5)[['Date', 'Time']].sort_values(by='Date', ascending=False)
                        st.dataframe(recent_mdm, hide_index=True, use_container_width=True)
                    else:
                        st.info("No MDM entries found.")

                # MODULE 3: ADMINISTRATIVE / FORMS (Updated with Roll filter)
                with col3:
                    st.write("### 📋 Admin & Forms")
                    student_forms = df_forms[
                        (df_forms['Class'] == selected_class) & 
                        (df_forms['Section'] == selected_section) & 
                        (df_forms['Student Name'] == selected_name) &
                        (df_forms['Roll'].astype(str) == str(selected_roll)) # Filters by exact Roll
                    ]
                    
                    if not student_forms.empty:
                        form_data = student_forms.iloc[0]
                        
                        status = form_data.get('Return Status', 'Unknown')
                        if status == 'Complete':
                            st.success(f"**Form Status:** {status}")
                        else:
                            st.warning(f"**Form Status:** {status}")
                            
                        wa_status = form_data.get('WhatsApp Added', 'No')
                        wa_group = form_data.get('WhatsApp Group', 'None')
                        if wa_status != 'No':
                            st.info(f"📱 **WhatsApp:** {wa_status} ({wa_group})")
                        else:
                            st.error("📱 **WhatsApp:** Not Added")
                            
                        st.caption(f"Last updated on Banglar Shiksha: {form_data.get('Banglar Shiksha Updated', 'No')}")
                    else:
                        st.info("No form distribution records found.")
