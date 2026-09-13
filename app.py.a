import streamlit as st
import json
import uuid
import base64
from pathlib import Path
from groq import Groq
from supabase import create_client
from rag.retriever import retrieve_context

st.set_page_config(
    page_title="Medication AI Assistant",
    page_icon="💊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# =========================================================
# SUPABASE CONNECTION
# =========================================================
supabase_url = st.secrets.get("SUPABASE_URL")
supabase_key = st.secrets.get("SUPABASE_KEY")

supabase = None

if supabase_url and supabase_key:
    supabase = create_client(supabase_url, supabase_key)
else:
    st.warning("Supabase is not configured. Chat history will not be saved.")

# Keep Supabase authenticated on every Streamlit rerun.
if supabase and st.session_state.get("access_token"):
    supabase.postgrest.auth(st.session_state.access_token)


# =========================================================
# LOGIN / SIGNUP
# =========================================================
if supabase and "user_id" not in st.session_state:

    st.markdown(
        """
        <style>
        .login-wrap { max-width: 760px; margin: 7vh auto 0 auto; text-align: center; }
        .login-title { font-size: 42px; font-weight: 800; letter-spacing: -1.5px; }
        .login-subtitle { opacity: .68; font-size: 16px; margin-bottom: 25px; }
        </style>
        <div class="login-wrap">
            <div class="login-title">💊 Medication AI</div>
            <div class="login-subtitle">
                Your safety-focused medication information assistant
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    tab_login, tab_signup = st.tabs(["🔐 Login", "✨ Create Account"])

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

                user = auth_response.user
                session = auth_response.session

                st.session_state.user_id = user.id
                st.session_state.user_email = user.email
                st.session_state.user_name = (
                    user.user_metadata.get("full_name")
                    if user.user_metadata
                    else None
                ) or user.email.split("@")[0].title()
                st.session_state.access_token = session.access_token

                st.rerun()

            except Exception as e:
                st.error(f"Login failed: {e}")

    with tab_signup:
        with st.form("signup_form"):
            signup_name = st.text_input(
                "Full Name",
                key="signup_name",
            )
            signup_email = st.text_input(
                "Email",
                key="signup_email",
            )
            signup_password = st.text_input(
                "Password",
                type="password",
                key="signup_password",
            )

            with st.expander("📄 Privacy Policy & Medical Disclaimer"):
                st.markdown(
                    """
                    **Medical Disclaimer**
                    This app provides educational medication information only.
                    It is not a doctor, pharmacist, diagnosis service,
                    prescription service, or replacement for qualified
                    healthcare advice.

                    **Privacy Policy**
                    - Your name and email are stored for your account.
                    - Your chat history is stored in Supabase.
                    - We do not intentionally share your account/chat data
                      with third parties.
                    - You can request account/data deletion.
                    - Medicine photos are analyzed for the current request
                      and are not intentionally stored by this app.

                    By creating an account, you agree to these terms.
                    """
                )

            agree_terms = st.checkbox(
                "I agree to the Privacy Policy and Medical Disclaimer."
            )

            signup_submit = st.form_submit_button(
                "Create Account",
                use_container_width=True,
            )

        if signup_submit:
            if not agree_terms:
                st.error(
                    "You must agree to the Privacy Policy and Medical Disclaimer."
                )
            else:
                try:
                    auth_response = supabase.auth.sign_up(
                        {
                            "email": signup_email,
                            "password": signup_password,
                            "options": {
                                "data": {
                                    "full_name": signup_name,
                                }
                            },
                        }
                    )

                    if auth_response.session:
                        st.session_state.user_id = auth_response.user.id
                        st.session_state.user_email = auth_response.user.email
                        st.session_state.user_name = signup_name or (
                            signup_email.split("@")[0].title()
                        )
                        st.session_state.access_token = (
                            auth_response.session.access_token
                        )
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
# SESSION STATE
# =========================================================
if "chat_messages" not in st.session_state:
    st.session_state.chat_messages = []

if "current_chat_id" not in st.session_state:
    st.session_state.current_chat_id = str(uuid.uuid4())

if "chat_loaded" not in st.session_state:
    st.session_state.chat_loaded = False

if "selected_medicine" not in st.session_state:
    st.session_state.selected_medicine = "None"

if "input_version" not in st.session_state:
    st.session_state.input_version = 0

if "image_result" not in st.session_state:
    st.session_state.image_result = None

if "image_bytes" not in st.session_state:
    st.session_state.image_bytes = None

if "chat_list" not in st.session_state:
    st.session_state.chat_list = []

# =========================================================
# HELPERS
# =========================================================
def get_display_name():
    name = st.session_state.get("user_name")
    if name:
        return name.split()[0]
    email = st.session_state.get("user_email", "User")
    return email.split("@")[0].replace(".", " ").title()


def load_saved_chats():
    if not supabase or not st.session_state.get("user_id"):
        return []

    try:
        response = (
            supabase.table("medication_chat_messages")
            .select("conversation_id, role, content, created_at")
            .eq("user_id", st.session_state.user_id)
            .order("created_at", desc=True)
            .limit(500)
            .execute()
        )

        rows = response.data or []
        conversations = {}

        for row in rows:
            chat_id = row.get("conversation_id")
            if not chat_id:
                continue

            if chat_id not in conversations:
                conversations[chat_id] = {
                    "chat_id": chat_id,
                    "title": "New conversation",
                    "created_at": row.get("created_at", ""),
                }

            if row.get("role") == "user":
                text = (row.get("content") or "").strip()
                if text:
                    conversations[chat_id]["title"] = text[:42]
                    if len(text) > 42:
                        conversations[chat_id]["title"] += "..."

        return list(conversations.values())

    except Exception:
        return []


def load_chat_messages(chat_id):
    if not supabase or not st.session_state.get("user_id"):
        return []

    try:
        response = (
            supabase.table("medication_chat_messages")
            .select("role, content, created_at")
            .eq("user_id", st.session_state.user_id)
            .eq("conversation_id", chat_id)
            .order("created_at", desc=False)
            .limit(200)
            .execute()
        )

        return [
            {
                "role": row.get("role"),
                "content": row.get("content"),
            }
            for row in (response.data or [])
            if row.get("role") in ["user", "assistant"]
        ]

    except Exception:
        return []


def start_new_chat():
    st.session_state.current_chat_id = str(uuid.uuid4())
    st.session_state.chat_messages = []
    st.session_state.chat_loaded = True
    st.session_state.selected_medicine = "None"
    st.session_state.image_result = None
    st.session_state.image_bytes = None
    st.session_state.input_version += 1


def save_message(role, content):
    if not supabase or not st.session_state.get("user_id"):
        return

    supabase.table("medication_chat_messages").insert(
        {
            "user_id": st.session_state.user_id,
            "conversation_id": st.session_state.current_chat_id,
            "role": role,
            "content": content,
        }
    ).execute()


def image_to_data_url(image_bytes, mime_type):
    encoded = base64.b64encode(image_bytes).decode("utf-8")
    return f"data:{mime_type};base64,{encoded}"


def identify_medicine_from_image(image_bytes, mime_type, client):
    image_url = image_to_data_url(image_bytes, mime_type)

    vision_prompt = """
You are identifying a medicine package or medicine label from a user-provided photo.
Your task is ONLY to read visible medicine/package information and identify the
medicine name if it is reasonably clear.

Rules:
- Do not guess a medicine name from an unclear image.
- Read visible brand name, generic name, strength, or active ingredient if available.
- If the medicine cannot be identified reliably, return UNKNOWN.
- Do not provide dosage or treatment advice.
- Return ONLY JSON with these keys:
  medicine_name
  generic_name
  confidence
  visible_text
  identification_note

confidence must be one of: HIGH, MEDIUM, LOW, UNKNOWN.
If the image is not a medicine package/label, return UNKNOWN.
"""

    response = client.chat.completions.create(
        model="qwen/qwen3.6-27b",
        messages=[
            {
                "role": "system",
                "content": vision_prompt,
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            "Identify the medicine from this image. "
                            "Do not guess if unclear."
                        ),
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": image_url,
                        },
                    },
                ],
            },
        ],
        temperature=0,
        max_completion_tokens=400,
        response_format={"type": "json_object"},
    )

    raw = response.choices[0].message.content
    return json.loads(raw)


def find_kb_medicine(medicine_name, medicine_records):
    if not medicine_name:
        return None

    target = medicine_name.strip().lower()

    for record in medicine_records:
        name = record.get("medicine_name", "").strip().lower()
        generic = record.get("generic_name", "").strip().lower()

        if target == name or target == generic:
            return record

    for record in medicine_records:
        name = record.get("medicine_name", "").strip().lower()
        generic = record.get("generic_name", "").strip().lower()

        if target in name or name in target or target in generic or generic in target:
            return record

    return None


# =========================================================
# LOAD KNOWLEDGE BASE
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
    medication_records = []
    medicine_names = []


# =========================================================
# LOAD CURRENT CHAT (once per session/chat switch)
# =========================================================
if not st.session_state.chat_loaded:
    existing = load_chat_messages(st.session_state.current_chat_id)

    if existing:
        st.session_state.chat_messages = existing

    st.session_state.chat_loaded = True

if not st.session_state.chat_list:
    st.session_state.chat_list = load_saved_chats()


# =========================================================
# SIDEBAR
# =========================================================
with st.sidebar:

    st.markdown(
        """
        <div style="padding:4px 0 8px 0;">
            <div style="font-size:25px;font-weight:800;">💊 Medication AI</div>
            <div style="opacity:.60;font-size:13px;">
                Safe • Verified • Educational
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.write(f"👤 **{get_display_name()}**")
    st.caption(st.session_state.get("user_email", ""))

    if st.button("➕ New Chat", use_container_width=True):
        start_new_chat()
        st.rerun()

    st.markdown("---")
    st.markdown("**Previous Chats**")

    if not st.session_state.chat_list:
        st.caption("No previous conversations yet.")
    else:
        for chat in st.session_state.chat_list:
            is_active = chat["chat_id"] == st.session_state.current_chat_id
            label = ("🟢 " if is_active else "") + chat["title"]

            if st.button(label, key=f"chat_{chat['chat_id']}", use_container_width=True):
                st.session_state.current_chat_id = chat["chat_id"]
                st.session_state.chat_loaded = False
                st.session_state.selected_medicine = "None"
                st.session_state.image_result = None
                st.session_state.image_bytes = None
                st.rerun()

    st.markdown("---")

    if st.button("🚪 Logout", use_container_width=True):
        try:
            supabase.auth.sign_out()
        except Exception:
            pass
        for key in ["user_id", "user_email", "user_name", "access_token"]:
            st.session_state.pop(key, None)
        st.rerun()

    with st.expander("⚠️ Delete Account Data"):
        st.warning(
            "This will permanently delete your chat history and profile data."
        )
        confirm_delete = st.checkbox("I confirm I want to delete my data.")
        if st.button("Delete My Data", type="primary", use_container_width=True):
            if confirm_delete:
                try:
                    uid = st.session_state.user_id
                    supabase.table("medication_chat_messages").delete().eq(
                        "user_id", uid
                    ).execute()
                    supabase.table("profiles").delete().eq("id", uid).execute()
                    supabase.auth.sign_out()
                    for key in ["user_id", "user_email", "user_name", "access_token"]:
                        st.session_state.pop(key, None)
                    st.success("Your data has been deleted.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Delete failed: {e}")
            else:
                st.error("Please tick the confirmation checkbox first.")

# =========================================================
# PREMIUM UI STYLING
# =========================================================
st.markdown(
    """
    <style>
    #MainMenu {visibility:hidden;}
    footer {visibility:hidden;}
    .block-container {
        max-width: 1120px;
        padding-top: 1.4rem;
        padding-bottom: 8rem;
    }
    .hero {
        padding: 24px 26px;
        border-radius: 26px;
        border: 1px solid rgba(120,120,120,.16);
        background:
            radial-gradient(circle at 90% 10%, rgba(70,130,255,.12), transparent 35%),
            linear-gradient(135deg, rgba(255,255,255,.08), rgba(120,120,120,.04));
        box-shadow: 0 18px 55px rgba(0,0,0,.07);
        margin-bottom: 20px;
    }
    .hero-title {
        font-size: clamp(27px, 5vw, 42px);
        font-weight: 850;
        letter-spacing: -1.8px;
        line-height: 1.05;
        margin-bottom: 8px;
    }
    .hero-subtitle {
        opacity: .66;
        font-size: 15px;
        max-width: 780px;
        line-height: 1.55;
    }
    [data-testid="stChatMessage"] {
        border-radius: 20px;
        margin-bottom: 9px;
    }
    section[data-testid="stSidebar"] {
        border-right: 1px solid rgba(120,120,120,.12);
    }
    .toolbar-row {
        display: flex;
        gap: 8px;
        margin-bottom: 6px;
    }
    @media (max-width: 700px) {
        .block-container {
            padding-left: .75rem;
            padding-right: .75rem;
            padding-top: .8rem;
        }
        .hero { padding: 21px; border-radius: 21px; }
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# =========================================================
# HEADER
# =========================================================
display_name = get_display_name()

st.markdown(
    f"""
    <div class="hero">
        <div class="hero-title">💊 Hi {display_name}, ask me anything about medicines</div>
        <div class="hero-subtitle">
            Educational medication information only. This AI does not diagnose
            or prescribe. For emergencies, always seek immediate medical help.
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)


# =========================================================
# DISPLAY EXISTING CHAT MESSAGES
# =========================================================
for msg in st.session_state.chat_messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])


