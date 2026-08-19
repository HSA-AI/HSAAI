import React, { useState, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  FlatList,
  RefreshControl,
  TextInput,
  TouchableOpacity,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import Icon from 'react-native-vector-icons/MaterialCommunityIcons';
import { HSAHeader } from '@components/index';
import { getDocuments, searchKnowledge, type KnowledgeDocument } from '@api/knowledge';
import { searchCachedDocuments } from '@db/docRepository';
import { colors } from '@theme/colors';
import { typography } from '@theme/typography';
import { spacing, radius } from '@theme/spacing';

const CLASSIFICATION_COLORS: Record<string, string> = {
  public: colors.info,
  internal: colors.success,
  confidential: colors.warning,
  restricted: colors.error,
};

export function KnowledgeHubScreen() {
  const [documents, setDocuments] = useState<KnowledgeDocument[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isSearching, setIsSearching] = useState(false);

  const loadDocuments = useCallback(async () => {
    try {
      setError(null);
      const data = await getDocuments();
      setDocuments(data.documents);
    } catch {
      // Fallback to cached documents
      const cached = await searchCachedDocuments('').catch(() => []);
      if (cached.length > 0) {
        setDocuments(cached);
        setError(null);
      } else {
        setError('تعذر تحميل الوثائق. تأكد من الاتصال بالشبكة.');
      }
    }
  }, []);

  React.useEffect(() => { loadDocuments(); }, [loadDocuments]);

  const onRefresh = async () => {
    setRefreshing(true);
    await loadDocuments();
    setRefreshing(false);
  };

  const handleSearch = async () => {
    if (!searchQuery.trim()) {
      loadDocuments();
      return;
    }
    setIsSearching(true);
    try {
      const results = await searchKnowledge(searchQuery);
      setDocuments(results.map(r => ({
        id: r.id,
        title: r.title,
        department: 'بحث',
        category: 'نتيجة بحث',
        size: '',
        uploadedAt: '',
        classification: 'internal' as const,
        summary: r.snippet,
      })));
    } catch {
      // Try cached search
      const cached = await searchCachedDocuments(searchQuery);
      setDocuments(cached);
    }
    setIsSearching(false);
  };

  const renderDocument = ({ item }: { item: KnowledgeDocument }) => {
    const classColor = CLASSIFICATION_COLORS[item.classification] || colors.textLight;
    return (
      <TouchableOpacity style={styles.docCard} activeOpacity={0.8}>
        <View style={styles.docHeader}>
          <View style={[styles.docIcon, { backgroundColor: `${classColor}20` }]}>
            <Icon name="file-document-outline" size={24} color={classColor} />
          </View>
          <View style={styles.docInfo}>
            <Text style={styles.docTitle} numberOfLines={2}>{item.title}</Text>
            <Text style={styles.docMeta}>{item.department} · {item.category}</Text>
          </View>
          <View style={[styles.classBadge, { backgroundColor: `${classColor}20` }]}>
            <Text style={[styles.classText, { color: classColor }]}>
              {item.classification}
            </Text>
          </View>
        </View>
        {item.summary && (
          <Text style={styles.docSummary} numberOfLines={2}>{item.summary}</Text>
        )}
        <View style={styles.docFooter}>
          <Text style={styles.docSize}>{item.size}</Text>
          {item.uploadedAt && <Text style={styles.docDate}>{item.uploadedAt}</Text>}
        </View>
      </TouchableOpacity>
    );
  };

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <HSAHeader title="مركز المعرفة" subtitle={`${documents.length} وثيقة`} />
      <View style={styles.searchContainer}>
        <TextInput
          style={styles.searchInput}
          value={searchQuery}
          onChangeText={setSearchQuery}
          placeholder="ابحث في الوثائق..."
          placeholderTextColor={colors.textLight}
          onSubmitEditing={handleSearch}
          returnKeyType="search"
          textAlign="right"
        />
        <TouchableOpacity style={styles.searchButton} onPress={handleSearch} disabled={isSearching}>
          <Icon name="magnify" size={22} color={colors.hsaBlack} />
        </TouchableOpacity>
      </View>
      <FlatList
        data={documents}
        keyExtractor={(item) => item.id}
        renderItem={renderDocument}
        contentContainerStyle={styles.list}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={colors.hsaYellow} />}
        ListEmptyComponent={
          error ? (
            <View style={styles.emptyContainer}>
              <Text style={styles.emptyText}>{error}</Text>
              <TouchableOpacity onPress={loadDocuments} style={styles.retryButton}>
                <Text style={styles.retryText}>إعادة المحاولة</Text>
              </TouchableOpacity>
            </View>
          ) : (
            <View style={styles.emptyContainer}>
              <Text style={styles.emptyText}>لا توجد وثائق</Text>
            </View>
          )
        }
      />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  searchContainer: {
    flexDirection: 'row',
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.sm,
    gap: spacing.sm,
  },
  searchInput: {
    flex: 1,
    ...typography.body,
    backgroundColor: colors.surface,
    color: colors.textWhite,
    borderRadius: radius.md,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm + 2,
    borderWidth: 1,
    borderColor: colors.borderDark,
    textAlign: 'right',
  },
  searchButton: {
    width: 44,
    height: 44,
    borderRadius: radius.md,
    backgroundColor: colors.hsaYellow,
    alignItems: 'center',
    justifyContent: 'center',
  },
  list: { padding: spacing.lg, paddingBottom: 80 },
  docCard: {
    backgroundColor: colors.surface,
    borderRadius: radius.lg,
    padding: spacing.md,
    marginBottom: spacing.sm,
  },
  docHeader: { flexDirection: 'row', alignItems: 'center' },
  docIcon: {
    width: 44,
    height: 44,
    borderRadius: radius.md,
    alignItems: 'center',
    justifyContent: 'center',
    marginLeft: spacing.sm,
  },
  docInfo: { flex: 1 },
  docTitle: { ...typography.h4, color: colors.textWhite, marginBottom: 2 },
  docMeta: { ...typography.caption, color: colors.textLight },
  classBadge: {
    borderRadius: radius.pill,
    paddingHorizontal: spacing.sm,
    paddingVertical: 3,
  },
  classText: { ...typography.overline, fontWeight: '800' },
  docSummary: {
    ...typography.bodySmall,
    color: colors.textSecondary,
    marginTop: spacing.sm,
  },
  docFooter: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginTop: spacing.sm,
    paddingTop: spacing.sm,
    borderTopWidth: 1,
    borderTopColor: colors.borderDark,
  },
  docSize: { ...typography.caption, color: colors.textLight },
  docDate: { ...typography.caption, color: colors.textLight },
  emptyContainer: { alignItems: 'center', padding: spacing.xxxl },
  emptyText: { ...typography.body, color: colors.textLight, textAlign: 'center', marginBottom: spacing.md },
  retryButton: {
    backgroundColor: colors.hsaYellow,
    paddingHorizontal: spacing.xl,
    paddingVertical: spacing.md,
    borderRadius: radius.md,
  },
  retryText: { ...typography.button, color: colors.hsaBlack },
});
