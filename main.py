import os
from typing import Dict, Any
from dotenv import load_dotenv

# IMPORTS DE LANGCHAIN
from langchain_neo4j import Neo4jGraph, GraphCypherQAChain
from langchain_groq import ChatGroq
from langchain_core.prompts import PromptTemplate

# IMPORT DE NUESTRA BASE DE DATOS LOCAL
from database import SQLiteHistoryManager

load_dotenv(override=True)

def initialize_agent():
    """Inicializa la infraestructura del Grafo y el Motor LLM."""
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

    # Prompt adaptado para entender relaciones de contexto histórico
    CYPHER_GENERATION_TEMPLATE = """
    Task: Generate a valid Cypher query to answer the user's question about an Academic Publications database.
    You are an expert Neo4j developer. Use ONLY the allowed schema elements.

    Schema:
    {schema}

    Instructions:
    1. CRITICAL: If the question is NOT strictly related to academic publications, authors, venues, or AI fields, 
       return EXACTLY this query: RETURN "BLOCK_QUERY" AS error
    2. The user prompt may contain context from previous questions. Use it to resolve terms like "of those", "them", or "the previous ones".
    3. Use case-insensitive matching ONLY for string properties using toLower().
    4. Do NOT use toLower() on numeric properties like year (año) or citations.
    5. Return only the plain string query, no markdown blocks.

    Question (with history context if applies): 
    {question}

    Cypher Query:"""

    cypher_prompt = PromptTemplate(
        template=CYPHER_GENERATION_TEMPLATE, 
        input_variables=["schema", "question"]
    )

    chain = GraphCypherQAChain.from_llm(
        llm=llm,
        graph=graph,
        verbose=False,
        cypher_prompt=cypher_prompt,
        validate_cypher=True,
        allow_dangerous_requests=True,
        return_direct=True
    )
    
    return chain, llm

def ask_expert(chat_id: str, question: str, chain: GraphCypherQAChain, llm: ChatGroq, db: SQLiteHistoryManager) -> str:
    """Procesa la pregunta del usuario inyectando memoria histórica y guardando la interacción automáticamente."""
    try:
        # 1. Recuperar el historial acumulado en SQLite para este chat específico
        historial_previo = db.get_chat_history_str(chat_id)
        
        # Enriquecemos la entrada combinando el historial y la nueva pregunta
        input_contextual = f"Historial de Conversación:\n{historial_previo}\n\nPregunta Actual: {question}"

        # 2. Ejecutar la cadena en Neo4j usando el contexto enriquecido
        response: Dict[str, Any] = chain.invoke({"query": input_contextual})
        graph_output = response.get("result", "")
        
        # Guardarraíl de dominio
        if not graph_output or "BLOCK_QUERY" in str(graph_output):
            return "Lo siento, solo puedo ayudarte con información sobre publicaciones de IA."
        
        # 3. Paso de Síntesis: Generar respuesta fluida considerando la memoria
        synthesis_template = f"""
        Eres un asistente analítico de publicaciones de IA. Traduce los datos del grafo en una respuesta fluida en español.
        
        Historial de la conversación para mantener coherencia:
        {historial_previo}

        Pregunta actual: {question}
        Datos nuevos extraídos del Grafo: {graph_output}

        Respuesta final detallada en español (si es una lista usa viñetas, incluye TODOS los datos del grafo):"""

        polished_response = llm.invoke(synthesis_template)
        final_answer = polished_response.content

        # 4. PERSISTENCIA AUTOMÁTICA: Guardar la interacción completa en SQLite
        db.save_message(chat_id, "user", question)
        db.save_message(chat_id, "assistant", final_answer)

        return final_answer

    except Exception as e:
        return f"Error controlado: No se pudo resolver la consulta en el grafo. (Detalles: {str(e)})"

# --- Demostración de Persistencia y Continuidad ---
if __name__ == "__main__":
    print("Inicializando agente con Memoria SQLite...")
    agent_chain, llm_engine = initialize_agent()
    db_manager = SQLiteHistoryManager()
    
    # Identificador único de sesión para las pruebas
    SESSION_ID = "chat_marketing_ia_01"
    db_manager.ensure_chat_exists(SESSION_ID, nombre="Sesión de Análisis de Áreas")
    
    print("Agente listo. Ejecutando ráfaga secuencial de preguntas...\n")
    
    # Interacción 1: Consulta General
    q1 = "¿Qué temas de IA se publicaron en 2024?"
    print(f"--> Usuario: {q1}")
    print(f"--> Agente:\n{ask_expert(SESSION_ID, q1, agent_chain, llm_engine, db_manager)}\n")
    print("-" * 60)
    
    # Interacción 2: Consulta Contextual (Usa la memoria de SQLite para resolver "de esos")
    q2 = "Y de esos temas que me mencionas, ¿cuál es el que corresponde a 'robótica'?"
    print(f"--> Usuario: {q2}")
    print(f"--> Agente:\n{ask_expert(SESSION_ID, q2, agent_chain, llm_engine, db_manager)}\n")