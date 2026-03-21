# --- 4. PDF GENERATOR ---
def generate_pdf(students_list, photo_dict):
    pdf = FPDF(orientation='P', unit='mm', format='A4')
    pdf.set_auto_page_break(auto=True, margin=10)
    pdf.add_page()
    
    # Portrait ID Card Standard Size: 54mm width x 86mm height
    x_start, y_start = 12, 12
    card_w, card_h = 54, 86
    x_gap, y_gap = 8, 8
    col, row = 0, 0
    
    for student in students_list:
        x = x_start + (col * (card_w + x_gap))
        y = y_start + (row * (card_h + y_gap))
        
        # Draw Card Border
        pdf.set_draw_color(0, 0, 0)
        pdf.set_line_width(0.3)
        pdf.rect(x, y, card_w, card_h)
        
        # Blue Header
        pdf.set_fill_color(0, 51, 153)
        pdf.rect(x, y, card_w, 12, 'F')
        
        # School Name
        pdf.set_font("Arial", 'B', 7)
        pdf.set_text_color(255, 255, 255)
        pdf.set_xy(x, y+2)
        pdf.cell(card_w, 4, "BHAGYABANTAPUR PRIMARY SCHOOL", 0, 1, 'C')
        pdf.set_font("Arial", '', 5)
        pdf.set_xy(x, y+6)
        pdf.cell(card_w, 3, "Mob: 7908390822  |  SESSION 2026", 0, 1, 'C')
        
        # Centered Photo (Top)
        photo_x, photo_y, photo_w, photo_h = x+18, y+14, 18, 22
        student_id = str(student.get('Sl', 0)) + "_" + str(student.get('Roll', '0'))
        
        if student_id in photo_dict and photo_dict[student_id] is not None:
            temp_path = tempfile.mktemp(suffix=".jpg")
            with open(temp_path, "wb") as f: f.write(photo_dict[student_id])
            try:
                pdf.image(temp_path, x=photo_x, y=photo_y, w=photo_w, h=photo_h)
                pdf.set_draw_color(0, 0, 0); pdf.rect(photo_x, photo_y, photo_w, photo_h)
            except: pass
        else:
            pdf.set_draw_color(200); pdf.rect(photo_x, photo_y, photo_w, photo_h) 
            pdf.set_text_color(150); pdf.set_font("Arial", '', 5)
            pdf.set_xy(photo_x, photo_y+10); pdf.cell(photo_w, 5, "NO PHOTO", 0, 0, 'C')
        
        # Student Name
        pdf.set_text_color(0)
        pdf.set_font("Arial", 'B', 9)
        pdf.set_xy(x, y+37)
        pdf.cell(card_w, 5, str(student.get('Name', '')).upper()[:22], 0, 1, 'C')
        
        # Details
        pdf.set_font("Arial", '', 7)
        detail_x, curr_y, line_h = x+4, y+43, 4
        
        for label, val in [
            ("Father", str(student.get('Father', ''))[:20]), 
            ("Class", f"{student.get('Class', '')} | Sec: {student.get('Section', 'A')}"), 
            ("Roll", str(student.get('Roll', ''))),
            ("DOB", student.get('DOB', '')),
            ("Mob", student.get('Mobile', ''))
        ]:
            pdf.set_xy(detail_x, curr_y)
            pdf.cell(card_w-8, line_h, f"{label}: {val}", 0, 1)
            curr_y += line_h

        # QR Code (Bottom Right)
        qr_data = f"BPS|{student.get('Name', '')}|{student.get('Class', '')}|{student.get('Roll', '')}"
        qr = qrcode.make(qr_data)
        qr_path = tempfile.mktemp(suffix=".png")
        qr.save(qr_path)
        pdf.image(qr_path, x=x+36, y=y+66, w=15, h=15)

        # Footer / Signature
        pdf.set_font("Arial", 'I', 6)
        pdf.set_xy(x, y+78)
        pdf.cell(card_w-4, 3, "Sukhamay Kisku", 0, 1, 'R')
        pdf.set_font("Arial", '', 5)
        pdf.set_xy(x, y+81)
        pdf.cell(card_w-4, 2, "Head Teacher", 0, 0, 'R')
        
        # Grid Math: 3 Columns x 3 Rows = 9 Cards per A4 Page
        col += 1
        if col >= 3: 
            col = 0
            row += 1
        if row >= 3: 
            pdf.add_page()
            col, row = 0, 0
            
    # Streamlit Cloud FPDF compatibility fix
    pdf_output = pdf.output(dest='S')
    if isinstance(pdf_output, str):
        return pdf_output.encode('latin-1')
    else:
        return bytes(pdf_output)
