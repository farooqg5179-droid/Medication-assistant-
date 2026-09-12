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
    if not supabase or not st.session_state."").strip().lower()
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
        parts.append(f"Generic: {record['generic_name']}")v
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
    return identify_medicines_from_image(image_bytes, mime_type, , ""))

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
                st.session_state.screening_answers = {}
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
            "This deletes your stored chat/profile data from the tables used by this app."
        )
        confirm_delete = st.checkbox("I confirm I want to delete my data.")
        if st.button("Delete My Data", type="primary", use_container_width=True):
            if not confirm_delete:
                st.error("Please tick the confirmation checkbox first.")
            else:
                try:
                    uid = st.session_state.user_id
                    supabase.table("medication_chat_messages").delete().eq(
                        "user_id", uid
                    ).execute()
                    supabase.table("profiles").delete().eq("id", uid).execute()
                    supabase.auth.sign_out()
                    for key in [
                        "user_id",
                        "user_email",
                        "user_name",
                        "access_token",
                    ]:
                        st.session_state.pop(key, None)
                    st.success("Your stored app data has been deleted.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Delete failed: {e}")

# =========================================================
# HEADER
# =========================================================
display_name = get_display_name()

st.markdown(
    f""" <div class="app-top"> <div class="app-title">💊 Medication AI</div> <div class="app-greeting">Hi {display_name} · Ask about a medicine or describe your symptoms</div> </div> """,
    unsafe_allow_html=True,
)

# =========================================================
# EXISTING CHAT
# =========================================================
for msg in st.session_state.chat_messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# =========================================================
# ATTACHMENT / MEDICINE TOOL ROW
# =========================================================
st.markdown(
    '<div class="tool-hint">＋ Camera or medicine/photo tools are available below</div>',
    unsafe_allow_html=True,
)

tool1, tool2 = st.columns([1, 1])

with tool1:
    with st.popover("＋ Medicine / Camera", use_container_width=True):
        st.caption("Upload a medicine photo or a doctor's prescription photo.")

        camera_photo = st.camera_input(
            "Take photo",
            key=f"camera_{st.session_state.input_version}",
        )

        uploaded_photo = st.file_uploader(
            "Upload photo",
            type=["png", "jpg", "jpeg"],
            key=f"photo_{st.session_state.input_version}",
        )

        photo_to_verify = camera_photo or uploaded_photo

        if photo_to_verify is not None:
            st.image(photo_to_verify, use_container_width=True)

            if st.button(
                "🔎 Verify Medicine",
                key=f"verify_{st.session_state.input_version}",
                use_container_width=True,
            ):
                try:
                    result = run_image_verification(
                        photo_to_verify.getvalue(),
                        photo_to_verify.type or "image/jpeg",
                    )
                    st.session_state.image_result = result
                    st.session_state.image_bytes = photo_to_verify.getvalue()
                    st.success("Image checked.")
                except Exception as e:
                    st.error(f"Could not verify image: {e}")

        if st.session_state.image_result:
            render_verified_image_result(
                st.session_state.image_result,
                medication_records,
            )

with tool2:
    with st.popover("💊 Medicine", use_container_width=True):
        st.caption("Optional medicine context")
        options = ["None"] + medicine_names

        selected_medicine = st.selectbox(
            "Medicine",
            options,
            index=(
                options.index(st.session_state.selected_medicine)
                if st.session_state.selected_medicine in options
                else 0
            ),
            label_visibility="collapsed",
        )
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
        "verified medicine is generally used for."
    )

selected_medicine = st.session_state.selected_medicine

# =========================================================
# CHAT PROCESSING
# =========================================================
if user_question:
    # -----------------------------------------------------
    # Image attached directly to chat input
    # -----------------------------------------------------
    if attached_file is not None:
        try:
            result = run_image_verification(
                attached_file.getvalue(),
                attached_file.type or "image/jpeg",
            )
            st.session_state.image_result = result
        except Exception as e:
            st.session_state.image_result = None
            st.warning(f"Image verification failed: {e}")

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

    api_key = symptoms require multiple medicines. 9. Do not recommend antibiotics for ordinary cold/flu symptoms. 10. If the user uploads a doctor's prescription, help READ/VERIFY the medicine names against the verified KB and explain what those medicines are generally used for. Do not replace the doctor's instructions. 11. If the image is unclear, say it is unclear and ask for a clearer photo. 12. Match the user's language automatically: English, Urdu script, Pakistani Roman Urdu, or mixed language. 13. Keep responses clean, short, and easy to read. 14. For serious warning signs, advise urgent medical care. In Pakistan mention Rescue 1122. The supplied knowledge-base context is the primary source. Do not use outside medical facts when the KB does not support them. """

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
