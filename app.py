import streamlit as st
import json
from pathlib import Path
from groq import Groq
from supabase import create_client
from rag.retriever import retrieve_context


# =========================================================
# PAGE CONFIG
# =========================================================

st.set_page_config(
    page_title="Medication AI Assistant",
    page_icon="💊",
    layout="wide",
    initial_sidebar_state="expanded",
)


# =========================================================
# PREMIUM CHATGPT-STYLE UI
# =========================================================

st.markdown(
    """ <style> /* ---------- App background ---------- */ .stApp { background: linear-gradient(180deg, #f8fafc 0%, #ffffff 35%, #ffffff 100%); } .block-container { max-width: 1050px; padding-top: 1.2rem; padding-bottom: 7rem; } /* ---------- Sidebar ---------- */ section[data-testid="stSidebar"] { background: #f8fafc; border-right: 1px solid #e5e7eb; } section[data-testid="stSidebar"] .block-container { padding-top: 1.2rem; } /* ---------- Brand ---------- */ .brand { display: flex; align-items: center; gap: 12px; padding: 4px 2px 16px 2px; } .brand-icon { width: 44px; height: 44px; border-radius: 14px; display: flex; align-items: center; justify-content: center; background: #111827; color: white; font-size: 23px; box-shadow: 0 8px 24px rgba(17, 24, 39, 0.15); } .brand-title { font-size: 18px; font-weight: 750; color: #111827; line-height: 1.1; } .brand-subtitle { font-size: 12px; color: #6b7280; margin-top: 3px; } /* ---------- Main header ---------- */ .hero { text-align: center; padding: 20px 10px 12px 10px; } .hero-icon { width: 62px; height: 62px; margin: 0 auto 14px auto; border-radius: 20px; display: flex; align-items: center; justify-content: center; background: #111827; color: white; font-size: 31px; box-shadow: 0 12px 30px rgba(17, 24, 39, 0.18); } .hero-title { font-size: 32px; font-weight: 800; color: #111827; letter-spacing: -0.8px; } .hero-subtitle { margin-top: 7px; color: #6b7280; font-size: 14px; } /* ---------- Welcome ---------- */ .welcome-card { max-width: 720px; margin: 35px auto 22px auto; padding: 28px; border: 1px solid #e5e7eb; border-radius: 22px; background: rgba(255,255,255,0.9); box-shadow: 0 12px 35px rgba(15,23,42,0.06); text-align: center; } .welcome-title { font-size: 24px; font-weight: 750; color: #111827; margin-bottom: 7px; } .welcome-text { color: #6b7280; font-size: 14px; line-height: 1.65; } /* ---------- Medicine selector ---------- */ .medicine-card { border: 1px solid #e5e7eb; border-radius: 16px; padding: 10px 12px 2px 12px; background: white; margin-bottom: 12px; } /* ---------- Chat bubbles ---------- */ div[data-testid="stChatMessage"] { border-radius: 18px; padding: 10px 12px; margin: 8px 0; } /* ---------- Chat input ---------- */ div[data-testid="stChatInput"] { padding-bottom: 8px; } div[data-testid="stChatInput"] textarea { border-radius: 18px; } /* ---------- Buttons ---------- */ .stButton > button { border-radius: 12px; min-height: 42px; font-weight: 600; } /* ---------- Small labels ---------- */ .section-label { color: #6b7280; font-size: 12px; font-weight: 650; text-transform: uppercase; letter-spacing: 0.6px; margin: 5px 0 7px 2px; } /* ---------- Mobile ---------- */ @media (max-width: 768px) { .block-container { padding-left: 12px; padding-right: 12px; padding-top: 0.7rem; } .hero-title { font-size: 25px; } .hero-icon { width: 54px; height: 54px; border-radius: 17px; font-size: 27px; } .welcome-card { margin-top: 22px; padding: 22px 16px; } .welcome-title { font-size: 21px; } } </style> """,
    unsafe_allow_html=True,
)


# =========================================================
# SESSION STATE
# =========================================================

if "chat_messages" not in st.session_state:
    st.session_state.chat_messages = []

if "selected_medicine" not in st.session_state:
    st.session_state.selected_medicine = "None"


# =========================================================
# SUPABASE CONNECTION SETUP
# =========================================================

