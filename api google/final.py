import streamlit as st
import requests
import base64
import json
import os
from email.mime.text import MIMEText
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
import google.generativeai as genai
from langgraph.graph import StateGraph, END
import unicodedata

EMAIL_ADDRESS = "anuvanshshrivastava014@gmail.com"
HUBSPOT_PRIVATE_APP_TOKEN = "pat-na2-f37c2365-f4cc-4e3c-9a97-532586da5e95"
CREDENTIALS_FILE = r"C:\Users\anany\Desktop\python\api google\credentials.json"
SCOPES = ['https://www.googleapis.com/auth/gmail.send']
GEMINI_API_KEY = "AIzaSyDQNS0rFb3dSNSxvYzNswF1MJ6BzVBkpWo"

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-1.5-flash")

st.set_page_config(page_title="Smart Email Chatbot")
st.title("📧 Smart Email Chatbot (Gemini NLP + Universal Chat)")

for key in ["chat_history", "email_state", "awaiting_email_input", "adding_contact", "new_contact_info", "awaiting_confirmation"]:
    if key not in st.session_state:
        st.session_state[key] = [] if key == "chat_history" else {} if key in ["email_state", "new_contact_info"] else False

def authenticate_gmail():
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
            with open('token.json', 'w') as token:
                token.write(creds.to_json())
    return creds

def extract_email_details(prompt):
    system_prompt = f"""
Extract this info in JSON format:
- First name
- Last name
- Purpose of the email
- Intent: "send" if the user wants to send the email, or "draft" if they just want to generate it.

Respond ONLY in JSON like:
{{
  "first_name": "John",
  "last_name": "Doe",
  "purpose": "to follow up on the meeting",
  "intent": "send"
}}

Prompt: "{prompt}"
"""
    try:
        response = model.generate_content(system_prompt)
        text = response.text
        json_str = text[text.find('{'):text.rfind('}') + 1]
        return json.loads(json_str)
    except:
        return None

def universal_chat(prompt):
    try:
        return model.generate_content(prompt).text.strip()
    except Exception as e:
        return f"❌ Gemini reply error: {e}"

def safe_text(text):
    try:
        return unicodedata.normalize("NFKD", text)
    except:
        return "⚠️ Error displaying message"

def find_contact(state):
    if state.get("email"):
        return state

    first_name = state.get("first_name", "").strip()
    last_name = state.get("last_name", "").strip()
    if not first_name or not last_name:
        state["error"] = "Missing first or last name."
        return state

    st.session_state["chat_history"].append({"role": "assistant", "content": "🔍 Searching HubSpot for contact..."})

    headers = {
        "Authorization": f"Bearer {HUBSPOT_PRIVATE_APP_TOKEN}",
        "Content-Type": "application/json"
    }
    data = {
        "filterGroups": [
            {"filters": [
                {"propertyName": "firstname", "operator": "CONTAINS_TOKEN", "value": first_name},
                {"propertyName": "lastname", "operator": "CONTAINS_TOKEN", "value": last_name}
            ]}
        ],
        "properties": ["email", "firstname", "lastname"]
    }
    try:
        response = requests.post("https://api.hubapi.com/crm/v3/objects/contacts/search", headers=headers, json=data)
        result = response.json()
        if result.get("results"):
            contact = result["results"][0]["properties"]
            state["email"] = contact.get("email")
            state["firstname"] = contact.get("firstname")
            st.session_state["chat_history"].append({
                "role": "assistant",
                "content": f"✅ Contact found: {contact['firstname']} {contact['lastname']} ({contact['email']})"
            })
        else:
            state["error"] = "❌ No email found for the contact. Please enter the contact's email first."
            st.session_state["awaiting_email_input"] = True
    except Exception as e:
        state["error"] = f"HubSpot API error: {e}"
    return state

def add_contact_to_hubspot(first_name, last_name, email):
    headers = {
        "Authorization": f"Bearer {HUBSPOT_PRIVATE_APP_TOKEN}",
        "Content-Type": "application/json"
    }
    data = {
        "properties": {
            "firstname": first_name,
            "lastname": last_name,
            "email": email
        }
    }
    response = requests.post("https://api.hubapi.com/crm/v3/objects/contacts", headers=headers, json=data)
    if response.status_code == 409:
        raise Exception("⚠️ A contact with this email already exists in HubSpot.")
    response.raise_for_status()
    return response.json()

def generate_email(state):
    if "error" in state: return state
    firstname = state.get("firstname", state.get("first_name", "there"))
    purpose = state.get("purpose", "our discussion")
    content = f"""
Hi {firstname},

I hope this email finds you well.

I'm reaching out regarding {purpose}. I’d love to talk more at your convenience.

Please let me know when you're available.

Best regards,  
Your teammate
"""
    state["email_content"] = content
    st.session_state["chat_history"].append({
        "role": "assistant", "content": f"✍️ Generated email:\n\n```text\n{content.strip()}\n```"
    })
    return state

