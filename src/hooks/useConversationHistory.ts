import { useState, useEffect } from 'react';

export interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  citations?: Array<{ title: string; chunkIndex: number; content: string }>;
}

export interface Conversation {
  id: string;
  title: string;
  messages: Message[];
  createdAt: Date;
}

const STORAGE_KEY = 'tutor_conversations';

export const useConversationHistory = () => {
  const [conversations, setConversations] = useState<Conversation[]>([]);

  useEffect(() => {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored) {
      const parsed = JSON.parse(stored);
      setConversations(parsed.map((c: any) => ({
        ...c,
        createdAt: new Date(c.createdAt),
        messages: c.messages.map((m: any) => ({
          ...m,
          timestamp: new Date(m.timestamp),
        })),
      })));
    }
  }, []);

  const saveConversations = (convs: Conversation[]) => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(convs));
    setConversations(convs);
  };

  const addConversation = (title: string): string => {
    const newConv: Conversation = {
      id: Date.now().toString(),
      title,
      messages: [],
      createdAt: new Date(),
    };
    saveConversations([newConv, ...conversations]);
    return newConv.id;
  };

  const addMessage = (conversationId: string, message: Omit<Message, 'id' | 'timestamp'>) => {
    const updated = conversations.map((conv) => {
      if (conv.id === conversationId) {
        return {
          ...conv,
          messages: [
            ...conv.messages,
            {
              ...message,
              id: Date.now().toString(),
              timestamp: new Date(),
            },
          ],
        };
      }
      return conv;
    });
    saveConversations(updated);
  };

  const deleteConversation = (id: string) => {
    saveConversations(conversations.filter((c) => c.id !== id));
  };

  return {
    conversations,
    addConversation,
    addMessage,
    deleteConversation,
  };
};
