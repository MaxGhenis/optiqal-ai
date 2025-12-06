import type { UserProfile } from '../types';

interface ProfileFormProps {
  profile: UserProfile;
  onChange: (profile: UserProfile) => void;
}

export function ProfileForm({ profile, onChange }: ProfileFormProps) {
  const conditions = [
    'Diabetes', 'Hypertension', 'Heart Disease', 'Asthma',
    'Arthritis', 'Depression', 'Anxiety', 'None'
  ];

  const toggleCondition = (condition: string) => {
    if (condition === 'None') {
      onChange({ ...profile, existingConditions: [] });
      return;
    }
    const current = profile.existingConditions;
    if (current.includes(condition)) {
      onChange({ ...profile, existingConditions: current.filter(c => c !== condition) });
    } else {
      onChange({ ...profile, existingConditions: [...current.filter(c => c !== 'None'), condition] });
    }
  };

  return (
    <div className="glass-card p-6 space-y-6">
      <h2 className="text-xl font-semibold gradient-text">Your Profile</h2>
      <p className="text-sm text-slate-400">
        Help us personalize QALY estimates to your situation
      </p>

      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-sm text-slate-400 mb-2">Age</label>
          <input
            type="number"
            value={profile.age}
            onChange={e => onChange({ ...profile, age: parseInt(e.target.value) || 0 })}
            className="w-full"
            min={0}
            max={120}
          />
        </div>
        <div>
          <label className="block text-sm text-slate-400 mb-2">Sex</label>
          <select
            value={profile.sex}
            onChange={e => onChange({ ...profile, sex: e.target.value as UserProfile['sex'] })}
            className="w-full"
          >
            <option value="male">Male</option>
            <option value="female">Female</option>
            <option value="other">Other</option>
          </select>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-sm text-slate-400 mb-2">Weight (kg)</label>
          <input
            type="number"
            value={profile.weight}
            onChange={e => onChange({ ...profile, weight: parseFloat(e.target.value) || 0 })}
            className="w-full"
            min={0}
            max={500}
          />
        </div>
        <div>
          <label className="block text-sm text-slate-400 mb-2">Height (cm)</label>
          <input
            type="number"
            value={profile.height}
            onChange={e => onChange({ ...profile, height: parseFloat(e.target.value) || 0 })}
            className="w-full"
            min={0}
            max={300}
          />
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-sm text-slate-400 mb-2">Exercise (hours/week)</label>
          <input
            type="number"
            value={profile.exerciseHoursPerWeek}
            onChange={e => onChange({ ...profile, exerciseHoursPerWeek: parseFloat(e.target.value) || 0 })}
            className="w-full"
            min={0}
            max={40}
            step={0.5}
          />
        </div>
        <div>
          <label className="block text-sm text-slate-400 mb-2">Sleep (hours/night)</label>
          <input
            type="number"
            value={profile.sleepHoursPerNight}
            onChange={e => onChange({ ...profile, sleepHoursPerNight: parseFloat(e.target.value) || 0 })}
            className="w-full"
            min={0}
            max={24}
            step={0.5}
          />
        </div>
      </div>

      <div>
        <label className="block text-sm text-slate-400 mb-2">Diet</label>
        <select
          value={profile.diet}
          onChange={e => onChange({ ...profile, diet: e.target.value as UserProfile['diet'] })}
          className="w-full"
        >
          <option value="omnivore">Omnivore</option>
          <option value="vegetarian">Vegetarian</option>
          <option value="vegan">Vegan</option>
          <option value="pescatarian">Pescatarian</option>
          <option value="keto">Keto</option>
          <option value="other">Other</option>
        </select>
      </div>

      <div>
        <label className="flex items-center gap-3 cursor-pointer">
          <input
            type="checkbox"
            checked={profile.smoker}
            onChange={e => onChange({ ...profile, smoker: e.target.checked })}
            className="w-5 h-5 rounded"
          />
          <span className="text-slate-300">Current smoker</span>
        </label>
      </div>

      <div>
        <label className="block text-sm text-slate-400 mb-3">Existing Conditions</label>
        <div className="flex flex-wrap gap-2">
          {conditions.map(condition => (
            <button
              key={condition}
              type="button"
              onClick={() => toggleCondition(condition)}
              className={`px-3 py-1.5 text-sm rounded-full transition-all ${
                (condition === 'None' && profile.existingConditions.length === 0) ||
                profile.existingConditions.includes(condition)
                  ? 'bg-emerald-500/30 text-emerald-300 border border-emerald-500/50'
                  : 'bg-slate-700/50 text-slate-400 border border-slate-600/50 hover:border-slate-500'
              }`}
              style={{ background: undefined }}
            >
              {condition}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
