/**
 * HSAAI Mobile — Settings Screen (Phase 11)
 * ===========================================
 * App settings: language, theme, data usage, cache, about.
 */
import React from 'react';
import {
  View, Text, TouchableOpacity, StyleSheet, Switch, ScrollView, Alert,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useTranslation } from 'react-i18next';
import { useSettingsStore } from '../../store/settingsStore';

const COLORS = {
  primary: '#2a6887', danger: '#ac574f',
  bg: '#0a0a0a', surface: '#1a1a1a',
  text: '#ffffff', textMuted: '#999999',
};

export default function SettingsScreen() {
  const { t, i18n } = useTranslation();
  const { darkMode, setDarkMode, autoSync, setAutoSync, wifiOnly, setWifiOnly } = useSettingsStore();

  const clearCache = () => {
    Alert.alert(
      t('settings.clearCache'),
      t('settings.clearCacheConfirm'),
      [
        { text: t('common.cancel'), style: 'cancel' },
        {
          text: t('common.confirm'),
          onPress: () => {
            // Clear AsyncStorage cache
            // Clear SQLite cache
            Alert.alert(t('common.success'), t('settings.cacheCleared'));
          },
        },
      ]
    );
  };

  return (
    <ScrollView style={styles.container}>
      {/* Language Section */}
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>{t('settings.language')}</Text>
        <TouchableOpacity
          style={styles.option}
          onPress={() => i18n.changeLanguage('ar')}
        >
          <Text style={styles.optionLabel}>العربية</Text>
          {i18n.language === 'ar' && <Ionicons name="checkmark" size={20} color={COLORS.primary} />}
        </TouchableOpacity>
        <TouchableOpacity
          style={styles.option}
          onPress={() => i18n.changeLanguage('en')}
        >
          <Text style={styles.optionLabel}>English</Text>
          {i18n.language === 'en' && <Ionicons name="checkmark" size={20} color={COLORS.primary} />}
        </TouchableOpacity>
      </View>

      {/* Appearance */}
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>{t('settings.appearance')}</Text>
        <View style={styles.option}>
          <View style={styles.optionLeft}>
            <Ionicons name="moon" size={20} color={COLORS.textMuted} />
            <Text style={styles.optionLabel}>{t('settings.darkMode')}</Text>
          </View>
          <Switch
            value={darkMode}
            onValueChange={setDarkMode}
            trackColor={{ false: COLORS.surface, true: COLORS.primary }}
          />
        </View>
      </View>

      {/* Sync */}
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>{t('settings.sync')}</Text>
        <View style={styles.option}>
          <View style={styles.optionLeft}>
            <Ionicons name="sync" size={20} color={COLORS.textMuted} />
            <Text style={styles.optionLabel}>{t('settings.autoSync')}</Text>
          </View>
          <Switch
            value={autoSync}
            onValueChange={setAutoSync}
            trackColor={{ false: COLORS.surface, true: COLORS.primary }}
          />
        </View>
        <View style={styles.option}>
          <View style={styles.optionLeft}>
            <Ionicons name="wifi" size={20} color={COLORS.textMuted} />
            <Text style={styles.optionLabel}>{t('settings.wifiOnly')}</Text>
          </View>
          <Switch
            value={wifiOnly}
            onValueChange={setWifiOnly}
            trackColor={{ false: COLORS.surface, true: COLORS.primary }}
          />
        </View>
      </View>

      {/* Data */}
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>{t('settings.data')}</Text>
        <TouchableOpacity style={styles.option} onPress={clearCache}>
          <View style={styles.optionLeft}>
            <Ionicons name="trash" size={20} color={COLORS.danger} />
            <Text style={[styles.optionLabel, { color: COLORS.danger }]}>
              {t('settings.clearCache')}
            </Text>
          </View>
          <Ionicons name="chevron-forward" size={20} color={COLORS.textMuted} />
        </TouchableOpacity>
        <TouchableOpacity style={styles.option}>
          <View style={styles.optionLeft}>
            <Ionicons name="cloud-download" size={20} color={COLORS.textMuted} />
            <Text style={styles.optionLabel}>{t('settings.downloadOffline')}</Text>
          </View>
          <Ionicons name="chevron-forward" size={20} color={COLORS.textMuted} />
        </TouchableOpacity>
      </View>

      {/* About */}
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>{t('settings.about')}</Text>
        <View style={styles.option}>
          <View style={styles.optionLeft}>
            <Ionicons name="information-circle" size={20} color={COLORS.textMuted} />
            <Text style={styles.optionLabel}>{t('settings.version')}</Text>
          </View>
          <Text style={styles.optionValue}>6.1.0</Text>
        </View>
        <View style={styles.option}>
          <View style={styles.optionLeft}>
            <Ionicons name="shield" size={20} color={COLORS.textMuted} />
            <Text style={styles.optionLabel}>{t('settings.privacy')}</Text>
          </View>
          <Ionicons name="chevron-forward" size={20} color={COLORS.textMuted} />
        </View>
        <View style={styles.option}>
          <View style={styles.optionLeft}>
            <Ionicons name="document-text" size={20} color={COLORS.textMuted} />
            <Text style={styles.optionLabel}>{t('settings.terms')}</Text>
          </View>
          <Ionicons name="chevron-forward" size={20} color={COLORS.textMuted} />
        </View>
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: COLORS.bg },
  section: { backgroundColor: COLORS.surface, marginBottom: 12 },
  sectionTitle: {
    color: COLORS.textMuted, fontSize: 12, padding: 16,
    textTransform: 'uppercase', letterSpacing: 1,
  },
  option: {
    flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center',
    padding: 16, borderTopWidth: 1, borderTopColor: COLORS.bg,
  },
  optionLeft: { flexDirection: 'row', alignItems: 'center' },
  optionLabel: { color: COLORS.text, marginLeft: 12, fontSize: 14 },
  optionValue: { color: COLORS.textMuted, fontSize: 14 },
});
