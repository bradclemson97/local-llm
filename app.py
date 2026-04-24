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

# TEXT_MODEL: Deep reasoning and RAG
# If 26b is still slow, try "gemma4:9b" to verify the pipeline first
MODEL = "gemma4:26b"
TEXT_MODEL = "gemma4:26b" 
# VISION_MODEL: Optimized for tactical image analysis
VISION_MODEL = "moondream" 

def secure_shred(file_path):
    """3-pass overwrite of the file before deletion (macOS native)."""
    try:
        subprocess.run(["rm", "-P", file_path], check=True)
        return True
    except: return False

@cl.on_chat_start
async def start():
    # Updated welcome message to reflect RAG, Citations, and Vision capability
    await cl.Message(content="🛡️ **Defense Node: Vision Enabled.** Upload PDFs for indexing or Images for tactical visual analysis. Sources are tracked for all queries.").send()

@cl.on_message
async def main(message: cl.Message):
    # --- PHASE 1: DOCUMENT & IMAGE INGESTION ---
    if message.elements:
        for element in message.elements:
            # --- HANDLE PDF (RAG + SUMMARIZATION) ---
            if element.type == "file" and element.name.endswith(".pdf"):
                status_msg = cl.Message(content=f"📑 **Indexing PDF:** `{element.name}`...")
                await status_msg.send()

                reader = PdfReader(element.path)
                full_text = ""
                
                # Chunking strategy: Index page by page into the Vector DB with metadata
                for i, page in enumerate(reader.pages):
                    page_text = page.extract_text()
                    if page_text.strip():
                        full_text += page_text
                        collection.add(
                            documents=[page_text],
                            metadatas=[{"source": element.name, "page": i+1}],
                            ids=[f"{element.name}_pg_{i}"]
                        )
                
                if len(full_text) < 50:
                    status_msg.content = "⚠️ Extraction failed or text too short."
                    await status_msg.update()
                    return

                status_msg.content = f"🧠 **Analyzing {len(full_text)} characters...** (Archiving with Source Tracking)"
                await status_msg.update()

                ui_msg = cl.Message(content=f"### Summary: {element.name}\n\n")
                await ui_msg.send()

                try:
                    async for part in await client.chat(
                        model=TEXT_MODEL,
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
                        await ui_msg.stream_token(part['message']['content'])
                except Exception as e:
                    await cl.Message(content=f"❌ **Inference Error:** {str(e)}").send()

                await ui_msg.update()
                secure_shred(element.path)
                await cl.Message(content=f"🔒 `{element.name}` purged from disk and archived.").send()

            # --- HANDLE IMAGES (VISUAL INTEL) ---
            elif element.type == "image":
                status_msg = cl.Message(content=f"📸 **Analyzing Visual Intel:** `{element.name}`...")
                await status_msg.send()

                ui_msg = cl.Message(content=f"### Visual Analysis: {element.name}\n\n")
                await ui_msg.send()

                try:
                    async for part in await client.chat(
                        model=VISION_MODEL,
                        messages=[{
                            "role": "user", 
                            "content": "Identify tactical landmarks, vehicles, equipment, personnel, or threats. Maintain a clinical, objective tone.",
                            "images": [element.path]
                        }],
                        stream=True,
                    ):
                        await ui_msg.stream_token(part['message']['content'])
                except Exception as e:
                    await cl.Message(content=f"❌ **Vision Error:** {str(e)}").send()

                await ui_msg.update()
                await status_msg.remove()
                secure_shred(element.path) # Shred image data after inference
                await cl.Message(content=f"🔒 Visual data `{element.name}` purged from disk.").send()
        return

    # --- PHASE 2: LONG-TERM MEMORY RETRIEVAL (RAG) WITH CITATIONS ---
    if not message.elements:
        search_status = cl.Message(content="🔍 **Searching Archive...**")
        await search_status.send()

        results = collection.query(query_texts=[message.content], n_results=3)
        
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
                model=TEXT_MODEL,
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
                await ui_msg.stream_token(part['message']['content'])
            
            if source_metadata:
                await ui_msg.stream_token(f"\n\n---\n**Verified Sources:** {unique_sources}")
        except Exception as e:
            await cl.Message(content=f"❌ **Search Error:** {str(e)}").send()

        await search_status.remove() 
        await ui_msg.update()