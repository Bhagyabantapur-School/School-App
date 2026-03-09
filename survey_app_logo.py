import streamlit as st
import pandas as pd
from fpdf import FPDF

# Load your students.csv
df = pd.read_csv("students.csv")

class BPS_Survey(FPDF):
    def __init__(self):
        super().__init__()
        # Use your renamed font file
        self.add_font('Bengali', '', 'Bengali.ttf', uni=True)

    def draw_digit_boxes(self, x, y):
        box_size = 6 
        for i in range(10):
            self.rect(x + (i * box_size), y, box_size, box_size)

    def draw_single_form(self, x, y, row):
        # Origin for this quadrant
        self.set_xy(x, y)
        
        # --- Add School Logo ---
        # Positioned at (x, y), scaled to 12mm width
        # Ensure 'logo.png' exists in your folder
        try:
            self.image('logo.png', x, y, 12) 
        except:
            # Fallback if logo is missing so the app doesn't crash
            self.rect(x, y, 12, 12) 
            self.set_font('Arial', 'B', 6)
            self.text(x+1, y+6, "LOGO")

        # --- Header (Adjusted X to make room for Logo) ---
        self.set_font('Arial', 'B', 11)
        self.set_xy(x + 15, y)
        self.cell(80, 6, "Bhagyabantapur Primary School (BPS)", ln=True, align='L')
        
        self.set_font('Bengali', '', 9)
        self.set_x(x + 15)
        self.cell(80, 5, u"অভিভাবক তথ্য যাচাই ফর্ম", ln=True, align='L')
        
        # --- Student Info Table ---
        curr_y = y + 15 # Moved down to avoid overlapping logo/header
        self.rect(x, curr_y, 96, 20) 
        
        self.set_font('Bengali', '', 9)
        # Row 1
        self.text(x + 2, curr_y + 6, f"Student: {row['Name']}")
        self.text(x + 55, curr_y + 6, f"Class: {row['Class']}")
        # Row 2
        self.text(x + 2, curr_y + 12, f"Father: {row['Father']}")
        self.text(x + 55, curr_y + 12, f"Section: {row['Section']}")
        # Row 3
        self.text(x + 2, curr_y + 18, f"Mother: {row['Mother']}")
        self.text(x + 55, curr_y + 18, f"Mobile: {str(row['Mobile']).split('.')[0]}")
        
        # --- Questions Section ---
        self.set_y(curr_y + 24)
        self.set_font('Bengali', '', 9)
        
        # Mobile Question
        self.text(x, self.get_y(), u"এই মোবাইল নম্বরটি কি সঠিক?  হ্যাঁ [   ]  না [   ]")
        self.ln(6)
        self.text(x, self.get_y(), u"সঠিক না হলে, সঠিক নম্বরটি দিন:")
        self.ln(2)
        self.draw_digit_boxes(x, self.get_y())
        
        # WhatsApp Question
        self.ln(12)
        self.text(x, self.get_y(), u"এটি কি আপনার হোয়াটসঅ্যাপ নম্বর?  হ্যাঁ [   ]  না [   ]")
        self.ln(6)
        self.text(x, self.get_y(), u"হোয়াটসঅ্যাপ নম্বর না হলে সেটি দিন:")
        self.ln(2)
        self.draw_digit_boxes(x, self.get_y())
        
        # --- Signature Section ---
        self.ln(15)
        self.set_font('Arial', '', 7)
        self.text(x, self.get_y(), "______________________")
        self.text(x + 60, self.get_y(), "______________________")
        self.set_font('Bengali', '', 8)
        self.text(x, self.get_y() + 4, u"অভিভাবকের স্বাক্ষর")
        self.text(x + 60, self.get_y() + 4, u"তারিখ")

# --- Streamlit UI ---
st.title("📋 BPS Guardian Survey (with Logo)")

selected_indices = st.multiselect(
    "Select Students:", 
    df.index, 
    format_func=lambda x: f"{df.iloc[x]['Name']} (Roll {df.iloc[x]['Roll']})"
)

if st.button("Generate PDF"):
    if not selected_indices:
        st.error("Please select students first!")
    else:
        pdf = BPS_Survey()
        for i in range(0, len(selected_indices), 4):
            pdf.add_page()
            # 4 Quadrants
            coords = [(7, 7), (107, 7), (7, 150), (107, 150)]
            for j, pos in enumerate(coords):
                if i + j < len(selected_indices):
                    pdf.draw_single_form(pos[0], pos[1], df.iloc[selected_indices[i+j]])
        
        pdf_bytes = pdf.output(dest='S').encode('latin-1')
        st.download_button("⬇️ Download BPS Surveys", pdf_bytes, "BPS_Guardian_Survey_Logo.pdf")