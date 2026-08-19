import React, { useEffect } from 'react';
import { StatusBar } from 'expo-status-bar';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import { AppNavigator } from '@navigation/AppNavigator';
import { useAuthStore } from '@store/authStore';
import { useChatStore } from '@store/chatStore';
import { getDatabase } from '@db/database';
import { colors } from '@theme/colors';
import { StyleSheet } from 'react-native';
import NetInfo from '@react-native-community/netinfo';

export default function App() {
  const { initialize } = useAuthStore();
  const { loadConversations, setOffline } = useChatStore();

  useEffect(() => {
    initialize();
    getDatabase().then(() => {
      loadConversations();
    }).catch(err => {
      console.error('[App] Database init error:', err);
    });
    const unsubscribe = NetInfo.addEventListener(state => {
      setOffline(!state.isConnected);
    });
    return () => { unsubscribe(); };
  }, []);

  return (
    <SafeAreaProvider>
      <StatusBar style="light" backgroundColor={colors.hsaBlack} />
      <AppNavigator />
    </SafeAreaProvider>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
});
