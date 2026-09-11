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

            signup_email = st.text_input(
                "Email", key="signup_email"
            )

            signup_password = st.text_input(
                "Password",
                type="password",
                key="signup_password"
            )

            with st.expander("📄 Privacy Policy & Medical Disclaimer"):
                st.markdown(""" **Medical Disclaimer:** Yeh app sirf educational/informational purpose ke liye hai. Ye kisi doctor, pharmacist ya qualified healthcare professional ka replacement nahi hai. Is app ki AI dwara di gayi information diagnosis, prescription ya treatment advice nahi hai. Kisi bhi medical decision se pehle apne doctor se mashwara zaroor karein. **Privacy Policy:** - Aapka naam aur email account banane ke liye store kiya jayega. - Aapki chat history Supabase database mein save hogi. - Aapka data kisi third party ke sath share nahi kiya jayega. - Aap kisi bhi waqt apna account aur data delete kar sakte hain. Account banane se aap in terms se agree karte hain. """)

            agree_terms = st.checkbox(
                "Main Privacy Policy aur Medical Disclaimer se agree karta/karti hoon"
            )

            signup_submit = st.form_submit_button("Create Account")

        if signup_submit:

            if not agree_terms:

                st.error(
                    "Account banane ke liye Privacy Policy se agree karna zaroori hai."
                )

            else:

                try:

                    auth_response = supabase.auth.sign_up(
                        {
                            "email": signup_email,
                            "password": signup_password,
                            "options": {
                                "data": {
                                    "full_name": signup_name
                                }
                            },
                        }
                    )

                    if auth_response.session:

                        st.session_state.user_id = auth_response.user.id
                        st.session_state.user_email = auth_response.user.email
                        st.session_state.access_token = auth_response.session.access_token

                        st.success("Account created successfully!")

                        st.rerun()

                    else:

                        st.success(
                            "Account created! Please check your email to confirm "
                            "your account, then log in."
                        )

                except Exception as e:

                    st.error(f"Sign up failed: {e}")

    # Stop here - do not show chat UI until logged in
    st.stop()


# ---------------------------------------------------
# Sidebar - user info + logout + delete account
# ---------------------------------------------------
if supabase and st.session_state.get("user_id"):

    with st.sidebar:

        st.write(
            f"👤 Logged in as: "
            f"**{st.session_state.get('user_email', 'User')}**"
        )

        st.divider()

        # ---------------------------------------------------
        # LOGOUT
        # ---------------------------------------------------
        if st.button(
            "🚪 Logout",
            use_container_width=True
        ):

            try:
                supabase.auth.sign_out()

            except Exception:
                pass

            for key in [
                "user_id",
                "user_email",
                "access_token"
            ]:
                st.session_state.pop(key, None)

            st.rerun()

        st.divider()

        # ---------------------------------------------------
        # DELETE ACCOUNT
        # ---------------------------------------------------
        st.warning("⚠️ Account Deletion")

        delete_confirm = st.checkbox(
            "I understand that deleting my account is permanent.",
            key="delete_account_confirm"
        )

        if st.button(
            "🗑️ Delete My Account",
            use_container_width=True,
            disabled=not delete_confirm
        ):

            try:

                # ---------------------------------------------------
                # Get current Supabase session
                # ---------------------------------------------------
                session = supabase.auth.get_session()

                access_token = None

                # ---------------------------------------------------
                # Get JWT from current Supabase session
                # ---------------------------------------------------
                if session:

                    if hasattr(session, "access_token"):
                        access_token = session.access_token

                    elif hasattr(session, "session") and session.session:
                        access_token = session.session.access_token

                # ---------------------------------------------------
                # Fallback to Streamlit session
                # ---------------------------------------------------
                if not access_token:

                    access_token = st.session_state.get(
                        "access_token"
                    )

                # ---------------------------------------------------
                # Make sure token exists
                # ---------------------------------------------------
                if not access_token:

                    st.error(
                        "Your session has expired. Please login again."
                    )

                else:

                    # ---------------------------------------------------
                    # Save latest token in Streamlit session
                    # ---------------------------------------------------
                    st.session_state.access_token = access_token

                    # ---------------------------------------------------
                    # Keep Supabase client authenticated
                    # ---------------------------------------------------
                    supabase.postgrest.auth(
                        access_token
                    )

                    # ---------------------------------------------------
                    # Call Supabase Edge Function
                    # ---------------------------------------------------
                    response = supabase.functions.invoke(
                        "delete-my-account",
                        invoke_options={
                            "headers": {
                                "Authorization": (
                                    f"Bearer {access_token}"
                                )
                            }
                        }
                    )

                    # ---------------------------------------------------
                    # Check response
                    # ---------------------------------------------------
                    if response:

                        # ---------------------------------------------------
                        # Clear local session
                        # ---------------------------------------------------
                        for key in [
                            "user_id",
                            "user_email",
                            "access_token",
                            "delete_account_confirm"
                        ]:
                            st.session_state.pop(
                                key,
                                None
                            )

                        st.success(
                            "Your account and chat history have been deleted."
                        )

                        st.rerun()

                    else:

                        st.error(
                            "Account deletion failed. Please try again."
                        )

            except Exception as e:

                st.error(
                    f"Account deletion failed: {e}"
                )


