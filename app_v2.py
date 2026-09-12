import streamlit as st
import json
import uuid
import base64
import re
from pathlib import Path
from groq import Groq
from supabase import create_client
from rag.retriever import retrieve_context

# =========================================================
# PAGE
# =========================================================
st.set_page_config(
    page_title="Medication AI Assistant",
    page_icon="💊",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# =========================================================
# SUPABASE
# =========================================================
supabase_url = st.secrets.get("SUPABASE_URL")
supabase_key = st.secrets.get("SUPABASE_KEY")

supabase = None
if supabase_url and supabase_key:
    supabase = create_client(supabase_url, supabase_key)
else:
    st.warning("Supabase is not configured. Chat history will not be saved.")

if supabase and st.session_state.get("access_token"):
    try:
        supabase.postgrest.auth(st.session_state.access_token)
    except Exception:
        pass

# =========================================================
# LOGIN / SIGNUP
# =========================================================
if supabase and "user_id" not in st.session_state:
    st.markdown(
        """ <style> .login-wrap{max-width:650px;margin:8vh auto 0;text-align:center} .login-title{font-size:34px;font-weight:800;letter-spacing:-1px} .login-subtitle{opacity:.65;margin-top:6px} </style> <div class="login-wrap"> <div class="login-title">💊 Medication AI</div> <div class="login-subtitle">Verified medication information assistant</div> </div> """,
        unsafe_allow_html=True,
    )

    tab_login, tab_signup = st.tabs(["🔐 Login", "✨ Create Account"])

    with tab_login:
        with st.form("login_form"):
            login_email = st.text_input("Email", key="login_email")
            login_password = st.text_input(
                "Password", type="password", key="login_password"
            )
            login_submit = st.form_submit_button(
                "Login", use_container_width=True
            )

        if login_submit:
            try:
                auth_response = supabase.auth.sign_in_with_password(
                    {"email": login_email, "password": login_password}
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
            signup_name = st.text_input("Full Name", key="signup_name")
            signup_email = st.text_input("Email", key="signup_email")
            signup_password = st.text_input(
                "Password", type="password", key="signup_password"
            )

            with st.expander("📄 Privacy Policy & Medical Disclaimer"):
                st.markdown(
                    """ **Medical Disclaimer** This app provides educational medication information only. It is not a doctor, diagnosis service, or replacement for qualified healthcare advice. **Privacy** - Account and chat data are stored in Supabase. - Medicine images are processed for the current request. - Do not upload unnecessary personal or sensitive documents. """
                )

            agree_terms = st.checkbox(
                "I agree to the Privacy Policy and Medical Disclaimer."
            )
            signup_submit = st.form_submit_button(
                "Create Account", use_container_width=True
            )

        if signup_submit:
            if not agree_terms:
                st.error("Please accept the Privacy Policy and Medical Disclaimer.")
            else:
                try:
                    auth_response = supabase.auth.sign_up(
                        {
                            "email": signup_email,
                            "password": signup_password,
                            "options": {"data": {"full_name": signup_name}},
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
                            "Account created! Please check your email and then log in."
                        )
                except Exception as e:
                    st.error(f"Sign up failed: {e}")

    st.stop()

# =========================================================
# SESSION STATE
# =========================================================
defaults = {
    "chat_messages": [],
    "current_chat_id": str(uuid.uuid4()),
    "chat_loaded": False,
    "selected_medicine": "None",
    "input_version": 0,
    "image_result": None,
    "image_bytes": None,
    "chat_list": [],
    "screening_active": False,
    "screening_started": False,
    "screening_answers": {},
}
for key, value in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value

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
        conversations = {}
        for row in response.data or []:
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
                    title = text[:42]
                    if len(text) > 42:
                        title += "..."
                    conversations[chat_id]["title"] = title
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
            {"role": row.get("role"), "content": row.get("content")}
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
    st.session_state.screening_active = False
    st.session_state.screening_started = False
    st.session_state.screening_answers = {}
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


def extract_json_object(raw_text):
    """Safely extract JSON without requiring Groq JSON mode."""
    if not raw_text:
        raise ValueError("Vision model returned an empty response.")

    text = raw_text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.I)
        text = re.sub(r"\s*```$", "", text)

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.S)
        if not match:
            raise ValueError("Could not find valid JSON in the vision response.")
        return json.loads(match.group(0))


def identify_medicines_from_image(image_bytes, mime_type, client):
    image_url = image_to_data_url(image_bytes, mime_type)

    vision_prompt = """ You are a medicine-label verification assistant. Read only information that is visibly present in the image. The image may contain: 1) a medicine box/blister/bottle, or 2) a doctor's handwritten/printed prescription or medicine list. Do NOT diagnose, prescribe, or give dosage instructions. Return ONLY one JSON object with exactly these keys: { "document_type": "medicine_package" | "prescription" | "unknown", "medicines": [ { "medicine_name": "string", "generic_name": "string", "strength": "string", "visible_text": "string", "confidence": "HIGH" | "MEDIUM" | "LOW" } ], "note": "short string" } Rules: - Never guess a medicine name when the image is unclear. - If handwriting is unclear, use LOW confidence or leave the medicine out. - Do not invent missing strength or dosage. - If no medicine can be reliably read, return an empty medicines list. """

    response = client.chat.completions.create(
        model="qwen/qwen3.6-27b",
        messages=[
            {"role": "system", "content": vision_prompt},
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "Read and verify the medicine names visible in this image.",
                    },
                    {
                        "type": "image_url",
                        "image_url": {"url": image_url},
                    },
                ],
            },
        ],
        temperature=0,
        max_completion_tokens=700,
    )

    raw = response.choices[0].message.content
    return extract_json_object(raw)


