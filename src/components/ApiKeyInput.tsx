import { Key, ExternalLink } from 'lucide-react';

interface ApiKeyInputProps {
  apiKey: string;
  onChange: (key: string) => void;
}

export function ApiKeyInput({ apiKey, onChange }: ApiKeyInputProps) {
  return (
    <div className="glass-card p-6 space-y-4">
      <div className="flex items-center gap-2">
        <Key className="w-5 h-5 text-amber-400" />
        <h2 className="text-lg font-semibold text-slate-200">API Key</h2>
      </div>
      <p className="text-sm text-slate-400">
        Enter your Anthropic API key to enable analysis. Your key is stored locally and never sent to our servers.
      </p>
      <input
        type="password"
        value={apiKey}
        onChange={e => onChange(e.target.value)}
        placeholder="sk-ant-..."
        className="w-full"
      />
      <a
        href="https://console.anthropic.com/settings/keys"
        target="_blank"
        rel="noopener noreferrer"
        className="inline-flex items-center gap-1 text-sm text-emerald-400 hover:text-emerald-300"
      >
        Get an API key <ExternalLink className="w-3 h-3" />
      </a>
    </div>
  );
}
