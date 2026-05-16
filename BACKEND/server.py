import os
import sqlite3
from typing import Dict, Any, List
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

# IMPORTS DE LANGCHAIN
from langchain_neo4j import Neo4jGraph, GraphCypherQAChain
from langchain_groq import ChatGroq
from langchain_core.prompts import PromptTemplate

load_dotenv(override=True)

app = FastAPI(title="API del Agente de IA para Publicaciones")

# Configuración flexible de CORS para desarrollo local
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Permite cualquier puerto local dinámico (3000, 5010, etc.)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_PATH = "chat_history.db"

# =====================================================================
# 1. GESTIÓN DE SQLITE (PERSISTENCIA LOCAL)
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

def get_history_str(chat_id: str) -> str:
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT role, content FROM messages WHERE chat_id = ? ORDER BY timestamp ASC", (chat_id,))
        rows = cursor.fetchall()
        return "\n".join([f"{'Usuario' if r=='user' else 'Agente'}: {c}" for r, c in rows]) if rows else "No hay historial previo."

# =====================================================================
# 2. INICIALIZACIÓN DEL AGENTE (NEO4J + GROQ)
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

# PROMPT DE CYPHER CORREGIDO: Prohíbe explícitamente funciones dentro de las llaves
CYPHER_TEMPLATE = """
Task: Generate a valid Cypher query to answer the user's question about an Academic Publications database.
Use ONLY the allowed schema elements.
Schema: {schema}

Instructions:
1. CRITICAL: If the question is NOT strictly related to academic publications, authors, institutions, venues, keywords, or AI areas, return EXACTLY: RETURN "BLOCK_QUERY" AS error
2. CRITICAL: Never put function calls inside node property brackets. (e.g., DO NOT DO: (a:Area {{area_ia: toLower("...")}})).
3. For case-insensitive string matching, use the WHERE clause and toLower() on the node property.
   Correct Example: MATCH (a:Area) WHERE toLower(a.area_ia) = "nlp"
4. Match numeric properties like year directly without functions (e.g., p.year = 2024).
5. Return only the plain Cypher string, no markdown formatting.

Question: {question}
Cypher Query:"""

chain = GraphCypherQAChain.from_llm(
    llm=llm, graph=graph, verbose=False,
    cypher_prompt=PromptTemplate(template=CYPHER_TEMPLATE, input_variables=["schema", "question"]),
    validate_cypher=True, allow_dangerous_requests=True, return_direct=True
)

# =====================================================================
# 3. ENDPOINTS DE LA API
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
        # Registrar o crear la sesión del chat si es nueva
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT OR IGNORE INTO chats (id, nombre) VALUES (?, ?)", (req.chat_id, req.question[:30] + "..."))
            conn.commit()

        # 1. Recuperar historial de SQLite
        historial = get_history_str(req.chat_id)
        
        # 2. PASO DE CONDENSACIÓN ULTRA ESTRICTO (EVITA CONTAMINACIÓN)
        if historial != "No hay historial previo.":
            condense_prompt = f"""
            System: Eres un optimizador de consultas RAG ultra preciso. Tu único trabajo es recibir un historial de chat y una nueva pregunta, y devolver una ÚNICA línea con la pregunta limpia en español.

            REGLAS ABSOLUTAS DE CONTROL:
            1. Si la nueva pregunta del usuario ya es independiente, clara y no usa pronombres ambiguos (como "esos", "ellos", "el anterior"), devuélvela EXACTAMENTE igual a como la escribió el usuario.
            2. NUNCA incluyas explicaciones, saludos ni introducciones (Prohibido iniciar con "Olvidando el tema anterior...", "La pregunta corregida es:", etc.).
            3. NUNCA menciones los temas fuera de dominio del historial (como perros, presidentes, etc.) en tu respuesta. Si el usuario cambió de tema, ignora el historial por completo.
            4. Devuelve única y exclusivamente el texto final de la pregunta.

            Historial de Conversación:
            {historial}

            Pregunta de seguimiento del usuario: {req.question}

            Pregunta resultante (Solo una línea de texto limpio):"""
            
            standalone_question = llm.invoke(condense_prompt).content.strip()
            # Limpieza de seguridad por si el LLM mete comillas por capricho
            standalone_question = standalone_question.replace('"', '').replace("'", "")
        else:
            standalone_question = req.question
            
        # 3. Consultar la base de datos de grafos con la pregunta limpia
        graph_res = chain.invoke({"query": standalone_question})
        graph_output = graph_res.get("result", "")

        # Guardarraíl de dominio
        if not graph_output or "BLOCK_QUERY" in str(graph_output):
            final_answer = "Lo siento, solo puedo ayudarte con información sobre publicaciones de IA."
        else:
            # 4. Paso de síntesis conversacional
            synthesis_prompt = f"""
            Eres un asistente de IA analítico. Convierte los datos del grafo en una respuesta fluida y detallada en español.
            CRITICAL: Incluye absolutamente TODOS los elementos encontrados en los datos de Neo4j, no omitas ninguno. Si es una lista usa viñetas limpias.
            Pregunta del usuario: {req.question}
            Datos de Neo4j obtenidos: {graph_output}
            Respuesta final pulida:"""
            
            final_answer = llm.invoke(synthesis_prompt).content

        # 5. Persistir automáticamente el par interactivo real en SQLite
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO messages (chat_id, role, content) VALUES (?, 'user', ?)", (req.chat_id, req.question))
            cursor.execute("INSERT INTO messages (chat_id, role, content) VALUES (?, 'assistant', ?)", (req.chat_id, final_answer))
            conn.commit()

        return {"response": final_answer}

    except Exception as e:
        import traceback
        print("\n" + "="*60)
        print("[ERROR CRÍTICO CAPTURADO EN EL SERVIDOR]")
        traceback.print_exc()
        print("="*60 + "\n")
        raise HTTPException(status_code=500, detail=str(e))