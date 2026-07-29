import { useCallback, useState } from 'react';
import {
  ActivityIndicator,
  FlatList,
  Pressable,
  RefreshControl,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';
import { useFocusEffect } from '@react-navigation/native';

import { describeError } from '@/src/api/errors';
import type { EventRead } from '@/src/api/types';
import { EventRow } from '@/src/components/EventRow';
import { useSettings } from '@/src/context/SettingsContext';
import { colors } from '@/src/theme/colors';

export default function CalendarScreen() {
  const { client } = useSettings();
  const [query, setQuery] = useState('');
  const [events, setEvents] = useState<EventRead[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(
    async (q?: string) => {
      if (!client) {
        return;
      }
      setLoading(true);
      setError(null);
      try {
        const result = await client.searchEvents({
          q: q?.trim() || undefined,
          limit: 50,
        });
        setEvents(result.items);
        setTotal(result.total);
      } catch (err) {
        setError(describeError(err));
      } finally {
        setLoading(false);
      }
    },
    [client],
  );

  useFocusEffect(
    useCallback(() => {
      void load();
    }, [load]),
  );

  if (!client) {
    return (
      <View style={styles.center}>
        <Text style={styles.missing}>Configure the host URL and API key in Settings.</Text>
      </View>
    );
  }

  return (
    <View style={styles.flex}>
      <View style={styles.searchRow}>
        <TextInput
          autoCapitalize="none"
          placeholder="Search events…"
          placeholderTextColor={colors.textDim}
          style={styles.input}
          value={query}
          onChangeText={setQuery}
          onSubmitEditing={() => void load(query)}
          returnKeyType="search"
        />
        <Pressable
          onPress={() => void load(query)}
          style={({ pressed }) => [styles.searchBtn, pressed && styles.pressed]}
        >
          <Text style={styles.searchBtnText}>Search</Text>
        </Pressable>
      </View>

      {error ? <Text style={styles.error}>{error}</Text> : null}

      <Text style={styles.count}>
        {loading && events.length === 0 ? 'Loading…' : `${total} event${total === 1 ? '' : 's'}`}
      </Text>

      <FlatList
        data={events}
        keyExtractor={(item) => item.id}
        renderItem={({ item }) => <EventRow event={item} />}
        refreshControl={
          <RefreshControl
            refreshing={loading}
            onRefresh={() => void load(query)}
            tintColor={colors.accent}
          />
        }
        ListEmptyComponent={
          loading ? (
            <ActivityIndicator color={colors.accent} style={{ marginTop: 40 }} />
          ) : (
            <Text style={styles.empty}>No events found. Create some from Chat.</Text>
          )
        }
      />
    </View>
  );
}

const styles = StyleSheet.create({
  flex: { flex: 1, backgroundColor: colors.bg },
  center: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    padding: 24,
    backgroundColor: colors.bg,
  },
  missing: {
    color: colors.textMuted,
    fontFamily: 'DMSans_400Regular',
    fontSize: 16,
    textAlign: 'center',
  },
  searchRow: {
    flexDirection: 'row',
    gap: 8,
    padding: 16,
    paddingBottom: 8,
  },
  input: {
    flex: 1,
    backgroundColor: colors.bgInput,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 12,
    paddingHorizontal: 14,
    paddingVertical: 12,
    color: colors.text,
    fontFamily: 'DMSans_400Regular',
    fontSize: 16,
  },
  searchBtn: {
    justifyContent: 'center',
    backgroundColor: colors.accent,
    borderRadius: 12,
    paddingHorizontal: 14,
  },
  searchBtnText: {
    color: colors.accentText,
    fontFamily: 'DMSans_600SemiBold',
    fontSize: 14,
  },
  pressed: { opacity: 0.85 },
  error: {
    marginHorizontal: 16,
    marginBottom: 8,
    color: colors.danger,
    fontFamily: 'DMSans_500Medium',
    fontSize: 13,
  },
  count: {
    marginHorizontal: 16,
    marginBottom: 4,
    color: colors.textDim,
    fontFamily: 'DMSans_400Regular',
    fontSize: 12,
  },
  empty: {
    marginTop: 40,
    textAlign: 'center',
    color: colors.textMuted,
    fontFamily: 'DMSans_400Regular',
    fontSize: 15,
    paddingHorizontal: 24,
  },
});
