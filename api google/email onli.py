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


EMAIL_ADDRESS = "anuvanshshrivatava014@gmail.com"
HUBSPOT_PRIVATE_APP_TOKEN = "pat-na2-f4b19780-5588-48bd-8139-c2be3f36d8bd"
CREDENTIALS_FILE = r"C:\path\to\your\credentials.json"
SCOPES = ['https://www.googleapis.com/auth/gmail.send']
GEMINI_API_KEY = "AIzaSyDQNS0rFb3dSNSxvYzNswF1MJ6BzVBkpWo"

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-1.5-flash")

st.title("📧 Smart Email Chatbot (Gemini NLP)")


if "chat_history" not in st.session_state:
    st.session_state["chat_history"] = []

if "email_state" not in st.session_state:
    st.session_state["email_state"] = {}


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
        return json.loads(json_str)
    except Exception as e:
        st.session_state["chat_history"].append({
            "role": "assistant",
            "content": f"❌ Gemini NLP Error: {e}"
        })
        return None


def find_contact(state):
    st.session_state["chat_history"].append({"role": "assistant", "content": "🔍 Searching HubSpot for contact..."})
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
            state["error"] = "Contact not found in HubSpot."
            st.session_state["chat_history"].append({
                "role": "assistant",
                "content": "❌ Contact not found in HubSpot."
            })
    except requests.exceptions.RequestException as e:
        state["error"] = f"HubSpot API error: {e}"
        st.session_state["chat_history"].append({
            "role": "assistant",
            "content": f"❌ HubSpot API error: {e}"
        })

    return state

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
        send_result = service.users().messages().send(userId="me", body={'raw': raw_message}).execute()

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


email_builder = StateGraph(dict)
email_builder.add_node("FindContact", find_contact)
email_builder.add_node("GenerateEmail", generate_email)
email_builder.add_node("SendEmail", send_email)

email_builder.set_entry_point("FindContact")
email_builder.add_edge("FindContact", "GenerateEmail")
email_builder.add_edge("GenerateEmail", "SendEmail")
email_builder.add_edge("SendEmail", END)

email_graph = email_builder.compile()


if prompt := st.chat_input("Say something like: Send an email to John Doe about the meeting"):
    st.session_state["chat_history"].append({"role": "user", "content": prompt})
    email_info = extract_email_details(prompt)

    if email_info:
        st.session_state["email_state"] = email_info
        with st.spinner("Processing your request..."):
            result = email_graph.invoke(email_info)
    else:
        st.session_state["chat_history"].append({
            "role": "assistant",
            "content": "🤔 I didn't understand that. Try:\n\nSend an email to Jane Smith about the product launch"
        })


for message in st.session_state["chat_history"]:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])