import streamlit as st
from streamlit_chat import message
import tempfile
import os
from langchain.document_loaders.csv_loader import CSVLoader
from langchain.embeddings import HuggingFaceBgeEmbeddings
from langchain.vectorstores import FAISS
from langchain.llms import ctransformers
from langchain.chains import RetrievalQA
from langchain import PromptTemplate

from transformers import AutoModel, AutoTokenizer


def load_llm():
    llm=ctransformers.CTransformers(
        model = r"C:\Users\anany\Desktop\python\api google\res\llama-2-7b-chat.ggmlv3.q8_0.bin",
        model_type="llama",
        max_new_tokens=512,
        temperature = 0.9
    )
    return llm 



st.title("CharuBot")
csv_data=st.file_uploader("upload the csv file",type="csv")

if csv_data:
    with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
        tmp_file.write(csv_data.getvalue())
        tmp_file_path=tmp_file.name
    loader=CSVLoader(file_path=tmp_file_path,encoding="utf-8",csv_args={'delimiter': ','})
    data=loader.load()
 
    st.json(data)
    embeddings=HuggingFaceBgeEmbeddings(model_name='thenlper/gte-large'
                                      ,model_kwargs={'device': 'cpu'})

    db=FAISS.from_documents(data,embeddings)
    db.save_local('faiss/cricket')
    llm=load_llm()

    prompt_temp = '''
With the information provided try to answer the question. 
If you cant answer the question based on the information either say you cant find an answer or unable to find an answer.
This is related to cricket domain. So try to understand in depth about the context and answer only based on the information provided. Dont generate irrelevant answers

Context: {context}
Question: {question}
Do provide only correct answers

Correct answer:
    '''
    custom_prompt_tmp=PromptTemplate(template=prompt_temp,
                        input_variables=['context','question'])
    retrieval_qa_chain=RetrievalQA.from_llm(llm=llm,
                                    retriever=db.as_retriever(search_kwargs={'k':1}),
                                   
                                    return_source_documents=True,
                                   
                                        )
    def cricbot(query):
        answer = retrieval_qa_chain({"query": query})
        return answer["result"]

    if 'user' not in st.session_state:
        st.session_state['user'] = ["Hey there"]

    if 'assistant' not in st.session_state:
        st.session_state['assistant'] = ["Hello I am Cricbot and I am ready to help with your doubts in cricket"]

    container = st.container()

    with container:
        with st.form(key='cricket_form', clear_on_submit=True):
            
            user_input = st.text_input("", placeholder="Talk to your csv data here", key='input')
            submit = st.form_submit_button(label='Answer')
            
        if submit:
            output = cricbot(user_input)
            
            st.session_state['user'].append(user_input)
            st.session_state['assistant'].append(output)

    if st.session_state['assistant']:
        for i in range(len(st.session_state['assistant'])):
            message(st.session_state["user"][i], is_user=True, key=str(i) + '_user')
            message(st.session_state["assistant"][i], key=str(i))




