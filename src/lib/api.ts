// API client for Flask backend
const getBackendUrl = () => {
  return localStorage.getItem('backend_url') || 'http://34.192.78.22:5000';
};

export interface IngestItem {
  type: 'pdf' | 'text' | 'youtube';
  name: string;
  text?: string;
  dataBase64?: string;
  url?: string;
}

export interface IngestRequest {
  items: IngestItem[];
  conversationId?: string;
}

export interface Citation {
  title: string;
  chunkIndex: number;
  content: string;
}

export interface AskResponse {
  answer: string;
  citations: Citation[];
}

export const ingestMaterials = async (request: IngestRequest): Promise<void> => {
  const response = await fetch(`${getBackendUrl()}/api/ingest`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    const error = await response.text();
    throw new Error(error || 'Failed to ingest materials');
  }
};

export const askQuestion = async (question: string, conversationIds?: string[]): Promise<AskResponse> => {
  const body: any = { question };
  if (conversationIds && conversationIds.length > 0) body.conversationIds = conversationIds;
  const response = await fetch(`${getBackendUrl()}/api/ask`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(body),
  });

  if (!response.ok) {
    const error = await response.text();
    throw new Error(error || 'Failed to get answer');
  }

  return response.json();
};

export const deleteMaterial = async (conversationId: string): Promise<void> => {
  const response = await fetch(`${getBackendUrl()}/api/materials/${conversationId}`, {
    method: 'DELETE',
  });

  if (!response.ok) {
    const error = await response.text();
    throw new Error(error || 'Failed to delete material');
  }
};
