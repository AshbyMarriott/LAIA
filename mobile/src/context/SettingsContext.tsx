import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from 'react';

import { createClient, LaiaClient } from '@/src/api/client';
import {
  clearSettings,
  loadSettings,
  saveSettings,
  settingsConfigured,
  type LaiaSettings,
} from '@/src/storage/settings';

interface SettingsContextValue {
  ready: boolean;
  settings: LaiaSettings | null;
  configured: boolean;
  client: LaiaClient | null;
  save: (next: LaiaSettings) => Promise<void>;
  clear: () => Promise<void>;
  refresh: () => Promise<void>;
}

const SettingsContext = createContext<SettingsContextValue | null>(null);

export function SettingsProvider({ children }: { children: React.ReactNode }) {
  const [ready, setReady] = useState(false);
  const [settings, setSettings] = useState<LaiaSettings | null>(null);

  const refresh = useCallback(async () => {
    const loaded = await loadSettings();
    setSettings(loaded);
    setReady(true);
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const save = useCallback(async (next: LaiaSettings) => {
    await saveSettings(next);
    setSettings({
      baseUrl: next.baseUrl.trim().replace(/\/+$/, ''),
      apiKey: next.apiKey.trim(),
    });
  }, []);

  const clear = useCallback(async () => {
    await clearSettings();
    setSettings(null);
  }, []);

  const client = useMemo(() => {
    if (!settingsConfigured(settings) || !settings) {
      return null;
    }
    return createClient(settings);
  }, [settings]);

  const value = useMemo(
    () => ({
      ready,
      settings,
      configured: settingsConfigured(settings),
      client,
      save,
      clear,
      refresh,
    }),
    [ready, settings, client, save, clear, refresh],
  );

  return (
    <SettingsContext.Provider value={value}>{children}</SettingsContext.Provider>
  );
}

export function useSettings(): SettingsContextValue {
  const ctx = useContext(SettingsContext);
  if (!ctx) {
    throw new Error('useSettings must be used within SettingsProvider');
  }
  return ctx;
}
