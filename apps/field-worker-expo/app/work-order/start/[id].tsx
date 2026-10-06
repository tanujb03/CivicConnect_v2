import React, { useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  KeyboardAvoidingView,
  Platform,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useLocalSearchParams, router } from 'expo-router';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Colors, Radii, Shadows, Spacing } from '../../../src/theme/tokens';
import { FontFamily } from '../../../src/theme/fonts';
import {
  PageHeader,
  Field,
  Textarea,
  Button,
  StatusChip,
  StateView,
  useToast,
  Card,
} from '../../../src/ui';
import { apiClient } from '../../../src/api/client';

export default function StartScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const { show } = useToast();
  const queryClient = useQueryClient();

  const [note, setNote] = useState('');
  const [noteError, setNoteError] = useState('');

  const { data: workOrder, isLoading } = useQuery({
    queryKey: ['workOrder', id],
    queryFn: () => apiClient.getWorkOrder(id!),
    enabled: !!id,
  });

  const mutation = useMutation({
    mutationFn: () =>
      apiClient.updateWorkOrder(id!, {
        status: 'IN_PROGRESS',
        note: note.trim() || undefined,
      }),
    onSuccess: (updated) => {
      queryClient.setQueryData(['workOrder', id], updated);
      queryClient.invalidateQueries({ queryKey: ['workOrders'] });
      queryClient.invalidateQueries({ queryKey: ['kpi'] });
      show('Work order accepted', 'success');
      router.back();
    },
    onError: () => show('Failed to update', 'error'),
  });

  const handleSubmit = () => {
    setNoteError('');
    mutation.mutate();
  };

  if (isLoading) {
    return (
      <SafeAreaView style={styles.root}>
        <StateView variant="loading" title="Loading..." />
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.root} edges={['top', 'bottom']}>
      <KeyboardAvoidingView
        style={styles.flex}
        behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
      >
        <PageHeader
          title="ACCEPT WORK"
          eyebrow="F03 — START"
          onBack={() => router.back()}
        />

        <ScrollView
          contentContainerStyle={styles.content}
          keyboardShouldPersistTaps="handled"
          showsVerticalScrollIndicator={false}
        >
          {workOrder ? (
            <Card shadow="hard" containerStyle={styles.infoCard}>
              <Text style={styles.woTitle}>{workOrder.title}</Text>
              <View style={styles.row}>
                <StatusChip status={workOrder.status} size="sm" />
              </View>
              <Text style={styles.address}>{workOrder.address}</Text>
            </Card>
          ) : null}

          <Text style={styles.sectionLabel}>
            Accepting this work order will set its status to IN PROGRESS and
            notify the supervisor.
          </Text>

          <Field
            label="Initial Note (optional)"
            hint="Describe what you observed on arrival"
            style={styles.fieldGap}
          >
            <Textarea
              value={note}
              onChangeText={setNote}
              placeholder="e.g. Arrived at site. Road damage extends approx. 5m from kerb..."
              numberOfLines={4}
            />
          </Field>

          <Button
            title={mutation.isPending ? 'Accepting...' : 'ACCEPT & START'}
            onPress={handleSubmit}
            variant="wine"
            loading={mutation.isPending}
          />

          <Button
            title="CANCEL"
            onPress={() => router.back()}
            variant="ghost"
            style={styles.cancelBtn}
          />
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: Colors.ground },
  flex: { flex: 1 },
  content: {
    paddingHorizontal: Spacing.screenH,
    paddingBottom: 48,
    gap: 16,
  },
  infoCard: { width: undefined, marginBottom: 4 },
  woTitle: {
    fontFamily: FontFamily.sansSemiBold,
    fontSize: 16,
    color: Colors.ink,
    marginBottom: 8,
    lineHeight: 22,
  },
  row: { flexDirection: 'row', gap: 6, marginBottom: 6 },
  address: {
    fontFamily: FontFamily.sans,
    fontSize: 13,
    color: Colors.muted,
  },
  sectionLabel: {
    fontFamily: FontFamily.sans,
    fontSize: 14,
    color: Colors.muted,
    lineHeight: 20,
  },
  fieldGap: { marginBottom: 4 },
  cancelBtn: { marginTop: 4 },
});
