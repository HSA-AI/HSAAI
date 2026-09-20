/**
 * HSAAI Mobile — Document Upload Screen (Phase 11)
 * =================================================
 * Upload documents (PDF, Word, images) to the knowledge base.
 * Supports file picker, camera capture, and drag-drop on tablet.
 */
import React, { useState } from 'react';
import {
  View, Text, TouchableOpacity, StyleSheet, ActivityIndicator,
  Alert, ProgressViewIOS, ProgressBarAndroid, Platform,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import * as DocumentPicker from 'expo-document-picker';
import * as ImagePicker from 'expo-image-picker';
import { useTranslation } from 'react-i18next';
// FIX F-05: client is a default export.
import client from '../../api/client';

const COLORS = {
  primary: '#2a6887', success: '#44925e', danger: '#ac574f',
  bg: '#0a0a0a', surface: '#1a1a1a', text: '#ffffff', textMuted: '#999999',
};

export default function DocumentUploadScreen() {
  const { t } = useTranslation();
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [uploadedFiles, setUploadedFiles] = useState<any[]>([]);

  const pickDocument = async () => {
    try {
      const result = await DocumentPicker.getDocumentAsync({
        multiple: true,
        copyToCacheDirectory: true,
      });
      if (!result.canceled && result.assets) {
        for (const asset of result.assets) {
          await uploadFile(asset);
        }
      }
    } catch (err) {
      Alert.alert(t('common.error'), t('documents.pickError'));
    }
  };

  const takePhoto = async () => {
    const { status } = await ImagePicker.requestCameraPermissionsAsync();
    if (status !== 'granted') {
      Alert.alert(t('common.error'), t('documents.cameraPermission'));
      return;
    }
    const result = await ImagePicker.launchCameraAsync({
      mediaTypes: ImagePicker.MediaTypeOptions.Images,
      quality: 0.8,
    });
    if (!result.canceled && result.assets) {
      await uploadFile(result.assets[0]);
    }
  };

  const pickImage = async () => {
    const result = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ImagePicker.MediaTypeOptions.Images,
      multiple: true,
      quality: 0.8,
    });
    if (!result.canceled && result.assets) {
      for (const asset of result.assets) {
        await uploadFile(asset);
      }
    }
  };

  const uploadFile = async (asset: any) => {
    setUploading(true);
    setProgress(0);
    try {
      const formData = new FormData();
      formData.append('file', {
        uri: asset.uri,
        type: asset.mimeType || 'application/octet-stream',
        name: asset.name || 'document',
      } as any);
      formData.append('tenant_id', 'hsa-foods');
      formData.append('category', 'uploaded');

      const response = await client.post('/v1/rag/documents', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
        onUploadProgress: (e) => {
          if (e.total) {
            setProgress(Math.round((e.loaded / e.total) * 100));
          }
        },
      });
      setUploadedFiles(prev => [...prev, {
        name: asset.name,
        size: asset.size,
        status: 'success',
        document_id: response.data.document_id,
      }]);
    } catch (err: any) {
      setUploadedFiles(prev => [...prev, {
        name: asset.name || 'unknown',
        size: asset.size || 0,
        status: 'error',
        error: err.message,
      }]);
    } finally {
      setUploading(false);
      setProgress(0);
    }
  };

  return (
    <View style={styles.container}>
      <Text style={styles.title}>{t('documents.title')}</Text>

      <View style={styles.buttonGrid}>
        <TouchableOpacity style={styles.uploadButton} onPress={pickDocument}>
          <Ionicons name="document" size={48} color={COLORS.primary} />
          <Text style={styles.buttonLabel}>{t('documents.pickDocument')}</Text>
        </TouchableOpacity>

        <TouchableOpacity style={styles.uploadButton} onPress={takePhoto}>
          <Ionicons name="camera" size={48} color={COLORS.primary} />
          <Text style={styles.buttonLabel}>{t('documents.takePhoto')}</Text>
        </TouchableOpacity>

        <TouchableOpacity style={styles.uploadButton} onPress={pickImage}>
          <Ionicons name="images" size={48} color={COLORS.primary} />
          <Text style={styles.buttonLabel}>{t('documents.pickImage')}</Text>
        </TouchableOpacity>
      </View>

      {uploading && (
        <View style={styles.progressContainer}>
          <Text style={styles.progressText}>{t('documents.uploading')} {progress}%</Text>
          {Platform.OS === 'ios' ? (
            <ProgressViewIOS progress={progress / 100} />
          ) : (
            <ProgressBarAndroid progress={progress / 100} styleAttr="Horizontal" />
          )}
        </View>
      )}

      <View style={styles.historyContainer}>
        <Text style={styles.historyTitle}>{t('documents.history')}</Text>
        {uploadedFiles.map((file, idx) => (
          <View key={idx} style={styles.fileItem}>
            <Ionicons
              name={file.status === 'success' ? 'checkmark-circle' : 'close-circle'}
              size={24}
              color={file.status === 'success' ? COLORS.success : COLORS.danger}
            />
            <View style={styles.fileInfo}>
              <Text style={styles.fileName}>{file.name}</Text>
              <Text style={styles.fileStatus}>
                {file.status === 'success' ? t('documents.uploaded') : file.error}
              </Text>
            </View>
          </View>
        ))}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: COLORS.bg, padding: 20 },
  title: { color: COLORS.text, fontSize: 24, fontWeight: 'bold', marginBottom: 20 },
  buttonGrid: { flexDirection: 'row', justifyContent: 'space-around', marginBottom: 30 },
  uploadButton: {
    alignItems: 'center', backgroundColor: COLORS.surface,
    borderRadius: 12, padding: 20, flex: 1, marginHorizontal: 4,
  },
  buttonLabel: { color: COLORS.text, marginTop: 8, fontSize: 12, textAlign: 'center' },
  progressContainer: { marginBottom: 20 },
  progressText: { color: COLORS.text, marginBottom: 8 },
  historyContainer: { flex: 1 },
  historyTitle: { color: COLORS.textMuted, fontSize: 14, marginBottom: 12 },
  fileItem: { flexDirection: 'row', alignItems: 'center', paddingVertical: 12, borderBottomWidth: 1, borderBottomColor: COLORS.surface },
  fileInfo: { marginLeft: 12, flex: 1 },
  fileName: { color: COLORS.text, fontSize: 14 },
  fileStatus: { color: COLORS.textMuted, fontSize: 12, marginTop: 2 },
});
