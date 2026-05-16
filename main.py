import os
from typing import Dict, Any
from dotenv import load_dotenv

# IMPORTS DE LANGCHAIN
from langchain_neo4j import Neo4jGraph, GraphCypherQAChain
from langchain_groq import ChatGroq
from langchain_core.prompts import PromptTemplate

load_dotenv(override=True)

def initialize_agent():
    """Inicializa la conexión con Neo4j y retorna la cadena de Cypher y el LLM por separado."""
    
    # 1. Conexión con AuraDB
    graph = Neo4jGraph(
        url=os.getenv("NEO4J_URI"),
        username=os.getenv("NEO4J_USERNAME"), 
        password=os.getenv("NEO4J_PASSWORD"),
        database=os.getenv("NEO4J_DATABASE"),
        refresh_schema=True
    )

    # 2. Configuración del motor LLM (Groq - Llama 3.3)
    llm = ChatGroq(
        model="llama-3.3-70b-versatile",
        temperature=0,
        groq_api_key=os.getenv("GROQ_API_KEY")
    )

    # 3. Prompt de Ingeniería de Cypher con Guardarraíl
    CYPHER_GENERATION_TEMPLATE = """
    Task: Generate a valid Cypher query to answer the user's question about an Academic Publications database.
    You are an expert Neo4j developer. Use ONLY the allowed schema elements.

    Schema:
    {schema}

    Instructions:
    1. CRITICAL: If the question is NOT strictly related to academic publications, authors, institutions, venues, keywords, or AI areas,
       do NOT attempt to solve it. Instead, return EXACTLY this valid Cypher query: RETURN "BLOCK_QUERY" AS error
    2. Use case-insensitive matching ONLY for string properties using toLower().
    3. CRITICAL: Do NOT use toLower() or toUpper() on numeric properties like year (año) or citations. Match numbers directly (e.g., p.year = 2024).
    4. Return only the plain string query, no markdown blocks.

    Question: {question}
    Cypher Query:"""

    cypher_prompt = PromptTemplate(
        template=CYPHER_GENERATION_TEMPLATE, 
        input_variables=["schema", "question"]
    )

    # 4. Construcción de la cadena Cypher
    chain = GraphCypherQAChain.from_llm(
        llm=llm,
        graph=graph,
        verbose=False,
        cypher_prompt=cypher_prompt,
        validate_cypher=True,
        allow_dangerous_requests=True,
        return_direct=True  # Mantenemos esto para interceptar el BLOCK_QUERY de forma segura
    )
    
    return chain, llm

def ask_expert(question: str, chain: GraphCypherQAChain, llm: ChatGroq) -> str:
    """Procesa la pregunta, valida el dominio y pule el resultado en lenguaje natural fluido."""
    try:
        # 1. Extraer los datos puros del Grafo
        response: Dict[str, Any] = chain.invoke({"query": question})
        graph_output = response.get("result", "")
        
        # 2. Validar Guardarraíl de dominio
        if not graph_output or "BLOCK_QUERY" in str(graph_output):
            return "Lo siento, solo puedo ayudarte con información sobre publicaciones de IA."
        
        # 3. PASO DE SÍNTESIS OPTIMIZADO: Convertir el array de Neo4j en una respuesta detallada
        synthesis_template = f"""
        Eres un asistente de IA experto y analítico especializado en publicaciones académicas de Inteligencia Artificial.
        Tu tarea es transformar los datos en bruto obtenidos de una base de datos de grafos en una respuesta redactada, clara, fluida y detallada en español para el usuario.

        Instrucciones de formato:
        - CRITICAL: Incluye absolutamente TODOS los elementos encontrados en los datos del grafo, no omitas ninguno.
        - Si los datos contienen una lista de elementos, ordénalos y preséntalos usando viñetas (bullet points) limpias.
        - Sé profesional, directo y añade un breve contexto introductorio coherente con la pregunta.

        Pregunta original del usuario: {question}
        Datos extraídos del Grafo (Neo4j): {graph_output}

        Respuesta final pulida en español:"""

        # Llamada secundaria a Llama para el formateo estético
        polished_response = llm.invoke(synthesis_template)
        return polished_response.content

    except Exception as e:
        return f"Error controlado: No se pudo resolver la consulta en el grafo. (Detalles: {str(e)})"

# --- Ejecución ---
if __name__ == "__main__":
    print("Inicializando agente inteligente con Groq...")
    agent_chain, llm_engine = initialize_agent()
    print("Agente listo y operando en capa gratuita.\n")
    
    # Prueba 1: Dominio correcto con datos del CSV
    p1 = "¿Qué temas de IA se publicaron en 2024?"
    print(f"Pregunta: {p1}")
    print(f"Respuesta:\n{ask_expert(p1, agent_chain, llm_engine)}\n")
    print("-" * 50)

    # Prueba 2: Fuera de dominio
    p2 = "¿Cuál es la capital de Francia?"
    print(f"Pregunta: {p2}")
    print(f"Respuesta:\n{ask_expert(p2, agent_chain, llm_engine)}\n")