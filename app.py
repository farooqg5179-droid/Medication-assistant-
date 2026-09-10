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
# Anonymous session
# ---------------------------------------------------
if supabase and "user_id" not in st.session_state:
    try:
        auth_response = supabase.auth.sign_in_anonymously()
        st.session_state.user_id = auth_response.user.id
    except Exception as e:
        st.session_state.user_id = None
        st.warning(f"Could not start Supabase session: {e}")

# ---------------------------------------------------
# App title
# ---------------------------------------------------
st.title("💊 Medication AI Assistant")
st.caption(
    "Educational medication information only. "
    "This AI does not diagnose or prescribe."
)

# ---------------------------------------------------
# Language selection
# ---------------------------------------------------
language = st.selectbox(
    "🌐 Select Language",
    [
        "English",
        "Roman Urdu",
        "Urdu"
    ]
)

# ---------------------------------------------------
# Language instructions
# ---------------------------------------------------
if language == "English":
    language_instruction = """
Reply only in English.
Use simple and clear English.
"""

elif language == "Roman Urdu":
    language_instruction = """
Reply only in Roman Urdu.
Use simple Pakistani Roman Urdu that is easy to understand.
Do not use Urdu script.
Keep medical medicine names in English where appropriate.
"""

else:
    language_instruction = """
Reply only in Urdu.
Use clear and simple Urdu script.
Keep medicine names in English where appropriate.
"""

# ---------------------------------------------------
# User question
# ---------------------------------------------------
question = st.text_input("💬 Ask a medication question")

if question:

    api_key = st.secrets.get("GROQ_API_KEY")

    if not api_key:
        st.error("Groq API key is not configured.")

    else:

        # ---------------------------------------------------
        # Retrieve knowledge base context
        # ---------------------------------------------------
        context = retrieve_context(question)

        # ---------------------------------------------------
        # Groq AI
        # ---------------------------------------------------
        client = Groq(api_key=api_key)

        system_prompt = f"""
You are a Medication Information Assistant.

{language_instruction}

Your responsibilities:

1. Provide general educational information about medicines.
2. Do not diagnose diseases.
3. Do not prescribe medicines.
4. Do not tell users to start, stop, or change prescription medicines.
5. Do not invent medical information.
6. Use the provided verified knowledge-base context as the primary source.
7. If the knowledge base does not contain enough information, clearly say that verified information is not available.
8. For overdose, poisoning, severe allergic reaction, breathing difficulty, unconsciousness, severe chest pain, or other emergencies, advise the user to seek immediate professional medical help.
9. Do not provide personalized prescription or dosage instructions.
10. Keep the answer clear, helpful, and easy to understand.
11. Preserve the medical meaning when translating into the selected language.

Selected language:
{language}
"""

        response = client.chat.completions.create(
            model="openai/gpt-oss-120b",
            messages=[
                {
                    "role": "system",
                    "content": system_prompt
                },
                {
                    "role": "user",
                    "content": f"""
Knowledge base context:

{context}

User question:

{question}
"""
                }
            ],
            temperature=0.2,
            max_tokens=500
        )

        answer = response.choices[0].message.content

        # ---------------------------------------------------
        # Display answer
        # ---------------------------------------------------
        st.markdown("### 🤖 AI Assistant")

        st.markdown(answer)

        # ---------------------------------------------------
        # Retrieved knowledge base
        # ---------------------------------------------------
        with st.expander("🔎 Retrieved Knowledge Base Context"):
            st.write(context)

        # ---------------------------------------------------
        # Save chat history to Supabase
        # ---------------------------------------------------
        if supabase and st.session_state.get("user_id"):

            try:

                supabase.table("medication_chat_messages").insert(
                    [
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
                    ]
                ).execute()

            except Exception as e:

                st.warning(
                    f"Could not save chat history: {e}"
            )
