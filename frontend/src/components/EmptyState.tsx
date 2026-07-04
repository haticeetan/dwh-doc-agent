import { FileText, Search, Info } from 'lucide-react';

interface EmptyStateProps {
  onExampleClick: (text: string) => void;
}

const CAPABILITIES = [
  {
    icon: FileText,
    title: 'Belgeleme',
    desc: 'Tablo yapısını ve kolonları otomatik dokümante eder',
    examples: [
      'FACT_SALES tablosunu belgele',
      'ORDERS ve ORDER_ITEMS tablolarını belgele',
    ],
  },
  {
    icon: Search,
    title: 'Keşif',
    desc: 'Veritabanındaki tabloları konuya göre bulur',
    examples: [
      'Satışla ilgili tablolar hangileri?',
      'Veritabanındaki tüm tabloları listele',
    ],
  },
  {
    icon: Info,
    title: 'Tablo Bilgisi',
    desc: 'Belirli bir tablonun içeriğini açıklar',
    examples: [
      'DIM_CUSTOMER tablosu ne içeriyor?',
      'FACT_SALES tablosunda kaç satır veri var?',
    ],
  },
];

export function EmptyState({ onExampleClick }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center h-full px-6 py-12">
      <h2 className="text-2xl font-bold text-slate-800 mb-1">Merhaba 👋</h2>
      <p className="text-slate-400 text-sm mb-10">
        Oracle veri ambarınız hakkında soru sorun
      </p>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 w-full max-w-3xl">
        {CAPABILITIES.map(({ icon: Icon, title, desc, examples }) => (
          <div
            key={title}
            className="bg-white rounded-2xl border border-slate-100 p-4 shadow-sm flex flex-col gap-3"
          >
            <div className="flex items-center gap-2">
              <div className="w-7 h-7 rounded-lg bg-blue-50 flex items-center justify-center flex-shrink-0">
                <Icon size={14} className="text-blue-600" />
              </div>
              <span className="text-sm font-semibold text-slate-700">{title}</span>
            </div>
            <p className="text-xs text-slate-400 leading-relaxed">{desc}</p>
            <div className="flex flex-col gap-1.5 mt-auto">
              {examples.map((ex) => (
                <button
                  key={ex}
                  onClick={() => onExampleClick(ex)}
                  className="text-left text-xs px-3 py-2 rounded-lg bg-slate-50 text-slate-600
                    hover:bg-blue-50 hover:text-blue-700 transition-colors duration-150 border border-transparent
                    hover:border-blue-100"
                >
                  {ex}
                </button>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
