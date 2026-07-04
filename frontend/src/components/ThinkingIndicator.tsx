import { useState, useEffect } from 'react';
import { Database } from 'lucide-react';

const STEPS = [
  'Oracle şeması okunuyor...',
  'İlişkiler analiz ediliyor...',
  'Dokümantasyon oluşturuluyor...',
  'Kalite kontrolü yapılıyor...',
  'Belge hazırlanıyor...',
];

export function ThinkingIndicator() {
  const [stepIndex, setStepIndex] = useState(0);

  useEffect(() => {
    const timer = setInterval(() => {
      setStepIndex((prev) => (prev + 1) % STEPS.length);
    }, 3500);
    return () => clearInterval(timer);
  }, []);

  return (
    <div className="flex items-start gap-3 animate-fade-in">
      <div className="w-8 h-8 rounded-full bg-blue-600 flex items-center justify-center flex-shrink-0 shadow-md">
        <Database size={15} className="text-white" />
      </div>
      <div className="bg-white rounded-2xl rounded-tl-sm px-4 py-3 shadow-sm border border-slate-100 max-w-xs">
        <div className="flex items-center gap-1.5 mb-2">
          <span
            className="w-2 h-2 bg-blue-500 rounded-full animate-bounce"
            style={{ animationDelay: '0ms' }}
          />
          <span
            className="w-2 h-2 bg-blue-400 rounded-full animate-bounce"
            style={{ animationDelay: '150ms' }}
          />
          <span
            className="w-2 h-2 bg-blue-300 rounded-full animate-bounce"
            style={{ animationDelay: '300ms' }}
          />
        </div>
        <p className="text-xs text-slate-400 transition-all duration-500">{STEPS[stepIndex]}</p>
      </div>
    </div>
  );
}
