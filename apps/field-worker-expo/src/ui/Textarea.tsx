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
import { Colors, Radii, Shadows } from '../theme/tokens';
import { FontFamily } from '../theme/fonts';
import { HardShadow } from './HardShadow';

export interface TextareaProps extends Omit<TextInputProps, 'style' | 'multiline'> {
  numberOfLines?: number;
  hasError?: boolean;
  shadow?: boolean;
  containerStyle?: StyleProp<ViewStyle>;
  inputStyle?: StyleProp<TextStyle>;
}

export const Textarea: React.FC<TextareaProps> = ({
  numberOfLines = 4,
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
        styles.wrapper,
        {
          borderColor: hasError
            ? Colors.fire
            : isFocused
            ? Colors.wine
            : Colors.ink,
          minHeight: numberOfLines * 24 + 24,
        },
      ]}
    >
      <TextInput
        multiline
        textAlignVertical="top"
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
  wrapper: {
    backgroundColor: Colors.surface,
    borderWidth: 2,
    borderRadius: Radii.md,
    padding: 12,
  },
  input: {
    fontFamily: FontFamily.sans,
    fontSize: 16,
    color: Colors.ink,
    flex: 1,
    minHeight: 80,
  },
});
