import { useCallback, useEffect, useRef, useState } from 'react';
import {
  FlatList,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';

import { describeError } from '@/src/api/errors';
import type { PendingState } from '@/src/api/types';
import { MessageBubble, type ChatMessage } from '@/src/components/MessageBubble';
import { PendingActions, ThinkingIndicator } from '@/src/components/PendingActions';
import { useSettings } from '@/src/context/SettingsContext';
import { colors } from '@/src/theme/colors';

let messageSeq = 0;
function nextId(prefix: string): string {
  messageSeq += 1;
  return `${prefix}-${Date.now()}-${messageSeq}`;
}

export default function ChatScreen() {
  const { client } = useSettings();
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: 'welcome',
      role: 'assistant',
      text: 'Ask me to create, find, update, or delete a calendar event.',
    },
  ]);
  const [draft, setDraft] = useState('');
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [pending, setPending] = useState<PendingState | null>(null);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const listRef = useRef<FlatList<ChatMessage>>(null);

  useEffect(() => {
    return () => {
      abortRef.current?.abort();
    };
  }, []);

  const sendMessage = useCallback(
    async (text: string) => {
      const trimmed = text.trim();
      if (!trimmed || !client || sending) {
        return;
      }

      setError(null);
      setDraft('');
      setMessages((prev) => [
        ...prev,
        { id: nextId('user'), role: 'user', text: trimmed },
      ]);
      setSending(true);

      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;

      try {
        const response = await client.chat(
          {
            message: trimmed,
            conversation_id: conversationId,
          },
          controller.signal,
        );
        setConversationId(response.conversation_id);
        setPending(response.pending);
        setMessages((prev) => [
          ...prev,
          {
            id: nextId('assistant'),
            role: 'assistant',
            text: response.reply,
            actionCommand: response.action?.command ?? null,
          },
        ]);
      } catch (err) {
        if (err instanceof Error && err.name === 'AbortError') {
          setMessages((prev) => [
            ...prev,
            { id: nextId('system'), role: 'system', text: 'Request cancelled.' },
          ]);
        } else {
          const message = describeError(err);
          setError(message);
          setMessages((prev) => [
            ...prev,
            { id: nextId('system'), role: 'system', text: message },
          ]);
        }
      } finally {
        setSending(false);
        abortRef.current = null;
      }
    },
    [client, conversationId, sending],
  );

  function onCancel() {
    abortRef.current?.abort();
  }

  function onNewConversation() {
    abortRef.current?.abort();
    setConversationId(null);
    setPending(null);
    setError(null);
    setSending(false);
    setMessages([
      {
        id: nextId('assistant'),
        role: 'assistant',
        text: 'New conversation. What should I do on your calendar?',
      },
    ]);
  }

  if (!client) {
    return (
      <View style={styles.center}>
        <Text style={styles.missing}>Configure the host URL and API key in Settings.</Text>
      </View>
    );
  }

  return (
    <KeyboardAvoidingView
      style={styles.flex}
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}
      keyboardVerticalOffset={88}
    >
      <View style={styles.toolbar}>
        <Pressable onPress={onNewConversation} style={styles.toolbarBtn}>
          <Text style={styles.toolbarText}>New chat</Text>
        </Pressable>
        {sending ? (
          <Pressable onPress={onCancel} style={styles.toolbarBtn}>
            <Text style={[styles.toolbarText, styles.cancelText]}>Cancel</Text>
          </Pressable>
        ) : null}
      </View>

      <FlatList
        ref={listRef}
        data={messages}
        keyExtractor={(item) => item.id}
        renderItem={({ item }) => <MessageBubble message={item} />}
        contentContainerStyle={styles.list}
        onContentSizeChange={() => listRef.current?.scrollToEnd({ animated: true })}
      />

      {sending ? <ThinkingIndicator /> : null}

      {pending && !sending ? (
        <PendingActions
          pending={pending}
          disabled={sending}
          onConfirm={(yes) => void sendMessage(yes ? 'yes' : 'no')}
          onSelectOption={(index) => void sendMessage(String(index))}
        />
      ) : null}

      {error && !sending ? <Text style={styles.errorBanner}>{error}</Text> : null}

      <View style={styles.composer}>
        <TextInput
          editable={!sending}
          multiline
          placeholder={
            pending?.type === 'slot_clarification'
              ? 'Type the missing detail…'
              : 'Message LAIA…'
          }
          placeholderTextColor={colors.textDim}
          style={styles.input}
          value={draft}
          onChangeText={setDraft}
          onSubmitEditing={() => void sendMessage(draft)}
        />
        <Pressable
          accessibilityRole="button"
          disabled={sending || !draft.trim()}
          onPress={() => void sendMessage(draft)}
          style={({ pressed }) => [
            styles.send,
            (sending || !draft.trim()) && styles.sendDisabled,
            pressed && styles.pressed,
          ]}
        >
          <Text style={styles.sendText}>Send</Text>
        </Pressable>
      </View>
    </KeyboardAvoidingView>
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
  toolbar: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingVertical: 8,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: colors.border,
  },
  toolbarBtn: {
    paddingVertical: 6,
    paddingHorizontal: 4,
  },
  toolbarText: {
    color: colors.accent,
    fontFamily: 'DMSans_500Medium',
    fontSize: 14,
  },
  cancelText: {
    color: colors.warning,
  },
  list: {
    paddingVertical: 16,
    flexGrow: 1,
  },
  errorBanner: {
    marginHorizontal: 16,
    marginBottom: 8,
    color: colors.danger,
    fontFamily: 'DMSans_500Medium',
    fontSize: 13,
  },
  composer: {
    flexDirection: 'row',
    alignItems: 'flex-end',
    gap: 10,
    paddingHorizontal: 12,
    paddingVertical: 12,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: colors.border,
    backgroundColor: colors.bgElevated,
  },
  input: {
    flex: 1,
    maxHeight: 120,
    minHeight: 44,
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
  send: {
    backgroundColor: colors.accent,
    borderRadius: 12,
    paddingHorizontal: 16,
    paddingVertical: 12,
  },
  sendDisabled: {
    opacity: 0.4,
  },
  sendText: {
    color: colors.accentText,
    fontFamily: 'DMSans_600SemiBold',
    fontSize: 15,
  },
  pressed: {
    opacity: 0.85,
  },
});
