import { Activity } from 'lucide-react';

export function Header() {
  return (
    <header className="text-center py-12 px-4">
      <div className="flex items-center justify-center gap-3 mb-4">
        <div className="p-3 bg-emerald-500/20 rounded-2xl">
          <Activity className="w-10 h-10 text-emerald-400" />
        </div>
        <h1 className="text-4xl md:text-5xl font-bold">
          <span className="gradient-text">OptiqAL</span>
          <span className="text-slate-400">.ai</span>
        </h1>
      </div>
      <p className="text-xl text-slate-400 max-w-2xl mx-auto">
        Quantify the impact of your choices on quality-adjusted life
      </p>
      <p className="text-sm text-slate-500 mt-2">
        AI-powered QALY estimation based on the best available causal evidence
      </p>
    </header>
  );
}
