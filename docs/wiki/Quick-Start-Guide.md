# Quick Start Guide

## Getting Started with Building Local AI Architectures

This guide helps you set up your first local AI system using the concepts from this textbook.

---

## Prerequisites

- **Hardware**: GPU machine (8GB+ VRAM) or multi-machine setup
- **Software**:
  - Python 3.11+
  - Docker & Docker Compose
  - Git
  - A local LLM running (e.g., LM Studio on port 1234)

---

## Step 1: Clone the Repository

```bash
git clone https://github.com/jjuhric/LocalAIDevelopment.git
cd LocalAIDevelopment
```

---

## Step 2: Set Up Environment Variables

Create a `.env` file in the root directory:

```bash
# .env
LLM_MODEL_NAME=llama2
LLM_API_URL=http://host.docker.internal:1234
DEBUG=true
LOG_LEVEL=INFO
```

**For Linux users**, replace `host.docker.internal` with `172.17.0.1`.

---

## Step 3: Build and Start Docker Container

```bash
# Build the Docker image
docker-compose build

# Start the service
docker-compose up -d

# Check logs
docker-compose logs -f api
```

Expected output:
```
api  | INFO:     Uvicorn running on http://0.0.0.0:8000
```

---

## Step 4: Test the API

### Health Check

```bash
curl http://localhost:8000/health
```

Expected response:
```json
{"status": "healthy"}
```

### Basic Chat Endpoint

```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Write a hello world Python program",
    "thread_id": "test_123"
  }'
```

### Streaming Endpoint

```bash
curl -X POST http://localhost:8000/api/agent/stream \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Generate a fibonacci function",
    "thread_id": "stream_test"
  }' \
  --stream
```

You should see live tokens streaming back!

---

## Step 5: Explore the Architecture

### Project Structure

```
LocalAIDevelopment/
├── app/
│   ├── main.py                 # FastAPI app entry point
│   ├── api/
│   │   └── routes.py          # API endpoints
│   └── services/
│       ├── team_graph.py       # LangGraph state machine
│       ├── llm_client.py       # LLM integration
│       └── checkpointer.py     # State persistence
├── docker-compose.yml          # Container orchestration
├── Dockerfile                  # Container definition
├── requirements.txt            # Python dependencies
└── docs/
    └── wiki/                   # This documentation
```

### Key Files to Review

1. **`app/services/team_graph.py`** - Understand the state machine design
2. **`app/api/routes.py`** - See how streaming works
3. **`docker-compose.yml`** - Learn container configuration

---

## Common Issues & Troubleshooting

### Issue 1: Connection Timeout

**Problem**: `Request timed out` when calling the API

**Solution**: 
- Check `timeout-keep-alive` is set to 120+ in docker-compose.yml
- Restart the container: `docker-compose restart api`
- Check LM Studio is running and accessible

### Issue 2: "Host not found"

**Problem**: `Cannot connect to host.docker.internal`

**Solution**:
- On Linux, use `172.17.0.1` instead
- Update `.env` file and rebuild: `docker-compose build`
- Verify LM Studio port: `curl http://localhost:1234/v1/models`

### Issue 3: Out of Memory

**Problem**: Container crashes with OOM error

**Solution**:
- Reduce model size in LM Studio (use smaller model)
- Increase Docker memory limit in docker-compose.yml:
  ```yaml
  deploy:
    resources:
      limits:
        memory: 12G
  ```

### Issue 4: State Not Persisting

**Problem**: Conversation history lost after container restart

**Solution**:
- Ensure volume is mapped in docker-compose.yml
- Check volume exists: `docker volume ls`
- Verify `checkpointer=MemorySaver()` in team_graph.py (for production, use SqliteSaver)

---

## Next Steps

1. **[Chapter 1: Docker & Infrastructure](Chapter-1:-Infrastructure-Foundation)** - Understand containerization
2. **[Chapter 2: State Machines](Chapter-2:-State-Machines-&-Checkpointing)** - Build fault-tolerant workflows
3. **[Chapter 3: P2P Networks](Chapter-3:-Peer-to-Peer-Networks)** - Eliminate bottlenecks
4. **[Chapter 4: Event Streaming](Chapter-4:-Real-Time-Event-Streaming)** - Real-time UI updates

---

## Example: Building Your First Multi-Agent System

### Goal: Code Generator + Reviewer

```python
# app/services/team_graph.py
from langgraph.graph import StateGraph, END
from langgraph.types import Command
from typing import TypedDict, Annotated
import operator

class CodeState(TypedDict):
    messages: Annotated[list, operator.add]
    code: str
    feedback: str

def generator(state: CodeState) -> Command:
    """Generate code"""
    code = "def hello():\n    print('Hello, World!')"
    return Command(
        update={"code": code},
        goto="reviewer"
    )

def reviewer(state: CodeState) -> Command:
    """Review code"""
    feedback = "Code looks good!"
    return Command(
        update={"feedback": feedback},
        goto=END
    )

# Build graph
workflow = StateGraph(CodeState)
workflow.add_node("generator", generator)
workflow.add_node("reviewer", reviewer)
workflow.set_entry_point("generator")

graph = workflow.compile()

# Run it
result = graph.invoke({
    "messages": ["Generate hello world"],
    "code": "",
    "feedback": ""
})

print(result)
```

---

## Resources

### Official Documentation
- [LangGraph Documentation](https://langchain-ai.github.io/langgraph/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Docker Documentation](https://docs.docker.com/)

### Local LLM Setup
- [LM Studio](https://lmstudio.ai/) - Easy local LLM runner
- [Ollama](https://ollama.ai/) - Command-line LLM tool
- [GPT4All](https://gpt4all.io/) - Offline AI assistant

### Related Concepts
- [Server-Sent Events (MDN)](https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events)
- [State Machines (Wikipedia)](https://en.wikipedia.org/wiki/Finite-state_machine)
- [Microservices Architecture](https://microservices.io/)

---

## Getting Help

### Debug Logs

Enable debug logging:

```bash
# In docker-compose.yml
environment:
  - LOG_LEVEL=DEBUG
```

Then restart: `docker-compose restart api`

### Community Resources

- GitHub Issues: [LocalAIDevelopment Issues](https://github.com/jjuhric/LocalAIDevelopment/issues)
- LangGraph Discord: [LangChain Community](https://discord.gg/6adMQxSpJS)

---

## What's Next?

Once you've completed this Quick Start:

1. ✅ Deploy to production with PostgreSQL checkpointing
2. ✅ Add more agents (linter, tester, documenter)
3. ✅ Build a React frontend with streaming support
4. ✅ Scale to multiple GPU machines
5. ✅ Implement monitoring and observability

---

**Happy building! 🚀**
