import { useState, useRef, useEffect, useCallback } from 'react';
import { Message, FileFormat, ConversationSummary } from './types';
import { sendChatMessage, getConversations, getConversationMessages } from './api';
import { Sidebar } from './components/Sidebar';
import { ChatMessage } from './components/ChatMessage';
import { ChatInput } from './components/ChatInput';
import { ThinkingIndicator } from './components/ThinkingIndicator';
import { EmptyState } from './components/EmptyState';

function generateId(): string {
  return Math.random().toString(36).substring(2, 9);
}

export default function App() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [sessionId, setSessionId] = useState<string>(() => crypto.randomUUID());
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isLoading]);

  const refreshConversations = useCallback(async () => {
    setConversations(await getConversations());
  }, []);

  useEffect(() => {
    refreshConversations();
  }, [refreshConversations]);

  const handleSend = useCallback(
    async (text: string, consent?: 'yes' | 'no') => {
      if (!text.trim() || isLoading) return;

      setMessages((prev) => [
        ...prev,
        { id: generateId(), role: 'user', content: text.trim(), timestamp: new Date() },
      ]);
      setIsLoading(true);

      try {
        const response = await sendChatMessage(text.trim(), sessionId, consent);
        setMessages((prev) => [
          ...prev,
          {
            id: generateId(),
            role: 'assistant',
            content: response.reply,
            intent: response.intent,
            jobId: response.job_id,
            format: response.format as FileFormat | undefined,
            timestamp: new Date(),
          },
        ]);
        refreshConversations();
      } catch {
        setMessages((prev) => [
          ...prev,
          {
            id: generateId(),
            role: 'assistant',
            content: "Sunucuya bağlanırken bir hata oluştu. `python main.py` komutunun çalıştığını kontrol edin.",
            timestamp: new Date(),
            isError: true,
          },
        ]);
      } finally {
        setIsLoading(false);
      }
    },
    [isLoading, sessionId, refreshConversations]
  );

  const handleConsent = useCallback(
    (answer: 'yes' | 'no') => handleSend(answer === 'yes' ? 'Evet, kullan' : 'Hayır, gerek yok', answer),
    [handleSend]
  );

  const handleNewChat = useCallback(() => {
    setMessages([]);
    setSessionId(crypto.randomUUID());
  }, []);

  const handleSelectConversation = useCallback(async (selectedSessionId: string) => {
    if (selectedSessionId === sessionId && messages.length > 0) return;
    setIsLoading(true);
    const history = await getConversationMessages(selectedSessionId);
    setMessages(
      history.map((m) => ({
        id: generateId(),
        role: m.role,
        content: m.content,
        intent: m.intent as Message['intent'],
        timestamp: new Date(m.created_at + 'Z'),
        fromHistory: true,
      }))
    );
    setSessionId(selectedSessionId);
    setIsLoading(false);
  }, [sessionId, messages.length]);

  return (
    <div className="flex h-screen bg-slate-50 overflow-hidden font-sans">
      <Sidebar
        onNewChat={handleNewChat}
        hasMessages={messages.length > 0}
        isLoading={isLoading}
        conversations={conversations}
        activeSessionId={sessionId}
        onSelectConversation={handleSelectConversation}
      />

      <div className="flex flex-col flex-1 min-w-0 overflow-hidden">
        <div className="flex-1 overflow-y-auto">
          {messages.length === 0 && !isLoading ? (
            <EmptyState onExampleClick={handleSend} />
          ) : (
            <div className="max-w-3xl mx-auto px-4 py-6 space-y-5">
              {messages.map((message, index) => (
                <ChatMessage
                  key={message.id}
                  message={message}
                  onConsent={
                    index === messages.length - 1 && !isLoading ? handleConsent : undefined
                  }
                />
              ))}
              {isLoading && <ThinkingIndicator />}
              <div ref={messagesEndRef} />
            </div>
          )}
        </div>

        <ChatInput onSend={handleSend} isLoading={isLoading} />
      </div>
    </div>
  );
}
