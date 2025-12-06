import { useState, useEffect } from 'react';
import { Header } from './components/Header';
import { ProfileForm } from './components/ProfileForm';
import { ChoiceInput } from './components/ChoiceInput';
import { ResultCard } from './components/ResultCard';
import { ApiKeyInput } from './components/ApiKeyInput';
import { analyzeChoice } from './api/analyze';
import type { UserProfile, ChoiceAnalysis } from './types';
import { AlertCircle } from 'lucide-react';

const DEFAULT_PROFILE: UserProfile = {
  age: 35,
  sex: 'male',
  weight: 75,
  height: 175,
  smoker: false,
  exerciseHoursPerWeek: 3,
  sleepHoursPerNight: 7,
  existingConditions: [],
  diet: 'omnivore',
};

function App() {
  const [profile, setProfile] = useState<UserProfile>(DEFAULT_PROFILE);
  const [apiKey, setApiKey] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<ChoiceAnalysis | null>(null);
  const [history, setHistory] = useState<ChoiceAnalysis[]>([]);

  // Load API key from localStorage
  useEffect(() => {
    const stored = localStorage.getItem('optiqal-api-key');
    if (stored) setApiKey(stored);

    const storedProfile = localStorage.getItem('optiqal-profile');
    if (storedProfile) {
      try {
        setProfile(JSON.parse(storedProfile));
      } catch {}
    }
  }, []);

  // Save API key to localStorage
  useEffect(() => {
    if (apiKey) {
      localStorage.setItem('optiqal-api-key', apiKey);
    }
  }, [apiKey]);

  // Save profile to localStorage
  useEffect(() => {
    localStorage.setItem('optiqal-profile', JSON.stringify(profile));
  }, [profile]);

  const handleAnalyze = async (choice: string) => {
    if (!apiKey) {
      setError('Please enter your Anthropic API key first');
      return;
    }

    setIsLoading(true);
    setError(null);
    setResult(null);

    try {
      const response = await analyzeChoice(profile, choice, apiKey);
      setResult(response.analysis);
      setHistory(prev => [response.analysis, ...prev.slice(0, 9)]);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'An error occurred');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen">
      <Header />

      <main className="max-w-6xl mx-auto px-4 pb-16">
        <div className="grid md:grid-cols-2 gap-6">
          {/* Left column: Inputs */}
          <div className="space-y-6">
            <ApiKeyInput apiKey={apiKey} onChange={setApiKey} />
            <ProfileForm profile={profile} onChange={setProfile} />
          </div>

          {/* Right column: Analysis */}
          <div className="space-y-6">
            <ChoiceInput onAnalyze={handleAnalyze} isLoading={isLoading} />

            {error && (
              <div className="glass-card p-4 border-rose-500/30 bg-rose-500/10">
                <div className="flex items-center gap-2 text-rose-400">
                  <AlertCircle className="w-5 h-5" />
                  <span>{error}</span>
                </div>
              </div>
            )}

            {result && <ResultCard analysis={result} />}

            {/* History */}
            {history.length > 1 && (
              <div className="glass-card p-6 space-y-4">
                <h3 className="text-lg font-semibold text-slate-300">Recent Analyses</h3>
                <div className="space-y-2">
                  {history.slice(1).map((item, i) => (
                    <button
                      key={item.id + i}
                      onClick={() => setResult(item)}
                      className="w-full text-left p-3 bg-slate-800/30 hover:bg-slate-800/50
                                 rounded-lg transition-colors group"
                      style={{ background: undefined }}
                    >
                      <div className="flex items-center justify-between">
                        <span className="text-sm text-slate-300 group-hover:text-white">
                          {item.choice}
                        </span>
                        <span className={`text-sm font-medium ${
                          item.impact.totalMinutes >= 0 ? 'text-emerald-400' : 'text-rose-400'
                        }`}>
                          {item.impact.totalMinutes >= 0 ? '+' : ''}{Math.round(item.impact.totalMinutes / 60)}h
                        </span>
                      </div>
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Footer disclaimer */}
        <footer className="mt-16 text-center text-sm text-slate-500 max-w-2xl mx-auto">
          <p>
            OptiqAL provides estimates based on published research and should not be considered medical advice.
            Estimates involve significant uncertainty and are personalized based on limited information.
            Always consult healthcare professionals for medical decisions.
          </p>
        </footer>
      </main>
    </div>
  );
}

export default App;