supabase_url = st.secrets.get("SUPABASE_URL")
supabase_key = st.secrets.get("SUPABASE_KEY")

supabase = None

if supabase_url and supabase_key:
    supabase = create_client(supabase_url, supabase_key)
else:
    st.warning("Supabase is not configured. Chat history will not be saved.")


# =========================================================
# KEEP SUPABASE CLIENT AUTHENTICATED
# =========================================================

if supabase and st.session_state.get("access_token"):
    supabase.postgrest.auth(st.session_state.access_token)


# =========================================================
# LOGIN / SIGNUP SCREEN
# =========================================================

if supabase and "user_id" not in st.session_state:

    st.markdown(
        """ <div class="hero"> <div class="hero-icon">💊</div> <div class="hero-title">Medication AI Assistant</div> <div class="hero-subtitle"> Clear, educational medication information powered by AI </div> </div> """,
        unsafe_allow_html=True,
    )

    tab_login, tab_signup = st.tabs(["🔐 Login", "📝 Sign Up"])

    # ---------------- LOGIN ----------------

    with tab_login:
        with st.form("login_form"):
            login_email = st.text_input("Email", key="login_email")
            login_password = st.text_input(
                "Password",
                type="password",
                key="login_password",
            )
            login_submit = st.form_submit_button(
                "Login",
                use_container_width=True,
            )

        if login_submit:
            try:
                auth_response = supabase.auth.sign_in_with_password(
                    {
                        "email": login_email,
                        "password": login_password,
                    }
                )

                st.session_state.user_id = auth_response.user.id
                st.session_state.user_email = auth_response.user.email
                st.session_state.access_token = auth_response.session.access_token
                st.session_state.chat_messages = []

                st.rerun()

            except Exception as e:
                st.error(f"Login failed: {e}")

    # ---------------- SIGNUP ----------------

    with tab_signup:
        with st.form("signup_form"):
            signup_name = st.text_input("Full Name", key="signup_name")
            signup_email = st.text_input("Email", key="signup_email")
            signup_password = st.text_input(
                "Password",
                type="password",
                key="signup_password",
            )

            with st.expander("📄 Privacy Policy & Medical Disclaimer"):
                st.markdown(
                    """ **Medical Disclaimer** Yeh app sirf educational/informational purpose ke liye hai. Ye kisi doctor, pharmacist ya qualified healthcare professional ka replacement nahi hai. Is app ki AI information diagnosis, prescription ya treatment advice nahi hai. Kisi bhi medical decision se pehle apne doctor se mashwara zaroor karein. **Privacy Policy** - Aapka naam aur email account banane ke liye store kiya jayega. - Aapki chat history Supabase database mein save hogi. - Aapka data kisi third party ke sath share nahi kiya jayega. - Aap kisi bhi waqt apna account aur data delete kar sakte hain. Account banane se aap in terms se agree karte hain. """
                )

            agree_terms = st.checkbox(
                "Main Privacy Policy aur Medical Disclaimer se agree karta/karti hoon"
            )

            signup_submit = st.form_submit_button(
                "Create Account",
                use_container_width=True,
            )

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
                        st.session_state.chat_messages = []

                        st.success("Account created successfully!")
                        st.rerun()
                    else:
                        st.success(
                            "Account created! Please check your email to confirm "
                            "your account, then log in."
                        )

                except Exception as e:
                    st.error(f"Sign up failed: {e}")

    st.stop()


# =========================================================
# SIDEBAR
# =========================================================

