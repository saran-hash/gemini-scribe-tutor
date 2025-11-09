// API client for Flask backend
const getBackendUrl = () => {
  return localStorage.getItem('backend_url') || 'http://localhost:5000';
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

export const askQuestion = async (question: string): Promise<AskResponse> => {
  const response = await fetch(`${getBackendUrl()}/api/ask`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ question }),
  });

  if (!response.ok) {
    const error = await response.text();
    throw new Error(error || 'Failed to get answer');
  }

  return response.json();
};
