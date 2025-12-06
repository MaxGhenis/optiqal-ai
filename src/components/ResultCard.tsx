import type { ChoiceAnalysis } from '../types';
import { Clock, Heart, TrendingUp, AlertTriangle, BookOpen, Lightbulb, ChevronDown, ChevronUp } from 'lucide-react';
import { useState } from 'react';

interface ResultCardProps {
  analysis: ChoiceAnalysis;
}

function formatTime(minutes: number): string {
  const absMinutes = Math.abs(minutes);
  const sign = minutes < 0 ? '-' : '+';

  if (absMinutes < 60) {
    return `${sign}${Math.round(absMinutes)} minutes`;
  } else if (absMinutes < 1440) {
    const hours = Math.floor(absMinutes / 60);
    const mins = Math.round(absMinutes % 60);
    return mins > 0
      ? `${sign}${hours} hour${hours > 1 ? 's' : ''} ${mins} min`
      : `${sign}${hours} hour${hours > 1 ? 's' : ''}`;
  } else if (absMinutes < 10080) {
    const days = Math.floor(absMinutes / 1440);
    const hours = Math.round((absMinutes % 1440) / 60);
    return hours > 0
      ? `${sign}${days} day${days > 1 ? 's' : ''} ${hours} hr`
      : `${sign}${days} day${days > 1 ? 's' : ''}`;
  } else if (absMinutes < 43800) {
    const weeks = Math.floor(absMinutes / 10080);
    const days = Math.round((absMinutes % 10080) / 1440);
    return days > 0
      ? `${sign}${weeks} week${weeks > 1 ? 's' : ''} ${days} day${days > 1 ? 's' : ''}`
      : `${sign}${weeks} week${weeks > 1 ? 's' : ''}`;
  } else {
    const months = (absMinutes / 43800).toFixed(1);
    return `${sign}${months} months`;
  }
}

function ConfidenceBadge({ level }: { level: 'low' | 'medium' | 'high' }) {
  const colors = {
    low: 'bg-amber-500/20 text-amber-400 border-amber-500/30',
    medium: 'bg-cyan-500/20 text-cyan-400 border-cyan-500/30',
    high: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30',
  };

  return (
    <span className={`px-2 py-0.5 text-xs rounded-full border ${colors[level]}`}>
      {level} confidence
    </span>
  );
}

function EvidenceTypeBadge({ type }: { type: string }) {
  const colors: Record<string, string> = {
    'meta-analysis': 'bg-purple-500/20 text-purple-400',
    'rct': 'bg-emerald-500/20 text-emerald-400',
    'cohort': 'bg-blue-500/20 text-blue-400',
    'case-control': 'bg-cyan-500/20 text-cyan-400',
    'cross-sectional': 'bg-amber-500/20 text-amber-400',
    'expert-opinion': 'bg-slate-500/20 text-slate-400',
  };

  return (
    <span className={`px-2 py-0.5 text-xs rounded ${colors[type] || colors['expert-opinion']}`}>
      {type.replace('-', ' ')}
    </span>
  );
}