# =========================================================
# PREMIUM CHAT UI
# =========================================================

st.markdown(""" <style> .block-container { max-width: 1050px; padding-top: 1.5rem; padding-bottom: 7rem; } #MainMenu {visibility: hidden;} footer {visibility: hidden;} .med-hero { padding: 24px 26px; border: 1px solid rgba(120,120,120,.18); border-radius: 22px; margin-bottom: 18px; background: linear-gradient(135deg, rgba(255,255,255,.08), rgba(120,120,120,.05)); box-shadow: 0 10px 35px rgba(0,0,0,.06); } .med-hero h1 { margin: 0; font-size: clamp(28px, 6vw, 42px); letter-spacing: -1px; } .med-hero p { margin: 8px 0 0; opacity: .72; } .welcome-card { padding: 22px; border-radius: 20px; border: 1px solid rgba(120,120,120,.16); margin: 10px 0 18px; } .welcome-card h3 { margin-top: 0; } .suggestion-title { font-size: 13px; font-weight: 700; opacity: .65; margin: 5px 0 6px; } .suggestion-note { font-size: 12px; opacity: .6; margin-top: 3px; } section[data-testid="stSidebar"] { border-right: 1px solid rgba(120,120,120,.14); } [data-testid="stChatMessage"] { border-radius: 18px; margin-bottom: 8px; } @media (max-width: 700px) { .block-container { padding-left: .8rem; padding-right: .8rem; padding-top: .8rem; } .med-hero { padding: 18px; border-radius: 18px; } .med-hero h1 { font-size: 28px; } } </style> """, unsafe_allow_html=True)

if "chat_messages" not in st.session_state:
    st.session_state.chat_messages = []

if "selected_medicine" not in st.session_state:
    st.session_state.selected_medicine = "None"

with st.sidebar:
    st.markdown("## 💊 Medication AI")
    st.caption("Your medication information assistant")

        if st.button("＋ New Chat", use_container_width=True, key="new_chat"):
    st.session_state.chat_messages = []
    st.session_state.selected_medicine = "None"
    st.session_state.input_version += 1
    st.rerun()

st.markdown(""" <div class="med-hero"> <h1>💊 Medication AI Assistant</h1> <p>Ask medication questions in English, Roman Urdu, or Urdu — the assistant automatically follows your language.</p> </div> """, unsafe_allow_html=True)

if not st.session_state.chat_messages:
    st.markdown(""" <div class="welcome-card"> <h3>👋 How can I help?</h3> <p>Type your medicine name or question below. Medicine suggestions will appear only when you start typing.</p> <p><b>Examples:</b> What is paracetamol used for? &nbsp; • &nbsp; Paracetamol ke side effects kya hain?</p> </div> """, unsafe_allow_html=True)

# ---------------------------------------------------
# Load medicine names
# ---------------------------------------------------
KB_PATH = (
    Path(__file__).resolve().parent
    / "knowledge_base"
    / "medications.json"
)

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

# ---------------------------------------------------
# Show previous chat
# ---------------------------------------------------
for message in st.session_state.chat_messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# ---------------------------------------------------
# ONE chat-style input
# Medicine suggestions appear only while typing.
# ---------------------------------------------------
if "input_version" not in st.session_state:
    st.session_state.input_version = 0

question = st.text_input(
    "",
    key=f"medication_question_{st.session_state.input_version}",
    placeholder="💬 Ask a medication question or type a medicine name…",
    label_visibility="collapsed"
)

# ---------------------------------------------------
# Medicine autocomplete suggestions
# ---------------------------------------------------
typed = question.strip().lower()
suggestions = []

if typed and medicine_names:
    # First prefer medicine names that are contained in the question.
    contained = [
        name for name in medicine_names
        if name.lower() in typed
    ]

    # Then support normal autocomplete such as "nap" -> "Naproxen".
    prefix = [
        name for name in medicine_names
        if name.lower().startswith(typed)
    ]

    suggestions = list(dict.fromkeys(contained + prefix))[:6]