def find_kb_medicine(medicine_name, medicine_records):
    if not medicine_name:
        return None

    target = medicine_name.strip().lower()

    for record in medicine_records:
        name = record.get("medicine_name", "").strip().lower()
        generic = record.get("generic_name", "").strip().lower()
        aliases = [
            str(x).strip().lower()
            for x in record.get("aliases", [])
            if str(x).strip()
        ]
        if target == name or target == generic or target in aliases:
            return record

    for record in medicine_records:
        name = record.get("medicine_name", "").strip().lower()
        generic = record.get("generic_name", "").strip().lower()
        if (
            (name and (target in name or name in target))
            or (generic and (target in generic or generic in target))
        ):
            return record

    return None


def medicine_details_text(record):
    """Only display facts that actually exist in the verified KB."""
    if not record:
        return ""

    parts = []
    if record.get("medicine_name"):
        parts.append(f"**{record['medicine_name']}**")
    if record.get("generic_name"):
        parts.append(f"Generic: {record['generic_name']}")
    if record.get("common_uses"):
        parts.append(f"Uses: {record['common_uses']}")
    if record.get("common_side_effects"):
        parts.append(f"Common side effects: {record['common_side_effects']}")
    if record.get("important_precautions"):
        parts.append(f"Precautions: {record['important_precautions']}")
    if record.get("serious_warnings"):
        parts.append(f"Serious warnings: {record['serious_warnings']}")
    if record.get("source"):
        parts.append(f"Source: {record['source']}")
    if record.get("source_url"):
        parts.append(f"Source URL: {record['source_url']}")
    return "\n\n".join(parts)


def run_image_verification(image_bytes, mime_type):
    api_key = st.secrets.get("GROQ_API_KEY")
    if not api_key:
        raise ValueError("Groq API key is not configured.")

    client = Groq(api_key=api_key)
    return identify_medicines_from_image(image_bytes, mime_type, client)


def render_verified_image_result(result, medication_records):
    medicines = result.get("medicines") or []

    if not medicines:
        st.warning(
            "Medicine could not be read clearly. Please upload a clearer photo, "
            "especially the medicine name/label."
        )
        return

    matched_count = 0
    for item in medicines:
        name = (item.get("medicine_name") or "").strip()
        confidence = (item.get("confidence") or "UNKNOWN").upper()

        if not name or confidence == "LOW":
            st.warning(
                f"⚠️ Could not reliably read one medicine name. "
                f"Please verify it manually."
            )
            continue

        record = find_kb_medicine(name, medication_records)

        if not record:
            st.info(
                f"**{name}** was read from the image, but it is not present in "
                "the verified medication knowledge base. I will not invent details."
            )
            continue

        matched_count += 1
        st.success(f"Verified in knowledge base: **{record.get('medicine_name')}**")
        st.markdown(medicine_details_text(record))

        if item.get("strength"):
            st.caption(f"Strength visible in image: {item['strength']}")

    if matched_count == 0:
        st.warning(
            "The medicine name was readable, but no matching verified record was found."
        )


