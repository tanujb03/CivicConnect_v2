import React from 'react';
import { View, Text, StyleSheet, StyleProp, ViewStyle } from 'react-native';
import { Colors, FontSizes, Spacing } from '../theme/tokens';
import { FontFamily } from '../theme/fonts';

export interface FieldProps {
  label?: string;
  error?: string;
  hint?: string;
  required?: boolean;
  children: React.ReactNode;
  style?: StyleProp<ViewStyle>;
}

export const Field: React.FC<FieldProps> = ({
  label,
  error,
  hint,
  required,
  children,
  style,
}) => {
  return (
    <View style={[styles.container, style]}>
      {label ? (
        <View style={styles.labelRow}>
          <Text style={styles.label}>
            {label}
            {required ? <Text style={styles.required}> *</Text> : null}
          </Text>
        </View>
      ) : null}

      {children}

      {error ? (
        <Text style={styles.errorText}>{error}</Text>
      ) : hint ? (
        <Text style={styles.hintText}>{hint}</Text>
      ) : null}
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    marginBottom: 16,
    width: '100%',
  },
  labelRow: {
    marginBottom: 6,
  },
  label: {
    fontFamily: FontFamily.sansSemiBold,
    fontSize: FontSizes.small,
    color: Colors.ink,
    letterSpacing: 0.3,
  },
  required: {
    color: Colors.fire,
  },
  errorText: {
    fontFamily: FontFamily.sans,
    fontSize: 12,
    color: Colors.fire,
    marginTop: 4,
  },
  hintText: {
    fontFamily: FontFamily.sans,
    fontSize: 12,
    color: Colors.muted,
    marginTop: 4,
  },
});
