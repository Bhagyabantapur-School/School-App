import streamlit as st
from PIL import Image
import io

st.set_page_config(page_title="Photo Resizer App")
st.title("📸 Photo Resizer Web App")

if 'resized_images' not in st.session_state:
    st.session_state.resized_images = []

target_size = (150, 150)

uploaded_files = st.file_uploader(
    "Step 1: Upload your original photos", 
    type=['png', 'jpg', 'jpeg'], 
    accept_multiple_files=True
)

if uploaded_files:
    if st.button("Step 2: Resize Photos"):
        st.session_state.resized_images = [] 
        with st.spinner("Resizing your photos..."):
            for uploaded_file in uploaded_files:
                img = Image.open(uploaded_file)
                img.thumbnail(target_size, Image.Resampling.LANCZOS)
                
                buf = io.BytesIO()
                img.save(buf, format=img.format, optimize=True, quality=85)
                byte_im = buf.getvalue()
                
                st.session_state.resized_images.append({
                    "name": f"resized_{uploaded_file.name}",
                    "data": byte_im,
                    "mime": f"image/{img.format.lower()}"
                })
        st.success("✅ Photos resized successfully!")

if st.session_state.resized_images:
    st.write("### Step 3: Download Resized Photos")
    for img_data in st.session_state.resized_images:
        st.download_button(
            label=f"⬇️ Download {img_data['name']}",
            data=img_data['data'],
            file_name=img_data['name'],
            mime=img_data['mime']
        )