# =========================================================
# COMPACT TOOLBAR (icon-only) — medicine picker + camera
# Sits right above the chat input, keeps the UI clean.
# =========================================================
toolbar_col1, toolbar_col2, toolbar_col3 = st.columns([1, 1, 6])

with toolbar_col1:
    with st.popover("💊", use_container_width=True):
        st.caption("Select a medicine (optional)")
        selected_medicine = st.selectbox(
            "Medicine",
            ["None"] + medicine_names,
            index=(["None"] + medicine_names).index(st.session_state.selected_medicine)
            if st.session_state.selected_medicine in (["None"] + medicine_names)
            else 0,
            label_visibility="collapsed",
        )
        st.session_state.selected_medicine = selected_medicine

        if selected_medicine != "None":
            st.success(f"Using: {selected_medicine}")

with toolbar_col2:
    with st.popover("📷", use_container_width=True):
        st.caption("Take a photo of the medicine")
        camera_photo = st.camera_input(
            "Camera",
            key=f"camera_{st.session_state.input_version}",
            label_visibility="collapsed",
        )

        if camera_photo is not None:
            st.session_state.image_bytes = camera_photo.getvalue()

            if st.button("Identify Medicine", key="identify_camera"):
                api_key = st.secrets.get("GROQ_API_KEY")
                if not api_key:
                    st.error("Groq API key is not configured.")
                else:
                    try:
                        vision_client = Groq(api_key=api_key)
                        result = identify_medicine_from_image(
                            st.session_state.image_bytes,
                            "image/jpeg",
                            vision_client,
                        )
                        st.session_state.image_result = result
                    except Exception as e:
                        st.error(f"Could not identify medicine: {e}")

        if st.session_state.image_result:
            result = st.session_state.image_result
            identified_name = (result.get("medicine_name") or "").strip()
            confidence = (result.get("confidence") or "UNKNOWN").upper()

            if identified_name and confidence in ["HIGH", "MEDIUM"]:
                matched_record = find_kb_medicine(identified_name, medication_records)
                final_name = matched_record.get("medicine_name", identified_name) if matched_record else identified_name
                st.success(f"Identified: **{final_name}**")
                st.session_state.selected_medicine = final_name
            else:
                st.warning("Could not confidently identify the medicine.")

