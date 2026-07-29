import { Platform } from 'react-native';
import * as SecureStore from 'expo-secure-store';

const KEYS = {
  baseUrl: 'laia.baseUrl',
  apiKey: 'laia.apiKey',
} as const;

export interface LaiaSettings {
  baseUrl: string;
  apiKey: string;
}

async function getItem(key: string): Promise<string | null> {
  if (Platform.OS === 'web') {
    try {
      return globalThis.localStorage?.getItem(key) ?? null;
    } catch {
      return null;
    }
  }
  return SecureStore.getItemAsync(key);
}

async function setItem(key: string, value: string): Promise<void> {
  if (Platform.OS === 'web') {
    globalThis.localStorage?.setItem(key, value);
    return;
  }
  await SecureStore.setItemAsync(key, value);
}

async function deleteItem(key: string): Promise<void> {
  if (Platform.OS === 'web') {
    globalThis.localStorage?.removeItem(key);
    return;
  }
  await SecureStore.deleteItemAsync(key);
}

export async function loadSettings(): Promise<LaiaSettings | null> {
  const [baseUrl, apiKey] = await Promise.all([
    getItem(KEYS.baseUrl),
    getItem(KEYS.apiKey),
  ]);
  if (!baseUrl?.trim() || !apiKey?.trim()) {
    return null;
  }
  return { baseUrl: baseUrl.trim(), apiKey: apiKey.trim() };
}

export async function saveSettings(settings: LaiaSettings): Promise<void> {
  await Promise.all([
    setItem(KEYS.baseUrl, settings.baseUrl.trim().replace(/\/+$/, '')),
    setItem(KEYS.apiKey, settings.apiKey.trim()),
  ]);
}

export async function clearSettings(): Promise<void> {
  await Promise.all([deleteItem(KEYS.baseUrl), deleteItem(KEYS.apiKey)]);
}

export function settingsConfigured(settings: LaiaSettings | null): boolean {
  return Boolean(settings?.baseUrl?.trim() && settings?.apiKey?.trim());
}
