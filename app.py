import streamlit as st
from groq import Groq
from supabase import create_client
from rag.retriever import retrieve_context

st.set_page_config(page_title="Medication AI Assistant", page_icon="💊")

# ---------------------------------------------------
# Supabase connection setup
# ---------------------------------------------------
supabase_url = st.secrets.get("SUPABASE_URL")
supabase_key = st.secrets.get("SUPABASE_KEY")

supabase = None
if supabase_url and supabase_key:
    supabase = create_client(supabase_url, supabase_key)
else:
    st.warning("Supabase is not configured. Chat history will not be saved.")

# ---------------------------------------------------
# Anonymous session so every user gets a user_id
# ---------------------------------------------------
if supabase and "user_id" not in st.session_state:
    try:
        auth_response = supabase.auth.sign_in_anonymously()
        st.session_state.user_id = auth_response.user.id
    except Exception as e:
        st.session_state.user_id = None
        st.warning(f"Could not start Supabase session: {e}")

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

        # ---------------------------------------------------
        # Save chat history to Supabase (medication_chat_messages)
        # ---------------------------------------------------
        if supabase and st.session_state.get("user_id"):
            try:
                supabase.table("medication_chat_messages").insert([
                    {
                        "user_id": st.session_state.user_id,
                        "role": "user",
                        "content": question,
                    },
                    {
                        "user_id": st.session_state.user_id,
                        "role": "assistant",
                        "content": answer,
                    },
                ]).execute()
            except Exception as e:
                st.warning(f"Could not save chat history: {e}")