with toolbar_col3:
    if st.session_state.selected_medicine != "None":
        st.caption(f"💊 Context: **{st.session_state.selected_medicine}**  ·  "
                    f"[clear]"
                    )


# =========================================================
# USER QUESTION INPUT (with attach icon built into the chat box)
# =========================================================
chat_submission = st.chat_input(
    "Ask a medication question",
    accept_file=True,
    file_type=["png", "jpg", "jpeg"],
    key=f"chat_input_{st.session_state.input_version}",
)

user_question = None
attached_file = None

if chat_submission:
    if hasattr(chat_submission, "text"):
        user_question = (chat_submission.text or "").strip()
        if chat_submission.files:
            attached_file = chat_submission.files[0]
    else:
        # Fallback for older Streamlit versions without file attach support
        user_question = str(chat_submission).strip()

# If the user only attached a photo with no typed question, default to asking about it
if attached_file and not user_question:
    user_question = "What is this medicine and what is it used for?"

selected_medicine = st.session_state.selected_medicine

if user_question:

    # ---------------------------------------------------
    # If a photo was attached directly in the chat box,
    # identify it before answering
    # ---------------------------------------------------
    if attached_file is not None:
        api_key = st.secrets.get("GROQ_API_KEY")
        if api_key:
            try:
                image_bytes = attached_file.getvalue()
                mime_type = attached_file.type or "image/jpeg"
                vision_client = Groq(api_key=api_key)
                result = identify_medicine_from_image(image_bytes, mime_type, vision_client)

                identified_name = (result.get("medicine_name") or "").strip()
                confidence = (result.get("confidence") or "UNKNOWN").upper()

                if identified_name and confidence in ["HIGH", "MEDIUM"]:
                    matched_record = find_kb_medicine(identified_name, medication_records)
                    final_name = matched_record.get("medicine_name", identified_name) if matched_record else identified_name
                    selected_medicine = final_name
                    st.session_state.selected_medicine = final_name
            except Exception:
                pass

    # Show and store the user's message immediately
    display_question = user_question
    if attached_file is not None:
        display_question = f"📷 {user_question}"

    st.session_state.chat_messages.append(
        {"role": "user", "content": display_question}
    )
    with st.chat_message("user"):
        if attached_file is not None:
            st.image(attached_file, width=180)
        st.markdown(user_question)

    retrieval_question = user_question
    if selected_medicine != "None":
        retrieval_question = f"{selected_medicine} {user_question}"

    api_key = st.secrets.get("GROQ_API_KEY")

    if not api_key:
        answer = "Groq API key is not configured."
        with st.chat_message("assistant"):
            st.error(answer)
        st.session_state.chat_messages.append(
            {"role": "assistant", "content": answer}
        )

    else:
        try:
            # -------------------------------------------------
            # Deterministic emergency safety layer
            # -------------------------------------------------
            emergency_terms = [
                "severe chest pain",
                "difficulty breathing",
                "can't breathe",
                "cannot breathe",
                "unconscious",
                "seizure",
                "severe allergic reaction",
                "anaphylaxis",
                "overdose",
                "poisoning",
                "severe bleeding",
                "stroke",
            ]

            lower_question = user_question.lower()
            is_emergency = any(term in lower_question for term in emergency_terms)

            if is_emergency:
                with st.chat_message("assistant"):
                    st.error(
                        "🚨 This may be a medical emergency. Please seek "
                        "immediate professional medical help. In Pakistan, "
                        "call **Rescue 1122** or go to the nearest emergency "
                        "department right away."
                    )

            # -------------------------------------------------
            # Retrieve knowledge base context
            # -------------------------------------------------
            context = retrieve_context(retrieval_question)

            # -------------------------------------------------
            # Groq AI response
            # -------------------------------------------------
            client = Groq(api_key=api_key)

            system_prompt = """
You are a Medication Information Assistant.

Your responsibilities:
1. Provide general educational information about medicines.
2. Do not diagnose diseases.
3. Do not prescribe medicines.
4. Do not tell users to start, stop, or change prescription medicines.
5. Do not provide personalized prescription or dosage instructions.
6. Do not invent medical information.
7. Use the provided verified knowledge-base context as the primary source.
8. If the knowledge base does not contain enough information, clearly say
   that verified information is not available.
9. For overdose, poisoning, severe allergic reaction, breathing difficulty,
   unconsciousness, severe chest pain, or other emergencies, advise the
   user to seek immediate professional medical help. For users in
   Pakistan, mention Rescue 1122.
10. Keep the answer clear, helpful, and easy to understand.
11. Use simple, easy-to-understand language.
"""

            response = client.chat.completions.create(
                model="openai/gpt-oss-120b",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {
                        "role": "user",
                        "content": (
                            f"Knowledge base context:\n{context}\n\n"
                            f"User question:\n{user_question}"
                        ),
                    },
                ],
                temperature=0.2,
                max_tokens=800,
            )

            answer = response.choices[0].message.content

            with st.chat_message("assistant"):
                st.markdown(answer)
                with st.expander("🔎 Retrieved Knowledge Base Context"):
                    st.write(context)

            st.session_state.chat_messages.append(
                {"role": "assistant", "content": answer}
            )

            # -------------------------------------------------
            # Save chat history to Supabase
            # -------------------------------------------------
            if st.session_state.get("user_id"):
                try:
                    save_message("user", display_question)
                    save_message("assistant", answer)

                    # Refresh sidebar chat list
                    st.session_state.chat_list = load_saved_chats()

                except Exception as e:
                    st.warning(f"Could not save chat history: {e}")

            # -------------------------------------------------
            # Reset inputs for next message
            # -------------------------------------------------
            st.session_state.selected_medicine = "None"
            st.session_state.image_result = None
            st.session_state.image_bytes = None
            st.session_state.input_version += 1

            st.rerun()

        except Exception as e:
            st.error(f"AI response failed: {e}")
