# 🔎 DeepResearcher: Autonomous Multi-Agent Intelligence
Transforming ambiguous queries into verified, executive-grade research reports through stateful agentic workflows.
## 🧐 Executive Summary
TDeepResearcher is a high-performance autonomous system designed to bridge the gap between simple RAG (Retrieval-Augmented Generation) and deep, iterative analysis. By leveraging a multi-agent orchestration layer, the system self-corrects, reflects on data quality, and scales its research effort dynamically to deliver high-fidelity, standardized English reports.
## 🛠️ Technology Stack
| Layer | Component | Description |
|------|-----------|-------------|
| Orchestration | LangGraph | Multi-agent state management with recursive reasoning loops and multi-model routing. |
| Core Reasoning | DeepSeek-V3 | Primary reasoning engine optimized for strategic planning and logical chain-of-thought analysis. |
| Multimodal & Speed | Gemini 1.5 Flash | Utilized for high-speed context processing, large-scale embeddings, and rapid data extraction. |
| Refinement | OpenAI GPT-4o | Specialized agent for final report polishing, critique, and structural verification. |
| API Backend | FastAPI | Asynchronous gateway managing background workers and long-polling research states. |
| Knowledge Base | ChromaDB | Vector persistence layer for RAG and long-term memory across research cycles. |
| Memory State | PostgreSQL | Transactional storage for persistent agent checkpoints, ensuring 100% resilience. |


## 🧠 Agentic Reasoning Framework
The core of this system is a high-performance **Multi-Agent Orchestration Layer**. Unlike traditional pipelines, this workflow implements **Compound Intelligence**—where agents autonomously reason and adapt their strategies based on real-time findings.

### Autonomous Lifecycle
The workflow is governed by a persistent state machine through four strategic phases:
1. **Interactive Scoping (HITL)**: Resolves semantic ambiguity through a Human-in-the-Loop cycle, generating a concrete "Source of Truth" Research Brief.
2. **Elastic Strategic Planning**: A central **Supervisor** determines whether the task requires a **Sequential Deep-Dive** or a **Parallel Fan-out** (Map-Reduce) across specialized agents.
3. **Iterative Reflection & Critique**: Peer-review layer that identifies informational gaps or contradictions, autonomously triggering recursive search cycles to fill them.
4. **Final Synthesis (The Reporter)**: Distills raw research into a structured executive document while updating the **Long-term Vector Memory**.

### Workflow Topology
![img.png](img.png)

## 📡 API Architecture & FastAPI Usage

FastAPI serves as the robust communication layer between the user interface and the autonomous background agents. It utilizes an **Asynchronous Request-Response Pattern** to ensure that long-running research tasks do not block the web server.

1. **The Asynchronous Polling Pattern**
    Deep research can take minutes to complete. To provide a smooth user experience, the system implements the **202 Accepted** pattern:

**Task Initiation**: When a research request is sent, FastAPI validates the input and immediately returns an `HTTP 202 Accepted` status with a chat_id.

**Background Execution**: The `BackgroundTasks` module triggers the LangGraph workflow in a non-blocking thread, allowing the API to remain responsive to other users.

**State Polling**: The frontend client polls a GET /chat/{chat_id} endpoint. FastAPI retrieves the latest "checkpoints" from the PostgreSQL database, providing real-time updates on the agent's current "thought" or "action." 

2. **Dependency Injection & Lifespan Management**
    The backend utilizes FastAPI’s Dependency Injection system to manage database sessions and LLM clients efficiently.
**Database Pooling**: Connections to `AsyncPostgresSaver` (for agent state) and ChromaDB (for vector memory) are managed through a global lifespan event. This ensures that connections are opened once at startup and closed gracefully on shutdown, preventing memory leaks.

**Security & Auth**: FastAPI’s `Depends` system is used to inject authentication and rate-limiting, ensuring the research engine is protected from misuse.

```
# Initiate a deep research task
curl -X POST "http://localhost:8000/chat" \
     -H "Content-Type: application/json" \
     -d '{"query": "Future of Solid State Batteries 2026"}'

# Response: 202 Accepted
# { "chat_id": "550e8400-e29b-41d4-a716-446655440000", "status": "Research Started" }

# Poll for results
curl -X GET "http://localhost:8000/chat/550e8400-e29b-41d4-a716-446655440000"
```

## 🚀 Deployment & Configuration

 **Containerized Orchestration**
```
# Clone the repository
git clone https://github.com/your-repo/deep-researcher.git
cd deep-researcher

# Build and run with Docker
docker-compose up --build
```

 **Environment Variables (.env)**

```
# Model Keys
DEEPSEEK_API_KEY=sk-...
OPENAI_API_KEY=sk-...
GOOGLE_API_KEY=AIza...

# Paths & Database
VECTOR_DB_PATH=/app/data/output
DATABASE_URL=postgresql+asyncpg://user:pass@db:5432/research_db
```

## 🛠️ Technical Considerations

**Stateful Resilience**: Utilizing `AsyncPostgresSaver`, the system is "Interrupt-Safe," allowing research to resume even after container restarts.

**Multi-LLM Redundancy**: The system can fall back to alternative models if a specific provider encounters rate limits or downtime.
