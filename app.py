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
    initial_sidebar_state="expanded"
)


# =========================================================
# CUSTOM CSS
# =========================================================

st.markdown(
    """
    <style>

    /* Main page */
    .stApp {
        background-color: #ffffff;
    }

    /* Reduce top spacing */
    .block-container {
        padding-top: 1.5rem;
        padding-bottom: 6rem;
        max-width: 1000px;
    }

    /* Header */
    .app-header {
        text-align: center;
        padding: 10px 0 20px 0;
    }

    .app-title {
        font-size: 30px;
        font-weight: 700;
        margin-bottom: 5px;
    }

    .app-subtitle {
        color: #6b7280;
        font-size: 14px;
    }

    /* Welcome screen */
    .welcome-box {
        text-align: center;
        padding: 45px 20px 30px 20px;
    }

    .welcome-icon {
        font-size: 48px;
        margin-bottom: 10px;
    }

    .welcome-title {
        font-size: 28px;
        font-weight: 700;
        margin-bottom: 8px;
    }

    .welcome-text {
        color: #6b7280;
        font-size: 15px;
    }

    /* Sidebar */
    section[data-testid="stSidebar"] {
        border-right: 1px solid #e5e7eb;
    }

    /* Chat messages */
    div[data-testid="stChatMessage"] {
        padding: 12px 8px;
        border-radius: 10px;
    }

    /* Chat input */
    div[data-testid="stChatInput"] {
        margin-bottom: 10px;
    }

    /* Buttons */
    .stButton > button {
        border-radius: 8px;
        min-height: 42px;
    }

    /* Medicine search */
    div[data-testid="stSelectbox"] {
        margin-bottom: 10px;
    }

    /* Mobile */
    @media (max-width: 768px) {

        .block-container {
            padding-left: 12px;
            padding-right: 12px;
            padding-top: 1rem;
        }

        .app-title {
            font-size: 24px;
        }

        .welcome-title {
            font-size: 23px;
        }

    }

    </style>
    """,
    unsafe_allow_html=True
)


# =========================================================
# SESSION STATE
# =========================================================

if "chat_messages" not in st.session_state:
    st.session_state.chat_messages = []

if "selected_medicine" not in st.session_state:
    st.session_state.selected_medicine = "None"


# =========================================================
# SUPABASE CONNECTION
# =========================================================

supabase_url = st.secrets.get("SUPABASE_URL")
supabase_key = st.secrets.get("SUPABASE_KEY")

supabase = None

if supabase_url and supabase_key:

    supabase = create_client(
        supabase_url,
        supabase_key
    )

else:

    st.warning(
        "Supabase is not configured. Chat history will not be saved."
    )


# =========================================================
# KEEP SUPABASE CLIENT AUTHENTICATED
# =========================================================

if supabase and st.session_state.get("access_token"):

    supabase.postgrest.auth(
        st.session_state.access_token
    )


# =========================================================
# LOGIN / SIGNUP
# =========================================================

if supabase and "user_id" not in st.session_state:

    st.markdown(
        """
        <div class="welcome-box">

            <div class="welcome-icon">💊</div>

            <div class="welcome-title">
                Medication AI Assistant
            </div>

            <div class="welcome-text">
                Get clear and educational medication information.
            </div>

        </div>
        """,
        unsafe_allow_html=True
    )

    tab_login, tab_signup = st.tabs(
        ["🔐 Login", "📝 Sign Up"]
    )


    # =====================================================
    # LOGIN
    # =====================================================

    with tab_login:

        with st.form("login_form"):

            login_email = st.text_input(
                "Email",
                key="login_email"
            )

            login_password = st.text_input(
                "Password",
                type="password",
                key="login_password"
            )

            login_submit = st.form_submit_button(
                "Login",
                use_container_width=True
            )


        if login_submit:

            try:

                auth_response = (
                    supabase.auth.sign_in_with_password(
                        {
                            "email": login_email,
                            "password": login_password
                        }
                    )
                )

                st.session_state.user_id = (
                    auth_response.user.id
                )

                st.session_state.user_email = (
                    auth_response.user.email
                )

                st.session_state.access_token = (
                    auth_response.session.access_token
                )

                st.session_state.chat_messages = []

                st.rerun()

            except Exception as e:

                st.error(
                    f"Login failed: {e}"
                )


    # =====================================================
    # SIGN UP
    # =====================================================

    with tab_signup:

        with st.form("signup_form"):

            signup_name = st.text_input(
                "Full Name",
                key="signup_name"
            )

            signup_email = st.text_input(
                "Email",
                key="signup_email"
            )

            signup_password = st.text_input(
                "Password",
                type="password",
                key="signup_password"
            )


            with st.expander(
                "📄 Privacy Policy & Medical Disclaimer"
            ):

                st.markdown(
                    """
                    **Medical Disclaimer**

                    Yeh app sirf educational/informational purpose ke liye hai.
                    Ye kisi doctor, pharmacist ya qualified healthcare professional
                    ka replacement nahi hai.

                    Is app ki AI information diagnosis,
                    prescription ya treatment advice nahi hai.

                    Kisi bhi medical decision se pehle apne doctor se
                    mashwara zaroor karein.

                    **Privacy Policy**

                    - Aapka naam aur email account banane ke liye store kiya jayega.
                    - Aapki chat history Supabase database mein save hogi.
                    - Aapka data kisi third party ke sath share nahi kiya jayega.
                    - Aap kisi bhi waqt apna account aur data delete kar sakte hain.

                    Account banane se aap in terms se agree karte hain.
                    """
                )


            agree_terms = st.checkbox(
                "Main Privacy Policy aur Medical Disclaimer se agree karta/karti hoon"
            )


            signup_submit = st.form_submit_button(
                "Create Account",
                use_container_width=True
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
                            }
                        }
                    )


                    if auth_response.session:

                        st.session_state.user_id = (
                            auth_response.user.id
                        )

                        st.session_state.user_email = (
                            auth_response.user.email
                        )

                        st.session_state.access_token = (
                            auth_response.session.access_token
                        )

                        st.success(
                            "Account created successfully!"
                        )

                        st.rerun()

                    else:

                        st.success(
                            "Account created! Please check your email to confirm your account, then log in."
                        )

                except Exception as e:

                    st.error(
                        f"Sign up failed: {e}"
                    )


    st.stop()


