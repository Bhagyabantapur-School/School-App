def generate_pdf(students_list, photo_dict):
    pdf = FPDF(orientation='P', unit='mm', format='A4')
    pdf.set_auto_page_break(auto=True, margin=10)
    pdf.add_page()
    x_start, y_start, card_w, card_h, gap = 10, 10, 86, 54, 8
    col, row = 0, 0
    
    for student in students_list:
        x = x_start + (col * (card_w + gap))
        y = y_start + (row * (card_h + gap))
        
        # Draw Card Background & Header
        pdf.set_draw_color(0, 0, 0); pdf.set_line_width(0.3); pdf.rect(x, y, card_w, card_h)
        pdf.set_fill_color(0, 123, 255); pdf.rect(x, y, card_w, 11, 'F')
        
        # --- LOGO ON THE RIGHT SIDE ---
        if os.path.exists('logo.png'): 
            # Placed on the far right (x + 68.5) so it doesn't touch the photo on the left
            pdf.image('logo.png', x=x+68.5, y=y+1, w=16, h=16)
            
        pdf.set_font("Arial", 'B', 8.5); pdf.set_text_color(255, 255, 255)
        # Shifted school name to the left to fill the space before the logo
        pdf.set_xy(x+2, y+1.5); pdf.cell(66, 5, "BHAGYABANTAPUR PRIMARY SCHOOL", 0, 1, 'C')
        pdf.set_font("Arial", '', 6)
        pdf.set_xy(x+2, y+6.5); pdf.cell(66, 3, "ID CARD - SESSION 2026", 0, 1, 'C')
        
        # Photo (Left Side)
        photo_x, photo_y, photo_w, photo_h = x+3, y+14, 18, 22
        student_id = str(student.get('Sl', 0)) + "_" + str(student.get('Roll', '0'))
        
        if student_id in photo_dict:
            temp_path = tempfile.mktemp(suffix=".jpg")
            with open(temp_path, "wb") as f: f.write(photo_dict[student_id])
            try:
                pdf.image(temp_path, x=photo_x, y=photo_y, w=photo_w, h=photo_h)
                pdf.set_draw_color(0, 0, 0); pdf.rect(photo_x, photo_y, photo_w, photo_h)
            except: pass
        else:
            pdf.set_draw_color(200); pdf.rect(photo_x, photo_y, photo_w, photo_h) 
            pdf.set_text_color(150); pdf.set_font("Arial", '', 5)
            pdf.set_xy(photo_x, y+20); pdf.cell(photo_w, 5, "NO PHOTO", 0, 0, 'C')
        
        # Details (Center)
        pdf.set_text_color(0); detail_x, curr_y, line_h = x+24, y+14, 4
        pdf.set_font("Arial", 'B', 9); pdf.set_xy(detail_x, curr_y)
        # Narrowed the text area slightly so long names don't bump into the hanging logo
        pdf.cell(44, line_h, f"{student.get('Name', '')}".upper()[:25], 0, 1); curr_y += 4.5
        pdf.set_font("Arial", '', 7)
        for label, val in [("Father", student.get('Father', '')), ("Class", f"{student.get('Class', '')} | Sec: {student.get('Section', 'A')}"), ("Roll", f"{student.get('Roll', '')} | Sex: {student.get('Gender', '')}"), ("DOB", f"{student.get('DOB', '')} | Blood: {student.get('BloodGroup', '')}")]:
            pdf.set_xy(detail_x, curr_y); pdf.cell(44, line_h, f"{label}: {val}", 0, 1); curr_y += line_h
        pdf.set_xy(detail_x, curr_y); pdf.set_font("Arial", 'B', 7); pdf.cell(44, line_h, f"Mob: {student.get('Mobile', '')}", 0, 1)

        # QR & Sig
        qr_data = f"Name:{student.get('Name', '')}|Roll:{student.get('Roll', '')}|Mob:{student.get('Mobile', '')}"
        qr = qrcode.make(qr_data); qr_path = tempfile.mktemp(suffix=".png"); qr.save(qr_path)
        pdf.image(qr_path, x=x+4.5, y=y+37, w=15, h=15)
        if os.path.exists('signature.png'): pdf.image('signature.png', x=x+58, y=y+41, w=22, h=8)
        
        pdf.set_font("Arial", 'I', 6); pdf.set_xy(x, y+49); pdf.cell(card_w-5, 3, "Sukhamay Kisku", 0, 1, 'R')
        pdf.set_font("Arial", '', 5); pdf.set_xy(x, y+51); pdf.cell(card_w-5, 2, "Head Teacher", 0, 0, 'R')
        
        col += 1
        if col >= 2: col, row = 0, row + 1
        if row >= 5: pdf.add_page(); col, row = 0, 0
            
    return pdf.output(dest='S').encode('latin-1')
