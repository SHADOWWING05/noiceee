import streamlit as st
import requests
from email.mime.text import MIMEText
import base64
import os
import json
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
import google.generativeai as genai

# ====== Configuration ======
EMAIL_ADDRESS = "anuvanshshrivatava014@gmail.com"
HUBSPOT_PRIVATE_APP_TOKEN = "pat-na2-f4b19780-5588-48bd-8139-c2be3f36d8bd"
CREDENTIALS_FILE = r"C:\Users\anany\Desktop\python\api google\credentials.json"
SCOPES = ['https://www.googleapis.com/auth/gmail.send']
GEMINI_API_KEY = "AIzaSyDQNS0rFb3dSNSxvYzNswF1MJ6BzVBkpWo"

genai.configure(api_key=GEMINI_API_KEY)

st.title("📧 Smart Email Chatbot (Gemini-powered)")

# ====== State Initialization ======
if "chat_history" not in st.session_state:
    st.session_state["chat_history"] = []

if "email_state" not in st.session_state:
    st.session_state["email_state"] = {}

# Initialize missing session state variables with default values
if "first_name" not in st.session_state:
    st.session_state["first_name"] = ""
if "last_name" not in st.session_state:
    st.session_state["last_name"] = ""
if "purpose" not in st.session_state:
    st.session_state["purpose"] = ""

# ====== Gmail Authentication ======
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
            creds = flow.run_local_server(port=0, access_type='offline', prompt='consent')
            with open(token_path, 'w') as token:
                token.write(creds.to_json())
    return creds

# ====== HubSpot: Create Contact ======
def create_contact(state):
    st.session_state["chat_history"].append({
        "role": "assistant",
        "content": "➕ Creating new contact in HubSpot..."
    })
    headers = {
        "Authorization": f"Bearer {HUBSPOT_PRIVATE_APP_TOKEN}",
        "Content-Type": "application/json"
    }
    first_name = state.get("first_name")
    last_name = state.get("last_name")
    email = state.get("email") or f"{first_name.lower()}.{last_name.lower()}@example.com"
    payload = {
        "properties": {
            "firstname": first_name,
            "lastname": last_name,
            "email": email
        }
    }
    try:
        response = requests.post("https://api.hubapi.com/crm/v3/objects/contacts", headers=headers, json=payload)
        response.raise_for_status()
        st.session_state["chat_history"].append({
            "role": "assistant",
            "content": f"✅ Contact created: {first_name} {last_name} ({email})"
        })
        state["email"] = email
        state["firstname"] = first_name
    except Exception as e:
        state["error"] = f"HubSpot contact creation error: {e}"
        st.session_state["chat_history"].append({
            "role": "assistant",
            "content": f"❌ Could not create contact: {e}"
        })
    return state

# ====== HubSpot: Find Contact ======
def find_contact(state):
    st.session_state["chat_history"].append({
        "role": "assistant",
        "content": "🔍 Searching HubSpot for contact..."
    })
    headers = {
        "Authorization": f"Bearer {HUBSPOT_PRIVATE_APP_TOKEN}",
        "Content-Type": "application/json"
    }
    first_name = state.get("first_name", "").strip()
    last_name = state.get("last_name", "").strip()
    if not first_name or not last_name:
        state["error"] = "Missing first or last name."
        st.session_state["chat_history"].append({
            "role": "assistant",
            "content": "❌ Missing first or last name for HubSpot search."
        })
        return state
    data = {
        "filterGroups": [
            {
                "filters": [
                    {"propertyName": "firstname", "operator": "CONTAINS_TOKEN", "value": first_name},
                    {"propertyName": "lastname", "operator": "CONTAINS_TOKEN", "value": last_name}
                ]
            }
        ],
        "properties": ["email", "firstname", "lastname"]
    }
    try:
        url = "https://api.hubapi.com/crm/v3/objects/contacts/search"
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()
        result = response.json()
        if "results" in result and len(result["results"]) > 0:
            contact = result["results"][0]["properties"]
            state["email"] = contact.get("email")
            state["firstname"] = contact.get("firstname")
            st.session_state["chat_history"].append({
                "role": "assistant",
                "content": f"✅ Contact found: {contact.get('firstname', '')} {contact.get('lastname', '')} ({contact.get('email', '')})"
            })
        else:
            st.session_state["chat_history"].append({
                "role": "assistant",
                "content": "❌ Contact not found in HubSpot. Creating new one..."
            })
            state = create_contact(state)
    except requests.exceptions.RequestException as e:
        state["error"] = f"HubSpot API error: {e}"
        st.session_state["chat_history"].append({
            "role": "assistant",
            "content": f"❌ HubSpot API error: {e}"
        })
    return state

# ====== Generate NLP Response ======
def generate_nlp_response(user_message):
    try:
        # Use genai.generate() to get the NLP response
        nlp_response = genai.generate(text=user_message)
        return nlp_response["text"]  # The response is in the "text" key
    except Exception as e:
        return f"Sorry, I couldn't process that input. Error: {e}"

# ====== Email Generation ======
def generate_email(state):
    if "error" in state:
        return state
    firstname = state.get("firstname", "there")
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
    return state

# ====== Email Sending ======
def send_email(state):
    if "error" in state or "email" not in state or "email_content" not in state:
        state["error"] = "Missing recipient or content."
        st.session_state["chat_history"].append({
            "role": "assistant",
            "content": "❌ Cannot send email. Missing required info."
        })
        return state
    st.session_state["chat_history"].append({
        "role": "assistant",
        "content": "📤 Sending email..."
    })
    try:
        creds = authenticate_gmail()
        service = build('gmail', 'v1', credentials=creds)
        message = MIMEText(state["email_content"])
        message["to"] = state["email"]
        message["from"] = EMAIL_ADDRESS
        message["subject"] = "A Message from Your teammate"
        raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
        service.users().messages().send(userId="me", body={'raw': raw_message}).execute()
        state["email_sent"] = True
        st.session_state["chat_history"].append({
            "role": "assistant",
            "content": "✅ Email sent successfully!"
        })
    except Exception as e:
        state["error"] = f"Email send error: {e}"
        st.session_state["chat_history"].append({
            "role": "assistant",
            "content": f"❌ Email send error: {e}"
        })
    return state

# ====== Main Workflow Function ======
def start_workflow():
    # Retrieve or initialize state
    email_state = st.session_state["email_state"]
    if not email_state.get("email_sent", False):
        # If email is not sent, execute the steps
        email_state = find_contact(email_state)
        email_state = generate_email(email_state)
        email_state = send_email(email_state)

    # Store state and show chat history
    st.session_state["email_state"] = email_state
    for message in st.session_state["chat_history"]:
        if message["role"] == "assistant":
            st.chat_message("assistant").markdown(message["content"])
        else:
            st.chat_message("user").markdown(message["content"])

# ====== User Interaction (Chatbot-style) ======
user_input = st.text_input("Your message:", key="user_input")

if user_input:
    nlp_response = generate_nlp_response(user_input)
    st.session_state["chat_history"].append({
        "role": "assistant",
        "content": nlp_response
    })
    start_workflow()