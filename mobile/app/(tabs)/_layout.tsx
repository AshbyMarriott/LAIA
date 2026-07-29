import { Tabs } from 'expo-router';
import { StyleSheet, Text, View } from 'react-native';

import { colors } from '@/src/theme/colors';

function TabLabel({ label, focused }: { label: string; focused: boolean }) {
  return (
    <Text style={[styles.label, focused && styles.labelFocused]}>{label}</Text>
  );
}

function TabMark({ mark, color }: { mark: string; color: string | undefined }) {
  return (
    <View style={styles.iconWrap}>
      <Text style={[styles.icon, { color: color ?? colors.textDim }]}>{mark}</Text>
    </View>
  );
}

export default function TabLayout() {
  return (
    <Tabs
      screenOptions={{
        headerStyle: { backgroundColor: colors.bg },
        headerTintColor: colors.text,
        headerTitleStyle: { fontFamily: 'SourceSerif4_600SemiBold' },
        headerShadowVisible: false,
        tabBarStyle: {
          backgroundColor: colors.bgElevated,
          borderTopColor: colors.border,
        },
        tabBarActiveTintColor: colors.accent,
        tabBarInactiveTintColor: colors.textDim,
      }}
    >
      <Tabs.Screen
        name="chat"
        options={{
          title: 'Chat',
          tabBarLabel: ({ focused }) => <TabLabel label="Chat" focused={focused} />,
          tabBarIcon: ({ color }) => <TabMark mark="◎" color={String(color)} />,
        }}
      />
      <Tabs.Screen
        name="calendar"
        options={{
          title: 'Calendar',
          tabBarLabel: ({ focused }) => <TabLabel label="Calendar" focused={focused} />,
          tabBarIcon: ({ color }) => <TabMark mark="▦" color={String(color)} />,
        }}
      />
      <Tabs.Screen
        name="settings"
        options={{
          title: 'Settings',
          tabBarLabel: ({ focused }) => <TabLabel label="Settings" focused={focused} />,
          tabBarIcon: ({ color }) => <TabMark mark="⚙" color={String(color)} />,
        }}
      />
    </Tabs>
  );
}

const styles = StyleSheet.create({
  label: {
    fontFamily: 'DMSans_500Medium',
    fontSize: 11,
    color: colors.textDim,
  },
  labelFocused: {
    color: colors.accent,
  },
  iconWrap: {
    alignItems: 'center',
    justifyContent: 'center',
  },
  icon: {
    fontSize: 18,
    lineHeight: 20,
  },
});
