import React from 'react';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import Icon from 'react-native-vector-icons/MaterialCommunityIcons';
import { DashboardScreen } from '@screens/dashboard/DashboardScreen';
import { ChatScreen } from '@screens/chat/ChatScreen';
import { AgentsScreen } from '@screens/agents/AgentsScreen';
import { KnowledgeHubScreen } from '@screens/knowledge/KnowledgeHubScreen';
import { ApprovalsScreen } from '@screens/governance/ApprovalsScreen';
import { NotificationsScreen } from '@screens/notifications/NotificationsScreen';
import { colors } from '@theme/colors';
import { typography } from '@theme/typography';

export type TabParamList = {
  Dashboard: undefined;
  Chat: undefined;
  Agents: undefined;
  Knowledge: undefined;
  Approvals: undefined;
  Notifications: undefined;
};

const Tab = createBottomTabNavigator<TabParamList>();

export function TabNavigator() {
  return (
    <Tab.Navigator
      screenOptions={{
        headerShown: false,
        tabBarActiveTintColor: colors.hsaYellow,
        tabBarInactiveTintColor: colors.textLight,
        tabBarStyle: {
          backgroundColor: colors.hsaBlack,
          borderTopColor: colors.hsaYellow,
          borderTopWidth: 2,
          height: 60,
          paddingBottom: 4,
          paddingTop: 4,
        },
        tabBarLabelStyle: {
          ...typography.caption,
          fontSize: 10,
          fontWeight: '600',
        },
      }}
    >
      <Tab.Screen
        name="Dashboard"
        component={DashboardScreen}
        options={{
          tabBarLabel: 'الرئيسية',
          tabBarIcon: ({ color, size }) => (
            <Icon name="view-dashboard" color={color} size={size} />
          ),
        }}
      />
      <Tab.Screen
        name="Chat"
        component={ChatScreen}
        options={{
          tabBarLabel: 'المساعد',
          tabBarIcon: ({ color, size }) => (
            <Icon name="chat-processing" color={color} size={size} />
          ),
        }}
      />
      <Tab.Screen
        name="Agents"
        component={AgentsScreen}
        options={{
          tabBarLabel: 'الوكلاء',
          tabBarIcon: ({ color, size }) => (
            <Icon name="robot" color={color} size={size} />
          ),
        }}
      />
      <Tab.Screen
        name="Knowledge"
        component={KnowledgeHubScreen}
        options={{
          tabBarLabel: 'المعرفة',
          tabBarIcon: ({ color, size }) => (
            <Icon name="book-open-variant" color={color} size={size} />
          ),
        }}
      />
      <Tab.Screen
        name="Approvals"
        component={ApprovalsScreen}
        options={{
          tabBarLabel: 'الموافقات',
          tabBarIcon: ({ color, size }) => (
            <Icon name="clipboard-check" color={color} size={size} />
          ),
        }}
      />
      <Tab.Screen
        name="Notifications"
        component={NotificationsScreen}
        options={{
          tabBarLabel: 'الإشعارات',
          tabBarIcon: ({ color, size }) => (
            <Icon name="bell" color={color} size={size} />
          ),
        }}
      />
    </Tab.Navigator>
  );
}
