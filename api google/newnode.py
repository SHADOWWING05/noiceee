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

# Configuration
EMAIL_ADDRESS = "anuvanshshrivatava014@gmail.com"
HUBSPOT_PRIVATE_APP_TOKEN = "YOUR TOKEN"
CREDENTIALS_FILE = r"C:\\path\\to\\your\\credentials.json"
SCOPES = ['https://www.googleapis.com/auth/gmail.send']
GEMINI_API_KEY = "YOUR API KEY"

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-1.5-flash")

st.set_page_config(page_title="Smart Email Chatbot")
st.title("📧 Smart Email Chatbot (Gemini NLP + Confirmation Flow)")

# ✅ Correct Initialization
if "chat_history" not in st.session_state:
    st.session_state["chat_history"] = []
if "email_state" not in st.session_state:
    st.session_state["email_state"] = {}
if "awaiting_email_input" not in st.session_state:
    st.session_state["awaiting_email_input"] = False
if "awaiting_confirmation" not in st.session_state:
    st.session_state["awaiting_confirmation"] = False
if "awaiting_contact_info" not in st.session_state:
    st.session_state["awaiting_contact_info"] = False
if "awaiting_subject" not in st.session_state:
    st.session_state["awaiting_subject"] = False
if "contact_info" not in st.session_state:
    st.session_state["contact_info"] = {}

# Gmail Auth
def authenticate_gmail():
    creds = None
    token_path = 'token.json'
    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
            with open(token_path, 'w') as token:
                token.write(creds.to_json())
    return creds

# Gemini NLP
def extract_email_details(prompt):
    system_prompt = f"""
Extract this info in JSON format:
- First name
- Last name
- Purpose of the email

Respond ONLY in JSON like:
{{
  "first_name": "John",
  "last_name": "Doe",
  "purpose": "the product launch"
}}

Prompt: "{prompt}"
"""
    try:
        response = model.generate_content(system_prompt)
        text = response.text
        json_str = text[text.find('{'):text.rfind('}') + 1]
        result = json.loads(json_str)
        return result if result.get("first_name") and result.get("last_name") and result.get("purpose") else None
    except:
        return None

def universal_chat(prompt):
    greetings = ["hello", "hi", "hey"]
    if any(greeting in prompt.lower() for greeting in greetings):
        return "👋 Hi there! How can I assist you today?"
    try:
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        return f"❌ Gemini reply error: {e}"

# HubSpot functions
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
    try:
        response = requests.post("https://api.hubapi.com/crm/v3/objects/contacts", headers=headers, json=data)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 409:
            st.session_state["chat_history"].append({"role": "assistant", "content": "⚠️ Contact already exists."})
            return None
        raise

def find_contact(state):
    if state.get("email"):
        return state

    st.session_state["chat_history"].append({"role": "assistant", "content": "🔍 Searching HubSpot for contact..."})
    headers = {
        "Authorization": f"Bearer {HUBSPOT_PRIVATE_APP_TOKEN}",
        "Content-Type": "application/json"
    }
    first_name = state.get("first_name", "").strip()
    last_name = state.get("last_name", "").strip()

    data = {
        "filterGroups": [
            {"filters": [
                {"propertyName": "firstname", "operator": "CONTAINS_TOKEN", "value": first_name},
                {"propertyName": "lastname", "operator": "CONTAINS_TOKEN", "value": last_name}
            ]}
        ],
        "properties": ["email", "firstname", "lastname"]
    }

    response = requests.post("https://api.hubapi.com/crm/v3/objects/contacts/search", headers=headers, json=data)
    result = response.json()
    if result.get("results"):
        contact = result["results"][0]["properties"]
        state["email"] = contact["email"]
        state["firstname"] = contact["firstname"]
        st.session_state["chat_history"].append({
            "role": "assistant",
            "content": f"✅ Contact found: {contact['firstname']} {contact['lastname']} ({contact['email']})"
        })
    else:
        state["error"] = "Contact not found"
        st.session_state["awaiting_email_input"] = True
        st.session_state["chat_history"].append({
            "role": "assistant",
            "content": "❌ Contact not found. Please enter their email."
        })
    return state

