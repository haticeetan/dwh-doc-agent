import { ChatApiResponse, ConversationSummary, ConversationMessage } from './types';

const BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000';

export async function sendChatMessage(
  message: string,
  sessionId: string,
  consent?: 'yes' | 'no'
): Promise<ChatApiResponse> {
  const response = await fetch(`${BASE_URL}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, session_id: sessionId, consent: consent ?? '' }),
  });

  if (!response.ok) {
    throw new Error(`Sunucu hatası: ${response.status}`);
  }

  return response.json();
}

export async function downloadFile(jobId: string, format: string): Promise<void> {
  const response = await fetch(`${BASE_URL}/download/${jobId}`);

  if (!response.ok) {
    throw new Error('Dosya indirilemedi');
  }

  const blob = await response.blob();
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `${jobId}.${format}`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  window.URL.revokeObjectURL(url);
}

export async function getConversations(): Promise<ConversationSummary[]> {
  try {
    const response = await fetch(`${BASE_URL}/conversations`);
    if (!response.ok) return [];
    return response.json();
  } catch {
    return [];
  }
}

export async function getConversationMessages(sessionId: string): Promise<ConversationMessage[]> {
  try {
    const response = await fetch(`${BASE_URL}/conversations/${sessionId}/messages`);
    if (!response.ok) return [];
    return response.json();
  } catch {
    return [];
  }
}

export async function checkHealth(): Promise<boolean> {
  try {
    const response = await fetch(`${BASE_URL}/health`, {
      method: 'GET',
      signal: AbortSignal.timeout(5000),
    });
    return response.ok;
  } catch {
    return false;
  }
}
