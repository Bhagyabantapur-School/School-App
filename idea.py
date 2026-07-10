import streamlit as st

st.title("💡 Central Brainstorming Hub")

# Input for new ideas
new_idea = st.text_input("Got an idea? Drop it here without judgment:")
if st.button("Submit Idea") and new_idea:
    if "ideas" not in st.session_state:
        st.session_state.ideas = []
    st.session_state.ideas.append(new_idea)

# Display submitted ideas
st.write("### 📌 Current Idea Pool")
if "ideas" in st.session_state and st.session_state.ideas:
    for i, idea in enumerate(st.session_state.ideas, 1):
        st.write(f"**{i}.** {idea}")
else:
    st.info("The board is clear. Start adding ideas!")
