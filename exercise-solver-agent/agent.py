from google.adk.agents import Agent
from google import genai
import wolframalpha
import asyncio
from concurrent.futures import ThreadPoolExecutor

import os
from google.adk.tools.langchain_tool import LangchainTool
from langchain.document_loaders import PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.vectorstores import FAISS
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain.chains import RetrievalQA, LLMChain
from langchain.prompts import PromptTemplate

import numpy as np


WOLFRAM_ALPHA_API_ID = ""
GEMINI_API_ID = ""

# client = genai.Client(api_key=GEMINI_API_ID)

# result = client.models.embed_content(
#         model="gemini-embedding-exp-03-07",
#         contents="What is the meaning of life?")

# ========================== VECTORDB and EMBEDDING AGENT ==================

def build_vectorstore(pdf_path: str) -> FAISS:
    loader = PyPDFLoader(pdf_path)
    docs = loader.load()
    splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    chunks = splitter.split_documents(docs)
    # 2️⃣ Use the Gemini embedding model
    embeddings = GoogleGenerativeAIEmbeddings(
        model="models/embedding-001"  # state-of-the-art Gemini embedding :contentReference[oaicite:0]{index=0}
    )
    return FAISS.from_documents(chunks, embeddings)

VECTORDB = build_vectorstore(os.getenv("BOOK_PATH"))

async def retrieval_tool(query: str) -> str:
    results = VECTORDB.similarity_search(query, k=5)
    if not results:
        return "Nessun risultato trovato."
    # Concatena i contenuti dei documenti trovati
    return "\n\n".join([doc.page_content for doc in results])

embedder_agent = Agent(
    name="embedder_agent",
    model="gemini-2.0-flash",
    instruction=
    """
    You are a library of books from which you can retrieve with te retrieval_tool.
    The user might ask you any kind of question related to these books or their content.
    Keep always in mind the general content of the books you have.

    If somebody, weather your root agent or the user asks you about something not contained in your books, please inform it you do not have that information.
    """,
        
    tools=[retrieval_tool],
    description="It is a library of books and knows everything about them"
)

# ========================= WOLFRAM ALPHA ================================
wolfram_client = wolframalpha.Client(WOLFRAM_ALPHA_API_ID)

executor = ThreadPoolExecutor()

async def wolfram_alpha(query: str) -> str:
    """
    Interacts with wolfram alpha to solve equations and systems.
    The input must follow the syntax wolfram alpha expects.
    The output is a full result, since it uses the Full Result API of Wolfram Alpha
    """
    def query_wolfram():
        res = wolfram_client.query(query)
        if res["@success"] == True:
            for pod in res.pods:
                if pod["@title"] == "Result" or pod["@title"] == "Results":  
                    return pod.text
            return "Risultato non trovato."
        else:
            return "Errore nella query"
    return await asyncio.get_event_loop().run_in_executor(executor, query_wolfram)

solver_agent = Agent(
    name="solver_agent",
    model="gemini-2.0-flash-001",
    description="Solves STEM disciplines problems given in input",
    instruction="""
    You will recieve an exercise in input related to the book you can access through the 'retrieval_tool' (as many time as you need).
    You have to build a solution for the exercise based on what you have in the book, for example the theorems, the lemmas, the examples...
    Use wolfram alpha tool as many times as you need if you have to perform any calculation.

    If the exercise is not about something explained in the book, kindly tell it to the user.
    """,
    tools=[wolfram_alpha, retrieval_tool],
)

# async def ask_solver_agent(exercise: str) -> str:
#     """
#     Generates the solution for the exercise/question in input
#     """
#     return await solver_agent.run(exercise)

question_generator_agent = Agent(
    name="question_generator_agent",
    model="gemini-2.0-flash-001",
    description="Generates exercises and can give solutions",
    instruction="""
    Generate an exercises based on what you find in the book you can access through 'retrieval_tool'.
    You have to choose the topic.
    It must be an exercise which is not just a repetition of something theoretical but it is a practical exercise.

    If user asks you for solution, you can use the 'ask_solver_agent' tool passing to it the exercise you generated.

    You can communicate with your sub_agents or use your tools as many time as needed
    """,
    tools=[retrieval_tool],
    sub_agents=[solver_agent]
)

# async def handle_user(exercise: str) -> str:
#     """
#     Handles the user for what concerns question and answers on STEM subjects
#     """
#     return await solver_agent.run(exercise)

root_agent = Agent(
    model='gemini-2.0-flash-001',
    name='root_agent',
    description='A helpful assistant which dispatch work to its tools',
    instruction="""
    You are the first interface for the user.
    You have 2 sub-agents:
    1. An agent, called `question_generator_agent`, that handles didactical exercies
    2. An agent, called `embedder_agent`, that has access to a book
    If the user asks for an exercise, forward it to the question_generator_agent.
    If the user wants some information, first of all consult the embedder_agent, he might know something thanks to his library.
    If it do not have those information, please tell the user you are not able to provide that information.

    Otherwise, feel free to act as you want, you do not have to strictly stick to rules.
    """,
    sub_agents = [question_generator_agent, embedder_agent]
)