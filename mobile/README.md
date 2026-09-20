# HSAAI Mobile App

**Hayel Saeed Anam Artificial Intelligence — Mobile Application**

React Native Android app for the HSAAI Enterprise AI platform.

## Features

- 💬 **Chat with HSAAI Assistant** — Full chat interface with offline support (SQLite)
- 📊 **Dashboard** — KPIs, weekly usage charts, service health, department adoption
- 🤖 **AI Agents** — Browse and interact with 6 specialized agents (HR, Finance, Legal, etc.)
- 📚 **Knowledge Hub** — Search and browse enterprise documents
- ✅ **Approvals & Governance** — Approve/reject pending requests
- 🔔 **Notifications** — Push notification history with priority levels

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Framework | React Native 0.74 + Expo 51 |
| Language | TypeScript 5.3 |
| Navigation | React Navigation 6 (Bottom Tabs + Stack) |
| State | Zustand 4 |
| API | Axios + Keycloak OIDC |
| Offline | react-native-sqlite-storage |
| Icons | react-native-vector-icons (MaterialCommunityIcons) |
| Auth | Keycloak OIDC (Resource Owner Password + Refresh Token) |

## HSA Brand Identity

| Element | Color |
|---------|-------|
| Primary | `#F0CF3A` (Gold/Yellow) |
| Background | `#050505` (Black) |
| Surface | `#0F172A` (Navy) |
| Success | `#059669` |
| Error | `#DC2626` |
| Warning | `#D97706` |

All screens use **RTL Arabic** layout.

## Project Structure

```
hsaai_mobile/
├── src/
│   ├── api/                 # API client + endpoints
│   │   ├── client.ts        # Axios with auth interceptors
│   │   ├── auth.ts          # Keycloak OIDC
│   │   ├── chat.ts          # Chat API
│   │   ├── dashboard.ts     # Dashboard API
│   │   ├── agents.ts        # Agents API
│   │   ├── knowledge.ts     # Knowledge hub API
│   │   ├── governance.ts    # Approvals API
│   │   └── notifications.ts # Notifications API
│   ├── components/          # Reusable UI components
│   │   ├── HSAButton.tsx
│   │   ├── HSAInput.tsx
│   │   ├── HSAHeader.tsx
│   │   ├── KPICard.tsx
│   │   ├── ChatBubble.tsx
│   │   ├── AgentCard.tsx
│   │   └── ApprovalCard.tsx
│   ├── screens/             # App screens
│   │   ├── auth/            # Login + Splash
│   │   ├── dashboard/       # Dashboard with KPIs
│   │   ├── chat/            # Chat with offline support
│   │   ├── agents/          # AI agents list
│   │   ├── knowledge/       # Document search
│   │   ├── governance/      # Approvals
│   │   └── notifications/   # Notifications
│   ├── navigation/          # React Navigation
│   │   ├── AppNavigator.tsx
│   │   └── TabNavigator.tsx
│   ├── store/               # Zustand stores
│   │   ├── authStore.ts
│   │   ├── chatStore.ts
│   │   └── settingsStore.ts
│   ├── db/                  # SQLite offline storage
│   │   ├── database.ts
│   │   ├── chatRepository.ts
│   │   └── docRepository.ts
│   ├── theme/               # HSA brand theme
│   │   ├── colors.ts
│   │   ├── typography.ts
│   │   └── spacing.ts
│   └── App.tsx              # Root component
├── package.json
├── tsconfig.json
├── app.json
├── babel.config.js
├── metro.config.js
└── index.ts
```

## Setup & Build

### Prerequisites
- Node.js 18+
- Java JDK 17
- Android Studio (with SDK 34)
- HSAAI backend running on `http://hsaai.local:8080`

### Install Dependencies
```bash
cd hsaai_mobile
npm install
```

### Run in Development
```bash
# Start Metro bundler
npm start

# Run on Android device/emulator
npm run android
```

### Build APK
```bash
# Generate release APK
npm run build:apk

# Output: HSAAI-Mobile.apk
```

### Install APK on Device
```bash
adb install HSAAI-Mobile.apk
```

## Configuration

### API Endpoint
Default: `http://hsaai.local:8080` (local network)

Change in `src/api/client.ts`:
```typescript
const API_BASE_URL = 'http://your-server:8080';
```

### Keycloak OIDC
Default config in `src/api/auth.ts`:
```typescript
const KEYCLOAK_CONFIG = {
  issuer: 'http://hsaai.local:8080/realms/hsaai',
  clientId: 'hsaai-mobile',
  redirectUri: 'hsaai://callback',
  scopes: ['openid', 'profile', 'email', 'offline_access'],
};
```

### Offline Storage
- Database: `hsaai.db` (SQLite)
- Tables: `conversations`, `messages`, `documents_cache`, `notifications`
- Conversations are stored locally and synced when online

## Authentication Flow

1. App starts → checks for stored token (SecureStore)
2. If no token → shows Login screen
3. User enters username/password → Keycloak OIDC (Password Grant)
4. Token stored securely → navigates to Main app
5. On 401 → auto-refresh using refresh_token
6. If refresh fails → logout + return to Login

## Offline Support

| Feature | Offline Behavior |
|---------|-----------------|
| Chat | Messages saved to SQLite, sent when online |
| Documents | Cached locally, searchable offline |
| Dashboard | Shows last cached data |
| Approvals | Cannot act offline (read-only) |
| Agents | Shows last cached list |
| Notifications | Stored locally, marked read offline |

## License

Enterprise Internal Use — HSA Group © 2026

## Version

6.1.0 — June 2026
