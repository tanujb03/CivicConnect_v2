import React, { useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { router } from 'expo-router';
import { Colors, Spacing, Radii } from '../../src/theme/tokens';
import { FontFamily } from '../../src/theme/fonts';
import {
  HardShadow,
  Button,
  Card,
  Chip,
  PriorityChip,
  StatusChip,
  SlaChip,
  PageHeader,
  Field,
  Input,
  Textarea,
  Toggle,
  SyncPill,
  OfflineBanner,
  StateView,
  PhotoTile,
  PlaceholderPhoto,
  KpiCard,
  useToast,
} from '../../src/ui';

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <View style={styles.section}>
      <Text style={styles.sectionTitle}>{title}</Text>
      {children}
    </View>
  );
}

export default function PrimitivesScreen() {
  const { show } = useToast();
  const [toggleVal, setToggleVal] = useState(false);
  const [inputVal, setInputVal] = useState('');
  const [textVal, setTextVal] = useState('');

  // Dates for SlaChip demo
  const futureDate = new Date(Date.now() + 5 * 60 * 60 * 1000).toISOString();
  const urgentDate = new Date(Date.now() + 1 * 60 * 60 * 1000).toISOString();
  const overdueDate = new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString();

  return (
    <SafeAreaView style={styles.root} edges={['top']}>
      <PageHeader
        title="PRIMITIVES"
        eyebrow="DEV SHOWCASE"
        onBack={() => router.back()}
      />
      <ScrollView
        contentContainerStyle={styles.content}
        showsVerticalScrollIndicator={false}
      >
        {/* BUTTONS */}
        <Section title="BUTTONS">
          <Button title="PRIMARY (Lime)" onPress={() => show('Primary!', 'success')} variant="primary" style={styles.btnGap} />
          <Button title="WINE" onPress={() => show('Wine!', 'info')} variant="wine" style={styles.btnGap} />
          <Button title="FIRE" onPress={() => show('Fire!', 'error')} variant="fire" style={styles.btnGap} />
          <Button title="SECONDARY" onPress={() => {}} variant="secondary" style={styles.btnGap} />
          <Button title="GHOST" onPress={() => {}} variant="ghost" style={styles.btnGap} />
          <Button title="DISABLED" onPress={() => {}} disabled style={styles.btnGap} />
          <Button title="LOADING..." onPress={() => {}} loading style={styles.btnGap} />
        </Section>

        {/* CHIPS */}
        <Section title="CHIPS">
          <View style={styles.row}>
            <PriorityChip priority="P1" />
            <PriorityChip priority="P2" />
            <PriorityChip priority="P3" />
          </View>
          <View style={[styles.row, styles.rowGap]}>
            <StatusChip status="OPEN" />
            <StatusChip status="IN_PROGRESS" />
            <StatusChip status="DONE" />
            <StatusChip status="CANCELLED" />
          </View>
          <View style={[styles.row, styles.rowGap]}>
            <SlaChip deadline={futureDate} />
            <SlaChip deadline={urgentDate} />
            <SlaChip deadline={overdueDate} />
          </View>
          <View style={[styles.row, styles.rowGap]}>
            <Chip label="CUSTOM CHIP" backgroundColor={Colors.limeTint} shadow />
          </View>
        </Section>

        {/* CARDS */}
        <Section title="CARDS">
          <Card shadow="card" containerStyle={styles.cardGap}>
            <Text style={styles.cardText}>Card with card shadow (5,5)</Text>
          </Card>
          <Card shadow="hard" containerStyle={styles.cardGap}>
            <Text style={styles.cardText}>Card with hard shadow (3,3)</Text>
          </Card>
          <Card shadow="lift" containerStyle={styles.cardGap}>
            <Text style={styles.cardText}>Card with lift shadow (8,9)</Text>
          </Card>
          <Card shadow="none" containerStyle={styles.cardGap}>
            <Text style={styles.cardText}>Card with no shadow</Text>
          </Card>
        </Section>

        {/* KPI CARDS */}
        <Section title="KPI CARDS">
          <View style={styles.row}>
            <KpiCard value="14" label="Open" backgroundColor={Colors.wine} textColor={Colors.lime} />
            <View style={{ width: 8 }} />
            <KpiCard value="3" label="Overdue" backgroundColor={Colors.fire} textColor={Colors.onFire} />
            <View style={{ width: 8 }} />
            <KpiCard value="5" label="Done" backgroundColor={Colors.limeTint} textColor={Colors.ink} />
          </View>
        </Section>

        {/* FORM INPUTS */}
        <Section title="INPUTS">
          <Field label="Text Input" hint="Hint text goes here" style={styles.fieldGap}>
            <Input
              value={inputVal}
              onChangeText={setInputVal}
              placeholder="Type something..."
            />
          </Field>
          <Field label="Textarea" required style={styles.fieldGap}>
            <Textarea
              value={textVal}
              onChangeText={setTextVal}
              placeholder="Multi-line input..."
              numberOfLines={3}
            />
          </Field>
          <Field label="Error Input" error="This field has an error" style={styles.fieldGap}>
            <Input
              value=""
              onChangeText={() => {}}
              placeholder="Has error"
              hasError
            />
          </Field>
        </Section>

        {/* TOGGLE */}
        <Section title="TOGGLE">
          <View style={styles.row}>
            <Toggle value={toggleVal} onValueChange={setToggleVal} />
            <Text style={styles.toggleLabel}>{toggleVal ? 'ON' : 'OFF'}</Text>
          </View>
          <View style={[styles.row, styles.rowGap]}>
            <Toggle value={true} onValueChange={() => {}} disabled />
            <Text style={styles.toggleLabel}>Disabled ON</Text>
          </View>
        </Section>

        {/* SYNC PILL */}
        <Section title="SYNC PILL">
          <View style={styles.row}>
            <SyncPill count={3} />
            <View style={{ width: 12 }} />
            <SyncPill count={99} />
            <View style={{ width: 12 }} />
            <SyncPill count={150} />
          </View>
        </Section>

        {/* OFFLINE BANNER */}
        <Section title="OFFLINE BANNER">
          <OfflineBanner pendingCount={4} onPress={() => show('Offline queue', 'warning')} />
        </Section>

        {/* PHOTOS */}
        <Section title="PHOTO TILES">
          <View style={styles.row}>
            <PlaceholderPhoto size={96} onPress={() => show('Camera!', 'info')} />
            <View style={{ width: 12 }} />
            <PlaceholderPhoto size={96} onPress={() => {}} />
          </View>
        </Section>

        {/* HARD SHADOW */}
        <Section title="HARD SHADOWS">
          <View style={styles.row}>
            <HardShadow offset={{ dx: 3, dy: 3 }} radius={Radii.md}>
              <View style={styles.shadowBox}>
                <Text style={styles.shadowBoxText}>3,3</Text>
              </View>
            </HardShadow>
            <HardShadow offset={{ dx: 5, dy: 5 }} radius={Radii.md}>
              <View style={styles.shadowBox}>
                <Text style={styles.shadowBoxText}>5,5</Text>
              </View>
            </HardShadow>
            <HardShadow offset={{ dx: 8, dy: 9 }} radius={Radii.md}>
              <View style={styles.shadowBox}>
                <Text style={styles.shadowBoxText}>8,9</Text>
              </View>
            </HardShadow>
          </View>
        </Section>

        {/* STATE VIEWS — inline mini versions */}
        <Section title="STATE VIEWS">
          <StateView
            variant="empty"
            title="No items"
            message="Empty state preview"
          />
        </Section>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: Colors.ground },
  content: {
    paddingHorizontal: Spacing.screenH,
    paddingBottom: 64,
  },
  section: {
    marginBottom: 32,
  },
  sectionTitle: {
    fontFamily: FontFamily.mono,
    fontSize: 10,
    fontWeight: '500',
    color: Colors.muted,
    letterSpacing: 1.5,
    textTransform: 'uppercase',
    marginBottom: 14,
    paddingBottom: 6,
    borderBottomWidth: 1,
    borderBottomColor: Colors.dot,
  },
  row: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    alignItems: 'center',
    gap: 10,
  },
  rowGap: { marginTop: 10 },
  btnGap: { marginBottom: 10 },
  cardGap: { marginBottom: 12, width: undefined },
  cardText: {
    fontFamily: FontFamily.sans,
    fontSize: 14,
    color: Colors.ink,
  },
  fieldGap: { marginBottom: 16 },
  toggleLabel: {
    fontFamily: FontFamily.mono,
    fontSize: 12,
    color: Colors.ink,
    marginLeft: 8,
  },
  shadowBox: {
    width: 80,
    height: 60,
    backgroundColor: Colors.lime,
    borderRadius: Radii.md,
    borderWidth: 2,
    borderColor: Colors.ink,
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: 20,
  },
  shadowBoxText: {
    fontFamily: FontFamily.mono,
    fontSize: 12,
    color: Colors.ink,
    fontWeight: '500',
  },
});
