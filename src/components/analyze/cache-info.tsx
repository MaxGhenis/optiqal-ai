"use client";

import { useState, useEffect } from "react";
import { getCacheStats, clearCache, type CacheStats } from "@/lib/cache";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Database, Trash2, RefreshCw } from "lucide-react";

/**
 * Cache information and management component
 *
 * Shows:
 * - Cache size and entry count
 * - Cache age
 * - Clear cache button
 */
export function CacheInfo() {
  const [stats, setStats] = useState<CacheStats | null>(null);
  const [isClearing, setIsClearing] = useState(false);

  const loadStats = () => {
    try {
      const cacheStats = getCacheStats();
      setStats(cacheStats);
    } catch {
      setStats(null);
    }
  };

  useEffect(() => {
    loadStats();
  }, []);

  const handleClearCache = () => {
    setIsClearing(true);
    try {
      clearCache();
      loadStats();
    } finally {
      setTimeout(() => setIsClearing(false), 500);
    }
  };

  const formatBytes = (bytes: number): string => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  const formatAge = (timestamp: number | null): string => {
    if (!timestamp) return "N/A";
    const ageMs = Date.now() - timestamp;
    const ageDays = Math.floor(ageMs / (24 * 60 * 60 * 1000));
    const ageHours = Math.floor((ageMs % (24 * 60 * 60 * 1000)) / (60 * 60 * 1000));

    if (ageDays > 0) return `${ageDays}d ${ageHours}h ago`;
    if (ageHours > 0) return `${ageHours}h ago`;
    return "< 1h ago";
  };

  if (!stats) {
    return null;
  }

  return (
    <Card className="border-gray-200">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Database className="h-4 w-4 text-gray-500" />
            <CardTitle className="text-sm font-medium">Cache</CardTitle>
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant="ghost"
              size="sm"
              onClick={loadStats}
              className="h-7 w-7 p-0"
              title="Refresh stats"
            >
              <RefreshCw className="h-3.5 w-3.5" />
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={handleClearCache}
              disabled={isClearing || stats.totalEntries === 0}
              className="h-7 px-2 text-xs"
              title="Clear cache"
            >
              <Trash2 className="h-3.5 w-3.5 mr-1" />
              Clear
            </Button>
          </div>
        </div>
        <CardDescription className="text-xs">
          Cached results reduce API costs
        </CardDescription>
      </CardHeader>
      <CardContent className="pb-4">
        <div className="grid grid-cols-3 gap-4 text-sm">
          <div>
            <div className="text-xs text-gray-500">Entries</div>
            <div className="font-medium">{stats.totalEntries}</div>
          </div>
          <div>
            <div className="text-xs text-gray-500">Size</div>
            <div className="font-medium">{formatBytes(stats.totalSize)}</div>
          </div>
          <div>
            <div className="text-xs text-gray-500">Oldest</div>
            <div className="font-medium text-xs">{formatAge(stats.oldestEntry)}</div>
          </div>
        </div>
        {stats.totalEntries > 0 && (
          <div className="mt-3 text-xs text-gray-500">
            Cache expires after 7 days. Max 100 entries.
          </div>
        )}
      </CardContent>
    </Card>
  );
}