# =========================================================
# KNOWLEDGE BASE
# =========================================================
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
except Exception as e:
    medication_records = []
    medicine_names = []
    st.warning(f"Medication knowledge base could not be loaded: {e}")

# =========================================================
# LOAD CHAT
# =========================================================
if not st.session_state.chat_loaded:
    existing = load_chat_messages(st.session_state.current_chat_id)
    if existing:
        st.session_state.chat_messages = existing
    st.session_state.chat_loaded = True

if not st.session_state.chat_list:
    st.session_state.chat_list = load_saved_chats()

# =========================================================
# CLEAN PROFESSIONAL UI
# =========================================================
st.markdown(
    """ <style> #MainMenu {visibility:hidden;} footer {visibility:hidden;} .block-container { max-width: 900px; padding-top: .8rem; padding-bottom: 7rem; padding-left: 1rem; padding-right: 1rem; } .app-top { text-align:center; margin: 2px 0 14px 0; } .app-title { font-size: 26px; font-weight: 800; letter-spacing: -0.8px; line-height: 1.1; } .app-greeting { margin-top: 5px; font-size: 13px; opacity: .58; } [data-testid="stChatMessage"] { border-radius: 18px; margin-bottom: 8px; } [data-testid="stChatMessageContent"] { font-size: 15px; line-height: 1.55; } .tool-hint { text-align:center; font-size:12px; opacity:.48; margin: 3px 0 5px; } .verified-card { border: 1px solid rgba(120,120,120,.18); border-radius: 16px; padding: 14px 16px; margin: 8px 0; } section[data-testid="stSidebar"] { border-right: 1px solid rgba(120,120,120,.12); } @media (max-width:700px) { .block-container { padding-left:.65rem; padding-right:.65rem; padding-top:.45rem; } .app-title {font-size:22px;} [data-testid="stChatMessageContent"] {font-size:14px;} } </style> """,
    unsafe_allow_html=True,
)

# =========================================================
# SIDEBAR
# =========================================================
with st.sidebar:
    st.markdown("### 💊 Medication AI")
    st.caption("Verified • Educational • Safety-focused")
    st.markdown(f"**{get_display_name()}**")
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
            label = (
                ("🟢 " if chat["chat_id"] == st.session_state.current_chat_id else "")
                + chat["title"]
            )
            if st.button(
                label,
                key=f"chat_{chat['chat_id']}",
                use_container_width=True,
            ):
                st.session_state.current_chat_id = chat["chat_id"]
                st.session_state.chat_loaded = False
                st.session_state.chat_messages = []
                st.session_state.selected_medicine = "None"
                st.session_state.image_result = None
                st.session_state.image_bytes = None
                st.session_state.screening_active = False
                st.session_state.screening_started = False
            options,
            index=(
                options.index(st.session_state.selected_medicine)
                if st.session_state.selected_medicine in options
                else 0
            ),
            label_visibility="collapsed",)
        st.session_state.selected_medicine = selected_medicine

        if selected_medicine != "None":
            record = find_kb_medicine(selected_medicine, medication_records)
            if record:
                st.markdown(medicine_details_text(record))

