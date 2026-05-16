'use client';

import { useState, useEffect, useRef, FormEvent } from 'react';

interface Chat {
  id: string;
  nombre: string;
}

interface Message {
  role: 'user' | 'assistant';
  content: string;
}

const API_BASE = 'http://localhost:8000/api';

export default function Home() {
  const [chats, setChats] = useState<Chat[]>([]);
  const [activeChatId, setActiveChatId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState<string>('');
  const [isLoading, setIsLoading] = useState<boolean>(false);

  const messagesEndRef = useRef<HTMLDivElement | null>(null);

  // Cargar lista de chats del sidebar al iniciar
  useEffect(() => {
    loadChats();
  }, []);

  // Auto-scroll al recibir nuevos mensajes
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const loadChats = async () => {
    try {
      const res = await fetch(`${API_BASE}/chats`);
      if (res.ok) setChats(await res.json());
    } catch (e) {
      console.error("Error cargando chats del backend:", e);
    }
  };

  const loadChatHistory = async (chatId: string) => {
    setActiveChatId(chatId);
    setIsLoading(true);
    try {
      const res = await fetch(`${API_BASE}/chats/${chatId}/messages`);
      if (res.ok) setMessages(await res.json());
    } catch (e) {
      console.error("Error cargando historial:", e);
    } finally {
      setIsLoading(false);
    }
  };

  const startNewChat = () => {
    setActiveChatId(null);
    setMessages([]);
  };

  const sendMessage = async (e: FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isLoading) return;

    // Si es un chat nuevo, le generamos un ID único temporal basado en tiempo
    const chatId = activeChatId || `chat_${Date.now()}`;
    if (!activeChatId) setActiveChatId(chatId);

    const userMsg: Message = { role: 'user', content: input };
    setMessages(prev => [...prev, userMsg]);
    setInput('');
    setIsLoading(true);

    try {
      const res = await fetch(`${API_BASE}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ chat_id: chatId, question: userMsg.content })
      });
      
      if (res.ok) {
        const data = await res.json();
        setMessages(prev => [...prev, { role: 'assistant', content: data.response }]);
        loadChats(); // Recargar el sidebar para actualizar nombres
      }
    } catch (e) {
      setMessages(prev => [...prev, { role: 'assistant', content: 'Error de comunicación con el backend.' }]);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex h-screen bg-gray-900 text-white font-sans">
      {/* SIDEBAR */}
      <aside className="w-64 bg-gray-950 p-4 flex flex-col border-r border-gray-800">
        <button 
          onClick={startNewChat}
          className="w-full bg-blue-600 hover:bg-blue-500 py-2 px-4 rounded mb-4 font-medium transition-colors"
        >
          + Nuevo Chat
        </button>
        <div className="flex-1 overflow-y-auto space-y-2">
          <p className="text-xs text-gray-500 font-semibold uppercase px-2">Historial</p>
          {chats.map(c => (
            <button
              key={c.id}
              onClick={() => loadChatHistory(c.id)}
              className={`w-full text-left p-2 rounded text-sm truncate block ${activeChatId === c.id ? 'bg-gray-800 text-blue-400' : 'text-gray-400 hover:bg-gray-900'}`}
            >
              {c.nombre}
            </button>
          ))}
        </div>
      </aside>

      {/* VENTANA DE CHAT */}
      <main className="flex-1 flex flex-col h-full">
        {/* Cuerpo de Mensajes */}
        <div className="flex-1 overflow-y-auto p-6 space-y-4">
          {messages.length === 0 ? (
            <div className="h-full flex items-center justify-center text-gray-500">
              Haz una pregunta sobre las publicaciones de IA para iniciar.
            </div>
          ) : (
            messages.map((m, i) => (
              <div key={i} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                <div className={`max-w-[75%] rounded p-3 text-sm whitespace-pre-wrap ${m.role === 'user' ? 'bg-blue-600' : 'bg-gray-800 text-gray-100'}`}>
                  {m.content}
                </div>
              </div>
            ))
          )}
          {isLoading && <div className="text-sm text-gray-500 animate-pulse">Consultando el grafo en AuraDB...</div>}
          <div ref={messagesEndRef} />
        </div>

        {/* Formulario de Entrada */}
        <footer className="p-4 bg-gray-950/50 border-t border-gray-800">
          <form onSubmit={sendMessage} className="flex gap-2 max-w-4xl mx-auto">
            <input
              type="text"
              value={input}
              onChange={e => setInput(e.target.value)}
              placeholder="Escribe tu consulta aquí..."
              className="flex-1 bg-gray-900 border border-gray-700 rounded px-4 py-2 text-sm focus:outline-none focus:border-blue-500"
            />
            <button type="submit" className="bg-blue-600 px-4 py-2 rounded text-sm font-medium hover:bg-blue-500">
              Enviar
            </button>
          </form>
        </footer>
      </main>
    </div>
  );
}