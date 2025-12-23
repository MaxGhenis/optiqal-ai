"use client";

import { useState, useEffect, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select } from "@/components/ui/select";
import { Card, CardContent } from "@/components/ui/card";
import { StructuredResultCard } from "@/components/analyze/structured-result-card";
import { ComparisonResultCard } from "@/components/analyze/comparison-result-card";
import { BaselineCard } from "@/components/analyze/baseline-card";
import {
  analyzeStructured,
  analyzeComparison,
  isComparisonQuery,
  type StructuredAnalysisResult,
  type ComparisonAnalysisResult,
} from "@/lib/analyze-structured";
import type { UserProfile } from "@/types";
import { DEFAULT_PROFILE } from "@/types";
import {
  Activity,
  Key,
  User,
  Sparkles,
  Loader2,
  AlertCircle,
  ArrowLeft,
  ChevronDown,
  ChevronUp,
} from "lucide-react";

function AnalyzePageContent() {
  const searchParams = useSearchParams();
  const initialQuery = searchParams.get("q") || "";

  const [apiKey, setApiKey] = useState("");
  const [profile, setProfile] = useState<UserProfile>(DEFAULT_PROFILE);
  const [choice, setChoice] = useState(initialQuery);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<StructuredAnalysisResult | null>(null);
  const [comparisonResult, setComparisonResult] = useState<ComparisonAnalysisResult | null>(null);
  const [showProfile, setShowProfile] = useState(false);
  const [useImperial, setUseImperial] = useState(true); // Default to imperial for US users

  // Unit conversion helpers
  const cmToFeetInches = (cm: number) => {
    const totalInches = cm / 2.54;
    const feet = Math.floor(totalInches / 12);
    const inches = Math.round(totalInches % 12);
    return { feet, inches };
  };

  const feetInchesToCm = (feet: number, inches: number) => {
    return (feet * 12 + inches) * 2.54;
  };

  const kgToLbs = (kg: number) => Math.round(kg * 2.20462);
  const lbsToKg = (lbs: number) => lbs / 2.20462;

  // Load from localStorage
  useEffect(() => {
    const storedKey = localStorage.getItem("optiqal-api-key");
    if (storedKey) setApiKey(storedKey);

    const storedProfile = localStorage.getItem("optiqal-profile");
    if (storedProfile) {
      try {
        setProfile(JSON.parse(storedProfile));
      } catch {
        // ignore
      }
    }

    const storedUnits = localStorage.getItem("optiqal-units");
    if (storedUnits) setUseImperial(storedUnits === "imperial");
  }, []);

  // Save to localStorage
  useEffect(() => {
    if (apiKey) {
      localStorage.setItem("optiqal-api-key", apiKey);
    }
  }, [apiKey]);

  useEffect(() => {
    localStorage.setItem("optiqal-profile", JSON.stringify(profile));
  }, [profile]);

  useEffect(() => {
    localStorage.setItem("optiqal-units", useImperial ? "imperial" : "metric");
  }, [useImperial]);

  const handleAnalyze = async () => {
    if (!apiKey) {
      setError("Please enter your Anthropic API key first");
      return;
    }
    if (!choice.trim()) {
      setError("Please enter a lifestyle choice to analyze");
      return;
    }

    setIsLoading(true);
    setError(null);
    setResult(null);
    setComparisonResult(null);

    try {
      // Check if this is a comparison query (A vs B)
      if (isComparisonQuery(choice)) {
        const response = await analyzeComparison(profile, choice, apiKey);
        setComparisonResult(response);
      } else {
        const response = await analyzeStructured(profile, choice, apiKey);
        setResult(response);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "An error occurred");
    } finally {
      setIsLoading(false);
    }
  };

  const updateProfile = (key: keyof UserProfile, value: unknown) => {
    setProfile((prev) => ({ ...prev, [key]: value }));
  };

  return (
    <div className="min-h-screen mesh-gradient relative">
      {/* Noise texture */}
      <div className="noise-overlay fixed inset-0 pointer-events-none" />

      {/* Header */}
      <header className="sticky top-0 z-50 glass border-b border-border/30">
        <div className="max-w-6xl mx-auto px-6 py-4 flex items-center justify-between">
          <Link href="/" className="flex items-center gap-2.5 group">
            <div className="relative">
              <Activity className="h-6 w-6 text-primary transition-transform group-hover:scale-110" />
            </div>
            <span className="text-lg font-semibold tracking-tight">
              optiqal
            </span>
          </Link>
          <Button variant="ghost" size="sm" asChild>
            <Link href="/">
              <ArrowLeft className="h-4 w-4 mr-2" />
              Back
            </Link>
          </Button>
        </div>
      </header>

      <main className="max-w-4xl mx-auto px-6 py-12">
        <div className="space-y-8">
          {/* Title */}
          <div className="text-center space-y-2">
            <h1 className="font-serif text-3xl md:text-4xl font-medium">
              Analyze a lifestyle choice
            </h1>
            <p className="text-muted-foreground">
              Get an AI-powered QALY estimate based on the best available
              evidence
            </p>
          </div>

          {/* API Key */}
          <Card className="mesh-gradient-card border-border/50">
            <CardContent className="p-6">
              <div className="flex items-start gap-4">
                <div className="p-2 rounded-lg bg-primary/10">
                  <Key className="h-5 w-5 text-primary" />
                </div>
                <div className="flex-1 space-y-3">
                  <div>
                    <Label htmlFor="apiKey" className="text-sm font-medium">
                      Anthropic API Key
                    </Label>
                    <p className="text-xs text-muted-foreground mt-0.5">
                      Stored in your browser only — calls go directly to Anthropic, not our servers
                    </p>
                  </div>
                  <Input
                    id="apiKey"
                    type="password"
                    placeholder="sk-ant-..."
                    value={apiKey}
                    onChange={(e) => setApiKey(e.target.value)}
                    className="font-mono text-sm"
                  />
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Profile */}
          <Card className="mesh-gradient-card border-border/50">
            <CardContent className="p-6">
              <button
                type="button"
                onClick={() => setShowProfile(!showProfile)}
                className="w-full flex items-center justify-between"
              >
                <div className="flex items-center gap-4">
                  <div className="p-2 rounded-lg bg-primary/10">
                    <User className="h-5 w-5 text-primary" />
                  </div>
                  <div className="text-left">
                    <p className="text-sm font-medium">Your Profile</p>
                    <p className="text-xs text-muted-foreground">
                      {profile.age}yo {profile.sex}, {profile.diet},{" "}
                      {profile.exerciseHoursPerWeek}h exercise/week
                    </p>
                  </div>
                </div>
                {showProfile ? (
                  <ChevronUp className="h-5 w-5 text-muted-foreground" />
                ) : (
                  <ChevronDown className="h-5 w-5 text-muted-foreground" />
                )}
              </button>

              {showProfile && (
                <div className="mt-6 pt-6 border-t border-border/50 space-y-6">
                  {/* Unit Toggle */}
                  <div className="flex items-center justify-end gap-2">
                    <span className={`text-xs ${!useImperial ? 'text-primary' : 'text-muted-foreground'}`}>Metric</span>
                    <button
                      type="button"
                      onClick={() => setUseImperial(!useImperial)}
                      className={`relative w-10 h-5 rounded-full transition-colors ${useImperial ? 'bg-primary' : 'bg-muted'}`}
                    >
                      <span className={`absolute top-0.5 w-4 h-4 bg-white rounded-full transition-transform ${useImperial ? 'translate-x-5' : 'translate-x-0.5'}`} />
                    </button>
                    <span className={`text-xs ${useImperial ? 'text-primary' : 'text-muted-foreground'}`}>Imperial</span>
                  </div>

                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    <div className="space-y-2">
                      <Label htmlFor="age">Age</Label>
                      <Input
                        id="age"
                        type="number"
                        value={profile.age}
                        onChange={(e) =>
                          updateProfile("age", parseInt(e.target.value) || 0)
                        }
                      />
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="sex">Sex</Label>
                      <Select
                        id="sex"
                        value={profile.sex}
                        onChange={(e) =>
                          updateProfile(
                            "sex",
                            e.target.value as UserProfile["sex"]
                          )
                        }
                      >
                        <option value="male">Male</option>
                        <option value="female">Female</option>
                        <option value="other">Other</option>
                      </Select>
                    </div>
                    {useImperial ? (
                      <>
                        <div className="space-y-2">
                          <Label>Height</Label>
                          <div className="flex gap-2">
                            <div className="flex-1">
                              <Input
                                id="heightFeet"
                                type="number"
                                placeholder="ft"
                                value={cmToFeetInches(profile.height).feet}
                                onChange={(e) => {
                                  const feet = parseInt(e.target.value) || 0;
                                  const currentInches = cmToFeetInches(profile.height).inches;
                                  updateProfile("height", feetInchesToCm(feet, currentInches));
                                }}
                              />
                            </div>
                            <div className="flex-1">
                              <Input
                                id="heightInches"
                                type="number"
                                placeholder="in"
                                value={cmToFeetInches(profile.height).inches}
                                onChange={(e) => {
                                  const inches = parseInt(e.target.value) || 0;
                                  const currentFeet = cmToFeetInches(profile.height).feet;
                                  updateProfile("height", feetInchesToCm(currentFeet, inches));
                                }}
                              />
                            </div>
                          </div>
                        </div>
                        <div className="space-y-2">
                          <Label htmlFor="weight">Weight (lbs)</Label>
                          <Input
                            id="weight"
                            type="number"
                            value={kgToLbs(profile.weight)}
                            onChange={(e) =>
                              updateProfile(
                                "weight",
                                lbsToKg(parseInt(e.target.value) || 0)
                              )
                            }
                          />
                        </div>
                      </>
                    ) : (
                      <>
                        <div className="space-y-2">
                          <Label htmlFor="height">Height (cm)</Label>
                          <Input
                            id="height"
                            type="number"
                            value={profile.height}
                            onChange={(e) =>
                              updateProfile(
                                "height",
                                parseInt(e.target.value) || 0
                              )
                            }
                          />
                        </div>
                        <div className="space-y-2">
                          <Label htmlFor="weight">Weight (kg)</Label>
                          <Input
                            id="weight"
                            type="number"
                            value={profile.weight}
                            onChange={(e) =>
                              updateProfile(
                                "weight",
                                parseInt(e.target.value) || 0
                              )
                            }
                          />
                        </div>
                      </>
                    )}
                  </div>

                  <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
                    <div className="space-y-2">
                      <Label htmlFor="exercise">Exercise (hrs/week)</Label>
                      <Input
                        id="exercise"
                        type="number"
                        step="0.5"
                        value={profile.exerciseHoursPerWeek}
                        onChange={(e) =>
                          updateProfile(
                            "exerciseHoursPerWeek",
                            parseFloat(e.target.value) || 0
                          )
                        }
                      />
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="sleep">Sleep (hrs/night)</Label>
                      <Input
                        id="sleep"
                        type="number"
                        step="0.5"
                        value={profile.sleepHoursPerNight}
                        onChange={(e) =>
                          updateProfile(
                            "sleepHoursPerNight",
                            parseFloat(e.target.value) || 0
                          )
                        }
                      />
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="diet">Diet</Label>
                      <Select
                        id="diet"
                        value={profile.diet}
                        onChange={(e) =>
                          updateProfile(
                            "diet",
                            e.target.value as UserProfile["diet"]
                          )
                        }
                      >
                        <option value="omnivore">Omnivore</option>
                        <option value="vegetarian">Vegetarian</option>
                        <option value="vegan">Vegan</option>
                        <option value="pescatarian">Pescatarian</option>
                        <option value="keto">Keto</option>
                        <option value="other">Other</option>
                      </Select>
                    </div>
                  </div>

                  <div className="flex items-center gap-3">
                    <input
                      type="checkbox"
                      id="smoker"
                      checked={profile.smoker}
                      onChange={(e) =>
                        updateProfile("smoker", e.target.checked)
                      }
                      className="w-4 h-4 rounded border-border bg-card text-primary focus:ring-primary"
                    />
                    <Label htmlFor="smoker">Current smoker</Label>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Baseline Projection */}
          <BaselineCard profile={profile} />

          {/* Choice Input */}
          <Card className="mesh-gradient-card border-border/50 card-highlight">
            <CardContent className="p-6 space-y-4">
              <div className="space-y-2">
                <Label htmlFor="choice" className="text-sm font-medium">
                  What lifestyle change are you considering?
                </Label>
                <Textarea
                  id="choice"
                  placeholder="e.g., Add 30 minutes of walking daily, switch to a standing desk, cut out alcohol..."
                  value={choice}
                  onChange={(e) => setChoice(e.target.value)}
                  className="min-h-[100px] text-base"
                />
              </div>

              <Button
                onClick={handleAnalyze}
                disabled={isLoading || !apiKey || !choice.trim()}
                className="w-full btn-glow bg-primary text-primary-foreground hover:bg-primary/90 h-12"
              >
                {isLoading ? (
                  <>
                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                    Analyzing...
                  </>
                ) : (
                  <>
                    <Sparkles className="h-4 w-4 mr-2" />
                    Analyze QALY Impact
                  </>
                )}
              </Button>
            </CardContent>
          </Card>

          {/* Error */}
          {error && (
            <Card className="border-destructive/50 bg-destructive/5">
              <CardContent className="p-4">
                <div className="flex items-center gap-3 text-destructive">
                  <AlertCircle className="h-5 w-5 flex-shrink-0" />
                  <p className="text-sm">{error}</p>
                </div>
              </CardContent>
            </Card>
          )}

          {/* Result */}
          {result && <StructuredResultCard result={result} />}
          {comparisonResult && <ComparisonResultCard result={comparisonResult} />}

          {/* Disclaimer */}
          <p className="text-xs text-muted-foreground text-center max-w-2xl mx-auto">
            Your data is not stored on our servers — API calls go directly to Anthropic.
            Estimates are based on peer-reviewed research but involve significant uncertainty
            and should not be considered medical advice. Always consult healthcare
            professionals for medical decisions.
          </p>
        </div>
      </main>
    </div>
  );
}

export default function AnalyzePage() {
  return (
    <Suspense
      fallback={
        <div className="min-h-screen mesh-gradient flex items-center justify-center">
          <Loader2 className="h-8 w-8 animate-spin text-primary" />
        </div>
      }
    >
      <AnalyzePageContent />
    </Suspense>
  );
}
