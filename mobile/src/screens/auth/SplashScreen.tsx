import React, { useEffect } from 'react';
import { View, Text, StyleSheet, ActivityIndicator } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useAuthStore } from '@store/authStore';
import { colors } from '@theme/colors';
import { typography } from '@theme/typography';

export function SplashScreen() {
  const { initialize, isAuthenticated } = useAuthStore();

  useEffect(() => {
    initialize();
  }, []);

  return (
    <SafeAreaView style={styles.container} edges={['top', 'bottom']}>
      <View style={styles.content}>
        <View style={styles.logoCircle}>
          <Text style={styles.logoText}>HSAAI</Text>
        </View>
        <Text style={styles.title}>Hayel Saeed Anam</Text>
        <Text style={styles.subtitle}>Artificial Intelligence</Text>
        <ActivityIndicator size="large" color={colors.hsaYellow} style={styles.loader} />
        <Text style={styles.loadingText}>جارٍ التحميل...</Text>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.hsaBlack,
  },
  content: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
  },
  logoCircle: {
    width: 120,
    height: 120,
    borderRadius: 60,
    backgroundColor: colors.hsaYellow,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 24,
  },
  logoText: {
    fontSize: 24,
    fontWeight: '900',
    color: colors.hsaBlack,
  },
  title: {
    ...typography.h2,
    color: colors.textWhite,
    fontWeight: '700',
  },
  subtitle: {
    ...typography.body,
    color: colors.hsaYellow,
    marginTop: 4,
    letterSpacing: 2,
  },
  loader: {
    marginTop: 32,
  },
  loadingText: {
    ...typography.caption,
    color: colors.textLight,
    marginTop: 12,
  },
});
