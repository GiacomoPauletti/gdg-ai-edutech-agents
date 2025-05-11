from google.adk.agents import Agent
from google import genai
import wolframalpha
import asyncio
from concurrent.futures import ThreadPoolExecutor

WOLFRAM_ALPHA_API_ID = ""
GEMINI_API_ID = ""

client = genai.Client(api_key=GEMINI_API_ID)

result = client.models.embed_content(
        model="gemini-embedding-exp-03-07",
        contents="What is the meaning of life?")


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


root_agent = Agent(
    model='gemini-2.0-flash-001',
    name='root_agent',
    description='An assistant for solving physics problems',
    instruction="""
    You have to help the user to solve Physics problems.
    You are given access to Wolfram Alpha to help you with the tool of name wolfram_alpha
    """,
    tools = [wolfram_alpha]
)
