import csv
import pandas as pd
import streamlit as st
import os
import google.generativeai as genai

GOOGLE_API_KEY = ""
genai.configure(api_key=GOOGLE_API_KEY)

model = genai.GenerativeModel("gemini-pro")
chat = model.start_chat(history=[])


def get_gemini_response(question, df):

    additional_context = df.to_string(index=False)  
    
    
    full_prompt = f"{additional_context} {question}"
    response = chat.send_message(full_prompt, stream=True)
    return response


st.set_page_config(page_title="DEMOOOO")

st.header("WOND PROJECT")

if 'chat_history' not in st.session_state:
    st.session_state['chat_history'] = []

if 'processed_csv_data' not in st.session_state:
    st.session_state['processed_csv_data'] = pd.DataFrame()  


input = st.text_input("Input: ", key="input")
submit = st.button("Ask the question")
csv_filename = r"C:\Users\anany\Desktop\python\chatbot\ind.csv"   

csv_file_path = os.path.join(os.getcwd(), csv_filename)

if submit and input:
    if os.path.exists(csv_file_path):  
        
        df = pd.read_csv(csv_file_path)
        st.session_state["processed_csv_data"] = df  
        
        
        response = get_gemini_response(input, df)
    else:
        
        st.error(f"CSV file '{csv_filename}' not found in the current directory.")
        response = get_gemini_response(input, pd.DataFrame())  

    
    st.session_state['chat_history'].append(("You", input))
    st.subheader("The Response is")
    for chunk in response:
        st.write(chunk.text)
        st.session_state['chat_history'].append(("Bot", chunk.text))

st.subheader("The Chat History is")
for role, text in st.session_state['chat_history']:
    st.write(f"{role}: {text}")

