import os
import re
import sqlite3
from typing import Dict, Any, List
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

# IMPORTS DE LANGCHAIN
from langchain_neo4j import Neo4jGraph
from langchain_groq import ChatGroq
from langchain_core.prompts import PromptTemplate

load_dotenv(override=True)

app = FastAPI(title="API Agente GraphRAG - Versión Demo Blindada")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_PATH = "chat_history.db"

# =====================================================================
# 1. GESTIÓN DE MEMORIA (SLIDING WINDOW)
# =====================================================================
def init_sqlite():
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS chats (
                id TEXT PRIMARY KEY,
                nombre TEXT
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id TEXT,
                role TEXT,
                content TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(chat_id) REFERENCES chats(id)
            )
        """)
        conn.commit()

init_sqlite()

def get_history_str_sliding_window(chat_id: str, limit: int = 10) -> str:
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT role, content FROM (
                SELECT role, content, timestamp FROM messages 
                WHERE chat_id = ? 
                ORDER BY timestamp DESC 
                LIMIT ?
            ) ORDER BY timestamp ASC
        """, (chat_id, limit))
        rows = cursor.fetchall()
        return "\n".join([f"{'Usuario' if r=='user' else 'Agente'}: {c}" for r, c in rows]) if rows else "No hay historial previo."


# =====================================================================
# 2. GUARDRAILS DE SEGURIDAD ABSOLUTA (INPUT & OUTPUT)
# =====================================================================
def contains_destructive_intent(text: str) -> bool:
    """
    GUARDRAIL DE ENTRADA: Detiene intentos de mutación, borrado o tutoriales 
    sobre comandos peligrosos analizando directamente el texto del usuario.
    """
    black_list = [r"\bDELETE\b", r"\bDROP\b", r"\bSET\b", r"\bREMOVE\b", r"\bMERGE\b", r"\bCREATE\b", r"\bALTER\b"]
    text_upper = text.upper()
    return any(re.search(pattern, text_upper) for pattern in black_list)


# =====================================================================
# 3. INFRAESTRUCTURA Y PROMPTS AVANZADOS
# =====================================================================
graph = Neo4jGraph(
    url=os.getenv("NEO4J_URI"),
    username=os.getenv("NEO4J_USERNAME"), 
    password=os.getenv("NEO4J_PASSWORD"),
    database=os.getenv("NEO4J_DATABASE"), 
    refresh_schema=True
)

llm = ChatGroq(
    model="llama-3.3-70b-versatile",
    temperature=0,
    groq_api_key=os.getenv("GROQ_API_KEY")
)

# Prompt rediseñado para forzar búsquedas parciales e inclusivas (CONTAINS)
CYPHER_TEMPLATE = """
Task: Generate a valid Cypher query to answer the user's question based ONLY on the provided Academic schema.
Schema: {schema}

Instructions:
1. CRITICAL: If the question is NOT related to academic publications, authors, areas, or keywords, return: RETURN "BLOCK_QUERY" AS error
2. Never put function calls inside node property brackets (e.g., NO (a:Area {{name: toLower("...")}})). Use WHERE instead.
3. For text or keyword matching (like searching for 'XGBoost', 'robótica', etc.), ALWAYS use `CONTAINS` and `toLower()` to guarantee partial and case-insensitive matches across titles, keywords or areas.
   - Example: MATCH (p:Publicacion) WHERE toLower(p.titulo) CONTAINS "xgboost"
4. Match numeric values like years directly (e.g., p.año = 2025).
5. Return ONLY the plain Cypher query string, no markdown blocks, no explanations.

Question: {question}
Cypher Query:"""


# =====================================================================
# 4. LÓGICA CENTRAL DE PROCESAMIENTO
# =====================================================================
class ChatRequest(BaseModel):
    chat_id: str
    question: str

@app.get("/api/chats")
def list_chats():
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, nombre FROM chats ORDER BY id DESC")
        return [{"id": r[0], "nombre": r[1]} for r in cursor.fetchall()]

@app.get("/api/chats/{chat_id}/messages")
def get_messages(chat_id: str):
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT role, content FROM messages WHERE chat_id = ? ORDER BY timestamp ASC", (chat_id,))
        return [{"role": r[0], "content": r[1]} for r in cursor.fetchall()]

