import streamlit as st
import json
from pathlib import Path
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
# Keep the Supabase client authenticated on every rerun
# (Streamlit reruns the whole script on every interaction)
# ---------------------------------------------------
if supabase and st.session_state.get("access_token"):
    supabase.postgrest.auth(st.session_state.access_token)

# ---------------------------------------------------
# LOGIN / SIGNUP SCREEN
# Shown only if user is not logged in
# ---------------------------------------------------
if supabase and "user_id" not in st.session_state:

    st.title("💊 Medication AI Assistant")
    st.caption("Please log in or create an account to continue.")

    tab_login, tab_signup = st.tabs(["Login", "Sign Up"])

    # ---------------- LOGIN TAB ----------------
    with tab_login:
        with st.form("login_form"):
            login_email = st.text_input("Email", key="login_email")
            login_password = st.text_input(
                "Password", type="password", key="login_password"
            )
            login_submit = st.form_submit_button("Login")

        if login_submit:
            try:
                auth_response = supabase.auth.sign_in_with_password(
                    {"email": login_email, "password": login_password}
                )
                st.session_state.user_id = auth_response.user.id
                st.session_state.user_email = auth_response.user.email
                st.session_state.access_token = auth_response.session.access_token
                st.rerun()
            except Exception as e:
                st.error(f"Login failed: {e}")

    # ---------------- SIGNUP TAB ----------------
    with tab_signup:
        with st.form("signup_form"):
            signup_name = st.text_input("Full Name", key="signup_name")
            signup_email = st.text_input("Email", key="signup_email")
            signup_password = st.text_input(
                "Password", type="password", key="signup_password"
            )
            signup_submit = st.form_submit_button("Create Account")

        if signup_submit:
            try:
                auth_response = supabase.auth.sign_up(
                    {
                        "email": signup_email,
                        "password": signup_password,
                        "options": {"data": {"full_name": signup_name}},
                    }
                )
                if auth_response.session:
                    # Email confirmation is OFF -> user is logged in immediately
                    st.session_state.user_id = auth_response.user.id
                    st.session_state.user_email = auth_response.user.email
                    st.session_state.access_token = auth_response.session.access_token
                    st.success("Account created successfully!")
                    st.rerun()
                else:
                    # Email confirmation is ON -> user must verify email first
                    st.success(
                        "Account created! Please check your email to confirm "
                        "your account, then log in."
                    )
            except Exception as e:
                st.error(f"Sign up failed: {e}")

    # Stop here - do not show the chat UI until logged in
    st.stop()

# ---------------------------------------------------
# Sidebar - user info + logout (only shown when logged in)
# ---------------------------------------------------
if supabase and st.session_state.get("user_id"):
    with st.sidebar:
        st.write(f"👤 Logged in as: **{st.session_state.get('user_email', 'User')}**")
        if st.button("Logout"):
            try:
                supabase.auth.sign_out()
            except Exception:
                pass
            for key in ["user_id", "user_email", "access_token"]:
                st.session_state.pop(key, None)
            st.rerun()

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
    language_instruction = """ Reply only in English. Use simple and clear English. """

elif language == "Roman Urdu":
    language_instruction = """ Reply only in Roman Urdu. Use simple Pakistani Roman Urdu that is easy to understand. Do not use Urdu script. Keep medical medicine names in English where appropriate. """

else:
    language_instruction = """ Reply only in Urdu. Use clear and simple Urdu script. Keep medicine names in English where appropriate. """

# ---------------------------------------------------
# Medicine Search / Autocomplete
# ---------------------------------------------------
KB_PATH = Path(__file__).resolve().parent / "knowledge_base" / "medications.json"

try:
    with open(KB_PATH, "r", encoding="utf-8") as file:
        medication_records = json.load(file)

    medicine_names = sorted(
        {
            record.get("medicine_name", "").strip()
            for record in medication_records
            if record.get("medicine_name", "").strip()
        }
    )

except Exception:
    medicine_names = []

selected_medicine = st.selectbox(
    "🔎 Search Medicine",
    ["None"] + medicine_names,
    index=0,
    help="Type the first letters of a medicine name to find it quickly."
)

# ---------------------------------------------------
# User question
# ---------------------------------------------------
question = st.text_input("💬 Ask a medication question")

# Add the selected medicine to the retrieval query without changing
# what the user sees or saves as their original question.
retrieval_question = question

if question and selected_medicine != "None":
    retrieval_question = f"{selected_medicine} {question}"

if question:

    api_key = st.secrets.get("GROQ_API_KEY")

    if not api_key:
        st.error("Groq API key is not configured.")

    else:

        # ---------------------------------------------------
        # Retrieve knowledge base context
        # ---------------------------------------------------
        context = retrieve_context(retrieval_question)

        # ---------------------------------------------------
        # Groq AI
        # ---------------------------------------------------
        client = Groq(api_key=api_key)

        system_prompt = f"""You are a Medication Information Assistant.

{language_instruction}

CORE RULE:
Answer exactly what the user asks, but provide a detailed and properly explained answer.

The user's question determines the scope of your answer. Do not add unrelated medicine information.

RESPONSE DETAIL:
- Give a detailed and well-explained answer.
- Normally provide 2-5 short paragraphs or 4-8 useful bullet points when the knowledge base supports them.
- Explain the requested topic clearly with relevant details and useful context.
- Do not make the answer unnecessarily short.
- If the user asks a simple question, still provide enough explanation to make the answer useful.
- Do not repeat the user's question.
- Use simple and easy-to-understand language.
- Preserve the selected language.

EXAMPLES:
- If the user asks "What is paracetamol used for?" → explain its common uses in detail.
- If the user asks "What are the side effects of paracetamol?" → explain the relevant common side effects clearly.
- If the user asks "What is paracetamol?" → give a clear and detailed basic explanation.
- If the user asks about precautions → explain the relevant precautions in detail.
- If the user asks about warnings → explain the relevant warnings clearly.
- If the user asks about interactions → provide relevant interactions only when verified information is available.

DO NOT automatically add:
- dosage
- side effects
- precautions
- warnings
- interactions
- alternatives
- advantages
- disadvantages
- other medicine information

unless the user specifically asks for them or they are necessary for immediate safety.

MEDICAL SAFETY:
1. Provide general educational information only.
2. Do not diagnose diseases.
3. Do not prescribe medicines.
4. Do not tell users to start, stop, or change prescription medicines.
5. Do not provide personalized prescription or dosage instructions.
6. Do not invent medical information.
7. Use the provided verified knowledge-base context as the primary source.
8. If the requested information is not present in the knowledge base, clearly say that verified information is not available.
9. Preserve the medical meaning when responding in the selected language.

EMERGENCY SAFETY:
If the user's message describes a possible medical emergency, prioritize emergency guidance.

Examples:
- severe chest pain
- severe difficulty breathing
- unconsciousness
- seizure
- severe allergic reaction
- suspected overdose or poisoning
- severe bleeding
- possible stroke
- another immediately life-threatening situation

For emergencies:
1. Clearly state that it may be an emergency.
2. Advise immediate professional medical help.
3. For users in Pakistan, advise calling Rescue 1122 or going to the nearest emergency department.
4. Do not give a long medication explanation before emergency guidance.

KNOWLEDGE BASE RULE:
- Use the provided knowledge-base context as the main source.
- Do not make up facts that are not supported by the knowledge base.
- If information is unavailable, clearly say that verified information is not available.

Selected language: {language}
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
                    "content": f""" Knowledge base context: {context} User question: {question} """
                }
            ],
            temperature=0.2,
            max_tokens=800
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
