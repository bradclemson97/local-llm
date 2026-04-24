# local-llm

A secure, air-gapped-ready intelligence workstation optimized for Apple Silicon (M4). This project enables local analysis of sensitive mission documents using Large Language Models (LLMs) and Retrieval-Augmented Generation (RAG) with 100% data sovereignty.

## Key Features

- **Local Inference**: Uses [Ollama](https://ollama.com/) to run models like `Gemma 4 26B` or `Qwen 3.6 35B` locally on your M4 GPU.
- **Mission-Specific RAG**: Persistent long-term memory via **ChromaDB**. Indexed documents and historic mission information can be queried across sessions.
- **Source Citations**: Automatic tracking of filenames and page numbers, ensuring traceability and preventing hallucination, creating a verifiable iltelligence tool.
- **Secure Data Handling**: Integrated military-grade **3-pass shredding** (`rm -P`) of uploaded PDF files immediately after processing.
- **MLX Optimized**: Specifically tuned for Apple Silicon unified memory to ensure high-speed processing of large document contexts (50+ pages).
- **Asynchronous Streaming**: Real-time feedback and word-by-word generation to prevent UI timeouts during heavy computation.
- **Vision Analaysis**: Process tactical maps, drone feeds (stills), and satellite imagery alongside text-based mission reports.
- **Reporting Export**: Secure PDF export of SITREP (Situation Report) based on chat history. 

---

## Prerequisites

- **Hardware**: Mac with Apple Silicon (M4 Max/Ultra with 48GB+ RAM recommended for 26B+ models).
- **Software**: 
  - Python 3.10+
  - [Ollama](https://ollama.com/) installed and running.

---

## Getting Started

Install Dependencies (global): 
```
brew install pipx
pipx ensurepath
brew install ollama
pipx install chainlit
pipx install pypdf
pipx install chromadb
```

Install models:
```
ollama pull gemma4:26b
ollama pull nomic-embed-text
ollama pull moondream
```

Install Dependencies (dedicated local environment):
```
cd ~/VSProjects/local-llm
```
Set up virtual envrionment:
```
python3 -m venv .venv
source .venv/bin/activate
```
Install dependencies:
```
pip install ollama
pip install chainlit
pip install pypdf
pip install chromadb
pip install fpdf2
```
---

## Running the application

1. Clear the Port
Run this to force-stop any hidden Ollama processes:
```
killall Ollama
```
Note: If it says "No matching processes were found," it might be running under a different service name. Run 
```
lsof -i :11434 
```
to see the exact Process ID (PID) using the port, then run 
```
kill -9 <PID>
```

2. The "Secure Start" Sequence
Now that the port is clear, start your dedicated, isolated server:

Start the Server (Tab A):
```
OLLAMA_HOST=127.0.0.1 ollama serve
```
(Leave this terminal tab open and running.)

Verify it’s alive (Tab B):
```
curl http://127.0.0.1:11434/api/tags
```
If you see a JSON list of your models (Qwen, Gemma, etc.), the server is officially "Mission Ready."

3. Launch the Intelligence Node
Now, go back to your project folder and launch the UI using the "Streaming" version of the code we discussed (to prevent those "Could not reach server" timeouts).
```
cd ~/VSProjects/local-llm
source .venv/bin/activate
python3 -m chainlit run app.py -w
```

Usage:
- Upload: Drop a mission PDF into the UI for an instant BLUF (Bottom Line Up Front) summary and archival.
- Query: Type questions to search the archive (e.g., "Identify all MANPADS sightings in the Arid Ridge sector").

Security Protocol
- Local Host Binding: The application is hard-coded to communicate with Ollama via 127.0.0.1 only.
- Ephemeral Processing: Original PDF files are overwritten 3 times on the physical disk before deletion.
-Archive Management: To purge the entire long-term memory archive, run:
```
rm -rf mission_db
```

---

## Retrieval-Augmented Generation (RAG) Long-Term Memory 

Implementing RAG is the move from a "Single-Mission Workstation" to a "Theater-Level Intelligence Archive." Instead of the LLM forgetting everything once the chat ends, RAG allows you to build a local, searchable library of every document you've ever processed.

Testing

1. Upload the Dummy Tactical Document. Wait for the summary and the "Purged from disk" message.

2. Refresh the browser (clearing the current chat session).

3. Type: "Where was Objective ALFA located and what was the CASEVAC LZ?"

How the RAG should handle this:
When you typed that question, the system didn't search the whole 50-page document. Instead, it followed this workflow:
- Vector Search: It looked through ./mission_db for chunks of text mathematically similar to "Objective ALFA" and "CASEVAC LZ."
- Context Injection: It retrieved the specific sentences containing those coordinates.
- Synthesis: It fed those snippets to the Gemma 4:26b model, which formatted them into the clear answer you received.

---
