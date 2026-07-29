import { router } from 'expo-router';
import { useState } from 'react';
import {
  ActivityIndicator,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';

import { createClient } from '@/src/api/client';
import { useSettings } from '@/src/context/SettingsContext';
import { colors } from '@/src/theme/colors';

export default function SetupScreen() {
  const { settings, save } = useSettings();
  const [baseUrl, setBaseUrl] = useState(settings?.baseUrl ?? '');
  const [apiKey, setApiKey] = useState(settings?.apiKey ?? '');
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function onTestAndSave() {
    setBusy(true);
    setError(null);
    setStatus(null);
    try {
      const client = createClient({ baseUrl, apiKey });
      const result = await client.checkConnection();
      if (!result.apiOk) {
        setError(result.error ?? 'API unreachable');
        return;
      }
      await save({ baseUrl, apiKey });
      if (!result.ollamaOk) {
        setStatus(
          'Connected to API, but Ollama looks unhealthy. You can continue; chat may fail until the host model is ready.',
        );
      } else {
        setStatus('Connected. Opening chat…');
      }
      router.replace('/(tabs)/chat');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Connection failed');
    } finally {
      setBusy(false);
    }
  }

  return (
    <KeyboardAvoidingView
      style={styles.flex}
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}
    >
      <ScrollView contentContainerStyle={styles.container} keyboardShouldPersistTaps="handled">
        <Text style={styles.brand}>LAIA</Text>
        <Text style={styles.lede}>
          Point this phone at your self-hosted assistant over Tailscale or WireGuard.
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
        <Text style={styles.hint}>
          Use the Tailscale IP or MagicDNS name of the machine running the LAIA API. The API binds to
          localhost on the host; reach it via your VPN.
        </Text>

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
        {status ? <Text style={styles.status}>{status}</Text> : null}

        <Pressable
          accessibilityRole="button"
          disabled={busy || !baseUrl.trim() || !apiKey.trim()}
          onPress={() => void onTestAndSave()}
          style={({ pressed }) => [
            styles.button,
            (busy || !baseUrl.trim() || !apiKey.trim()) && styles.buttonDisabled,
            pressed && styles.pressed,
          ]}
        >
          {busy ? (
            <ActivityIndicator color={colors.accentText} />
          ) : (
            <Text style={styles.buttonText}>Test connection & continue</Text>
          )}
        </Pressable>
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  flex: { flex: 1, backgroundColor: colors.bg },
  container: {
    padding: 24,
    paddingBottom: 48,
    gap: 8,
  },
  brand: {
    color: colors.text,
    fontFamily: 'SourceSerif4_700Bold',
    fontSize: 40,
    marginBottom: 4,
  },
  lede: {
    color: colors.textMuted,
    fontFamily: 'DMSans_400Regular',
    fontSize: 16,
    lineHeight: 24,
    marginBottom: 20,
  },
  label: {
    marginTop: 12,
    color: colors.text,
    fontFamily: 'DMSans_600SemiBold',
    fontSize: 13,
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
  hint: {
    color: colors.textDim,
    fontFamily: 'DMSans_400Regular',
    fontSize: 13,
    lineHeight: 18,
    marginTop: 6,
  },
  error: {
    marginTop: 12,
    color: colors.danger,
    fontFamily: 'DMSans_500Medium',
    fontSize: 14,
    lineHeight: 20,
  },
  status: {
    marginTop: 12,
    color: colors.success,
    fontFamily: 'DMSans_500Medium',
    fontSize: 14,
    lineHeight: 20,
  },
  button: {
    marginTop: 24,
    backgroundColor: colors.accent,
    borderRadius: 12,
    paddingVertical: 16,
    alignItems: 'center',
  },
  buttonDisabled: {
    opacity: 0.45,
  },
  buttonText: {
    color: colors.accentText,
    fontFamily: 'DMSans_600SemiBold',
    fontSize: 16,
  },
  pressed: {
    opacity: 0.85,
  },
});
