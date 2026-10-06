import React from 'react';
import { View, Text, StyleSheet, ActivityIndicator } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { Colors, FontSizes, Spacing } from '../theme/tokens';
import { FontFamily } from '../theme/fonts';
import { Button } from './Button';

export type StateViewVariant = 'loading' | 'empty' | 'error';

export interface StateViewProps {
  variant: StateViewVariant;
  title?: string;
  message?: string;
  actionLabel?: string;
  onAction?: () => void;
}

export const StateView: React.FC<StateViewProps> = ({
  variant,
  title,
  message,
  actionLabel,
  onAction,
}) => {
  const getDefault = (): { icon: string; title: string; message: string } => {
    switch (variant) {
      case 'loading':
        return { icon: '', title: 'Loading...', message: 'Please wait' };
      case 'empty':
        return {
          icon: 'checkbox-outline',
          title: 'Nothing here',
          message: 'No items found',
        };
      case 'error':
        return {
          icon: 'alert-circle-outline',
          title: 'Something went wrong',
          message: 'Please try again',
        };
    }
  };

  const defaults = getDefault();
  const displayTitle = title ?? defaults.title;
  const displayMessage = message ?? defaults.message;

  return (
    <View style={styles.container}>
      {variant === 'loading' ? (
        <ActivityIndicator size="large" color={Colors.wine} style={styles.icon} />
      ) : (
        <Ionicons
          name={defaults.icon as any}
          size={48}
          color={variant === 'error' ? Colors.fire : Colors.muted}
          style={styles.icon}
        />
      )}

      <Text style={styles.title}>{displayTitle}</Text>
      <Text style={styles.message}>{displayMessage}</Text>

      {actionLabel && onAction ? (
        <View style={styles.actionWrapper}>
          <Button
            title={actionLabel}
            onPress={onAction}
            variant={variant === 'error' ? 'fire' : 'secondary'}
            size="default"
          />
        </View>
      ) : null}
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: Spacing.screenH * 2,
    paddingVertical: 48,
  },
  icon: {
    marginBottom: 20,
  },
  title: {
    fontFamily: FontFamily.display,
    fontSize: FontSizes.cardTitle,
    color: Colors.ink,
    textAlign: 'center',
    marginBottom: 8,
  },
  message: {
    fontFamily: FontFamily.sans,
    fontSize: FontSizes.body,
    color: Colors.muted,
    textAlign: 'center',
    lineHeight: 24,
  },
  actionWrapper: {
    marginTop: 24,
    width: '100%',
  },
});
