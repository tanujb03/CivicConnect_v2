import React, { useState } from 'react';
import {
  TextInput,
  View,
  StyleSheet,
  TextInputProps,
  StyleProp,
  ViewStyle,
  TextStyle,
} from 'react-native';
import { Colors, Radii, Shadows, TouchTargets } from '../theme/tokens';
import { FontFamily } from '../theme/fonts';
import { HardShadow } from './HardShadow';

export interface InputProps extends Omit<TextInputProps, 'style'> {
  leftIcon?: React.ReactNode;
  rightIcon?: React.ReactNode;
  hasError?: boolean;
  shadow?: boolean;
  containerStyle?: StyleProp<ViewStyle>;
  inputStyle?: StyleProp<TextStyle>;
}

export const Input: React.FC<InputProps> = ({
  leftIcon,
  rightIcon,
  hasError = false,
  shadow = true,
  containerStyle,
  inputStyle,
  onFocus,
  onBlur,
  ...props
}) => {
  const [isFocused, setIsFocused] = useState(false);

  const inputContent = (
    <View
      style={[
        styles.inputWrapper,
        {
          borderColor: hasError
            ? Colors.fire
            : isFocused
            ? Colors.wine
            : Colors.ink,
          backgroundColor: Colors.surface,
        },
      ]}
    >
      {leftIcon ? <View style={styles.iconLeft}>{leftIcon}</View> : null}
      <TextInput
        placeholderTextColor={Colors.muted}
        style={[styles.input, inputStyle]}
        onFocus={(e) => {
          setIsFocused(true);
          onFocus?.(e);
        }}
        onBlur={(e) => {
          setIsFocused(false);
          onBlur?.(e);
        }}
        {...props}
      />
      {rightIcon ? <View style={styles.iconRight}>{rightIcon}</View> : null}
    </View>
  );

  if (!shadow) {
    return <View style={containerStyle}>{inputContent}</View>;
  }

  return (
    <HardShadow
      offset={Shadows.hard}
      radius={Radii.md}
      containerStyle={containerStyle}
    >
      {inputContent}
    </HardShadow>
  );
};

const styles = StyleSheet.create({
  inputWrapper: {
    height: TouchTargets.default,
    flexDirection: 'row',
    alignItems: 'center',
    borderWidth: 2,
    borderRadius: Radii.md,
    paddingHorizontal: 12,
  },
  input: {
    flex: 1,
    height: '100%',
    fontFamily: FontFamily.sans,
    fontSize: 16,
    color: Colors.ink,
  },
  iconLeft: {
    marginRight: 8,
  },
  iconRight: {
    marginLeft: 8,
  },
});
