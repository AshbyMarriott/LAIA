import { StyleSheet, Text, View } from 'react-native';

import { colors } from '@/src/theme/colors';

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant' | 'system';
  text: string;
  actionCommand?: string | null;
}

export function MessageBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === 'user';
  const isSystem = message.role === 'system';

  return (
    <View
      style={[
        styles.row,
        isUser ? styles.rowUser : styles.rowOther,
      ]}
    >
      <View
        style={[
          styles.bubble,
          isUser && styles.userBubble,
          message.role === 'assistant' && styles.assistantBubble,
          isSystem && styles.systemBubble,
        ]}
      >
        <Text style={[styles.text, isSystem && styles.systemText]}>{message.text}</Text>
        {message.actionCommand ? (
          <Text style={styles.meta}>action: {message.actionCommand}</Text>
        ) : null}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  row: {
    marginBottom: 10,
    paddingHorizontal: 16,
  },
  rowUser: {
    alignItems: 'flex-end',
  },
  rowOther: {
    alignItems: 'flex-start',
  },
  bubble: {
    maxWidth: '88%',
    borderRadius: 16,
    paddingHorizontal: 14,
    paddingVertical: 10,
  },
  userBubble: {
    backgroundColor: colors.userBubble,
    borderBottomRightRadius: 4,
  },
  assistantBubble: {
    backgroundColor: colors.assistantBubble,
    borderBottomLeftRadius: 4,
    borderWidth: 1,
    borderColor: colors.border,
  },
  systemBubble: {
    backgroundColor: 'transparent',
    borderWidth: 0,
    paddingHorizontal: 4,
  },
  text: {
    color: colors.text,
    fontFamily: 'DMSans_400Regular',
    fontSize: 16,
    lineHeight: 22,
  },
  systemText: {
    color: colors.textMuted,
    fontSize: 14,
    textAlign: 'center',
  },
  meta: {
    marginTop: 6,
    color: colors.accent,
    fontFamily: 'DMSans_500Medium',
    fontSize: 12,
  },
});
