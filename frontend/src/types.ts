export type Intent = 'chitchat' | 'discovery' | 'document' | 'awaiting_consent';
export type FileFormat = 'docx' | 'pdf';

export interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  intent?: Intent;
  jobId?: string;
  format?: FileFormat;
  timestamp: Date;
  isError?: boolean;
  fromHistory?: boolean;
}

export interface ChatApiResponse {
  reply: string;
  intent: Intent;
  job_id?: string;
  format?: string;
}

export interface ConversationSummary {
  session_id: string;
  title: string;
  last_message_at: string;
}

export interface ConversationMessage {
  role: 'user' | 'assistant';
  content: string;
  intent?: string;
  created_at: string;
}
