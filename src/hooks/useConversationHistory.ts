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
const CURRENT_KEY = 'tutor_current_conversation';

export const useConversationHistory = () => {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [currentConversationId, setCurrentConversationId] = useState<string | null>(null);

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

  useEffect(() => {
    const cur = localStorage.getItem(CURRENT_KEY);
    if (cur) setCurrentConversationId(cur);
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
    const updated = [newConv, ...conversations];
    saveConversations(updated);
    // set as current
    localStorage.setItem(CURRENT_KEY, newConv.id);
    setCurrentConversationId(newConv.id);
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

  const addMessageToCurrent = (message: Omit<Message, 'id' | 'timestamp'>) => {
    if (!currentConversationId) {
      const convId = addConversation('Conversation ' + new Date().toLocaleString());
      addMessage(convId, message);
      return convId;
    }
    addMessage(currentConversationId, message);
    return currentConversationId;
  };

  const setCurrentConversation = (id: string | null) => {
    if (id) {
      localStorage.setItem(CURRENT_KEY, id);
    } else {
      localStorage.removeItem(CURRENT_KEY);
    }
    setCurrentConversationId(id);
  };

  const getCurrentConversation = (): Conversation | undefined => {
    return conversations.find((c) => c.id === currentConversationId);
  };

  const deleteConversation = (id: string) => {
    saveConversations(conversations.filter((c) => c.id !== id));
  };

  return {
    conversations,
    addConversation,
    addMessage,
    deleteConversation,
    currentConversationId,
    setCurrentConversation,
    getCurrentConversation,
    addMessageToCurrent,
  };
};
