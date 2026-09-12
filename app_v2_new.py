import streamlit as st
import json
import uuid
import base64
import re
import requests
from pathlib import Path
from groq import Groq
from supabase import create_client
from rag.retriever import retrieve_context


# =========================================================
# LOCATION & SPECIALIST HELPERS
# =========================================================
def get_location_from_ip():
    """Approximate location only; never silently uses precise device GPS."""
    try:
        r = requests.get("https://ipapi.co/json/", timeout=5)
        if r.ok:
            data = r.json()
            return {
                "city": data.get("city"),
                "region": data.get("region"),
                "country": data.get("country_name"),
                "latitude": data.get("latitude"),
                "longitude": data.get("longitude"),
            }
    except Exception:
        pass
    return None


def specialist_for_condition(text):
    t = (text or "").lower()
    rules = [
        (["heart", "cardiac", "cardiology", "dil", "seena", "chest pain"], "Cardiologist"),
        (["kidney", "renal", "gurda", "gurd"], "Nephrologist"),
        (["diabetes", "diabetic", "sugar", "blood sugar"], "Endocrinologist / Diabetologist"),
        (["skin", "rash", "acne", "itching", "dermat"], "Dermatologist"),
        (["stomach", "gastric", "ulcer", "digest", "pet"], "Gastroenterologist"),
        (["lung", "asthma", "breathing", "respiratory", "saans"], "Pulmonologist"),
        (["brain", "migraine", "seizure", "neurolog"], "Neurologist"),
        (["child", "baby", "infant", "pediatric"], "Pediatrician"),
        (["eye", "vision", "ophthalm"], "Ophthalmologist"),
        (["ear", "nose", "throat", "ent"], "ENT Specialist"),
    ]
    for keywords, specialist in rules:
        if any(k in t for k in keywords):
            return specialist
    return "General Physician"


def nearby_places_url(specialist_or_type, city=None):
    q = requests.utils.quote(f"{specialist_or_type} near {city}" if city else specialist_or_type)
    return f"https://www.google.com/maps/search/?api=1&query={q}"

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
# LOCATION-BASED CARE SUPPORT
# =========================================================
with st.sidebar:
    st.markdown("### 📍 Nearby Care")
    st.caption("Location is optional. We use approximate location to help you find nearby care.")
    if st.button("📍 Find Nearby Clinics & Emergency Care", use_container_width=True):
        loc = get_location_from_ip()
        if loc and loc.get("city"):
            st.session_state["approx_location"] = loc
        else:
            st.warning("Location could not be determined. You can search your city manually.")
    loc = st.session_state.get("approx_location")
    if loc and loc.get("city"):
        st.success(f"Approx. location: {loc['city']}, {loc.get('region','')}")
        st.link_button("🏥 Nearby Clinics", nearby_places_url("medical clinic", loc["city"]), use_container_width=True)
        st.link_button("🚑 Nearby Emergency Departments", nearby_places_url("emergency department hospital", loc["city"]), use_container_width=True)
        st.caption("Approximate location may be inaccurate. Always verify the facility and emergency availability.")