def send_email(state):
    if "email" not in state or "email_content" not in state:
        st.session_state["chat_history"].append({"role": "assistant", "content": "❌ Cannot send email. Missing required info."})
        return state
    creds = authenticate_gmail()
    service = build('gmail', 'v1', credentials=creds)
    message = MIMEText(state["email_content"])
    message["to"] = state["email"]
    message["from"] = EMAIL_ADDRESS
    message["subject"] = "A Message from Your teammate"
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
    service.users().messages().send(userId="me", body={"raw": raw}).execute()
    st.session_state["chat_history"].append({"role": "assistant", "content": "✅ Email sent successfully!"})
    return state

def handle_add_contact_flow(prompt):
    contact_info = st.session_state["new_contact_info"]
    if not st.session_state["adding_contact"]:
        st.session_state["adding_contact"] = True
        st.session_state["chat_history"].append({"role": "assistant", "content": "📝 Please provide the contact's first name."})
    elif "first_name" not in contact_info:
        contact_info["first_name"] = prompt.strip()
        st.session_state["chat_history"].append({"role": "assistant", "content": "📝 Please provide the contact's last name."})
    elif "last_name" not in contact_info:
        contact_info["last_name"] = prompt.strip()
        st.session_state["chat_history"].append({"role": "assistant", "content": "📧 Please provide the contact's email address."})
    elif "email" not in contact_info:
        contact_info["email"] = prompt.strip()
        try:
            add_contact_to_hubspot(contact_info["first_name"], contact_info["last_name"], contact_info["email"])
            st.session_state["chat_history"].append({"role": "assistant", "content": "✅ Contact added successfully!"})
        except Exception as e:
            st.session_state["chat_history"].append({"role": "assistant", "content": f"❌ Failed to add contact: {e}"})
        st.session_state["adding_contact"] = False
        st.session_state["new_contact_info"] = {}

def handle_confirmation_flow(prompt):
    if "yes" in prompt.lower():
        st.session_state["chat_history"].append({"role": "assistant", "content": "✅ Confirmation received. Proceeding with the email process."})
        compiled_graph.invoke(st.session_state["email_state"])
        st.session_state["awaiting_confirmation"] = False
    elif "no" in prompt.lower():
        st.session_state["chat_history"].append({"role": "assistant", "content": "❌ Confirmation not received. How else can I help you?"})
        st.session_state["awaiting_confirmation"] = False
    else:
        st.session_state["chat_history"].append({"role": "assistant", "content": "❓ Please reply with 'yes' or 'no'."})

email_builder = StateGraph(dict)
email_builder.add_node("FindContact", find_contact)
email_builder.add_node("GenerateEmail", generate_email)
email_builder.add_node("SendEmail", send_email)
email_builder.set_entry_point("FindContact")
email_builder.add_edge("FindContact", "GenerateEmail")
email_builder.add_edge("GenerateEmail", "SendEmail")
compiled_graph = email_builder.compile()

if prompt := st.chat_input("Say something like: Send email to John Doe about meeting"):
    st.session_state["chat_history"].append({"role": "user", "content": prompt})

    if st.session_state.get("awaiting_confirmation"):
        handle_confirmation_flow(prompt)
    elif st.session_state.get("adding_contact"):
        handle_add_contact_flow(prompt)
    elif any(p in prompt.lower() for p in ["add contact", "add a contact", "add me a contact", "create contact", "new contact"]):
        handle_add_contact_flow(prompt)
    elif st.session_state.get("awaiting_email_input") and "@" in prompt:
        email = prompt.strip()
        info = st.session_state.get("email_state", {})
        try:
            add_contact_to_hubspot(info["first_name"], info["last_name"], email)
            info["email"] = email
            st.session_state["awaiting_email_input"] = False
            st.session_state["chat_history"].append({"role": "assistant", "content": "✅ Email saved. Please confirm before sending."})
            st.session_state["awaiting_confirmation"] = True
            st.session_state["chat_history"].append({"role": "assistant", "content": f"Please confirm if the following details are correct:\n\n{info}"})
        except Exception as e:
            st.session_state["chat_history"].append({"role": "assistant", "content": f"❌ Failed to save email: {e}"})
    else:
        email_info = extract_email_details(prompt)

        # Check that email_info contains valid data
        if (
            email_info and 
            email_info.get("first_name") and 
            email_info.get("last_name") and 
            email_info.get("purpose")
        ):
            st.session_state["email_state"] = email_info
            intent = email_info.get("intent", "send")
            if intent == "draft":
                st.session_state["chat_history"].append({"role": "assistant", "content": "📝 Generating email draft only (no sending)..."})
                generate_email(email_info)
            else:
                st.session_state["awaiting_confirmation"] = True
                st.session_state["chat_history"].append({"role": "assistant", "content": f"Please confirm if the following details are correct:\n\n{email_info}"})
        else:
            # fallback to universal chat
            with st.spinner("Thinking..."):
                reply = universal_chat(prompt)
            st.session_state["chat_history"].append({"role": "assistant", "content": reply})

for message in st.session_state["chat_history"]:
    with st.chat_message(message["role"]):
        st.markdown(safe_text(message["content"]))
