import streamlit as st
from groq import Groq
from rag.retriever import retrieve_context

st.set_page_config(page_title="Medication AI Assistant", page_icon="💊")

st.title("💊 Medication AI Assistant")
st.caption("Educational medication information only. This AI does not diagnose or prescribe.")

question = st.text_input("Ask a medication question")

if question:
    api_key = st.secrets.get("GROQ_API_KEY")

    if not api_key:
        st.error("Groq API key is not configured.")
    else:
        context = retrieve_context(question)

        client = Groq(api_key=api_key)

        response = client.chat.completions.create(
            model="openai/gpt-oss-120b",
            messages=[
                {
                    "role": "system",
                    "content": "You are a Medication Information Assistant. Provide general educational information about medicines. Do not diagnose diseases. Do not prescribe medicines. Do not tell users to start, stop, or change prescription medicines. Do not invent medical information. Use the provided knowledge-base context as the primary source. If the knowledge base does not contain enough information, clearly say that verified information is not available. For overdose, poisoning, severe allergic reaction, breathing difficulty, unconsciousness, severe chest pain, or other emergencies, advise immediate professional medical help."
                },
                {
                    "role": "user",
                    "content": f"Knowledge base context:\\n{context}\\n\\nUser question:\\n{question}"
                }
            ],
            temperature=0.2,
            max_tokens=500
        )

        answer = response.choices[0].message.content

        st.markdown(answer)

        with st.expander("🔎 Retrieved Knowledge Base Context"):
            st.write(context)
