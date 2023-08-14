import os
import openai
import gradio as gr
import argparse
import logging
from langchain.embeddings import OpenAIEmbeddings
from langchain.vectorstores import Chroma
from langchain.callbacks.base import BaseCallbackHandler
from langchain.chains import RetrievalQA
from langchain.chat_models import ChatOpenAI
import label_studio_sdk as ls
from label_studio_callback_handler import LabelStudioCallbackHandler

# Logging setup
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(levelname)s - %(message)s', 
                    datefmt='%d-%b-%y %H:%M:%S')
logger = logging.getLogger(__name__)


def main(api_key, ls_url, project_id, persist_dir):
    ls_callback = LabelStudioCallbackHandler(
        api_key=api_key,
        url=ls_url,
        project_id=project_id
    )

    vectorstore = Chroma(persist_directory=persist_dir, embedding_function=OpenAIEmbeddings())

    qa_chain_with_labelstudio = RetrievalQA.from_chain_type(
        llm=ChatOpenAI(model_name="gpt-3.5-turbo", temperature=0, 
        max_tokens=1000, callbacks=[ls_callback]),chain_type="stuff",
        retriever=vectorstore.as_retriever(), return_source_documents=True)
    
    def predict(message, history):
        history_openai_format = []
        history_openai_format.append({"role": "user", "content": message})
        response = qa_chain_with_labelstudio({"query": str(history_openai_format)})
        return response['result']

    gr.ChatInterface(predict).queue().launch(debug=True) 

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Parameterized script for chat interface.")
    parser.add_argument("--api_key", default=os.environ.get('LABEL_STUDIO_API_KEY', 'fallback_value'), help="Label Studio API key.")
    parser.add_argument("--ls_url", default="http://localhost:8080", help="Label Studio URL.")
    parser.add_argument("--project_id", type=int, help="Label Studio project ID.")
    parser.add_argument("--persist_dir", default="pd", help="Persist directory for vectorstore.")
    
    args = parser.parse_args()

    main(args.api_key, args.ls_url, args.project_id, args.persist_dir)
