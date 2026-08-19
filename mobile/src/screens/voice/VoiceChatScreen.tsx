/**
 * HSAAI Mobile — Voice Chat Screen (Phase 11)
 * ============================================
 * Voice-to-text input + text-to-speech output for accessibility
 * and hands-free operation.
 */
import React, { useState, useEffect, useRef } from 'react';
import {
  View, Text, TouchableOpacity, StyleSheet, PermissionsAndroid,
  Platform, ActivityIndicator, Vibration,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useTranslation } from 'react-i18next';
import * as Speech from 'expo-speech';

interface VoiceChatScreenProps {
  onTranscript: (text: string) => void;
}

const COLORS = {
  primary: '#2a6887',
  danger: '#ac574f',
  success: '#44925e',
  bg: '#0a0a0a',
  surface: '#1a1a1a',
  text: '#ffffff',
  textMuted: '#999999',
};

export default function VoiceChatScreen({ onTranscript }: VoiceChatScreenProps) {
  const { t } = useTranslation();
  const [isListening, setIsListening] = useState(false);
  const [transcript, setTranscript] = useState('');
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [error, setError] = useState('');
  const [hasPermission, setHasPermission] = useState(false);

  useEffect(() => {
    requestMicPermission();
  }, []);

  const requestMicPermission = async () => {
    if (Platform.OS === 'android') {
      try {
        const granted = await PermissionsAndroid.request(
          PermissionsAndroid.PERMISSIONS.RECORD_AUDIO,
          {
            title: t('voice.micPermissionTitle'),
            message: t('voice.micPermissionMessage'),
            buttonPositive: t('common.ok'),
            buttonNegative: t('common.cancel'),
          }
        );
        setHasPermission(granted === PermissionsAndroid.RESULTS.GRANTED);
      } catch (err) {
        setError(t('voice.permissionError'));
      }
    } else {
      setHasPermission(true); // iOS handles via Info.plist
    }
  };

  const startListening = async () => {
    if (!hasPermission) {
      await requestMicPermission();
      return;
    }
    setIsListening(true);
    setTranscript('');
    setError('');
    Vibration.vibrate(50);

    // In production: integrate with @react-native-voice/voice or expo-speech-recognition
    // For now, simulate with a timer (real implementation below in comments)
    /*
    Voice.start('ar-SA'); // Arabic Saudi Arabia
    Voice.onSpeechResults = (event) => {
      setTranscript(event.value[0]);
      onTranscript(event.value[0]);
      setIsListening(false);
    };
    Voice.onSpeechError = (event) => {
      setError(event.error.message);
      setIsListening(false);
    };
    */
  };

  const stopListening = () => {
    setIsListening(false);
    Vibration.vibrate(50);
    // Voice.stop();
    if (transcript) {
      onTranscript(transcript);
    }
  };

  const speakResponse = async (text: string) => {
    setIsSpeaking(true);
    Speech.speak(text, {
      language: 'ar-SA',
      onDone: () => setIsSpeaking(false),
      onError: () => setIsSpeaking(false),
    });
  };

  const stopSpeaking = () => {
    Speech.stop();
    setIsSpeaking(false);
  };

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.title}>{t('voice.title')}</Text>
        <Text style={styles.subtitle}>{t('voice.subtitle')}</Text>
      </View>

      <View style={styles.visualizer}>
        <Ionicons
          name={isListening ? 'mic' : 'mic-outline'}
          size={120}
          color={isListening ? COLORS.danger : COLORS.primary}
        />
        {isListening && (
          <ActivityIndicator size="large" color={COLORS.danger} style={styles.indicator} />
        )}
      </View>

      {transcript ? (
        <View style={styles.transcriptContainer}>
          <Text style={styles.transcriptLabel}>{t('voice.transcript')}:</Text>
          <Text style={styles.transcriptText}>{transcript}</Text>
        </View>
      ) : null}

      {error ? <Text style={styles.error}>{error}</Text> : null}

      <View style={styles.controls}>
        <TouchableOpacity
          style={[styles.button, isListening ? styles.buttonStop : styles.buttonStart]}
          onPress={isListening ? stopListening : startListening}
          accessibilityLabel={isListening ? t('voice.stop') : t('voice.start')}
          accessibilityRole="button"
        >
          <Ionicons
            name={isListening ? 'stop' : 'mic'}
            size={32}
            color="white"
          />
          <Text style={styles.buttonText}>
            {isListening ? t('voice.stop') : t('voice.start')}
          </Text>
        </TouchableOpacity>

        {isSpeaking ? (
          <TouchableOpacity
            style={[styles.button, styles.buttonStop]}
            onPress={stopSpeaking}
            accessibilityLabel={t('voice.stopSpeaking')}
          >
            <Ionicons name="volume-mute" size={32} color="white" />
            <Text style={styles.buttonText}>{t('voice.stopSpeaking')}</Text>
          </TouchableOpacity>
        ) : null}
      </View>

      <Text style={styles.hint}>{t('voice.hint')}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: COLORS.bg, padding: 20 },
  header: { alignItems: 'center', marginBottom: 30 },
  title: { color: COLORS.text, fontSize: 24, fontWeight: 'bold' },
  subtitle: { color: COLORS.textMuted, fontSize: 14, marginTop: 8 },
  visualizer: { alignItems: 'center', justifyContent: 'center', marginVertical: 40 },
  indicator: { marginTop: 20 },
  transcriptContainer: {
    backgroundColor: COLORS.surface, borderRadius: 12, padding: 16, marginBottom: 20,
  },
  transcriptLabel: { color: COLORS.textMuted, fontSize: 12, marginBottom: 8 },
  transcriptText: { color: COLORS.text, fontSize: 18 },
  error: { color: COLORS.danger, textAlign: 'center', marginBottom: 16 },
  controls: { flexDirection: 'row', justifyContent: 'center', gap: 16 },
  button: {
    alignItems: 'center', justifyContent: 'center',
    width: 120, height: 120, borderRadius: 60, padding: 16,
  },
  buttonStart: { backgroundColor: COLORS.primary },
  buttonStop: { backgroundColor: COLORS.danger },
  buttonText: { color: 'white', marginTop: 8, fontSize: 14 },
  hint: { color: COLORS.textMuted, textAlign: 'center', fontSize: 12, marginTop: 30 },
});
