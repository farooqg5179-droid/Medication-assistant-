yukiimport os
import streamlit as st
from groq import Groq

st.set_page_config(page_title="Medication AI Assistant", page_icon="💊")

st.title("💊 Medication AI Assistant")
st.caption("Educational medication information only.")

question = st.text_input("Ask a medication question")

if question:
 api_key = st.secrets.get("GROQ_API_KEY")

    if not api_key:
        st.error("Groq API key is not configured.")
    else:
        client = Groq(api_key=api_key)

        response = client.chat.completions.create(
            model="openai/gpt-oss-120b",
            messages=[
                {
                    "role": "system",
                    "content": "You are a Medication Information Assistant. Provide general educational information about medicines. Do not diagnose, prescribe, or tell users to start, stop, or change prescription medicines. Do not invent medical information. For overdose, poisoning, severe allergic reaction, breathing difficulty, unconsciousness, severe chest pain, or other emergencies, advise immediate professional medical help."
                },
                {
                    "role": "user",
                    "content": question
                }
            ],
            temperature=0.2,
            max_tokens=500
        )

        st.write(response.choices[0].message.content)