def generate_email(state):
    if "error" in state:
        return state
    firstname = state.get("firstname", state.get("first_name", "there"))
    purpose = state.get("purpose", "our discussion")
    email_content = f"""
Hi {firstname},

I hope this email finds you well.

I'm reaching out regarding {purpose}. I’d love to talk more at your convenience.

Please let me know when you're available.

Best regards,  
Your teammate
"""
    state["email_content"] = email_content
    st.session_state["chat_history"].append({
        "role": "assistant",
        "content": f"✍️ Generated email:\n\n```text\n{email_content.strip()}\n```"
    })
    st.session_state["awaiting_subject"] = True
    st.session_state["chat_history"].append({
        "role": "assistant",
        "content": "📩 Please provide a subject for the email."
    })
    return state

def get_subject(state):
    subject = state.get("subject")
    if not subject:
        st.session_state["chat_history"].append({
            "role": "assistant",
            "content": "❌ Please provide a subject for the email."
        })
        return state

    state["email_subject"] = subject
    st.session_state["chat_history"].append({
        "role": "assistant",
        "content": f"📝 Email subject set: {subject}"
    })
    st.session_state["awaiting_confirmation"] = True
    st.session_state["chat_history"].append({
        "role": "assistant",
        "content": "📩 Would you like to send this email? Reply with **yes** or **no**."
    })
    return state

def confirm_send(state):
    if st.session_state.get("awaiting_confirmation"):
        state["halt"] = True
    return state

def send_email(state):
    if "error" in state or "email" not in state or "email_content" not in state or "email_subject" not in state:
        st.session_state["chat_history"].append({"role": "assistant", "content": "❌ Cannot send email. Missing required info."})
        return state
    st.session_state["chat_history"].append({"role": "assistant", "content": "📤 Sending email..."})
    creds = authenticate_gmail()
    service = build('gmail', 'v1', credentials=creds)
    message = MIMEText(state["email_content"])
    message["to"] = state["email"]
    message["from"] = EMAIL_ADDRESS
    message["subject"] = state["email_subject"]
    raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
    service.users().messages().send(userId="me", body={'raw': raw_message}).execute()
    st.session_state["chat_history"].append({"role": "assistant", "content": "✅ Email sent successfully!"})
    return state

# LangGraph
email_builder = StateGraph(dict)
email_builder.add_node("FindContact", find_contact)
email_builder.add_node("GenerateEmail", generate_email)
email_builder.add_node("GetSubject", get_subject)
email_builder.add_node("ConfirmSend", confirm_send)
email_builder.add_node("SendEmail", send_email)
email_builder.set_entry_point("FindContact")
email_builder.add_edge("FindContact", "GenerateEmail")
email_builder.add_edge("GenerateEmail", "GetSubject")
email_builder.add_edge("GetSubject", "ConfirmSend")
email_builder.add_edge("ConfirmSend", "SendEmail")
email_builder.add_edge("SendEmail", END)
email_graph = email_builder.compile()

# Chat Input Handler
if prompt := st.chat_input("Say something like: send email to John Doe about meeting"):
    st.session_state["chat_history"].append({"role": "user", "content": prompt})

    if 'add contact' in prompt.lower():
        st.session_state["awaiting_contact_info"] = True
        st.session_state["chat_history"].append({"role": "assistant", "content": "📝 Please provide the contact's first name."})
    elif 'send email' in prompt.lower():
        extracted = extract_email_details(prompt)
        if extracted:
            st.session_state["email_state"].update(extracted)
            email_graph.run(st.session_state["email_state"])
        else:
            st.session_state["chat_history"].append({"role": "assistant", "content": "❌ Couldn't understand the email details. Try again."})
    else:
        response = universal_chat(prompt)
        st.session_state["chat_history"].append({"role": "assistant", "content": response})

# Show chat history
for message in st.session_state["chat_history"]:
    st.markdown(f"**{message['role'].capitalize()}:** {message['content']}")