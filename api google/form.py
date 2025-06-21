import streamlit as st
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import base64
import os
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from google.auth.transport.requests import Request


SCOPES = ['https://www.googleapis.com/auth/gmail.send']
TOKEN_PATH = r"C:\Users\anany\Desktop\python\token.json"
CREDENTIALS_PATH = r"C:\Users\anany\Desktop\python\api google\credentials.json"
EMAIL_RECEIVER = "anuvanshshrivastava014@gmail.com"
WEBSITE_LINK = "https://weppdev.tech/"


def gmail_service():
    creds = None
    if os.path.exists(TOKEN_PATH):
        creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_PATH, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_PATH, 'w') as token:
            token.write(creds.to_json())
    return build('gmail', 'v1', credentials=creds)


def send_email(subject, body, to_email, is_html=False):
    if is_html:
        message = MIMEMultipart("alternative")
        message['to'] = to_email
        message['from'] = "me"
        message['subject'] = subject
        message.attach(MIMEText(body, "html"))
    else: 
        message = MIMEText(body)
        message['to'] = to_email
        message['from'] = "me"
        message['subject'] = subject

    raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
    try:
        service = gmail_service()
        service.users().messages().send(userId="me", body={'raw': raw_message}).execute()
        return True
    except Exception as e:
        st.error(f"❌ Error sending email: {e}")
        return False

def handle_submission(full_name, company_name, user_email, phone, budget, services, project_details):
 
    subject_admin = f"New Contact Submission from {full_name}"
    body_admin = f"""
Name: {full_name}
Company: {company_name}
Email: {user_email}
Phone: {phone}
Budget: {budget}
Services Interested: {', '.join(services)}
Project Details:
{project_details}
    """
   
    subject_user = "Thank You for Contacting Weppdev 🚀"
    body_user = f"""
<html>
  <body style="background-color:#3b0e54 ; padding: 20px; font-family: Arial, sans-serif;">
    <h2 style="color:white;">Thank you, {full_name}! 🎉</h2>
    <p style="color:white;">We’ve received your message and our team will be in touch shortly.</p>
    <p style="color:white;">Meanwhile, you can explore more about us by visiting our website:</p>
    <a href="{WEBSITE_LINK}" target="_blank" 
       style="background-color: #2563eb; color:white; padding: 10px 20px; 
              text-decoration: none; border-radius: 6px; display: inline-block; border: 1px solid #000000;">
       Visit Weppdev
    </a>
    <p style="color:white; margin-top: 20px;">We appreciate your interest in Weppdev!</p>
    <pre style="color:white; margin-top: 20px;">our team is constantly working on your request:-
      {project_details}</pre>
  </body>
</html>
"""


    sent_admin = send_email(subject_admin, body_admin, EMAIL_RECEIVER)
    sent_user = send_email(subject_user, body_user, user_email, is_html=True)

    if sent_admin and sent_user:
        st.success("✅ Message sent! You’ll also receive a confirmation email.")
    else:
        st.error("❌ Failed to send message. Please try again later.")


st.set_page_config(page_title="Contact Us - Weppdev", layout="centered")
st.markdown("""
    <style>
    .title {
        text-align: center;
        color: white;
        font-size: 2.5em;
        font-weight: bold;
        margin-top: 20px;
    }
    .subtitle {
        text-align: center;
        color: #cbd5e1;
        margin-bottom: 40px;
    }
    .form-style {
        background-color: #1e293b;
        padding: 30px;
        border-radius: 12px;
        color: white;
    }
    </style>
""", unsafe_allow_html=True)

st.markdown('<div class="title">Contact Us</div>', unsafe_allow_html=True)
st.markdown('<div class="subtitle">Let us know what you need help with!</div>', unsafe_allow_html=True)

with st.form("start_project", border=False):
    st.markdown('<div class="form-style">', unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    with col1:
        full_name = st.text_input("Full Name*", "")
        company_name = st.text_input("Company Name", "")
    with col2:
        email = st.text_input("Email Address*", "")
        phone = st.text_input("Phone Number", "")

    budget = st.selectbox("Budget Range", ["Select budget range", "< $5,000", "$5,000 - $10,000", "$10,000 - $25,000", "$25,000+"])

    st.markdown("Services of Interest")
    col1, col2 = st.columns(2)
    with col1:
        ai_auto = st.checkbox("AI Automation")
        data_infra = st.checkbox("Data Infrastructure")
        ecommerce = st.checkbox("eCommerce Solutions")
    with col2:
        enterprise = st.checkbox("Enterprise SaaS")
        analytics = st.checkbox("Analytics Dashboards")
        custom_dev = st.checkbox("Custom Development")

    project_details = st.text_area("Project Details*", height=150)
    submitted = st.form_submit_button("Send Message 🚀")

    if submitted:
        if full_name and email and project_details:
            services = []
            if ai_auto: services.append("AI Automation")
            if data_infra: services.append("Data Infrastructure")
            if ecommerce: services.append("eCommerce")
            if enterprise: services.append("Enterprise SaaS")
            if analytics: services.append("Analytics")
            if custom_dev: services.append("Custom Development")

            handle_submission(full_name, company_name, email, phone, budget, services, project_details)
        else:
            st.error("❌ Please fill in all required fields.")

    st.markdown('</div>', unsafe_allow_html=True)