# =========================================================
# LOGIN / SIGNUP
# =========================================================
if supabase and "user_id" not in st.session_state:
    st.markdown(
        """
        <style>
        .login-wrap{
            max-width:650px;
            margin:8vh auto 0;
            text-align:center
        }
        .login-title{
            font-size:34px;
            font-weight:800;
            letter-spacing:-1px
        }
        .login-subtitle{
            opacity:.65;
            margin-top:6px
        }
        </style>

        <div class="login-wrap">
            <div class="login-title">💊 Medication AI</div>
            <div class="login-subtitle">
                Verified medication information assistant
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    tab_login, tab_signup = st.tabs(["🔐 Login", "✨ Create Account"])

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
                auth_response = supabase.auth.sign_in_with_password(
                    {
                        "email": login_email,
                        "password": login_password
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

                    This app provides educational medication information only.
                    It is not a doctor, diagnosis service, or replacement for
                    qualified healthcare advice.

                    **Privacy**

                    - Account and chat data are stored in Supabase.
                    - Medicine images are processed for the current request.
                    - Do not upload unnecessary personal or sensitive documents.
                    """
                )

            agree_terms = st.checkbox(
                "I agree to the Privacy Policy and Medical Disclaimer."
            )

            signup_submit = st.form_submit_button(
                "Create Account",
                use_container_width=True
            )

        if signup_submit:
            if not agree_terms:
                st.error(
                    "Please accept the Privacy Policy and Medical Disclaimer."
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
                        st.session_state.user_id = (
                            auth_response.user.id
                        )

                        st.session_state.user_email = (
                            auth_response.user.email
                        )

                        st.session_state.user_name = (
                            signup_name
                            or signup_email.split("@")[0].title()
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
                            "Account created! Please check your email "
                            "and then log in."
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

    email = st.session_state.get(
        "user_email",
        "User"
    )

    return (
        email
        .split("@")[0]
        .replace(".", " ")
        .title()
    )


def load_saved_chats():
    if (
        not supabase
        or not st.session_state.get("user_id")
    ):
        return []

    try:
        response = (
            supabase
            .table("medication_chat_messages")
            .select(
                "conversation_id, role, content, created_at"
            )
            .eq(
                "user_id",
                st.session_state.user_id
            )
            .order(
                "created_at",
                desc=True
            )
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
                    "created_at": row.get(
                        "created_at",
                        ""
                    ),
                }

            if row.get("role") == "user":
                text = (
                    row.get("content") or ""
                ).strip()

                if text:
                    title = text[:42]

                    if len(text) > 42:
                        title += "..."

                    conversations[chat_id]["title"] = title

        return list(
            conversations.values()
        )

    except Exception:
        return []


def load_chat_messages(chat_id):
    if (
        not supabase
        or not st.session_state.get("user_id")
    ):
        return []

    try:
        response = (
            supabase
            .table("medication_chat_messages")
            .select(
                "role, content, created_at"
            )
            .eq(
                "user_id",
                st.session_state.user_id
            )
            .eq(
                "conversation_id",
                chat_id
            )
            .order(
                "created_at",
                desc=False
            )
            .limit(200)
            .execute()
        )

        return [
            {
                "role": row.get("role"),
                "content": row.get("content")
            }
            for row in (response.data or [])
            if row.get("role")
            in ["user", "assistant"]
        ]

    except Exception:
        return []


def start_new_chat():
    st.session_state.current_chat_id = str(
        uuid.uuid4()
    )

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
    if (
        not supabase
        or not st.session_state.get("user_id")
    ):
        return

    supabase.table(
        "medication_chat_messages"
    ).insert(
        {
            "user_id": st.session_state.user_id,
            "conversation_id": (
                st.session_state.current_chat_id
            ),
            "role": role,
            "content": content,
        }
    ).execute()


def image_to_data_url(
    image_bytes,
    mime_type
):
    encoded = base64.b64encode(
        image_bytes
    ).decode("utf-8")

    return (
        f"data:{mime_type};base64,{encoded}"
    )


def extract_json_object(raw_text):
    """
    Safely extract JSON without requiring Groq JSON mode.
    """

    if not raw_text:
        raise ValueError(
            "Vision model returned an empty response."
        )

    text = raw_text.strip()

    if text.startswith("```"):
        text = re.sub(
            r"^```(?:json)?\s*",
            "",
            text,
            flags=re.I
        )

        text = re.sub(
            r"\s*```$",
            "",
            text
        )

    try:
        return json.loads(text)

    except json.JSONDecodeError:
        match = re.search(
            r"\{.*\}",
            text,
            flags=re.S
        )

        if not match:
            raise ValueError(
                "Could not find valid JSON in the vision response."
            )

        return json.loads(
            match.group(0)
        )


def identify_medicines_from_image(
    image_bytes,
    mime_type,
    client
):
    image_url = image_to_data_url(
        image_bytes,
        mime_type
    )

    vision_prompt = """
    You are a medicine-label verification assistant.

    Read only information that is visibly present in the image.

    The image may contain:
    1) a medicine box/blister/bottle, or
    2) a doctor's handwritten/printed prescription or medicine list.

    Do NOT diagnose, prescribe, or give dosage instructions.

    Return ONLY one JSON object with exactly these keys:

    {
      "document_type":
        "medicine_package" | "prescription" | "unknown",

      "medicines": [
        {
          "medicine_name": "string",
          "generic_name": "string",
          "strength": "string",
          "visible_text": "string",
          "confidence":
            "HIGH" | "MEDIUM" | "LOW"
        }
      ],

      "note": "short string"
    }

    Rules:

    - Never guess a medicine name when the image is unclear.
    - If handwriting is unclear, use LOW confidence or leave the medicine out.
    - Do not invent missing strength or dosage.
    - If no medicine can be reliably read, return an empty medicines list.
    """

    response = client.chat.completions.create(
        model="qwen/qwen3.6-27b",
        messages=[
            {
                "role": "system",
                "content": vision_prompt
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            "Read and verify the medicine names "
                            "visible in this image."
                        ),
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": image_url
                        },
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
                or
                (generic and (target in generic or generic in target))
            ):
                return record
    
        return None


def medicine_details_text(record):
    if not record:
        return ""

    parts = []

    if record.get("medicine_name"):
        parts.append(
            f"**{record['medicine_name']}**"
        )

    if record.get("generic_name"):
        parts.append(
            f"Generic: {record['generic_name']}"
        )

    if record.get("common_uses"):
        parts.append(
            f"Uses: {record['common_uses']}"
        )

    if record.get("common_side_effects"):
        parts.append(
            f"Common side effects: "
            f"{record['common_side_effects']}"
        )

    if record.get("important_precautions"):
        parts.append(
            f"Precautions: "
            f"{record['important_precautions']}"
        )

    if record.get("serious_warnings"):
        parts.append(
            f"Serious warnings: "
            f"{record['serious_warnings']}"
        )

    if record.get("source"):
        parts.append(
            f"Source: {record['source']}"
        )

    if record.get("source_url"):
        parts.append(
            f"Source URL: {record['source_url']}"
        )

    return "\n\n".join(parts)


def run_image_verification(
    image_bytes,
    mime_type
):
    api_key = st.secrets.get("GROQ_API_KEY")

    if not api_key:
        raise ValueError(
            "Groq API key is not configured."
        )

    client = Groq(api_key=api_key)

    return identify_medicines_from_image(
        image_bytes,
        mime_type,
        client
    )


def render_verified_image_result(
    result,
    medication_records
):
    medicines = result.get("medicines") or []

    if not medicines:
        st.warning(
            "Medicine could not be read clearly. "
            "Please upload a clearer photo, "
            "especially the medicine name or label."
        )
        return

    matched_count = 0

    for item in medicines:
        name = (
            item.get("medicine_name") or ""
        ).strip()

        confidence = (
            item.get("confidence")
            or "UNKNOWN"
        ).upper()

        if not name or confidence == "LOW":
            st.warning(
                "⚠️ Could not reliably read one "
                "medicine name. Please verify it manually."
            )
            continue

        record = find_kb_medicine(
            name,
            medication_records
        )

        if not record:
            st.info(
                f"**{name}** was read from the image, "
                "but it is not present in the verified "
                "medication knowledge base. "
                "I will not invent details."
            )
            continue

        matched_count += 1

        st.success(
            "Verified in knowledge base: "
            f"**{record.get('medicine_name')}**"
        )

        st.markdown(
            medicine_details_text(record)
        )

        if item.get("strength"):
            st.caption(
                "Strength visible in image: "
                f"{item['strength']}"
            )

    if matched_count == 0:
        st.warning(
            "The medicine name was readable, "
            "but no matching verified record was found."
        )


# =========================================================
# KNOWLEDGE BASE
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

except Exception as e:
    medication_records = []
    medicine_names = []

    st.warning(
        "Medication knowledge base could not "
        f"be loaded: {e}"
    )


# =========================================================
# LOAD CHAT
# =========================================================

if not st.session_state.chat_loaded:

    existing = load_chat_messages(
        st.session_state.current_chat_id
    )

    if existing:
        st.session_state.chat_messages = existing

    st.session_state.chat_loaded = True


if not st.session_state.chat_list:
    st.session_state.chat_list = load_saved_chats()


# =========================================================
# PROFESSIONAL UI
# =========================================================

st.markdown(
    """
    <style>

    #MainMenu {
        visibility: hidden;
    }

    footer {
        visibility: hidden;
    }

    .block-container {
        max-width: 900px;
        padding-top: .8rem;
        padding-bottom: 7rem;
        padding-left: 1rem;
        padding-right: 1rem;
    }

    .app-top {
        text-align: center;
        margin: 2px 0 14px 0;
    }

    .app-title {
        font-size: 26px;
        font-weight: 800;
        letter-spacing: -0.8px;
        line-height: 1.1;
    }

    .app-greeting {
        margin-top: 5px;
        font-size: 13px;
        opacity: .58;
    }

    [data-testid="stChatMessage"] {
        border-radius: 18px;
        margin-bottom: 8px;
    }

    [data-testid="stChatMessageContent"] {
        font-size: 15px;
        line-height: 1.55;
    }

    .tool-hint {
        text-align: center;
        font-size: 12px;
        opacity: .48;
        margin: 3px 0 5px;
    }

    .verified-card {
        border: 1px solid rgba(120,120,120,.18);
        border-radius: 16px;
        padding: 14px 16px;
        margin: 8px 0;
    }

    section[data-testid="stSidebar"] {
        border-right: 1px solid rgba(120,120,120,.12);
    }

    @media (max-width:700px) {

        .block-container {
            padding-left: .65rem;
            padding-right: .65rem;
            padding-top: .45rem;
        }

        .app-title {
            font-size: 22px;
        }

        [data-testid="stChatMessageContent"] {
            font-size: 14px;
        }

    }

    </style>
    """,
    unsafe_allow_html=True
)


# =========================================================
# HEADER
# =========================================================

st.markdown(
    f"""
    <div class="app-top">
        <div class="app-title">
            💊 Medication AI
        </div>
        <div class="app-greeting">
            Hello {get_display_name()} 👋
            • Verified medication information
        </div>
    </div>
    """,
    unsafe_allow_html=True
)


# =========================================================
# SIDEBAR
# =========================================================

with st.sidebar:

    st.markdown("### 💊 Medication AI")

    st.caption(
        "Verified • Educational • Safety-focused"
    )

    st.markdown(
        f"**{get_display_name()}**"
    )

    st.caption(
        st.session_state.get(
            "user_email",
            ""
        )
    )

    if st.button(
        "➕ New Chat",
        use_container_width=True
    ):
        start_new_chat()
        st.rerun()

    # -------------------------------------------------
    # ACCOUNT ACTIONS
    # -------------------------------------------------
    st.markdown("---")
    st.markdown("### ⚙️ Account")

    if st.button("🚪 Logout / Sign out", use_container_width=True):
        try:
            if supabase:
                supabase.auth.sign_out()
        except Exception:
            pass

        for key in [
            "user_id",
            "user_email",
            "user_name",
            "access_token",
            "chat_messages",
            "chat_list",
            "current_chat_id",
        ]:
            st.session_state.pop(key, None)

        st.rerun()

    with st.expander("⚠️ Delete Account", expanded=False):
        st.caption(
            "This permanently deletes your account and its stored app data. "
            "This action cannot be undone."
        )

        confirm_delete = st.checkbox(
            "I understand that my account will be permanently deleted.",
            key="confirm_delete_account",
        )

        if st.button(
            "🗑️ Permanently Delete Account",
            type="secondary",
            use_container_width=True,
            disabled=not confirm_delete,
        ):
            try:
                if not supabase:
                    st.error("Supabase is not configured.")
                else:
                    # The Edge Function must be deployed as `delete-account`.
                    # It securely deletes the authenticated Supabase user.
                    supabase.functions.invoke("delete-account")

                    try:
                        supabase.auth.sign_out()
                    except Exception:
                        pass

                    for key in list(st.session_state.keys()):
                        del st.session_state[key]

                    st.success("Account deleted successfully.")
                    st.rerun()
            except Exception as e:
                st.error(
                    "Account deletion failed. Make sure the Supabase "
                    "`delete-account` Edge Function is deployed."
                )

    st.markdown("---")

    # -------------------------------------------------
    # PRIVACY / TERMS / MEDICAL SAFETY
    # -------------------------------------------------
    st.markdown("### 🛡️ Safety & Legal")

    with st.expander("🔒 Privacy Policy", expanded=False):
        st.markdown("""
### Privacy Policy

**Effective date: September 12, 2026**

Medication AI Assistant is an educational medication-information application. We respect your privacy and aim to collect and process only the information necessary to provide the application's features.

#### 1. What information may be processed
- **Account information:** email address and account/profile information needed for authentication and account management.
- **Chat information:** questions and AI responses may be stored in your account's chat history so you can access previous conversations.
- **Uploaded images:** if you upload a medicine package, label, or prescription, the image is processed to identify visible medicine names. The application does not intentionally treat image recognition as a diagnosis.
- **Technical information:** normal service-level technical data may be processed by the hosting/platform providers required to operate the application.

#### 2. How information is used
Your information may be used to:
- authenticate your account;
- provide medication-information and knowledge-base features;
- save and display your conversation history;
- process uploaded medicine or prescription images when you request verification; and
- maintain, secure, troubleshoot, and improve the application.

#### 3. Knowledge-base approach
Medication information is intended to be grounded in the application's verified medication knowledge base. The application is designed to avoid inventing medicines or unsupported medical facts. A knowledge-base match does not mean that the information is appropriate for your individual medical situation.

#### 4. Third-party processing
The application uses third-party infrastructure and AI services, including **Supabase** for application data/authentication and **Groq** for AI processing. Information submitted to features that require these services may be processed by those providers according to their own terms and privacy practices.

**Do not upload information that you do not have permission to share.** Avoid unnecessary personal identifiers, medical-record numbers, identity documents, financial information, passwords, or other highly sensitive information.

#### 5. Security
We use authentication, database access controls, and platform security features intended to protect user information. However, no internet service can guarantee absolute security. You should use a strong password and avoid sharing your account credentials.

#### 6. Data retention and deletion
Account-related information and saved chats may remain available while your account is active. The application provides an account-deletion feature where available. Deletion may be subject to technical processing and any records that must legally or operationally be retained.

#### 7. Children's privacy
This application is not designed to collect information from children for independent medical decision-making. A parent or legal guardian should supervise use by minors.

#### 8. International use
The application may be accessed from different countries. Privacy and health-data laws differ by jurisdiction. This policy describes the application's intended data practices; it is **not a statement that the application is certified or compliant with every privacy or healthcare law worldwide**.

#### 9. Your responsibility
You are responsible for reviewing information before relying on it and for using appropriate professional healthcare services. Never use this application as the sole basis for an urgent or high-risk medical decision.

#### 10. Policy changes
This policy may be updated as the application, infrastructure, or legal requirements change. The latest version shown in the application should be treated as the current version.

**Important:** This Privacy Policy is a product-facing policy template and is not a substitute for legal advice. Before public commercial launch, have it reviewed for the countries where the application will operate.
""")

    with st.expander("📜 Terms & Conditions", expanded=False):
        st.markdown("""
### Terms & Conditions

**Effective date: September 12, 2026**

By creating an account or using Medication AI Assistant, you acknowledge that you have read and agree to these Terms & Conditions. If you do not agree, do not use the application.

#### 1. Purpose of the service
Medication AI Assistant is an **educational and informational knowledge-base application** designed to help users understand general medication information. It is not intended to replace a physician, pharmacist, nurse, emergency service, or other qualified healthcare professional.

#### 2. No diagnosis or treatment
The application does not provide a medical diagnosis, personalized treatment plan, personalized prescription, or personalized dosage instruction. It must not be used to decide whether to start, stop, increase, decrease, or change a prescription medicine.

#### 3. AI limitations
AI systems can misunderstand text, images, handwriting, medicine names, abbreviations, or context and can produce incomplete or incorrect output. Image recognition is an assistance feature, not proof of medicine identity. If a medicine name cannot be read or verified confidently, you should rely on the original packaging, prescription, pharmacist, or doctor.

#### 4. Verified knowledge base
The application's verified knowledge base is the primary source for medication explanations. If a medicine is not available in the verified knowledge base, the application may state that verified information is unavailable rather than inventing an answer.

#### 5. Prescription images
If you upload a doctor's prescription, the application may help identify visible medicine names and compare them with the verified knowledge base. It **does not replace the prescribing doctor's instructions** and must not be used to alter a prescription.

#### 6. Emergency situations
**Do not use this application for emergencies.** If you have severe difficulty breathing, severe chest pain, loss of consciousness, uncontrolled bleeding, severe allergic reaction, suspected poisoning/overdose, sudden serious weakness, or another life-threatening condition, seek emergency medical care immediately. In Pakistan, contact **Rescue 1122** or go to the nearest emergency department.

#### 7. User responsibilities
You agree to:
- provide information honestly when using the application;
- verify important medication information with a qualified healthcare professional;
- keep your login credentials secure;
- avoid uploading information belonging to another person unless you are authorized to do so; and
- comply with applicable laws when using the service.

#### 8. Prohibited use
You must not use the application to provide medical care to another person without appropriate professional authority, attempt to bypass security controls, abuse the service, upload unlawful content, or use AI output as a substitute for professional clinical judgment.

#### 9. Availability
The application may occasionally be unavailable because of maintenance, infrastructure failures, third-party service outages, network problems, or other technical issues. No uninterrupted availability is guaranteed.

#### 10. Third-party services
The application depends on third-party services for hosting, authentication, database infrastructure, and AI processing. Their availability and policies may affect the service.

#### 11. No guarantee of medical outcome
The application does not guarantee accuracy, completeness, suitability, or a particular health outcome. Healthcare decisions should be made with qualified professionals who can evaluate the user's complete clinical situation.

#### 12. Limitation of reliance
To the maximum extent permitted by applicable law, you acknowledge that use of the application and reliance on AI-generated information is at your own risk. Nothing in these Terms is intended to exclude rights or protections that cannot legally be excluded.

#### 13. Changes to these Terms
These Terms may be updated when the service or applicable requirements change. Continued use after an update constitutes acceptance of the updated Terms to the extent permitted by applicable law.

**Important:** These Terms are a product-facing legal template and should be reviewed by a qualified lawyer before commercial or international launch.
""")

    with st.expander("🚨 Medical Safety & Disclaimer", expanded=False):
        st.warning("**This is an educational medication-information tool — NOT a doctor, pharmacist, emergency service, or replacement for professional medical care.**")
        st.markdown("""
### Medical Safety Notice

- Information is provided for **general educational and reference purposes only**.
- Do not use the app to diagnose a disease or determine your personal treatment.
- Do not start, stop, or change prescription medicines based only on an AI response.
- Do not rely on the app for personalized dosage decisions.
- Always verify important information with your doctor or pharmacist.
- If the application cannot verify a medicine from its knowledge base, treat the information as unavailable rather than assuming the medicine is safe or appropriate.
- AI image recognition can make mistakes, especially with blurry photos or handwritten prescriptions.

**Emergency:** If you believe you are experiencing a serious or life-threatening condition, stop using the app and seek immediate medical care. In Pakistan, call **Rescue 1122** or go to the nearest emergency department.
""")

    with st.expander("ℹ️ About This Application", expanded=False):
        st.markdown("""
### Medication AI Assistant

Medication AI Assistant combines a **verified medication knowledge base, retrieval-based search (RAG), and generative AI** to make medication information easier to understand.

The application can help users:
- ask questions about medicines available in the verified knowledge base;
- understand common uses, common side effects, precautions, and serious warnings;
- upload a medicine image for name recognition and knowledge-base verification;
- upload a prescription image to help identify visible medicine names; and
- review previous conversations through saved chat history.

The system is intentionally designed around a safety principle: **when verified information is unavailable, it should say so rather than fabricate medical facts.**

This application is an educational technology project and should not be represented as a regulated medical device, clinical decision-support system, or medical provider unless and until the product has completed the appropriate regulatory, clinical, legal, privacy, security, and validation requirements for the target jurisdiction.
""")

    st.caption("Educational use only • Not medical advice • For emergencies contact local emergency services")

    st.markdown("---")

    st.markdown(
        "**Previous Chats**"
    )

    if not st.session_state.chat_list:

        st.caption(
            "No previous conversations yet."
        )

    else:

        for chat in st.session_state.chat_list:

            label = (
                (
                    "🟢 "
                    if chat["chat_id"]
                    == st.session_state.current_chat_id
                    else ""
                )
                + chat["title"]
            )

            if st.button(
                label,
                key=f"chat_{chat['chat_id']}",
                use_container_width=True
            ):

                st.session_state.current_chat_id = (
                    chat["chat_id"]
                )

                st.session_state.chat_loaded = False

                st.session_state.chat_messages = []

                st.session_state.selected_medicine = (
                    "None"
                )

                st.session_state.image_result = None

                st.session_state.image_bytes = None

                st.session_state.screening_active = False

                st.session_state.screening_started = False

                st.session_state.screening_answers = {}

                st.rerun()

    st.markdown("---")

    st.markdown(
        "### 💊 Medicine Knowledge"
    )

    options = [
        "None"
    ] + medicine_names

    selected_medicine = st.selectbox(
        "Select a medicine",
        options,
        index=(
            options.index(
                st.session_state.selected_medicine
            )
            if st.session_state.selected_medicine
            in options
            else 0
        ),
        label_visibility="collapsed"
    )

    st.session_state.selected_medicine = (
        selected_medicine
    )

    if selected_medicine != "None":

        record = find_kb_medicine(
            selected_medicine,
            medication_records
        )

        if record:
            st.markdown(
                medicine_details_text(record)
            )


# =========================================================
# EMPTY CHAT WELCOME
# =========================================================

if not st.session_state.chat_messages:

    st.markdown(
        """
        <div style="
            text-align:center;
            padding:42px 12px 18px;
            opacity:.85;
        ">

        <div style="
            font-size:42px;
            margin-bottom:10px;
        ">
        💊
        </div>

        <div style="
            font-size:24px;
            font-weight:800;
        ">
        How can I help?
        </div>

        <div style="
            font-size:14px;
            opacity:.62;
            margin-top:8px;
        ">
        Ask about a medicine, describe symptoms,
        or upload a medicine/prescription photo.
        </div>

        </div>
        """,
        unsafe_allow_html=True
    )

    st.markdown(
        """
        <div class="tool-hint">
        🔎 Verified KB &nbsp; • &nbsp;
        📷 Medicine image &nbsp; • &nbsp;
        📄 Prescription reading
        </div>
        """,
        unsafe_allow_html=True
    )


# =========================================================
# SHOW CHAT HISTORY
# =========================================================

for message in st.session_state.chat_messages:

    role = message.get("role")

    content = message.get(
        "content",
        ""
    )

    if role not in [
        "user",
        "assistant"
    ]:
        continue

    with st.chat_message(role):

        st.markdown(content)


# =========================================================
# CHAT INPUT
# =========================================================

chat_submission = st.chat_input(
    "Message Medication AI…",
    accept_file=True,
    file_type=[
        "png",
        "jpg",
        "jpeg"
    ],
    key=(
        f"chat_input_"
        f"{st.session_state.input_version}"
    )
)


user_question = None
attached_file = None


if chat_submission:

    if hasattr(
        chat_submission,
        "text"
    ):

        user_question = (
            chat_submission.text or ""
        ).strip()

        st.session_state["user_input_for_specialist"] = user_question


        if chat_submission.files:

            attached_file = (
                chat_submission.files[0]
            )

    else:

        user_question = (
            str(chat_submission)
            .strip()
        )


# =========================================================
# IMAGE UPLOAD
# =========================================================

if attached_file:

    try:

        image_bytes = (
            attached_file.getvalue()
        )

        mime_type = (
            getattr(
                attached_file,
                "type",
                None
            )
            or "image/jpeg"
        )

        st.session_state.image_bytes = (
            image_bytes
        )

        st.session_state.image_result = None

        with st.spinner(
            "🔎 Reading medicine image..."
        ):

            result = run_image_verification(
                image_bytes,
                mime_type
            )

        st.session_state.image_result = result

        st.markdown(
            "### 📷 Image Verification"
        )

        document_type = result.get(
            "document_type",
            "unknown"
        )

        if document_type == "prescription":

            st.info(
                "📄 This appears to be a prescription. "
                "I can read medicine names and verify "
                "them against the knowledge base, but "
                "I will not replace your doctor's instructions."
            )

        elif document_type == "medicine_package":

            st.info(
                "💊 This appears to be a medicine package."
            )

        render_verified_image_result(
            result,
            medication_records
        )

    except Exception as e:

        st.error(
            "Image verification failed: "
            f"{e}"
        )



# =========================================================
# SPECIALIST SUGGESTION
# =========================================================
specialist_text = st.session_state.get("user_input_for_specialist", "")
if specialist_text:
    suggested_specialist = specialist_for_condition(specialist_text)
    if suggested_specialist != "General Physician":
        st.info(
            f"👨‍⚕️ Based on the topic you mentioned, a **{suggested_specialist}** "
            "may be the appropriate specialist to discuss it with. "
            "This is general guidance, not a diagnosis."
        )
        loc = st.session_state.get("approx_location")
        if loc and loc.get("city"):
            st.link_button(
                f"🔎 Find {suggested_specialist} Near Me",
                nearby_places_url(suggested_specialist, loc["city"]),
                use_container_width=True,
            )

# =========================================================
# TEXT QUESTION / AI RESPONSE
# =========================================================

if user_question:

    display_question = user_question

    if attached_file:

        display_question = (
            f"{user_question}\n\n"
            "📷 Image attached for verification."
        )

    st.session_state.chat_messages.append(
        {
            "role": "user",
            "content": display_question
        }
    )

    with st.chat_message("user"):
        st.markdown(display_question)

    api_key = st.secrets.get(
        "GROQ_API_KEY"
    )

    if not api_key:

        st.error(
            "Groq API key is not configured."
        )

    else:

        try:

            # -------------------------------------------------
            # RETRIEVE VERIFIED KNOWLEDGE
            # -------------------------------------------------

            context = retrieve_context(
                user_question
            )

            # -------------------------------------------------
            # IMAGE CONTEXT
            # -------------------------------------------------

            image_context = ""

            if st.session_state.image_result:

                image_context = json.dumps(
                    st.session_state.image_result,
                    ensure_ascii=False
                )

            # -------------------------------------------------
            # SELECTED MEDICINE
            # -------------------------------------------------

            selected_medicine = (
                st.session_state.get(
                    "selected_medicine",
                    "None"
                )
            )

            # -------------------------------------------------
            # EMERGENCY KEYWORDS
            # -------------------------------------------------

            emergency_terms = [
                "chest pain",
                "difficulty breathing",
                "can't breathe",
                "cannot breathe",
                "severe bleeding",
                "unconscious",
                "fainted",
                "seizure",
                "stroke",
                "face drooping",
                "weakness one side",
                "suicide",
                "overdose",
                "poisoning"
            ]

            lower_question = (
                user_question.lower()
            )

            is_emergency = any(
                term in lower_question
                for term in emergency_terms
            )

            # -------------------------------------------------
            # SYSTEM PROMPT
            # -------------------------------------------------

            system_prompt = """
You are Medication AI, a safety-focused medication
INFORMATION assistant.

You are NOT a doctor.

You do NOT diagnose.

You do NOT prescribe.

You do NOT replace a healthcare professional.

Your job is to provide educational medication
information using the VERIFIED KNOWLEDGE BASE.

IMPORTANT WORKFLOW:

If the user describes symptoms and asks what medicine
to use, do NOT immediately provide a medicine recommendation.

First ask only the minimum relevant safety questions.

For headache, consider:
- When did it start?
- Whole head or one side?
- How severe?
- Vomiting?
- Vision change?
- Weakness?
- Fainting?
- Neck stiffness?
- Injury?

For fever/flu:
- How long?
- Temperature if measured?
- Cough?
- Sore throat?
- Body aches?
- Breathing difficulty?

For stomach problems:
- Acidity/heartburn?
- Diarrhea?
- Vomiting?
- Abdominal pain?
- When did it start?
- Blood?
- Black stool?
- Severe pain?
- Dehydration?
- Repeated vomiting?

For nose symptoms:
- Dry?
- Blocked?
- Watery?
- Nose bleeding?
- How long?

When relevant ask:
- Age
- Medicine allergies
- Current medicines
- Heart disease
- Kidney disease
- Liver disease
- Pregnancy possibility
- Breastfeeding

Do not ask unnecessary questions if the user's
previous answers already cover them.

AFTER SCREENING:

Only provide general educational medicine information
supported by the VERIFIED KNOWLEDGE BASE.

RULES:

1. Never invent a medicine.
2. Never invent a medical fact.
3. Never diagnose.
4. Never write a personalized prescription.
5. Never provide personalized dosage.
6. Never tell a user to start, stop, or change
   prescription medicine.
7. Do not assume multiple symptoms require
   multiple medicines.
8. Do not recommend antibiotics for ordinary
   cold or flu symptoms.
9. If a medicine is not in the verified KB,
   say verified information is unavailable.
10. If an image identifies a medicine, verify it
    against the KB before explaining it.
11. If a prescription is uploaded, help read and
    verify medicine names, but do not replace
    the doctor's instructions.
12. If image quality is unclear, say so.
13. Match the user's language automatically:
    English, Urdu script, Pakistani Roman Urdu,
    or mixed language.
14. Keep responses simple and easy to read.
15. For serious warning signs, advise urgent
    medical care. In Pakistan mention Rescue 1122.
16. The supplied verified KB is the primary source.
17. Do not fabricate information that is not
    supported by the KB.

When giving medication information, prefer this structure:

Medicine name
Generic name
Common uses
Common side effects
Important precautions
Serious warnings
Source

Do not provide personalized dosage.
"""

            # -------------------------------------------------
            # CHAT HISTORY
            # -------------------------------------------------

            history_for_model = []

            for item in (
                st.session_state.chat_messages[-10:]
            ):


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

            st.session_state.selected_medicine = "None"
            st.session_state.input_version += 1
            st.rerun()

        except Exception as e:
            st.error(f"AI response failed: {e}")
