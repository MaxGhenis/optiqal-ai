import { useState } from 'react';
import { Sparkles, Search } from 'lucide-react';

interface ChoiceInputProps {
  onAnalyze: (choice: string) => void;
  isLoading: boolean;
}

const exampleChoices = [
  "Switch from regular detergent to plastic-free",
  "Upgrade to a temperature-controlled mattress",
  "Cut out dairy from my diet",
  "Start taking vitamin D supplements",
  "Switch from driving to biking for my commute",
  "Reduce alcohol to weekends only",
  "Start meditating 10 minutes daily",
  "Switch to a standing desk",
  "Replace soda with sparkling water",
  "Add 30 minutes of walking daily",
];

export function ChoiceInput({ onAnalyze, isLoading }: ChoiceInputProps) {
  const [choice, setChoice] = useState('');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (choice.trim() && !isLoading) {
      onAnalyze(choice.trim());
    }
  };

  return (
    <div className="glass-card p-6 space-y-4">
      <h2 className="text-xl font-semibold gradient-text flex items-center gap-2">
        <Sparkles className="w-5 h-5" />
        Analyze a Choice
      </h2>
      <p className="text-sm text-slate-400">
        What lifestyle change are you considering? We'll estimate its QALY impact.
      </p>

      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="relative">
          <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-400" />
          <input
            type="text"
            value={choice}
            onChange={e => setChoice(e.target.value)}
            placeholder="e.g., Switch to a plant-based diet"
            className="w-full pl-12 pr-4"
            disabled={isLoading}
          />
        </div>
        <button
          type="submit"
          disabled={!choice.trim() || isLoading}
          className="w-full flex items-center justify-center gap-2"
        >
          {isLoading ? (
            <>
              <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              Analyzing...
            </>
          ) : (
            <>
              <Sparkles className="w-5 h-5" />
              Estimate QALY Impact
            </>
          )}
        </button>
      </form>

      <div className="pt-4 border-t border-slate-700/50">
        <p className="text-xs text-slate-500 mb-3">Try an example:</p>
        <div className="flex flex-wrap gap-2">
          {exampleChoices.slice(0, 5).map((example, i) => (
            <button
              key={i}
              type="button"
              onClick={() => setChoice(example)}
              disabled={isLoading}
              className="px-3 py-1.5 text-xs bg-slate-700/30 text-slate-400 rounded-full
                         hover:bg-slate-600/40 hover:text-slate-300 transition-all
                         border border-slate-600/30"
              style={{ background: undefined }}
            >
              {example}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
