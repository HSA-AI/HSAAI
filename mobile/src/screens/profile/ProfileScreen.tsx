/**
 * HSAAI Mobile — Profile Screen (Phase 11)
 * =========================================
 * User profile, preferences, and account management.
 */
import React from 'react';
import {
  View, Text, TouchableOpacity, StyleSheet, Image,
  Switch, Alert,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useTranslation } from 'react-i18next';
import { useAuthStore } from '../../store/authStore';

const COLORS = {
  primary: '#2a6887', danger: '#ac574f',
  bg: '#0a0a0a', surface: '#1a1a1a',
  text: '#ffffff', textMuted: '#999999',
};

export default function ProfileScreen({ navigation }: any) {
  const { t, i18n } = useTranslation();
  const { user, logout } = useAuthStore();

  const [notificationsEnabled, setNotificationsEnabled] = React.useState(true);
  const [biometricEnabled, setBiometricEnabled] = React.useState(false);

  const handleLogout = () => {
    Alert.alert(
      t('profile.logoutTitle'),
      t('profile.logoutConfirm'),
      [
        { text: t('common.cancel'), style: 'cancel' },
        { text: t('common.logout'), style: 'destructive', onPress: () => logout() },
      ]
    );
  };

  const menuItems = [
    { icon: 'person-circle', label: t('profile.editProfile'), screen: 'EditProfile' },
    { icon: 'shield-checkmark', label: t('profile.security'), screen: 'Security' },
    { icon: 'card', label: t('profile.billing'), screen: 'Billing' },
    { icon: 'cube', label: t('profile.apiKeys'), screen: 'ApiKeys' },
    { icon: 'help-circle', label: t('profile.help'), screen: 'Help' },
    { icon: 'information-circle', label: t('profile.about'), screen: 'About' },
  ];

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <View style={styles.avatarContainer}>
          <Ionicons name="person" size={48} color={COLORS.primary} />
        </View>
        <View style={styles.userInfo}>
          <Text style={styles.userName}>{user?.name || t('profile.guest')}</Text>
          <Text style={styles.userEmail}>{user?.email || ''}</Text>
          <View style={styles.roleBadge}>
            <Text style={styles.roleText}>{user?.role || 'employee'}</Text>
          </View>
        </View>
      </View>

      <View style={styles.statsRow}>
        <View style={styles.statItem}>
          <Text style={styles.statValue}>{user?.stats?.tasksCompleted || 0}</Text>
          <Text style={styles.statLabel}>{t('profile.tasksCompleted')}</Text>
        </View>
        <View style={styles.statItem}>
          <Text style={styles.statValue}>{user?.stats?.agentsRun || 0}</Text>
          <Text style={styles.statLabel}>{t('profile.agentsRun')}</Text>
        </View>
        <View style={styles.statItem}>
          <Text style={styles.statValue}>{user?.stats?.documents || 0}</Text>
          <Text style={styles.statLabel}>{t('profile.documents')}</Text>
        </View>
      </View>

      <View style={styles.section}>
        <Text style={styles.sectionTitle}>{t('profile.preferences')}</Text>
        <View style={styles.settingRow}>
          <View style={styles.settingLeft}>
            <Ionicons name="notifications" size={20} color={COLORS.textMuted} />
            <Text style={styles.settingLabel}>{t('profile.notifications')}</Text>
          </View>
          <Switch
            value={notificationsEnabled}
            onValueChange={setNotificationsEnabled}
            trackColor={{ false: COLORS.surface, true: COLORS.primary }}
          />
        </View>
        <View style={styles.settingRow}>
          <View style={styles.settingLeft}>
            <Ionicons name="finger-print" size={20} color={COLORS.textMuted} />
            <Text style={styles.settingLabel}>{t('profile.biometric')}</Text>
          </View>
          <Switch
            value={biometricEnabled}
            onValueChange={setBiometricEnabled}
            trackColor={{ false: COLORS.surface, true: COLORS.primary }}
          />
        </View>
        <TouchableOpacity
          style={styles.settingRow}
          onPress={() => i18n.changeLanguage(i18n.language === 'ar' ? 'en' : 'ar')}
        >
          <View style={styles.settingLeft}>
            <Ionicons name="language" size={20} color={COLORS.textMuted} />
            <Text style={styles.settingLabel}>{t('profile.language')}</Text>
          </View>
          <Text style={styles.settingValue}>
            {i18n.language === 'ar' ? 'العربية' : 'English'}
          </Text>
        </TouchableOpacity>
      </View>

      <View style={styles.section}>
        <Text style={styles.sectionTitle}>{t('profile.account')}</Text>
        {menuItems.map((item, idx) => (
          <TouchableOpacity
            key={idx}
            style={styles.menuItem}
            onPress={() => navigation.navigate(item.screen)}
          >
            <View style={styles.menuLeft}>
              <Ionicons name={item.icon as any} size={20} color={COLORS.primary} />
              <Text style={styles.menuLabel}>{item.label}</Text>
            </View>
            <Ionicons name="chevron-forward" size={20} color={COLORS.textMuted} />
          </TouchableOpacity>
        ))}
      </View>

      <TouchableOpacity style={styles.logoutButton} onPress={handleLogout}>
        <Ionicons name="log-out" size={20} color="white" />
        <Text style={styles.logoutText}>{t('common.logout')}</Text>
      </TouchableOpacity>

      <Text style={styles.version}>HSAAI Mobile v6.1.0</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: COLORS.bg },
  header: {
    flexDirection: 'row', alignItems: 'center', padding: 20,
    backgroundColor: COLORS.surface, marginBottom: 12,
  },
  avatarContainer: {
    width: 80, height: 80, borderRadius: 40, backgroundColor: COLORS.bg,
    justifyContent: 'center', alignItems: 'center', marginRight: 16,
  },
  userInfo: { flex: 1 },
  userName: { color: COLORS.text, fontSize: 20, fontWeight: 'bold' },
  userEmail: { color: COLORS.textMuted, fontSize: 14, marginTop: 4 },
  roleBadge: {
    backgroundColor: COLORS.primary, paddingHorizontal: 8, paddingVertical: 2,
    borderRadius: 4, alignSelf: 'flex-start', marginTop: 8,
  },
  roleText: { color: 'white', fontSize: 10, textTransform: 'uppercase' },
  statsRow: {
    flexDirection: 'row', backgroundColor: COLORS.surface, marginBottom: 12, padding: 16,
  },
  statItem: { flex: 1, alignItems: 'center' },
  statValue: { color: COLORS.text, fontSize: 24, fontWeight: 'bold' },
  statLabel: { color: COLORS.textMuted, fontSize: 10, marginTop: 4 },
  section: { backgroundColor: COLORS.surface, marginBottom: 12 },
  sectionTitle: {
    color: COLORS.textMuted, fontSize: 12, padding: 16,
    textTransform: 'uppercase',
  },
  settingRow: {
    flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center',
    padding: 16, borderTopWidth: 1, borderTopColor: COLORS.bg,
  },
  settingLeft: { flexDirection: 'row', alignItems: 'center' },
  settingLabel: { color: COLORS.text, marginLeft: 12, fontSize: 14 },
  settingValue: { color: COLORS.textMuted, fontSize: 14 },
  menuItem: {
    flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center',
    padding: 16, borderTopWidth: 1, borderTopColor: COLORS.bg,
  },
  menuLeft: { flexDirection: 'row', alignItems: 'center' },
  menuLabel: { color: COLORS.text, marginLeft: 12, fontSize: 14 },
  logoutButton: {
    flexDirection: 'row', justifyContent: 'center', alignItems: 'center',
    backgroundColor: COLORS.danger, marginHorizontal: 20, marginBottom: 12,
    padding: 16, borderRadius: 12,
  },
  logoutText: { color: 'white', marginLeft: 8, fontSize: 16, fontWeight: 'bold' },
  version: { color: COLORS.textMuted, textAlign: 'center', fontSize: 10, marginBottom: 20 },
});
