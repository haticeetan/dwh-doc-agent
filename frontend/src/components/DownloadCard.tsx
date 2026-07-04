import { useState } from 'react';
import { FileText, FileType2, Download, CheckCircle, Loader2 } from 'lucide-react';
import { downloadFile } from '../api';
import { FileFormat } from '../types';

interface DownloadCardProps {
  jobId: string;
  format: FileFormat;
}

export function DownloadCard({ jobId, format }: DownloadCardProps) {
  const [status, setStatus] = useState<'idle' | 'loading' | 'done' | 'error'>('idle');

  const isDocx = format === 'docx';
  const label = isDocx ? 'Word Belgesi' : 'PDF Belgesi';
  const ext = format.toUpperCase();
  const Icon = isDocx ? FileText : FileType2;
  const accentColor = isDocx ? 'bg-blue-600' : 'bg-red-500';
  const borderColor = isDocx ? 'border-blue-100' : 'border-red-100';
  const badgeColor = isDocx ? 'bg-blue-50 text-blue-700' : 'bg-red-50 text-red-700';

  const handleDownload = async () => {
    if (status !== 'idle') return;
    setStatus('loading');
    try {
      await downloadFile(jobId, format);
      setStatus('done');
    } catch {
      setStatus('error');
      setTimeout(() => setStatus('idle'), 3000);
    }
  };

  return (
    <div
      className={`mt-3 flex items-center gap-3 bg-white border ${borderColor} rounded-xl px-4 py-3 shadow-sm max-w-sm`}
    >
      <div className={`w-10 h-10 rounded-xl ${accentColor} flex items-center justify-center flex-shrink-0`}>
        <Icon size={18} className="text-white" />
      </div>

      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-0.5">
          <p className="text-slate-800 text-sm font-semibold truncate">Belge Hazır</p>
          <span className={`text-xs font-bold px-1.5 py-0.5 rounded ${badgeColor}`}>{ext}</span>
        </div>
        <p className="text-slate-400 text-xs truncate">{label}</p>
      </div>

      <button
        onClick={handleDownload}
        disabled={status === 'loading' || status === 'done'}
        className={`
          flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold
          transition-all duration-200 flex-shrink-0
          ${status === 'done'
            ? 'bg-emerald-50 text-emerald-600 cursor-default'
            : status === 'error'
            ? 'bg-red-50 text-red-600 cursor-pointer'
            : status === 'loading'
            ? 'bg-slate-100 text-slate-400 cursor-not-allowed'
            : isDocx
            ? 'bg-blue-600 hover:bg-blue-700 text-white cursor-pointer'
            : 'bg-red-500 hover:bg-red-600 text-white cursor-pointer'
          }
        `}
      >
        {status === 'loading' ? (
          <Loader2 size={13} className="animate-spin" />
        ) : status === 'done' ? (
          <>
            <CheckCircle size={13} />
            İndirildi
          </>
        ) : status === 'error' ? (
          'Hata'
        ) : (
          <>
            <Download size={13} />
            İndir
          </>
        )}
      </button>
    </div>
  );
}
