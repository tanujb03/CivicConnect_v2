import { Alert, Platform } from 'react-native';

interface AlertButton {
  text: string;
  onPress?: () => void;
  style?: 'default' | 'cancel' | 'destructive';
}

/**
 * Universal alert/confirm helper that works seamlessly on both Web and Native.
 * On Native: calls React Native Alert.alert.
 * On Web: executes window.confirm or window.alert and correctly triggers button callbacks!
 */
export function showAppAlert(
  title: string,
  message?: string,
  buttons?: AlertButton[]
) {
  if (Platform.OS === 'web' && typeof window !== 'undefined') {
    if (!buttons || buttons.length <= 1) {
      window.alert([title, message].filter(Boolean).join('\n'));
      if (buttons?.[0]?.onPress) {
        buttons[0].onPress();
      }
      return;
    }

    // Has multiple buttons (e.g. Cancel and Confirm/Delete/SignOut)
    const destructiveOrConfirmBtn = buttons.find(b => b.style === 'destructive') || buttons[buttons.length - 1];
    const cancelBtn = buttons.find(b => b.style === 'cancel');

    const confirmed = window.confirm([title, message].filter(Boolean).join('\n'));
    if (confirmed) {
      destructiveOrConfirmBtn?.onPress?.();
    } else {
      cancelBtn?.onPress?.();
    }
    return;
  }

  // Native iOS / Android
  Alert.alert(
    title,
    message,
    buttons?.map(b => ({
      text: b.text,
      onPress: b.onPress,
      style: b.style,
    }))
  );
}
