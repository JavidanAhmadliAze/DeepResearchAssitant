from langchain_chroma import Chroma
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from dotenv import load_dotenv
from langchain.tools import tool

load_dotenv()
embedding = GoogleGenerativeAIEmbeddings(model="gemini-embedding-001")

vector_store = Chroma(
    collection_name="deep_research_texts",
    embedding_function=embedding,
    persist_directory=r"C:\Users\User\team_8\team_8\agentic_core\cognition\memory",
    collection_metadata={"hnsw:space": "cosine"}
)
@tool
def retrieve_data_with_score(research_brief: str):
    """
    Retrieve relevant documents from memory using the research brief.
    Only return results if top score <= 0.30; otherwise indicate that further research is needed.
    """
    retrieved_docs_with_score = vector_store.similarity_search_with_score(
        query=research_brief, k=10
    )

    best_score = min(score for _, score in retrieved_docs_with_score) if retrieved_docs_with_score else 1
    needs_research = best_score > 0.30

    if needs_research:
        return {
            "needs_research": True,
            "serialized": "",
        }

    serialized = "\n\n".join(
        f"Content: {doc.page_content}" for doc, _ in retrieved_docs_with_score
    )

    return {
        "needs_research": False,
        "serialized": serialized
    }

if __name__ == '__main__':
    result = retrieve_data_with_score("best agentic deep research assistant tools according to performance, latency, cost")
    print("Needs further research?", result["needs_research"])
    print("Serialized documents:\n", result["serialized"])
