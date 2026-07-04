import { useState, useRef, useEffect, KeyboardEvent } from 'react';
import { Send, Loader2 } from 'lucide-react';

interface ChatInputProps {
  onSend: (text: string) => void;
  isLoading: boolean;
}

export function ChatInput({ onSend, isLoading }: ChatInputProps) {
  const [value, setValue] = useState('');
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const adjustHeight = () => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = `${Math.min(el.scrollHeight, 160)}px`;
  };

  useEffect(() => {
    adjustHeight();
  }, [value]);

  const handleSend = () => {
    const trimmed = value.trim();
    if (!trimmed || isLoading) return;
    onSend(trimmed);
    setValue('');
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="bg-white border-t border-slate-100 px-4 py-3">
      <div className="max-w-3xl mx-auto">
        <div
          className={`flex items-end gap-3 bg-slate-50 border rounded-2xl px-4 py-3 transition-all duration-150 ${
            isLoading
              ? 'border-slate-200'
              : 'border-slate-200 focus-within:border-blue-400 focus-within:bg-white focus-within:shadow-sm'
          }`}
        >
          <textarea
            ref={textareaRef}
            value={value}
            onChange={(e) => setValue(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={isLoading}
            placeholder="Bir soru sorun veya tablo adı yazın..."
            rows={1}
            className="flex-1 bg-transparent resize-none outline-none text-sm text-slate-700
              placeholder-slate-400 leading-relaxed min-h-[24px] disabled:opacity-50"
          />
          <button
            onClick={handleSend}
            disabled={!value.trim() || isLoading}
            className={`
              w-8 h-8 rounded-xl flex items-center justify-center flex-shrink-0
              transition-all duration-150 mb-0.5
              ${value.trim() && !isLoading
                ? 'bg-blue-600 hover:bg-blue-700 text-white shadow-sm'
                : 'bg-slate-200 text-slate-400 cursor-not-allowed'
              }
            `}
          >
            {isLoading ? (
              <Loader2 size={14} className="animate-spin" />
            ) : (
              <Send size={13} />
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