if typed and suggestions:
    st.markdown(
        '<div class="suggestion-title">💊 Medicine suggestions</div>',
        unsafe_allow_html=True
    )

    cols = st.columns(min(3, len(suggestions)))

    for i, medicine in enumerate(suggestions):
        with cols[i % len(cols)]:
            if st.button(
                medicine,
                key=f"medicine_suggestion_{i}_{medicine}",
                use_container_width=True
            ):
                st.session_state.selected_medicine = medicine
                st.rerun()

if st.session_state.selected_medicine != "None":
    st.caption(
        f"💊 Selected medicine: **{st.session_state.selected_medicine}**"
    )

# ---------------------------------------------------
# Send button
# ---------------------------------------------------
send = st.button(
    "➤ Send",
    type="primary",
    use_container_width=True,
    disabled=not bool(question.strip())
)

if send and question.strip():
    user_question = question.strip()

    # Keep the medicine selected from autocomplete.
    selected_medicine = st.session_state.selected_medicine

    st.session_state.chat_messages.append(
        {"role": "user", "content": user_question}
    )

    with st.chat_message("user"):
        st.markdown(user_question)

    retrieval_question = user_question

    if selected_medicine != "None":
        retrieval_question = f"{selected_medicine} {user_question}"

    api_key = st.secrets.get("GROQ_API_KEY")

    if not api_key:
        answer = "Groq API key is not configured."
        st.error(answer)
    else:
        try:
            # ---------------------------------------------------
            # Retrieve knowledge base context
            # ---------------------------------------------------
            context = retrieve_context(retrieval_question)

            # ---------------------------------------------------
            # Groq AI
            # ---------------------------------------------------
            client = Groq(api_key=api_key)

            system_prompt = """ You are a Medication Information Assistant. LANGUAGE: - Automatically detect the language/style of the user's latest message. - If the user writes English, answer in simple English. - If the user writes Roman Urdu, answer in natural, easy Pakistani Roman Urdu. - If the user writes Urdu script, answer in clear, simple Urdu script. - If the user mixes languages, naturally match the user's mixed style. - Do not ask the user to select a language. CORE RULE: Answer exactly what the user asks, but provide a detailed and properly explained answer. The user's question determines the scope. Do not add unrelated medicine information. RESPONSE DETAIL: - Normally provide 2-5 short paragraphs or 4-8 useful bullet points when the knowledge base supports them. - Use simple language. - Do not repeat the user's question. - Keep medicine names in English where appropriate. DO NOT automatically add: - dosage - side effects - precautions - warnings - interactions - alternatives - advantages/disadvantages unless the user asks for them or they are necessary for immediate safety. MEDICAL SAFETY: 1. Provide general educational information only. 2. Do not diagnose diseases. 3. Do not prescribe medicines. 4. Do not tell users to start, stop, or change prescription medicines. 5. Do not provide personalized prescription or dosage instructions. 6. Do not invent medical information. 7. Use the provided verified knowledge-base context as the primary source. 8. If requested information is not present in the knowledge base, clearly say verified information is not available. 9. Preserve the medical meaning when changing language. EMERGENCY SAFETY: If the message describes a possible emergency (such as severe chest pain, severe breathing difficulty, unconsciousness, seizure, severe allergic reaction, suspected overdose/poisoning, severe bleeding, or possible stroke): - Clearly say it may be an emergency. - Advise immediate professional medical help. - For users in Pakistan, advise Rescue 1122 or the nearest emergency department. - Do not give a long medication explanation before emergency guidance. KNOWLEDGE BASE: Use the provided knowledge-base context as the main source. Do not make up facts that are not supported by it. """

            recent_messages = st.session_state.chat_messages[-7:-1]
            history_text = ""

            if recent_messages:
                history_text = "\n\nRecent conversation:\n" + "\n".join(
                    f'{m["role"].title()}: {m["content"]}'
                    for m in recent_messages
                )

            response = client.chat.completions.create(
                model="openai/gpt-oss-120b",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {
                        "role": "user",
                        "content": (
                            f"Knowledge base context:\n{context}\n"
                            f"{history_text}\n\n"
                            f"Latest user question: {user_question}"
                        )
                    }
                ],
                temperature=0.2,
                max_tokens=800
            )

            answer = response.choices[0].message.content

            with st.chat_message("assistant"):
                st.markdown(answer)

                with st.expander("🔎 Retrieved Knowledge Base Context"):
                    st.write(context)

            st.session_state.chat_messages.append(
                {"role": "assistant", "content": answer}
            )

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
                                "content": user_question,
                            },
                            {
                                "user_id": st.session_state.user_id,
                                "role": "assistant",
                                "content": answer,
                            },
                        ]
                    ).execute()
                except Exception as e:
                    st.warning(f"Could not save chat history: {e}")

            # Clear the input and medicine selection after sending.
            st.session_state.selected_medicine = "None"
st.session_state.input_version += 1
st.rerun()
        except Exception as e:
            st.error(f"AI response failed: {e}")
