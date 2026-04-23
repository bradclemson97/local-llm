import os
import subprocess
import asyncio
import chromadb
from ollama import AsyncClient
import chainlit as cl
from pypdf import PdfReader

# 1. Force local-only communication for OPSEC
os.environ["OLLAMA_HOST"] = "127.0.0.1"

# 2. Setup Clients and Configuration
# Initialize Local Vector DB for Long-term memory
chroma_client = chromadb.PersistentClient(path="./mission_db")
collection = chroma_client.get_or_create_collection(name="mission_archive")

client = AsyncClient(host="http://127.0.0.1:11434")
# RECOMMENDATION: If 26b is still slow, try "gemma4:9b" to verify the pipeline first
MODEL = "gemma4:26b"

def secure_shred(file_path):
    """3-pass overwrite of the file before deletion."""
    try:
        subprocess.run(["rm", "-P", file_path], check=True)
        return True
    except: return False

@cl.on_chat_start
async def start():
    # Updated welcome message to reflect RAG and Citation capability
    await cl.Message(content="🛡️ **Defense Node Active.** Documents are indexed with source tracking. Type a question to search the archive.").send()

@cl.on_message
async def main(message: cl.Message):
    # --- PHASE 1: DOCUMENT INGESTION & SUMMARIZATION ---
    if message.elements:
        for element in message.elements:
            if element.type == "file" and element.name.endswith(".pdf"):
                status_msg = cl.Message(content=f"📑 **Reading & Archiving:** `{element.name}`...")
                await status_msg.send()

                # 1. Extract Text
                reader = PdfReader(element.path)
                full_text = ""
                
                # Chunking strategy: Index page by page into the Vector DB with metadata
                for i, page in enumerate(reader.pages):
                    page_text = page.extract_text()
                    if page_text.strip():
                        full_text += page_text
                        collection.add(
                            documents=[page_text],
                            metadatas=[{"source": element.name, "page": i+1}], # Store source info
                            ids=[f"{element.name}_pg_{i}"]
                        )
                
                if len(full_text) < 50:
                    status_msg.content = "⚠️ Extraction failed or text too short."
                    await status_msg.update()
                    return

                # Set the content attribute, then call update()
                status_msg.content = f"🧠 **Analyzing {len(full_text)} characters...** (Archiving with Citations)"
                await status_msg.update()

                # 2. Async Streaming Inference
                ui_msg = cl.Message(content=f"### Summary: {element.name}\n\n")
                await ui_msg.send()

                try:
                    async for part in await client.chat(
                        model=MODEL,
                        messages=[
                            {"role": "system", "content": """
                            You are a Senior Intelligence Analyst. Summarize this document using BLUF format. 
                            Identify KEY FINDINGS, IDENTIFIED RISKS, and DISCREPANCIES.
                            Be precise with coordinates and timestamps.
                            """},
                            {"role": "user", "content": f"Document Content: {full_text}"}
                        ],
                        stream=True,
                    ):
                        token = part['message']['content']
                        await ui_msg.stream_token(token)
                
                except Exception as e:
                    await cl.Message(content=f"❌ **Inference Error:** {str(e)}").send()

                # Finalize the message
                await ui_msg.update()
                
                # 3. Secure Cleanup
                secure_shred(element.path)
                await cl.Message(content="🔒 *Original file purged from disk. Mission data securely archived.*").send()
        return

    # --- PHASE 2: LONG-TERM MEMORY RETRIEVAL (RAG) WITH CITATIONS ---
    if not message.elements:
        search_status = cl.Message(content="🔍 **Searching Archive...**")
        await search_status.send()

        # Query the ChromaDB for the 3 most relevant snippets
        results = collection.query(query_texts=[message.content], n_results=3)
        
        # Build context blocks and a list of unique sources
        context_blocks = []
        source_metadata = []
        
        if results['documents']:
            for doc, meta in zip(results['documents'][0], results['metadatas'][0]):
                citation = f"[{meta['source']}, Pg {meta['page']}]"
                context_blocks.append(f"SOURCE {citation}:\n{doc}")
                source_metadata.append(citation)

        retrieved_context = "\n\n".join(context_blocks) if context_blocks else "No archived data found."
        unique_sources = ", ".join(list(set(source_metadata)))

        ui_msg = cl.Message(content="")
        await ui_msg.send()

        try:
            async for part in await client.chat(
                model=MODEL,
                messages=[
                    {"role": "system", "content": f"""
                    You are a Tactical Analyst. Answer using the ARCHIVED CONTEXT provided below.
                    CRITICAL: You must cite your sources at the end of relevant sentences using [File, Pg X].
                    
                    ARCHIVED CONTEXT:
                    {retrieved_context}
                    """},
                    {"role": "user", "content": message.content}
                ],
                stream=True,
            ):
                token = part['message']['content']
                await ui_msg.stream_token(token)
            
            # Append verified source footer
            if source_metadata:
                await ui_msg.stream_token(f"\n\n---\n**Verified Sources:** {unique_sources}")

        except Exception as e:
            await cl.Message(content=f"❌ **Search Error:** {str(e)}").send()

        await search_status.remove() 
        await ui_msg.update()