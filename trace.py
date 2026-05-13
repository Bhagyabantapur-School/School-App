import streamlit as st
import math
import qrcode
from fpdf import FPDF
import tempfile
import os

# --- Layout Configuration for A4 Paper ---
# Standard A4 size is 210mm x 297mm
LABELS_PER_ROW = 3
ROWS_PER_PAGE = 7
LABELS_PER_PAGE = LABELS_PER_ROW * ROWS_PER_PAGE

A4_WIDTH = 210
A4_HEIGHT = 297
MARGIN_X = 10
MARGIN_Y = 10

# Calculate individual label dimensions
LABEL_W = (A4_WIDTH - (2 * MARGIN_X)) / LABELS_PER_ROW
LABEL_H = (A4_HEIGHT - (2 * MARGIN_Y)) / ROWS_PER_PAGE

def generate_label_pdf(item_type, description, location, quantity):
    pdf = FPDF(orientation='P', unit='mm', format='A4')
    pdf.set_auto_page_break(auto=False)
    pdf.add_page()
    pdf.set_font("helvetica", size=8)

    # Use a temporary directory to store the QR code images before embedding them
    with tempfile.TemporaryDirectory() as temp_dir:
        for i in range(quantity):
            # Calculate current row, column, and page
            current_label_on_page = i % LABELS_PER_PAGE
            if i > 0 and current_label_on_page == 0:
                pdf.add_page()

            col = current_label_on_page % LABELS_PER_ROW
            row = current_label_on_page // LABELS_PER_ROW

            # Calculate X and Y coordinates on the A4 page
            x = MARGIN_X + (col * LABEL_W)
            y = MARGIN_Y + (row * LABEL_H)

            # Generate unique QR Code data (e.g., adding a sequential ID for batch printing)
            unique_id = f"{item_type[:3].upper()}-{i+1:03d}"
            qr_data = f"ID: {unique_id}\nType: {item_type}\nDesc: {description}\nLoc: {location}"
            
            # Create and save the QR code image
            qr = qrcode.make(qr_data)
            qr_path = os.path.join(temp_dir, f"qr_{i}.png")
            qr.save(qr_path)

            # Draw a subtle border for the label (optional, helps with cutting)
            pdf.rect(x, y, LABEL_W, LABEL_H)

            # Place the QR Code (sizing it to fit nicely inside the label)
            qr_size = LABEL_H - 15 
            pdf.image(qr_path, x=x + 2, y=y + 2, w=qr_size, h=qr_size)

            # Place the Text next to the QR code
            text_x = x + qr_size + 4
            text_y = y + 8
            pdf.text(x=text_x, y=text_y, text=f"ID: {unique_id}")
            pdf.text(x=text_x, y=text_y + 4, text=f"{item_type}")
            
            # Handle slightly longer descriptions
            short_desc = description[:20] + "..." if len(description) > 20 else description
            pdf.text(x=text_x, y=text_y + 8, text=f"{short_desc}")
            pdf.text(x=text_x, y=text_y + 12, text=f"Loc: {location}")

    # Output the PDF as bytes
    return pdf.output(dest="S")

# --- Streamlit UI ---
st.subheader("Generate QR Asset Labels")

with st.form("batch_label_form"):
    col1, col2 = st.columns(2)
    with col1:
        item_type = st.text_input("Item Type", placeholder="e.g., Wireless Audio")
        description = st.text_input("Description", placeholder="e.g., DJI Mic Mini TX unit")
    with col2:
        # Pre-populate with locations relevant to your setup
        location = st.selectbox("Storage Location", [
            "Studio Gear Box 1", 
            "School Office - Cabinet A", 
            "Computer Lab", 
            "Everyday Carry (Backpack)"
        ])
        quantity = st.number_input("Quantity to Generate", min_value=1, value=10, step=1)
    
    generate_btn = st.form_submit_button("Preview & Generate PDF")

if generate_btn and item_type and description:
    # --- Math for UI Feedback ---
    pages_needed = math.ceil(quantity / LABELS_PER_PAGE)
    slots_filled_on_last_page = quantity % LABELS_PER_PAGE
    
    if slots_filled_on_last_page == 0:
        slots_filled_on_last_page = LABELS_PER_PAGE # It perfectly divided
        
    is_fully_completed = slots_filled_on_last_page == LABELS_PER_PAGE
    empty_slots = LABELS_PER_PAGE - slots_filled_on_last_page

    # --- Display Metrics ---
    st.markdown("### Print Job Summary")
    m1, m2, m3 = st.columns(3)
    m1.metric("A4 Pages Required", pages_needed)
    m2.metric("Total Labels", quantity)
    
    if is_fully_completed:
        m3.success("✅ The final A4 page is perfectly full!")
    else:
        m3.warning(f"⚠️ Last page has {empty_slots} blank sticker slots.")

    # --- Generate PDF ---
    with st.spinner("Generating PDF with QR codes..."):
        pdf_bytes = generate_label_pdf(item_type, description, location, quantity)
        
    st.download_button(
        label="📄 Download A4 Print Sheet (PDF)",
        data=pdf_bytes,
        file_name=f"Trace_Labels_{item_type.replace(' ', '_')}.pdf",
        mime="application/pdf",
        type="primary"
    )
elif generate_btn:
    st.error("Please fill in the Item Type and Description.")
