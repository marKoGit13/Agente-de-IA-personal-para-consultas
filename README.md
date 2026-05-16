# 🤖 GraphRAG Academic Agent · IA Full-Stack (v2)

<div align="center">

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-Backend-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Next.js](https://img.shields.io/badge/Next.js-15-Frontend-000000?style=for-the-badge&logo=nextdotjs&logoColor=white)](https://nextjs.org/)
[![Neo4j](https://img.shields.io/badge/Neo4j-AuraDB-Graph-4581C3?style=for-the-badge&logo=neo4j&logoColor=white)](https://neo4j.com/cloud/platform/aura-graph-database/)
[![Groq](https://img.shields.io/badge/Groq-Llama%203.3%2070B-00E5A0?style=for-the-badge&logo=llama&logoColor=black)](https://groq.com/)
[![License](https://img.shields.io/badge/Licencia-MIT-yellow?style=for-the-badge)](LICENSE)

*Agente de IA generativa basado en Grafos para la ingesta, consulta y descubrimiento semántico en el dominio de la Inteligencia Artificial académica.*

[Características](#-características-principales) •
[Arquitectura](#️-arquitectura-del-sistema) •
[Instalación](#️-guía-de-instalación) •
[Demo](#-guión-de-validación) •
[Esquema de Datos](#-modelo-de-datos)

</div>

---

## 📖 Descripción General

Este repositorio alberga la evolución de un sistema de **Generación Aumentada por Recuperación basado en Grafos (GraphRAG)** . A diferencia de los RAG tradicionales que solo consultan embeddings vectoriales, este agente mapea el conocimiento en un **grafo relacional nativo en Neo4j AuraDB**. Un LLM de vanguardia (**Llama 3.3 70B vía Groq**) actúa como el cerebro lógico, traduciendo lenguaje natural a consultas **Cypher** y sintetizando respuestas, todo orquestado por un backend en **FastAPI** y presentado en un frontend moderno con **Next.js 15**.

---

## 🚀 Características Principales

Esta versión se ha rediseñado con un enfoque de ingeniería de software robusto y seguro para entornos de producción.

| Pilar | Innovación Técnica |
| :--- | :--- |
| **🛡️ Ciberseguridad Activa (Guardrails)** | Analizador sintáctico que intercepta y bloquea comandos destructivos (`DELETE`, `DROP`, `CREATE`, etc.) antes de llegar a la base de datos, garantizando la inmutabilidad del grafo. |
| **🧠 Memoria con Ventana Deslizante** | Historial conversacional persistido en **SQLite**, limitado a las últimas 10 interacciones. Previene la saturación del contexto del LLM y optimiza los costos de API. |
| **🩺 Auto-Corrección Resiliente** | Mecanismo **Self-Healing** que, ante un error de sintaxis en la query Cypher, captura la excepción e inicia un sub-ciclo de reparación con el LLM de forma transparente para el usuario. |
| **🔍 Búsqueda Inclusiva y Flexible** | Uso forzado de los operadores `CONTAINS` y `toLower` en las consultas generadas, asegurando coincidencias precisas sin importar mayúsculas, minúsculas o tipeos parciales. |

---

## 🏗️ Arquitectura del Sistema

El siguiente diagrama describe el flujo de extremo a extremo de una consulta, desde la interfaz de usuario hasta la generación de la respuesta.

```mermaid
flowchart TD
    %% Configuración de Capas Estructurales (Subgrafos)
    subgraph Capa_Cliente [💻 Capa de Presentación]
        A[Frontend Next.js]
    end

    subgraph Capa_Seguridad [⚙️ Motor de Orquestación y Guardrails]
        B(Backend FastAPI)
        G{🛡️ Guardrail 1: <br> ¿Intento Destructivo?}
        E{⚠️ Guardrail 2: <br> ¿Fuera de Dominio?}
        SC{🔧 Self-Correction: <br> ¿Error de Sintaxis?}
    end

    subgraph Capa_Datos [🗄️ Capa de Persistencia]
        C[(SQLite DB <br> Sliding Window: Máx 10)]
        H[(Neo4j AuraDB <br> Cloud Graph)]
    end

    subgraph Capa_IA [🧠 Capa de Razonamiento Semántico]
        D(Groq LLM <br> Llama 3.3 70B)
    end

    %% Ciclo de Vida de la Consulta
    A -->|1. Pregunta + chat_id| B
    B --> G
    
    %% Flujo de Bloqueo Mecánico
    G -->|Sí: CREATE/DELETE/DROP| F1[❌ Bloqueo Mecánico: Acción Rechazada]
    F1 -->|Respuesta de Control Segura| A

    %% Flujo Seguro: Memoria Condensada
    G -->|No: Es Seguro| C1[2. Cargar Historial de Sesión]
    C1 --> C
    C -->|Filtro de Últimos 10 Mensajes| B
    B -->|3. Condensación de Contexto Cruzado| D
    D -->|Pregunta Purificada e Independiente| B
    
    %% Generación de Código e Intercepción de Dominio
    B -->|4. Traducir a Cypher + CONTAINS| D
    D -->|Query Generada| E
    
    E -->|Sí: BLOCK_QUERY| F2[🚫 Bloqueo Estático: Tema No Académico]
    F2 -->|Mensaje Informativo de Dominio| A
    
    %% Ejecución en Grafo y Auto-Sanación
    E -->|No: Query Válida| H1[5. Ejecutar vía protocolo neo4j+ssc]
    H1 --> H
    H --> SC
    
    SC -->|Sí: Excepción de compilación| D1[🔄 Bucle de Auto-Corrección Activo]
    D1 -->|1 Reintento con rastro del error| H
    
    %% Síntesis, Persistencia y Despliegue
    H -->|6. Datos Puros Relacionales JSON| I(7. Groq LLM: Síntesis de Alta Fidelidad)
    I -->|8. Registro Atómico de Interacción| C
    I -->|9. Respuesta Pulida en Markdown + Auto-scroll| A

    %% Definición de Estilos
    classDef frontend fill:#1e1b4b,stroke:#4f46e5,stroke-width:2px,color:#ffffff;
    classDef backend fill:#0f172a,stroke:#2563eb,stroke-width:2px,color:#ffffff;
    classDef llm fill:#022c22,stroke:#10b981,stroke-width:2px,color:#ffffff;
    classDef db fill:#1c1917,stroke:#78716c,stroke-width:2px,color:#ffffff;
    classDef block fill:#7f1d1d,stroke:#ef4444,stroke-width:2px,color:#ffffff;
    
    class A frontend;
    class B,G,E,SC backend;
    class D,I,D1 llm;
    class C,H db;
    class F1,F2 block;

    style Capa_Cliente fill:none,stroke:#4338ca,stroke-dasharray: 5 5,color:#cbd5e1
    style Capa_Seguridad fill:none,stroke:#1d4ed8,stroke-dasharray: 5 5,color:#cbd5e1
    style Capa_Datos fill:none,stroke:#475569,stroke-dasharray: 5 5,color:#cbd5e1
    style Capa_IA fill:none,stroke:#047857,stroke-dasharray: 5 5,color:#cbd5e1