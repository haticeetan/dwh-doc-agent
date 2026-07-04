import { Database, Plus, MessageSquare, LayoutDashboard } from 'lucide-react';
import { ConversationSummary } from '../types';

interface SidebarProps {
  onNewChat: () => void;
  hasMessages: boolean;
  isLoading: boolean;
  conversations: ConversationSummary[];
  activeSessionId: string;
  onSelectConversation: (sessionId: string) => void;
}

function calendarDay(date: Date): number {
  return new Date(date.getFullYear(), date.getMonth(), date.getDate()).getTime();
}

function formatDate(isoString: string): string {
  const date = new Date(isoString + 'Z');
  const now = new Date();
  const todayMs = calendarDay(now);
  const dateMs = calendarDay(date);
  const diffDays = Math.round((todayMs - dateMs) / 86400000);
  if (diffDays === 0) return date.toLocaleTimeString('tr-TR', { hour: '2-digit', minute: '2-digit' });
  if (diffDays === 1) return 'Dün';
  if (diffDays < 7) return `${diffDays} gün önce`;
  return date.toLocaleDateString('tr-TR', { day: 'numeric', month: 'short' });
}

function groupConversations(convs: ConversationSummary[]) {
  const today: ConversationSummary[] = [];
  const yesterday: ConversationSummary[] = [];
  const older: ConversationSummary[] = [];

  const todayMs = calendarDay(new Date());
  const yesterdayMs = todayMs - 86400000;

  for (const c of convs) {
    const dateMs = calendarDay(new Date(c.last_message_at + 'Z'));
    if (dateMs === todayMs) today.push(c);
    else if (dateMs === yesterdayMs) yesterday.push(c);
    else older.push(c);
  }
  return { today, yesterday, older };
}

function ConvGroup({ label, items, activeSessionId, onSelect }: {
  label: string;
  items: ConversationSummary[];
  activeSessionId: string;
  onSelect: (id: string) => void;
}) {
  if (!items.length) return null;
  return (
    <div className="mb-3">
      <p className="text-[10px] font-semibold text-slate-600 uppercase tracking-wider px-2 mb-1">
        {label}
      </p>
      {items.map((conv) => (
        <button
          key={conv.session_id}
          onClick={() => onSelect(conv.session_id)}
          className={`w-full text-left flex items-start gap-2 px-2.5 py-2 rounded-lg transition-colors duration-100 group mb-0.5 ${
            conv.session_id === activeSessionId
              ? 'bg-white/10 text-white'
              : 'text-slate-400 hover:bg-white/5 hover:text-slate-200'
          }`}
        >
          <MessageSquare
            size={13}
            className={`flex-shrink-0 mt-0.5 ${
              conv.session_id === activeSessionId ? 'text-blue-400' : 'text-slate-600 group-hover:text-slate-400'
            }`}
          />
          <div className="min-w-0 flex-1">
            <p className="text-xs truncate leading-snug">{conv.title}</p>
            <p className="text-[10px] text-slate-600 mt-0.5">{formatDate(conv.last_message_at)}</p>
          </div>
        </button>
      ))}
    </div>
  );
}

export function Sidebar({ onNewChat, hasMessages, isLoading, conversations, activeSessionId, onSelectConversation }: SidebarProps) {
  const { today, yesterday, older } = groupConversations(conversations);

  return (
    <aside className="w-60 bg-[#0F172A] flex flex-col flex-shrink-0 border-r border-white/5">
      {/* Logo */}
      <div className="px-4 pt-5 pb-4">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-blue-600 flex items-center justify-center flex-shrink-0">
            <Database size={16} className="text-white" />
          </div>
          <span className="text-white font-semibold text-sm tracking-tight">DWH DocAgent</span>
        </div>
      </div>

      {/* New Chat */}
      <div className="px-3 pb-3">
        <button
          onClick={onNewChat}
          disabled={!hasMessages || isLoading}
          className="w-full flex items-center gap-2 px-3 py-2 rounded-lg
            bg-blue-600 hover:bg-blue-500 disabled:opacity-30 disabled:cursor-not-allowed
            text-white text-xs font-medium transition-colors duration-150"
        >
          <Plus size={14} />
          Yeni Sohbet
        </button>
      </div>

      <div className="px-3 mb-2 border-t border-white/5 pt-3">
        <p className="text-[10px] font-semibold text-slate-600 uppercase tracking-wider px-2 mb-2 flex items-center gap-1.5">
          <LayoutDashboard size={10} />
          Geçmiş
        </p>
      </div>

      {/* Conversation list */}
      <div className="flex-1 overflow-y-auto px-3 pb-4">
        {conversations.length === 0 ? (
          <p className="text-slate-600 text-xs text-center mt-4 px-2">
            Henüz sohbet yok
          </p>
        ) : (
          <>
            <ConvGroup label="Bugün" items={today} activeSessionId={activeSessionId} onSelect={onSelectConversation} />
            <ConvGroup label="Dün" items={yesterday} activeSessionId={activeSessionId} onSelect={onSelectConversation} />
            <ConvGroup label="Önceki" items={older} activeSessionId={activeSessionId} onSelect={onSelectConversation} />
          </>
        )}
      </div>
    </aside>
  );
}