# =========================================================
# CHAT INPUT
# =========================================================
chat_submission = st.chat_input(
    "Message Medication AI…",
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
        user_question = str(chat_submission).strip()

if attached_file and not user_question:
    user_question = (
        "Please identify the medicine(s) in this image and explain what each "
        "verified -----------------------
                # Screening-first medical assistant
                # -------------------------------------------------
                system_prompt = """ You are Medication AI, a safety-focused medication INFORMATION assistant. Your job is NOT to diagnose or prescribe. IMPORTANT WORKFLOW: When a user describes symptoms and asks what medicine to use, do NOT immediately give a medicine recommendation. First ask the minimum relevant screening questions needed to make the educational information safer. Ask only relevant questions, not a giant questionnaire. For headache, consider asking: - When did it start? - Whole head or one side? - How severe is it? - Any vomiting, vision change, weakness, fainting, neck stiffness, or injury? For fever/flu: - How long? - Temperature if measured? - Cough, sore throat, body aches, breathing difficulty? For stomach problems: - Is it acidity/heartburn, diarrhea, vomiting, or abdominal pain? - When did it start? - Any blood, black stool, severe pain, dehydration, or repeated vomiting? For runny/dry nose: - Is the nose dry, blocked, or watery? - Any nose bleeding? - How long? For any person who may be pregnant: - Ask whether pregnancy is possible or confirmed before discussing medicine information that could be affected by pregnancy. When relevant, ask about: - age - medicine allergies - heart disease - kidney/liver disease - current medicines - pregnancy/breastfeeding If the user's answers already cover the relevant safety questions, do not keep asking unnecessary questions. AFTER SCREENING: Only then provide general educational medicine information based on the VERIFIED KNOWLEDGE BASE supplied in the prompt. Rules: 1. Never invent a medicine or medical fact. 2. Never diagnose the user's condition. 3. Never write a personalized prescription. 4. Never tell the user to take a personalized dose such as "half tablet", "one tablet morning/evening", or a personalized schedule. 5. Do not tell the user to start, stop, or change prescription medicine. 6. If a medicine appears in the verified KB, explain its documented uses, common side effects, precautions, serious warnings, and source when useful. 7. If a medicine is not in the verified KB, say that verified information is not available instead of guessing. 8. Do not assume that multiple symptoms require multiple medicines. 9. Do not recommend antibiotics for ordinary cold/flu symptoms. 10. If the user uploads a doctor's prescription, help READ/VERIFY the medicine names against the verified KB and explain what those medicines are generally used for. Do not replace the doctor's instructions. 11. If the image is unclear, say it is unclear and ask for a clearer photo. 12. Match the user's language automatically: English, Urdu script, Pakistani Roman Urdu, or mixed language. 13. Keep responses clean, short, and easy to read. 14. For serious warning signs, advise urgent medical care. In Pakistan mention Rescue 1122. The supplied knowledge-base context is the primary source. Do not use outside medical facts when the KB does not support them. """

                history_for_model = []
                for item in st.session_state.chat_messages[-10:]:
                    history_for_model.append(
                        {
                            "role": item["role"],
                            "content": item["content"],
                        }
                    )

                user_content = (
                    f"VERIFIED KNOWLEDGE BASE CONTEXT:\n{context}\n\n"
                    f"IMAGE VERIFICATION CONTEXT:\n{image_context}\n\n"
                    f"SELECTED MEDICINE:\n{selected_medicine}\n\n"
                    f"CURRENT USER MESSAGE:\n{user_question}"
                )

                messages = [{"role": "system", "content": system_prompt}]
                messages.extend(history_for_model)
                messages.append({"role": "user", "content": user_content})

                client = Groq(api_key=api_key)
                response = client.chat.completions.create(
                    model="openai/gpt-oss-120b",
                    messages=messages,
                    temperature=0.15,
                    max_tokens=900,
                )
                answer = response.choices[0].message.content

            with st.chat_message("assistant"):
                st.markdown(answer)

                if not is_emergency and context:
                    with st.expander("🔎 Verified knowledge used"):
                        st.write(context)

            st.session_state.chat_messages.append(
                {"role": "assistant", "content": answer}
            )

            if st.session_state.get("user_id"):
                try:
                    save_message("user", display_question)
                    save_message("assistant", answer)
                    st.session_state.chat_list = load_saved_chats()
                except Exception as e:
                    st.warning(f"Could not save chat history: {e}")

            # Keep image result visible until user starts another action.
            st.session_state.selected_medicine = "None"
            st.session_state.input_version += 1
            st.rerun()

        except Exception as e:
            st.error(f"AI response failed: {e}")
