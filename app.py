import streamlit as st
from rag.retriever import retrieve_context
from services.groq_service import ask_groq
from services.safety import safety_check

st.set_page_config(page_title="Medication AI Assistant", page_icon="💊", layout="centered")

st.title("💊 Medication AI Assistant")
st.caption("Educational medication information only. Not a doctor or a prescription service.")

if "messages" not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

question = st.chat_input("Ask about a medicine...")

if question:
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    safety = safety_check(question)

    if safety["emergency"]:
        answer = safety["message"]
    else:
        context = retrieve_context(question)
        answer = ask_groq(question, context)

    st.session_state.messages.append({"role": "assistant", "content": answer})
    with st.chat_message("assistant"):
        st.markdown(answer)
