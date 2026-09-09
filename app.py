import streamlit as st

st.set_page_config(page_title="Medication AI Assistant", page_icon="💊")

st.title("💊 Medication AI Assistant")
st.write("Welcome to the Medication AI Assistant.")

st.info("This AI assistant provides general educational information about medicines. It does not diagnose, prescribe, or replace a doctor or pharmacist.")

st.subheader("Ask a Medication Question")

question = st.text_input("Enter your question")

if question:
    st.write("Your question:", question)
    st.success("Question received successfully.")
