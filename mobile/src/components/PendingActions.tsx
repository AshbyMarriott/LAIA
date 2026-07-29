import { ActivityIndicator, Pressable, StyleSheet, Text, View } from 'react-native';

import type { PendingState } from '@/src/api/types';
import { colors } from '@/src/theme/colors';

interface PendingActionsProps {
  pending: PendingState;
  disabled?: boolean;
  onConfirm: (yes: boolean) => void;
  onSelectOption: (index: number, label: string) => void;
}

export function PendingActions({
  pending,
  disabled,
  onConfirm,
  onSelectOption,
}: PendingActionsProps) {
  if (pending.type === 'confirmation') {
    return (
      <View style={styles.panel}>
        <Text style={styles.title}>Confirm</Text>
        <Text style={styles.body}>Reply yes or no to continue.</Text>
        <View style={styles.row}>
          <Pressable
            accessibilityRole="button"
            disabled={disabled}
            onPress={() => onConfirm(true)}
            style={({ pressed }) => [
              styles.button,
              styles.primary,
              (pressed || disabled) && styles.pressed,
            ]}
          >
            <Text style={styles.primaryText}>Yes</Text>
          </Pressable>
          <Pressable
            accessibilityRole="button"
            disabled={disabled}
            onPress={() => onConfirm(false)}
            style={({ pressed }) => [
              styles.button,
              styles.secondary,
              (pressed || disabled) && styles.pressed,
            ]}
          >
            <Text style={styles.secondaryText}>No</Text>
          </Pressable>
        </View>
      </View>
    );
  }

  if (pending.type === 'disambiguation' && pending.options?.length) {
    return (
      <View style={styles.panel}>
        <Text style={styles.title}>Choose an event</Text>
        {pending.options.map((opt, index) => (
          <Pressable
            key={opt.id}
            accessibilityRole="button"
            disabled={disabled}
            onPress={() => onSelectOption(index + 1, opt.label)}
            style={({ pressed }) => [
              styles.option,
              (pressed || disabled) && styles.pressed,
            ]}
          >
            <Text style={styles.optionIndex}>{index + 1}</Text>
            <Text style={styles.optionLabel}>{opt.label}</Text>
          </Pressable>
        ))}
      </View>
    );
  }

  if (pending.type === 'slot_clarification') {
    return (
      <View style={styles.panel}>
        <Text style={styles.title}>Needs a detail</Text>
        <Text style={styles.body}>
          {pending.clarification_question ?? 'Answer in the message box below.'}
        </Text>
      </View>
    );
  }

  return null;
}

export function ThinkingIndicator() {
  return (
    <View style={styles.thinking}>
      <ActivityIndicator color={colors.accent} size="small" />
      <Text style={styles.thinkingText}>LAIA is thinking… this can take a few seconds</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  panel: {
    marginHorizontal: 16,
    marginBottom: 10,
    padding: 14,
    borderRadius: 14,
    backgroundColor: colors.pendingBg,
    borderWidth: 1,
    borderColor: colors.pendingBorder,
    gap: 10,
  },
  title: {
    color: colors.text,
    fontFamily: 'SourceSerif4_600SemiBold',
    fontSize: 18,
  },
  body: {
    color: colors.textMuted,
    fontFamily: 'DMSans_400Regular',
    fontSize: 14,
    lineHeight: 20,
  },
  row: {
    flexDirection: 'row',
    gap: 10,
  },
  button: {
    flex: 1,
    alignItems: 'center',
    paddingVertical: 12,
    borderRadius: 10,
  },
  primary: {
    backgroundColor: colors.accent,
  },
  secondary: {
    backgroundColor: colors.bgInput,
    borderWidth: 1,
    borderColor: colors.border,
  },
  primaryText: {
    color: colors.accentText,
    fontFamily: 'DMSans_600SemiBold',
    fontSize: 15,
  },
  secondaryText: {
    color: colors.text,
    fontFamily: 'DMSans_600SemiBold',
    fontSize: 15,
  },
  option: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    paddingVertical: 12,
    paddingHorizontal: 12,
    borderRadius: 10,
    backgroundColor: colors.bgInput,
    borderWidth: 1,
    borderColor: colors.border,
  },
  optionIndex: {
    width: 24,
    height: 24,
    borderRadius: 12,
    textAlign: 'center',
    textAlignVertical: 'center',
    overflow: 'hidden',
    color: colors.accentText,
    backgroundColor: colors.accent,
    fontFamily: 'DMSans_600SemiBold',
    fontSize: 13,
    lineHeight: 24,
  },
  optionLabel: {
    flex: 1,
    color: colors.text,
    fontFamily: 'DMSans_400Regular',
    fontSize: 15,
    lineHeight: 20,
  },
  pressed: {
    opacity: 0.7,
  },
  thinking: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    marginHorizontal: 16,
    marginBottom: 8,
    paddingVertical: 8,
  },
  thinkingText: {
    flex: 1,
    color: colors.textMuted,
    fontFamily: 'DMSans_400Regular',
    fontSize: 13,
  },
});