export function ResultCard({ analysis }: ResultCardProps) {
  const [showEvidence, setShowEvidence] = useState(false);
  const { impact, evidence, mechanismExplanation, caveats, personalizedFactors } = analysis;
  const isPositive = impact.totalMinutes >= 0;

  return (
    <div className="glass-card p-6 space-y-6">
      {/* Main Impact */}
      <div className="text-center space-y-2">
        <p className="text-sm text-slate-400 uppercase tracking-wide">Estimated QALY Impact</p>
        <div className={`text-4xl font-bold ${isPositive ? 'text-emerald-400' : 'text-rose-400'}`}>
          {formatTime(impact.totalMinutes)}
        </div>
        <p className="text-sm text-slate-500">of quality-adjusted life</p>
        <ConfidenceBadge level={impact.confidenceLevel} />
      </div>

      {/* Confidence Interval */}
      <div className="bg-slate-800/50 rounded-lg p-4">
        <p className="text-xs text-slate-400 mb-2">95% Confidence Interval</p>
        <div className="relative h-8">
          <div className="absolute inset-0 flex items-center">
            <div className="w-full h-1 bg-slate-700 rounded-full">
              <div
                className="h-full confidence-bar"
                style={{
                  marginLeft: `${Math.max(0, 50 + (impact.confidenceInterval.low / (Math.abs(impact.confidenceInterval.high) + Math.abs(impact.confidenceInterval.low) + 1)) * 50)}%`,
                  width: `${Math.min(100, ((impact.confidenceInterval.high - impact.confidenceInterval.low) / (Math.abs(impact.confidenceInterval.high) + Math.abs(impact.confidenceInterval.low) + 1)) * 50)}%`
                }}
              />
            </div>
          </div>
          <div className="absolute inset-0 flex items-center justify-between text-xs text-slate-400 px-2">
            <span>{formatTime(impact.confidenceInterval.low)}</span>
            <span>{formatTime(impact.confidenceInterval.high)}</span>
          </div>
        </div>
      </div>

      {/* Breakdown */}
      <div className="grid grid-cols-2 gap-4">
        <div className="bg-slate-800/30 rounded-lg p-4">
          <div className="flex items-center gap-2 text-cyan-400 mb-2">
            <Clock className="w-4 h-4" />
            <span className="text-sm font-medium">Longevity</span>
          </div>
          <p className={`text-lg font-semibold ${impact.longevityMinutes >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
            {formatTime(impact.longevityMinutes)}
          </p>
          <p className="text-xs text-slate-500 mt-1">Impact on lifespan</p>
        </div>
        <div className="bg-slate-800/30 rounded-lg p-4">
          <div className="flex items-center gap-2 text-purple-400 mb-2">
            <Heart className="w-4 h-4" />
            <span className="text-sm font-medium">Quality</span>
          </div>
          <p className={`text-lg font-semibold ${impact.qualityMinutes >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
            {formatTime(impact.qualityMinutes)}
          </p>
          <p className="text-xs text-slate-500 mt-1">Equivalent quality gain</p>
        </div>
      </div>

      {/* Mechanism */}
      <div className="space-y-2">
        <div className="flex items-center gap-2 text-slate-300">
          <Lightbulb className="w-4 h-4 text-amber-400" />
          <span className="text-sm font-medium">How it works</span>
        </div>
        <p className="text-sm text-slate-400 leading-relaxed">{mechanismExplanation}</p>
      </div>

      {/* Personalized Factors */}
      {personalizedFactors.length > 0 && (
        <div className="space-y-2">
          <div className="flex items-center gap-2 text-slate-300">
            <TrendingUp className="w-4 h-4 text-emerald-400" />
            <span className="text-sm font-medium">Personalized to you</span>
          </div>
          <ul className="space-y-1">
            {personalizedFactors.map((factor, i) => (
              <li key={i} className="text-sm text-slate-400 flex items-start gap-2">
                <span className="text-emerald-400 mt-1">•</span>
                {factor}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Caveats */}
      {caveats.length > 0 && (
        <div className="bg-amber-500/10 border border-amber-500/20 rounded-lg p-4 space-y-2">
          <div className="flex items-center gap-2 text-amber-400">
            <AlertTriangle className="w-4 h-4" />
            <span className="text-sm font-medium">Important caveats</span>
          </div>
          <ul className="space-y-1">
            {caveats.map((caveat, i) => (
              <li key={i} className="text-sm text-amber-200/70 flex items-start gap-2">
                <span className="text-amber-400 mt-1">•</span>
                {caveat}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Evidence */}
      <div className="space-y-3">
        <button
          type="button"
          onClick={() => setShowEvidence(!showEvidence)}
          className="w-full flex items-center justify-between text-slate-300
                     bg-slate-800/30 hover:bg-slate-800/50 transition-colors
                     rounded-lg px-4 py-3"
          style={{ background: undefined }}
        >
          <span className="flex items-center gap-2">
            <BookOpen className="w-4 h-4 text-blue-400" />
            <span className="text-sm font-medium">Evidence sources ({evidence.length})</span>
          </span>
          {showEvidence ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
        </button>

        {showEvidence && (
          <div className="space-y-3 pt-2">
            {evidence.map((source, i) => (
              <div key={i} className="bg-slate-800/20 rounded-lg p-4 space-y-2">
                <div className="flex items-start justify-between gap-3">
                  <h4 className="text-sm font-medium text-slate-300">{source.title}</h4>
                  <span className="text-xs text-slate-500 shrink-0">{source.year}</span>
                </div>
                <div className="flex items-center gap-2">
                  <EvidenceTypeBadge type={source.type} />
                  {source.sampleSize && (
                    <span className="text-xs text-slate-500">n={source.sampleSize.toLocaleString()}</span>
                  )}
                  {source.effectSize && (
                    <span className="text-xs text-slate-400">{source.effectSize}</span>
                  )}
                </div>
                <p className="text-xs text-slate-400">{source.summary}</p>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
