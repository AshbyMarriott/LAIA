import { router } from 'expo-router';
import { useState } from 'react';
import {
  ActivityIndicator,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';

import { createClient } from '@/src/api/client';
import { describeError } from '@/src/api/errors';
import { useSettings } from '@/src/context/SettingsContext';
import { colors } from '@/src/theme/colors';

export default function SettingsScreen() {
  const { settings, save, clear } = useSettings();
  const [baseUrl, setBaseUrl] = useState(settings?.baseUrl ?? '');
  const [apiKey, setApiKey] = useState(settings?.apiKey ?? '');
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function onSave() {
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      const client = createClient({ baseUrl, apiKey });
      const result = await client.checkConnection();
      if (!result.apiOk) {
        setError(result.error ?? 'API unreachable');
        return;
      }
      await save({ baseUrl, apiKey });
      setMessage(
        result.ollamaOk
          ? 'Saved. API and Ollama look healthy.'
          : 'Saved. API reachable; Ollama check failed — chat may not work yet.',
      );
    } catch (err) {
      setError(describeError(err));
    } finally {
      setBusy(false);
    }
  }

  async function onClear() {
    await clear();
    setBaseUrl('');
    setApiKey('');
    setMessage(null);
    setError(null);
    router.replace('/setup');
  }

  return (
    <ScrollView contentContainerStyle={styles.container} keyboardShouldPersistTaps="handled">
      <Text style={styles.section}>Connection</Text>
      <Text style={styles.help}>
        Reach the LAIA host over Tailscale or WireGuard. Do not expose Ollama publicly.
      </Text>

      <Text style={styles.label}>Host URL</Text>
      <TextInput
        autoCapitalize="none"
        autoCorrect={false}
        keyboardType="url"
        placeholder="http://100.x.y.z:8000"
        placeholderTextColor={colors.textDim}
        style={styles.input}
        value={baseUrl}
        onChangeText={setBaseUrl}
      />

      <Text style={styles.label}>API key</Text>
      <TextInput
        autoCapitalize="none"
        autoCorrect={false}
        placeholder="LAIA_API_KEY"
        placeholderTextColor={colors.textDim}
        secureTextEntry
        style={styles.input}
        value={apiKey}
        onChangeText={setApiKey}
      />

      {error ? <Text style={styles.error}>{error}</Text> : null}
      {message ? <Text style={styles.ok}>{message}</Text> : null}

      <Pressable
        disabled={busy || !baseUrl.trim() || !apiKey.trim()}
        onPress={() => void onSave()}
        style={({ pressed }) => [
          styles.button,
          (busy || !baseUrl.trim() || !apiKey.trim()) && styles.disabled,
          pressed && styles.pressed,
        ]}
      >
        {busy ? (
          <ActivityIndicator color={colors.accentText} />
        ) : (
          <Text style={styles.buttonText}>Test & save</Text>
        )}
      </Pressable>

      <Pressable
        onPress={() => void onClear()}
        style={({ pressed }) => [styles.dangerBtn, pressed && styles.pressed]}
      >
        <Text style={styles.dangerText}>Clear credentials</Text>
      </Pressable>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    padding: 20,
    paddingBottom: 48,
    backgroundColor: colors.bg,
    flexGrow: 1,
  },
  section: {
    color: colors.text,
    fontFamily: 'SourceSerif4_600SemiBold',
    fontSize: 22,
    marginBottom: 6,
  },
  help: {
    color: colors.textMuted,
    fontFamily: 'DMSans_400Regular',
    fontSize: 14,
    lineHeight: 20,
    marginBottom: 16,
  },
  label: {
    marginTop: 12,
    color: colors.text,
    fontFamily: 'DMSans_600SemiBold',
    fontSize: 12,
    letterSpacing: 0.4,
    textTransform: 'uppercase',
  },
  input: {
    marginTop: 6,
    backgroundColor: colors.bgInput,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 12,
    paddingHorizontal: 14,
    paddingVertical: 14,
    color: colors.text,
    fontFamily: 'DMSans_400Regular',
    fontSize: 16,
  },
  error: {
    marginTop: 12,
    color: colors.danger,
    fontFamily: 'DMSans_500Medium',
    fontSize: 14,
  },
  ok: {
    marginTop: 12,
    color: colors.success,
    fontFamily: 'DMSans_500Medium',
    fontSize: 14,
  },
  button: {
    marginTop: 24,
    backgroundColor: colors.accent,
    borderRadius: 12,
    paddingVertical: 16,
    alignItems: 'center',
  },
  buttonText: {
    color: colors.accentText,
    fontFamily: 'DMSans_600SemiBold',
    fontSize: 16,
  },
  disabled: { opacity: 0.45 },
  pressed: { opacity: 0.85 },
  dangerBtn: {
    marginTop: 16,
    alignItems: 'center',
    paddingVertical: 14,
  },
  dangerText: {
    color: colors.danger,
    fontFamily: 'DMSans_500Medium',
    fontSize: 15,
  },
});
