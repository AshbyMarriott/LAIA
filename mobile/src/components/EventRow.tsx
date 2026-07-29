import { StyleSheet, Text, View } from 'react-native';

import type { EventRead } from '@/src/api/types';
import { colors } from '@/src/theme/colors';

function formatWhen(event: EventRead): string {
  const start = new Date(event.start_at);
  const end = new Date(event.end_at);

  if (event.all_day) {
    return `${start.toLocaleDateString(undefined, {
      weekday: 'short',
      month: 'short',
      day: 'numeric',
      timeZone: event.timezone,
    })} · all day`;
  }

  const date = start.toLocaleDateString(undefined, {
    weekday: 'short',
    month: 'short',
    day: 'numeric',
    timeZone: event.timezone,
  });
  const startTime = start.toLocaleTimeString(undefined, {
    hour: 'numeric',
    minute: '2-digit',
    timeZone: event.timezone,
  });
  const endTime = end.toLocaleTimeString(undefined, {
    hour: 'numeric',
    minute: '2-digit',
    timeZone: event.timezone,
  });
  return `${date} · ${startTime} – ${endTime}`;
}

export function EventRow({ event }: { event: EventRead }) {
  return (
    <View style={styles.row}>
      <Text style={styles.title}>{event.title}</Text>
      <Text style={styles.when}>{formatWhen(event)}</Text>
      {event.location ? <Text style={styles.meta}>{event.location}</Text> : null}
      {event.description ? (
        <Text style={styles.meta} numberOfLines={2}>
          {event.description}
        </Text>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  row: {
    paddingVertical: 14,
    paddingHorizontal: 16,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: colors.border,
    gap: 4,
  },
  title: {
    color: colors.text,
    fontFamily: 'SourceSerif4_600SemiBold',
    fontSize: 17,
  },
  when: {
    color: colors.accent,
    fontFamily: 'DMSans_500Medium',
    fontSize: 13,
  },
  meta: {
    color: colors.textMuted,
    fontFamily: 'DMSans_400Regular',
    fontSize: 13,
    lineHeight: 18,
  },
});
