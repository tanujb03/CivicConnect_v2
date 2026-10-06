import React from 'react';
import {
  View,
  Image,
  Pressable,
  StyleSheet,
  StyleProp,
  ViewStyle,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { Colors, Radii, Shadows } from '../theme/tokens';
import { HardShadow } from './HardShadow';

export interface PhotoTileProps {
  uri: string;
  size?: number;
  onPress?: () => void;
  onRemove?: () => void;
  style?: StyleProp<ViewStyle>;
}

export const PhotoTile: React.FC<PhotoTileProps> = ({
  uri,
  size = 96,
  onPress,
  onRemove,
  style,
}) => {
  return (
    <HardShadow
      offset={Shadows.hard}
      radius={Radii.md}
      containerStyle={[{ width: size, height: size }, style]}
    >
      <Pressable
        onPress={onPress}
        style={[
          styles.tile,
          {
            width: size,
            height: size,
            borderRadius: Radii.md,
          },
        ]}
      >
        <Image
          source={{ uri }}
          style={[
            styles.image,
            { width: size, height: size, borderRadius: Radii.md },
          ]}
          resizeMode="cover"
        />
        {onRemove ? (
          <Pressable
            onPress={onRemove}
            hitSlop={8}
            style={styles.removeButton}
            accessibilityLabel="Remove photo"
          >
            <Ionicons name="close-circle" size={22} color={Colors.fire} />
          </Pressable>
        ) : null}
      </Pressable>
    </HardShadow>
  );
};

export interface PlaceholderPhotoProps {
  size?: number;
  onPress?: () => void;
  label?: string;
  style?: StyleProp<ViewStyle>;
}

export const PlaceholderPhoto: React.FC<PlaceholderPhotoProps> = ({
  size = 96,
  onPress,
  style,
}) => {
  return (
    <HardShadow
      offset={Shadows.hard}
      radius={Radii.md}
      containerStyle={[{ width: size, height: size }, style]}
    >
      <Pressable
        onPress={onPress}
        style={[
          styles.placeholder,
          {
            width: size,
            height: size,
            borderRadius: Radii.md,
          },
        ]}
        accessibilityLabel="Add photo"
        accessibilityRole="button"
      >
        <Ionicons name="camera-outline" size={28} color={Colors.muted} />
      </Pressable>
    </HardShadow>
  );
};

const styles = StyleSheet.create({
  tile: {
    overflow: 'hidden',
    borderWidth: 2,
    borderColor: Colors.ink,
  },
  image: {
    flex: 1,
  },
  removeButton: {
    position: 'absolute',
    top: 4,
    right: 4,
    backgroundColor: Colors.surface,
    borderRadius: 12,
  },
  placeholder: {
    backgroundColor: Colors.ground,
    borderWidth: 2,
    borderColor: Colors.ink,
    borderStyle: 'dashed',
    justifyContent: 'center',
    alignItems: 'center',
  },
});
