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

EMAIL_ADDRESS = "anuvanshshrivatava014@gmail.com"
HUBSPOT_PRIVATE_APP_TOKEN = "pat-na2-bf4d72a7-c916-4335-8048-879bff86e8d5"
CREDENTIALS_FILE = r"C:\Users\anany\Desktop\python\api google\credentials.json"
SCOPES = ['https://www.googleapis.com/auth/gmail.send']
GEMINI_API_KEY = "AIzaSyDQNS0rFb3dSNSxvYzNswF1MJ6BzVBkpWo"

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-1.5-flash")

st.set_page_config(page_title="Smart Email Chatbot")
st.title("📧 Smart Email Chatbot (Gemini NLP + Universal Chat)")

if "chat_history" not in st.session_state:
    st.session_state["chat_history"] = []
if "email_state" not in st.session_state:
    st.session_state["email_state"] = {}
if "awaiting_email_input" not in st.session_state:
    st.session_state["awaiting_email_input"] = False

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
        result = json.loads(json_str)
        return result if result.get("first_name") and result.get("last_name") and result.get("purpose") else None
    except:
        return None

def universal_chat(prompt):
    try:
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        return f"❌ Gemini reply error: {e}"

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
            st.session_state["chat_history"].append({"role": "assistant", "content": "⚠️ Contact already exists. Using existing contact."})
            return None
        raise

def find_contact(state):
    if state.get("email"):  # Skip HubSpot search if email is known
        return state

    st.session_state["chat_history"].append({"role": "assistant", "content": "🔍 Searching HubSpot for contact..."})


    headers = {
        "Authorization": f"Bearer {HUBSPOT_PRIVATE_APP_TOKEN}",
        "Content-Type": "application/json"
    }
    first_name = state.get("first_name", "").strip()
    last_name = state.get("last_name", "").strip()
    if not first_name or not last_name:
        state["error"] = "Missing first or last name."
        return state

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
        response.raise_for_status()
        result = response.json()
        if result.get("results"):
            contact = result["results"][0]["properties"]
            state["email"] = contact.get("email")
            state["firstname"] = contact.get("firstname")
            st.session_state["chat_history"].append({
                "role": "assistant",
                "content": f"✅ Contact found: {contact.get('firstname', '')} {contact.get('lastname', '')} ({contact.get('email', '')})"
            })
        else:
            state["error"] = "Contact not found in HubSpot."
            st.session_state["awaiting_email_input"] = True
            st.session_state["chat_history"].append({
                "role": "assistant",
                "content": "❌ Contact not found in HubSpot.\n\nPlease enter the contact's email in chat."
            })
    except Exception as e:
        state["error"] = f"HubSpot API error: {e}"
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
    return state

def send_email(state):
    if "error" in state or "email" not in state or "email_content" not in state:
        st.session_state["chat_history"].append({"role": "assistant", "content": "❌ Cannot send email. Missing required info."})
        return state
    st.session_state["chat_history"].append({"role": "assistant", "content": "📤 Sending email..."})


    try:
        creds = authenticate_gmail()
        service = build('gmail', 'v1', credentials=creds)
        message = MIMEText(state["email_content"]) 
        message["to"] = state["email"]
        message["from"] = EMAIL_ADDRESS
        message["subject"] = "A Message from Your teammate"
        raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
        service.users().messages().send(userId="me", body={'raw': raw_message}).execute()
        st.session_state["chat_history"].append({"role": "assistant", "content": "✅ Email sent successfully!"})
    except Exception as e:
        st.session_state["chat_history"].append({"role": "assistant", "content": f"❌ Email send error: {e}"})
    return state

def safe_text(text):
    try:
        return unicodedata.normalize("NFKD", text)
    except:
        return "⚠️ Error displaying message"


# Define state graph for handling email flow
email_builder = StateGraph(dict)
email_builder.add_node("FindContact", find_contact)
email_builder.add_node("GenerateEmail", generate_email)
email_builder.add_node("SendEmail", send_email)
email_builder.set_entry_point("FindContact")
email_builder.add_edge("FindContact", "GenerateEmail")
email_builder.add_edge("GenerateEmail", "SendEmail")
email_builder.add_edge("SendEmail", END)
email_graph = email_builder.compile()


# Handle user input
if prompt := st.chat_input("Say something like: Send an email to John Doe about the meeting or just say hi!"):
    st.session_state["chat_history"].append({"role": "user", "content": prompt})

    if st.session_state.get("awaiting_email_input") and "@" in prompt:
        email = prompt.strip()
        info = st.session_state.get("email_state", {})
        try:
            add_contact_to_hubspot(info["first_name"], info["last_name"], email)
            info["email"] = email
            st.session_state["awaiting_email_input"] = False
            st.session_state["chat_history"].append({"role": "assistant", "content": "✅ Contact added successfully!"})
            email_graph.invoke(info)
        except Exception as e:
            st.session_state["chat_history"].append({"role": "assistant", "content": f"❌ Failed to add contact: {e}"})
    else:
        email_info = extract_email_details(prompt)
        if email_info:
            st.session_state["email_state"] = email_info
            st.session_state["awaiting_email_input"] = False
            with st.spinner("Processing your request..."):
                email_graph.invoke(email_info)
        else:
            with st.spinner("Thinking..."):
                reply = universal_chat(prompt)
            st.session_state["chat_history"].append({"role": "assistant", "content": reply})


# Display chat history
for message in st.session_state["chat_history"]:
    with st.chat_message(message["role"]):
        st.markdown(safe_text(message["content"]))
