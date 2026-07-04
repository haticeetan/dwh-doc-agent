import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Database, User, AlertCircle, Check, X } from 'lucide-react';
import { Message } from '../types';
import { DownloadCard } from './DownloadCard';

interface ChatMessageProps {
  message: Message;
  onConsent?: (answer: 'yes' | 'no') => void;
}

function formatTime(date: Date): string {
  return date.toLocaleTimeString('tr-TR', { hour: '2-digit', minute: '2-digit' });
}

const mdComponents = {
  table: ({ children }: { children?: React.ReactNode }) => (
    <div className="overflow-x-auto my-3 rounded-lg border border-slate-200">
      <table className="w-full border-collapse text-sm">{children}</table>
    </div>
  ),
  thead: ({ children }: { children?: React.ReactNode }) => (
    <thead className="bg-blue-600 text-white">{children}</thead>
  ),
  th: ({ children }: { children?: React.ReactNode }) => (
    <th className="px-3 py-2 text-left font-semibold text-xs uppercase tracking-wide">{children}</th>
  ),
  td: ({ children }: { children?: React.ReactNode }) => (
    <td className="px-3 py-2 border-b border-slate-100 text-slate-700 text-sm">{children}</td>
  ),
  tr: ({ children }: { children?: React.ReactNode }) => (
    <tr className="hover:bg-slate-50 transition-colors">{children}</tr>
  ),
  h1: ({ children }: { children?: React.ReactNode }) => (
    <h1 className="text-lg font-bold text-slate-800 mt-5 mb-2 pb-2 border-b border-slate-200 first:mt-0">{children}</h1>
  ),
  h2: ({ children }: { children?: React.ReactNode }) => (
    <h2 className="text-sm font-bold text-blue-700 mt-4 mb-2 uppercase tracking-wide">{children}</h2>
  ),
  h3: ({ children }: { children?: React.ReactNode }) => (
    <h3 className="text-sm font-semibold text-slate-700 mt-3 mb-1.5">{children}</h3>
  ),
  p: ({ children }: { children?: React.ReactNode }) => (
    <p className="text-slate-600 leading-relaxed my-1.5 text-sm">{children}</p>
  ),
  ul: ({ children }: { children?: React.ReactNode }) => (
    <ul className="list-disc list-outside pl-4 space-y-1 my-2">{children}</ul>
  ),
  ol: ({ children }: { children?: React.ReactNode }) => (
    <ol className="list-decimal list-outside pl-4 space-y-1 my-2">{children}</ol>
  ),
  li: ({ children }: { children?: React.ReactNode }) => (
    <li className="text-slate-600 text-sm">{children}</li>
  ),
  strong: ({ children }: { children?: React.ReactNode }) => (
    <strong className="font-semibold text-slate-800">{children}</strong>
  ),
  code: ({ children, className }: { children?: React.ReactNode; className?: string }) => {
    const isBlock = className?.includes('language-');
    if (isBlock) {
      return (
        <pre className="bg-slate-900 text-slate-100 rounded-lg p-4 overflow-x-auto my-3 text-xs font-mono">
          <code>{children}</code>
        </pre>
      );
    }
    return (
      <code className="bg-slate-100 text-blue-700 px-1.5 py-0.5 rounded text-xs font-mono">
        {children}
      </code>
    );
  },
  hr: () => <hr className="border-slate-200 my-4" />,
  blockquote: ({ children }: { children?: React.ReactNode }) => (
    <blockquote className="border-l-4 border-blue-300 pl-4 italic text-slate-500 my-3">{children}</blockquote>
  ),
};

export function ChatMessage({ message, onConsent }: ChatMessageProps) {
  const isUser = message.role === 'user';

  if (isUser) {
    return (
      <div className="flex items-end justify-end gap-2.5 animate-slide-up">
        <div className="flex flex-col items-end gap-1 max-w-[75%]">
          <div className="bg-blue-600 text-white rounded-2xl rounded-br-sm px-4 py-3 shadow-sm">
            <p className="text-sm leading-relaxed whitespace-pre-wrap">{message.content}</p>
          </div>
          <span className="text-xs text-slate-400">{formatTime(message.timestamp)}</span>
        </div>
        <div className="w-8 h-8 rounded-full bg-slate-200 flex items-center justify-center flex-shrink-0 mb-5">
          <User size={15} className="text-slate-500" />
        </div>
      </div>
    );
  }

  return (
    <div className="flex items-start gap-2.5 animate-slide-up">
      <div
        className={`w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 shadow-md ${
          message.isError ? 'bg-red-500' : 'bg-blue-600'
        }`}
      >
        {message.isError ? (
          <AlertCircle size={15} className="text-white" />
        ) : (
          <Database size={15} className="text-white" />
        )}
      </div>

      <div className="flex flex-col gap-1 max-w-[85%] min-w-0">
        <div
          className={`rounded-2xl rounded-tl-sm px-4 py-3 shadow-sm ${
            message.isError
              ? 'bg-red-50 border border-red-100'
              : 'bg-white border border-slate-100'
          }`}
        >
          {message.isError ? (
            <p className="text-sm text-red-600 leading-relaxed">{message.content}</p>
          ) : (
            <div className="min-w-0">
              <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                components={mdComponents as Record<string, React.ElementType>}
              >
                {message.content}
              </ReactMarkdown>
            </div>
          )}
        </div>

        {message.jobId && message.format && (
          <DownloadCard jobId={message.jobId} format={message.format} />
        )}

        {message.intent === 'awaiting_consent' && onConsent && !message.fromHistory && (
          <div className="flex gap-2 mt-3">
            <button
              onClick={() => onConsent('yes')}
              className="flex items-center gap-1.5 px-4 py-2 rounded-full
                bg-blue-600 text-white text-sm font-medium
                hover:bg-blue-700 active:scale-[0.97] transition-all duration-150 shadow-sm"
            >
              <Check size={14} strokeWidth={2.5} />
              Evet, kullan
            </button>
            <button
              onClick={() => onConsent('no')}
              className="flex items-center gap-1.5 px-4 py-2 rounded-full
                bg-slate-100 text-slate-600 text-sm font-medium
                hover:bg-slate-200 active:scale-[0.97] transition-all duration-150"
            >
              <X size={14} strokeWidth={2} />
              Hayır, gerek yok
            </button>
          </div>
        )}

        <span className="text-xs text-slate-400 ml-1">{formatTime(message.timestamp)}</span>
      </div>
    </div>
  );
}