@app.post("/api/chat")
def process_question(req: ChatRequest):
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT OR IGNORE INTO chats (id, nombre) VALUES (?, ?)", (req.chat_id, req.question[:30] + "..."))
            conn.commit()

        # 1. Intercepción del Guardrail de Entrada (Evita explicaciones y hackeos)
        if contains_destructive_intent(req.question):
            final_answer = "Seguridad: Acción rechazada. Este agente está configurado en modo de solo lectura y no procesará comandos de modificación (CREATE, DELETE, MERGE, etc.), ni ofrecerá guías sobre su ejecución."
            
            # Guardamos el intento en el historial para mantener la coherencia del chat
            with sqlite3.connect(DB_PATH) as conn:
                cursor = conn.cursor()
                cursor.execute("INSERT INTO messages (chat_id, role, content) VALUES (?, 'user', ?)", (req.chat_id, req.question))
                cursor.execute("INSERT INTO messages (chat_id, role, content) VALUES (?, 'assistant', ?)", (req.chat_id, final_answer))
                conn.commit()
            return {"response": final_answer}

        # 2. Cargar historial conversacional (Sliding Window)
        historial = get_history_str_sliding_window(req.chat_id, limit=10)
        
        # 3. Paso de Condensación Avanzado (Fusión de Entidades y Pronombres)
        if historial != "No hay historial previo.":
            condense_prompt = f"""
            System: Eres un optimizador RAG. Tu meta es fusionar el historial y la nueva pregunta en una consulta única e independiente en español.
            
            REGLAS DE CONTEXTO CORTANTE:
            1. Si el usuario usa referencias cruzadas como "de esos", "anteriormente", "cuáles de ellos", busca en el último mensaje del Agente los filtros implícitos (como años, áreas o listas de IDs) y colócalos explícitamente en la nueva pregunta.
               - Ejemplo de reescritura: Si hablaron de publicaciones de 2025 y el usuario dice "¿cuáles son de robótica?", tú devuelves: "¿Cuáles de las publicaciones del año 2025 corresponden al área de robótica?"
            2. Si la pregunta cambia drásticamente de tema, ignora el historial.
            3. Devuelve únicamente la pregunta formulada, sin preámbulos.

            Historial de Conversación:
            {historial}

            Pregunta de seguimiento: {req.question}

            Pregunta independiente final:"""
            
            standalone_question = llm.invoke(condense_prompt).content.strip().replace('"', '').replace("'", "")
        else:
            standalone_question = req.question

        # 4. Generación y Limpieza del Query Cypher
        cypher_prompt_formated = PromptTemplate(
            template=CYPHER_TEMPLATE, input_variables=["schema", "question"]
        ).format(schema=graph.schema, question=standalone_question)
        
        generated_cypher = llm.invoke(cypher_prompt_formated).content.strip()
        generated_cypher = generated_cypher.replace("```cypher", "").replace("```", "").strip()

        graph_output = None
        
        if "BLOCK_QUERY" in generated_cypher or contains_destructive_intent(generated_cypher):
            graph_output = "BLOCK_QUERY"
        else:
            # 5. Ejecución con bucle de Auto-Corrección Activo
            try:
                print(f"[INFO] Ejecutando Cypher: {generated_cypher}")
                graph_output = graph.query(generated_cypher)
            except Exception as cypher_error:
                print(f"[SELF-HEALING] Error en Neo4j: {cypher_error}. Intentando auto-corrección...")
                
                correction_prompt = f"System: Corrige la siguiente consulta Cypher que falló en Neo4j.\nSchema: {graph.schema}\nQuery Fallida: {generated_cypher}\nError: {str(cypher_error)}\nInstrucciones: Usa WHERE para transformaciones de texto. Devuelve solo la query limpia.\nQuery Corregida:"
                
                try:
                    corrected_cypher = llm.invoke(correction_prompt).content.strip().replace("```cypher", "").replace("```", "").strip()
                    if contains_destructive_intent(corrected_cypher):
                        graph_output = "BLOCK_QUERY"
                    else:
                        print(f"[SELF-HEALING] Re-ejecutando query corregida: {corrected_cypher}")
                        graph_output = graph.query(corrected_cypher)
                except Exception as retry_error:
                    print(f"[CRITICAL] Error persistente tras auto-corrección: {retry_error}")
                    graph_output = "BLOCK_QUERY"

        # 6. Mapeo de respuestas y Síntesis Conversacional de Alta Fidelidad
        if graph_output == "BLOCK_QUERY":
            final_answer = "Lo siento, solo puedo ayudarte con información sobre publicaciones de IA."
        elif not graph_output:
            final_answer = "No encontré registros académicos en el sistema que coincidan con los filtros de tu consulta actual."
        else:
            synthesis_prompt = f"""
            System: Convierte los datos estructurados del grafo en una respuesta fluida y detallada en español.
            REGLA CRÍTICA: Incluye TODOS los campos e IDs provistos por Neo4j sin omitir ninguno. Si hay listas, estructúralas con viñetas Markdown limpias.
            Pregunta original del usuario: {req.question}
            Datos obtenidos de Neo4j: {graph_output}
            Respuesta pulida final:"""
            final_answer = llm.invoke(synthesis_prompt).content

        # 7. Persistencia Atómica en SQLite
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO messages (chat_id, role, content) VALUES (?, 'user', ?)", (req.chat_id, req.question))
            cursor.execute("INSERT INTO messages (chat_id, role, content) VALUES (?, 'assistant', ?)", (req.chat_id, final_answer))
            conn.commit()

        return {"response": final_answer}

    except Exception as e:
        import traceback
        print("\n" + "="*60)
        print("[ERROR EN EL SERVIDOR]")
        traceback.print_exc()
        print("="*60 + "\n")
        raise HTTPException(status_code=500, detail=str(e))