# =========================================================
# SIDEBAR
# =========================================================

if supabase and st.session_state.get("user_id"):

    with st.sidebar:

        st.markdown(
            "### 💊 Medication AI"
        )

        st.caption(
            "Your personal medication information assistant"
        )

        st.divider()


        # =================================================
        # NEW CHAT
        # =================================================

        if st.button(
            "＋ New Chat",
            use_container_width=True
        ):

            st.session_state.chat_messages = []

            st.rerun()


        st.divider()


        # =================================================
        # USER INFO
        # =================================================

        st.write(
            "👤 **Account**"
        )

        st.caption(
            st.session_state.get(
                "user_email",
                "User"
            )
        )


        st.divider()


        # =================================================
        # LOGOUT
        # =================================================

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
                "access_token",
                "chat_messages"
            ]:

                st.session_state.pop(
                    key,
                    None
                )


            st.rerun()


        st.divider()


        # =================================================
        # DELETE ACCOUNT
        # =================================================

        st.markdown(
            "### ⚠️ Account"
        )

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

                session = supabase.auth.get_session()

                access_token = None


                if session:

                    if hasattr(
                        session,
                        "access_token"
                    ):

                        access_token = (
                            session.access_token
                        )

                    elif (
                        hasattr(session, "session")
                        and session.session
                    ):

                        access_token = (
                            session.session.access_token
                        )


                if not access_token:

                    access_token = (
                        st.session_state.get(
                            "access_token"
                        )
                    )


                if not access_token:

                    st.error(
                        "Your session has expired. Please login again."
                    )

                else:

                    st.session_state.access_token = (
                        access_token
                    )


                    supabase.postgrest.auth(
                        access_token
                    )


                    response = (
                        supabase.functions.invoke(
                            "delete-my-account",
                            invoke_options={
                                "headers": {
                                    "Authorization": (
                                        f"Bearer {access_token}"
                                    )
                                }
                            }
                        )
                    )


                    if response:

                        for key in [
                            "user_id",
                            "user_email",
                            "access_token",
                            "delete_account_confirm",
                            "chat_messages"
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
# APP HEADER
# =========================================================

st.markdown(
    """
    <div class="app-header">

        <div class="app-title">
            💊 Medication AI Assistant
        </div>

        <div class="app-subtitle">
            Educational medication information powered by AI
        </div>

    </div>
    """,
    unsafe_allow_html=True
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

    with open(
        KB_PATH,
        "r",
        encoding="utf-8"
    ) as file:

        medication_records = json.load(file)


    medicine_names = sorted(
        {
            record.get(
                "medicine_name",
                ""
            ).strip()

            for record in medication_records

            if record.get(
                "medicine_name",
                ""
            ).strip()
        }
    )


except Exception:

    medicine_names = []


# =========================================================
# MEDICINE SEARCH
# =========================================================

selected_medicine = st.selectbox(
    "🔎 Search Medicine",
    ["None"] + medicine_names,
    index=0,
    key="medicine_selector",
    help="Search for a medicine before asking your question."
)


# =========================================================
# WELCOME MESSAGE
# =========================================================

if not st.session_state.chat_messages:

    st.markdown(
        """
        <div class="welcome-box">

            <div class="welcome-icon">
                💊
            </div>

            <div class="welcome-title">
                How can I help you?
            </div>

            <div class="welcome-text">
                Ask me about a medicine, its uses, precautions,
                side effects or other verified information.
            </div>

        </div>
        """,
        unsafe_allow_html=True
    )


# =========================================================
# DISPLAY PREVIOUS CHAT
# =========================================================

for message in st.session_state.chat_messages:

    with st.chat_message(
        message["role"]
    ):

        st.markdown(
            message["content"]
        )


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

    # -----------------------------------------------------
    # Add user message
    # -----------------------------------------------------

    st.session_state.chat_messages.append(
        {
            "role": "user",
            "content": question
        }
    )


    # -----------------------------------------------------
    # Display user message
    # -----------------------------------------------------

    with st.chat_message("user"):

        st.markdown(question)


    # -----------------------------------------------------
    # Medicine retrieval query
    # -----------------------------------------------------

    retrieval_question = question


    if selected_medicine != "None":

        retrieval_question = (
            f"{selected_medicine} {question}"
        )


    # -----------------------------------------------------
    # Groq API
    # -----------------------------------------------------

    api_key = st.secrets.get(
        "GROQ_API_KEY"
    )


    if not api_key:

        error_message = (
            "Groq API key is not configured."
        )

        st.session_state.chat_messages.append(
            {
                "role": "assistant",
                "content": error_message
            }
        )

        with st.chat_message("assistant"):

            st.error(
                error_message
            )


    else:

        try:

            # -------------------------------------------------
            # Retrieve knowledge base
            # -------------------------------------------------

            context = retrieve_context(
                retrieval_question
            )


            # -------------------------------------------------
            # Groq client
            # -------------------------------------------------

            client = Groq(
                api_key=api_key
            )


            # -------------------------------------------------
            # Automatic language detection
            # -------------------------------------------------

            system_prompt = """
You are a Medication Information Assistant.

LANGUAGE RULE:
Automatically detect the language and writing style of the user's latest message.

Reply in the SAME language and writing style used by the user.

Examples:

User: What is paracetamol used for?
Reply in simple English.

User: Paracetamol kis liye use hoti hai?
Reply in simple Pakistani Roman Urdu.

User: پیراسیٹامول کس لیے استعمال ہوتی ہے؟
Reply in simple Urdu script.

If the user naturally mixes English and Roman Urdu, reply naturally in the same mixed style.

Do NOT ask the user to select a language.
Do NOT mention language detection.

MEDICAL RESPONSE RULES:

Answer exactly what the user asks.

Give a useful and properly explained answer, but do not add unrelated medicine information.

Normally provide:
- 2-5 short paragraphs
OR
- 4-8 useful bullet points.

Use simple language.

Do not unnecessarily repeat the user's question.

Do not automatically add:
- dosage
- side effects
- precautions
- warnings
- interactions
- alternatives
- advantages
- disadvantages

unless the user asks about them or they are necessary for immediate safety.

MEDICAL SAFETY:

1. Provide general educational information only.
2. Do not diagnose diseases.
3. Do not prescribe medicines.
4. Do not tell users to start, stop, or change prescription medicines.
5. Do not provide personalized prescription or dosage instructions.
6. Do not invent medical information.
7. Use the provided verified knowledge-base context as the primary source.
8. If requested information is not available in the knowledge base, clearly say that verified information is not available.
9. Preserve medical meaning when responding in another language.

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

Use the provided knowledge-base context as the main source.

Do not make up facts that are not supported by the knowledge base.

If information is unavailable, clearly say:

"Verified information is not available in the current knowledge base."
"""
            recent_messages = st.session_state.chat_messages[-6:]

            messages = [
                {
                    "role": "system",
                    "content": system_prompt
                }
            ]

            for msg in recent_messages:
                messages.append(
                    {
                        "role": msg["role"],
                        "content": msg["content"]
                    }
                )

            messages.append(
                {
                    "role": "user",
                    "content": (
                        f"Knowledge base context:\n{context}\n\n"
                        f"User question:\n{question}"
                    )
                }
            )

            response = client.chat.completions.create(
                model="openai/gpt-oss-120b",
                messages=messages,
                temperature=0.2,
                max_tokens=800
            )

            answer = response.choices[0].message.content

            st.session_state.chat_messages.append(
                {
                    "role": "assistant",
                    "content": answer
                }
            )

            with st.chat_message("assistant"):
                st.markdown(answer)

            if supabase and st.session_state.get("user_id"):

                try:

                    supabase.table(
                        "medication_chat_messages"
                    ).insert(
                        [
                            {
                                "user_id": st.session_state.user_id,
                                "role": "user",
                                "content": question
                            },
                            {
                                "user_id": st.session_state.user_id,
                                "role": "assistant",
                                "content": answer
                            }
                        ]
                    ).execute()

                except Exception as e:

                    st.warning(
                        f"Chat history could not be saved: {e}"
                    )

        except Exception as e:

            error_message = f"AI response failed: {e}"

            st.session_state.chat_messages.append(
                {
                    "role": "assistant",
                    "content": error_message
                }
            )

            with st.chat_message("assistant"):
                st.error(error_message)