if supabase and st.session_state.get("user_id"):

    with st.sidebar:

        st.markdown(
            """ <div class="brand"> <div class="brand-icon">💊</div> <div> <div class="brand-title">Medication AI</div> <div class="brand-subtitle">Your medication assistant</div> </div> </div> """,
            unsafe_allow_html=True,
        )

        if st.button("＋ New Chat", use_container_width=True):
            st.session_state.chat_messages = []
            st.session_state.selected_medicine = "None"
            st.rerun()

        st.divider()

        st.markdown("**👤 Account**")
        st.caption(st.session_state.get("user_email", "User"))

        st.divider()

        if st.button("🚪 Logout", use_container_width=True):
            try:
                supabase.auth.sign_out()
            except Exception:
                pass

            for key in [
                "user_id",
                "user_email",
                "access_token",
                "chat_messages",
                "delete_account_confirm",
            ]:
                st.session_state.pop(key, None)

            st.rerun()

        st.divider()

        st.markdown("**⚠️ Account Deletion**")

        delete_confirm = st.checkbox(
            "I understand that deleting my account is permanent.",
            key="delete_account_confirm",
        )

        if st.button(
            "🗑️ Delete My Account",
            use_container_width=True,
            disabled=not delete_confirm,
        ):
            try:
                session = supabase.auth.get_session()
                access_token = None

                if session:
                    if hasattr(session, "access_token"):
                        access_token = session.access_token
                    elif hasattr(session, "session") and session.session:
                        access_token = session.session.access_token

                if not access_token:
                    access_token = st.session_state.get("access_token")

                if not access_token:
                    st.error("Your session has expired. Please login again.")
                else:
                    st.session_state.access_token = access_token
                    supabase.postgrest.auth(access_token)

                    response = supabase.functions.invoke(
                        "delete-my-account",
                        invoke_options={
                            "headers": {
                                "Authorization": f"Bearer {access_token}"
                            }
                        },
                    )

                    if response:
                        for key in [
                            "user_id",
                            "user_email",
                            "access_token",
                            "delete_account_confirm",
                            "chat_messages",
                        ]:
                            st.session_state.pop(key, None)

                        st.success(
                            "Your account and chat history have been deleted."
                        )
                        st.rerun()
                    else:
                        st.error(
                            "Account deletion failed. Please try again."
                        )

            except Exception as e:
                st.error(f"Account deletion failed: {e}")


# =========================================================
# APP HEADER
# =========================================================

st.markdown(
    """ <div class="hero"> <div class="hero-icon">💊</div> <div class="hero-title">Medication AI Assistant</div> <div class="hero-subtitle"> Educational medication information powered by AI </div> </div> """,
    unsafe_allow_html=True,
)


# =========================================================
# MEDICINE DATABASE
# =========================================================

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


# =========================================================
# MEDICINE SEARCH
# =========================================================

st.markdown('<div class="section-label">Medicine</div>', unsafe_allow_html=True)

st.markdown('<div class="medicine-card">', unsafe_allow_html=True)

selected_medicine = st.selectbox(
    "🔎 Search Medicine",
    ["None"] + medicine_names,
    index=0,
    key="medicine_selector",
    label_visibility="collapsed",
    help="Search for a medicine before asking your question.",
)

st.markdown("</div>", unsafe_allow_html=True)


# =========================================================
# WELCOME SCREEN
# =========================================================

if not st.session_state.chat_messages:

    st.markdown(
        """ <div class="welcome-card"> <div class="welcome-title">How can I help you?</div> <div class="welcome-text"> Ask about a medicine, its uses, precautions, side effects, warnings, interactions, or other verified information. <br><br> You can write in <b>English, Roman Urdu, Urdu, or naturally mix them.</b> </div> </div> """,
        unsafe_allow_html=True,
    )


# =========================================================
# DISPLAY CHAT HISTORY
# =========================================================

for message in st.session_state.chat_messages:

    with st.chat_message(message["role"]):
        st.markdown(message["content"])


# =========================================================
# CHAT INPUT
# =========================================================

question = st.chat_input(
    "Ask a medication question..."
)


# =========================================================
# PROCESS USER QUESTION
# =========================================================

