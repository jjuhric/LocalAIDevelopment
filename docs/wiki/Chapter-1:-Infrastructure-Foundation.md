# Chapter 1: The Infrastructure Foundation (Docker & FastAPI)

## 1.1 The Concept: Decoupling Compute from Orchestration

Before writing any AI logic, we must establish a production-ready environment. Running AI applications directly on a host operating system (Windows/Mac) leads to **dependency conflicts** that cause "works on my machine" failures.

The solution is **Containerization via Docker**.

### Why Containerize?

In enterprise architecture, we separate two critical layers:

| Layer | Purpose | Hardware |
|-------|---------|----------|
| **Compute Layer** | GPU running heavy LLM math (via LM Studio) | Dedicated GPU machine |
| **Orchestration Layer** | Python application managing state and routing | Low-power device (Raspberry Pi) |

By containerizing the Orchestration Layer using **Docker and FastAPI**, we create a lightweight, portable microservice that can:
- Run control logic on inexpensive hardware
- Communicate over the network to a dedicated GPU machine
- Scale horizontally across multiple machines
- Survive OS upgrades and dependency conflicts

---

## 1.2 The Implementation: docker-compose.yml

We use Docker Compose to define and run our multi-container application. A critical tuning step: because local LLMs take time to process requests on consumer hardware, we must extend Uvicorn timeouts to prevent premature disconnections.

### Docker Compose Configuration

```yaml
# docker-compose.yml
services:
  api:
    build: .
    container_name: agent_api
    ports:
      - "8000:8000"
    # Override Uvicorn timeouts for local LLM inference
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --timeout-keep-alive 120 --timeout-graceful-shutdown 120
    env_file:
      - .env
    volumes:
      - "./local_memory_backup:/app/backup"
```

### Line-by-Line Breakdown

| Code Segment | Explanation & Teaching Point |
|--------------|-------------------------------|
| `services: api: build: .` | Instructs Docker to build the image using the Dockerfile in the root directory |
| `ports: - "8000:8000"` | Maps port 8000 inside the container to port 8000 on the host, making the API accessible locally |
| `command: uvicorn app.main:app ...` | **CRITICAL STEP**: Overrides the default container entrypoint. Explicitly adds `--timeout-keep-alive 120`. Standard web servers timeout after 30s. Local AI models often take longer to "wake up" and process tokens. Without this extension, the server will sever the connection mid-thought, causing "Request timed out" errors. |
| `env_file: - .env` | Loads environment variables from `.env` file into the container |
| `volumes: - "./local_memory_backup:/app/backup"` | Maps a folder on the host to a folder inside the container. This ensures that when the container is destroyed, database checkpoints (memory) are safely persisted on the hard drive |

### Key Insight: The Timeout Problem

**Standard Behavior:**
- Default Uvicorn timeout: 30 seconds
- Local GPU inference time: 30-120+ seconds (depending on model size and complexity)
- Result: Connection drops mid-generation ❌

**Solution:**
- Override to: 120 seconds (or higher)
- Local AI models get time to compute
- Connection stays open for entire generation ✅

---

## 1.3 The Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

This Dockerfile:
1. Uses Python 3.11 slim image (lightweight)
2. Sets working directory to `/app`
3. Installs Python dependencies
4. Copies application code
5. Runs Uvicorn on startup

---

## 1.4 Environment Variables

Create a `.env` file in your root directory:

```bash
# .env
LLM_MODEL_NAME=llama2
LLM_API_URL=http://host.docker.internal:1234
THREAD_ID=default
DEBUG=false
```

**Key Notes for Docker:**
- `host.docker.internal` allows the container to reach services on the host machine (Windows/Mac)
- On Linux, use `172.17.0.1` instead
- Keep sensitive keys in `.env` and add to `.gitignore`

---

## 1.5 Running Your Container

### Build and Run

```bash
# Build the Docker image
docker-compose build

# Start the service in the background
docker-compose up -d

# View logs
docker-compose logs -f api

# Stop the service
docker-compose down
```

### Verify It's Running

```bash
# Test the API endpoint
curl http://localhost:8000/health
```

---

## 1.6 Local Compute Separation Example

### Architecture Diagram

```
┌─────────────────────────────────────┐
│     Local Development Machine       │
├─────────────────────────────────────┤
│                                     │
│  ┌─────────────────────────────┐   │
│  │   Docker Container          │   │
│  │  (Orchestration Layer)      │   │
│  │                             │   │
│  │  - FastAPI server           │   │
│  │  - LangGraph logic          │   │
│  │  - State management         │   │
│  │  Port: 8000                 │   │
│  └────────────┬────────────────┘   │
│               │                     │
│               │ HTTP calls          │
│               │ (over local network)│
│               ▼                     │
└─────────────────────────────────────┘
                 │
        ┌────────┴────────┐
        ▼                  ▼
    
┌──────────────────────┐  ┌──────────────────────┐
│  GPU Machine (local) │  │  LM Studio instance  │
│  (Compute Layer)     │  │  Port: 1234          │
│                      │  │                      │
│  Heavy LLM inference │  │  Llama 3 / Qwen     │
│  on dedicated GPU     │  │                      │
└──────────────────────┘  └──────────────────────┘
```

This separation allows:
- **Flexible hardware**: Run orchestration on Pi, compute on GPU machine
- **Scalability**: Add more GPU machines without touching orchestration code
- **Resilience**: One machine failing doesn't take down the entire system

---

## Student Comprehension Check

### Question 1: Timeout Configuration
**Q: Why do we need to override the `timeout-keep-alive` setting in Uvicorn when working with local AI?**

**A:** Local hardware (like CPUs or consumer GPUs) computes AI tokens slower than cloud clusters. If a complex prompt takes 45 seconds to process, the default 30-second web server timeout will drop the connection before the AI finishes. We extend the timeout to 120 seconds (or higher) to give the hardware adequate time to compute and return results.

### Question 2: Data Persistence
**Q: What happens to data stored strictly inside a Docker container when the container is restarted?**

**A:** It is permanently destroyed. That is why we use `volumes` to map critical storage (like databases and checkpoints) out to the host machine. The volume persists even after container destruction, ensuring your state history survives restarts.

### Question 3: Port Mapping
**Q: Why do we map port 8000:8000 in docker-compose?**

**A:** The first port (8000) is the port inside the container where Uvicorn listens. The second port (8000) is the port on your host machine. This mapping makes the API accessible at `localhost:8000`. If we mapped `8001:8000`, the API would be at `localhost:8001`.

### Question 4: Local LLM Communication
**Q: How does the container inside Docker reach an LM Studio instance running on the host machine?**

**A:** On Windows/Mac, use `host.docker.internal:port`. On Linux, use `172.17.0.1:port`. This special hostname/IP allows containers to reach the host's network services. Without this, the container would be isolated and unable to reach your local LLM.

---

## Key Takeaways

✅ **Containerization** isolates our orchestration layer from OS dependencies  
✅ **Timeout tuning** prevents connection drops during slow local inference  
✅ **Volume persistence** keeps our state history safe across restarts  
✅ **Compute separation** allows flexible hardware allocation (Pi for logic, GPU for inference)  

---

**Next:** [Chapter 2: State Machines & Checkpointing](Chapter-2:-State-Machines-&-Checkpointing)