if question:

    # Add user message immediately
    st.session_state.chat_messages.append(
        {
            "role": "user",
            "content": question,
        }
    )

    with st.chat_message("user"):
        st.markdown(question)

    # -----------------------------------------------------
    # Medicine retrieval query
    # -----------------------------------------------------

    retrieval_question = question

    if selected_medicine != "None":
        retrieval_question = f"{selected_medicine} {question}"

    # -----------------------------------------------------
    # Groq API
    # -----------------------------------------------------

    api_key = st.secrets.get("GROQ_API_KEY")

    if not api_key:

        error_message = "Groq API key is not configured."

        st.session_state.chat_messages.append(
            {
                "role": "assistant",
                "content": error_message,
            }
        )

        with st.chat_message("assistant"):
            st.error(error_message)

    else:

        try:

            # -------------------------------------------------
            # Retrieve knowledge base context
            # -------------------------------------------------

            context = retrieve_context(retrieval_question)

            # -------------------------------------------------
            # Groq client
            # -------------------------------------------------

            client = Groq(api_key=api_key)

            # -------------------------------------------------
            # Automatic language detection
            # -------------------------------------------------
            # No language selector is used.
            # The AI follows the language/style of the latest user message.

            system_prompt = """ You are a Medication Information Assistant. LANGUAGE RULE: Automatically detect the language and writing style of the user's latest message. Reply in the SAME language and writing style used by the user. Examples: User: What is paracetamol used for? Reply in simple English. User: Paracetamol kis liye use hoti hai? Reply in simple Pakistani Roman Urdu. User: پیراسیٹامول کس لیے استعمال ہوتی ہے؟ Reply in simple Urdu script. If the user naturally mixes English and Roman Urdu, reply naturally in the same mixed style. Do NOT ask the user to select a language. Do NOT mention language detection. MEDICAL RESPONSE RULES: Answer exactly what the user asks. Give a useful and properly explained answer, but do not add unrelated medicine information. Normally provide: - 2-5 short paragraphs OR - 4-8 useful bullet points. Use simple language. Do not unnecessarily repeat the user's question. Do not automatically add: - dosage - side effects - precautions - warnings - interactions - alternatives - advantages - disadvantages unless the user asks about them or they are necessary for immediate safety. MEDICAL SAFETY: 1. Provide general educational information only. 2. Do not diagnose diseases. 3. Do not prescribe medicines. 4. Do not tell users to start, stop, or change prescription medicines. 5. Do not provide personalized prescription or dosage instructions. 6. Do not invent medical information. 7. Use the provided verified knowledge-base context as the primary source. 8. If requested information is not available in the knowledge base, clearly say that verified information is not available. 9. Preserve medical meaning when responding in another language. EMERGENCY SAFETY: If the user's message describes a possible medical emergency, prioritize emergency guidance. Examples: - severe chest pain - severe difficulty breathing - unconsciousness - seizure - severe allergic reaction - suspected overdose or poisoning - severe bleeding - possible stroke - another immediately life-threatening situation For emergencies: 1. Clearly state that it may be an emergency. 2. Advise immediate professional medical help. 3. For users in Pakistan, advise calling Rescue 1122 or going to the nearest emergency department. 4. Do not give a long medication explanation before emergency guidance. KNOWLEDGE BASE RULE: Use the provided knowledge-base context as the main source. Do not make up facts that are not supported by the knowledge base. If information is unavailable, clearly say: "Verified information is not available in the current knowledge base." """

            # -------------------------------------------------
            # Build conversation context
            # -------------------------------------------------

            recent_messages = st.session_state.chat_messages[-8:]

            messages = [
                {
                    "role": "system",
                    "content": system_prompt,
                }
            ]

            # Exclude the newest user message here because it is
            # sent separately with the knowledge-base context below.
            for msg in recent_messages[:-1]:
                messages.append(
                    {
                        "role": msg["role"],
                        "content": msg["content"],
                    }
                )

            messages.append(
                {
                    "role": "user",
                    "content": (
                        f"Knowledge base context:\n{context}\n\n"
                        f"User question:\n{question}"
                    ),
                }
            )

            # -------------------------------------------------
            # Groq response
            # -------------------------------------------------

            response = client.chat.completions.create(
                model="openai/gpt-oss-120b",
                messages=messages,
                temperature=0.2,
                max_tokens=800,
            )

            answer = response.choices[0].message.content

            if not answer:
                answer = "I could not generate a response. Please try again."

            # -------------------------------------------------
            # Save to local chat state
            # -------------------------------------------------

            st.session_state.chat_messages.append(
                {
                    "role": "assistant",
                    "content": answer,
                }
            )

            # -------------------------------------------------
            # Display answer
            # -------------------------------------------------

            with st.chat_message("assistant"):
                st.markdown(answer)

                with st.expander("🔎 Retrieved Knowledge Base Context"):
                    st.write(context)

            # -------------------------------------------------
            # Save chat history to Supabase
            # -------------------------------------------------

            if supabase and st.session_state.get("user_id"):

                try:
                    supabase.table(
                        "medication_chat_messages"
                    ).insert(
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

        except Exception as e:

            error_message = f"AI response failed: {e}"

            st.session_state.chat_messages.append(
                {
                    "role": "assistant",
                    "content": error_message,
                }
            )

            with st.chat_message("assistant"):
                st.error(error_message)
