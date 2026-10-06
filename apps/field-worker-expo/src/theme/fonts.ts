import { useFonts } from 'expo-font';
import {
  DelaGothicOne_400Regular,
} from '@expo-google-fonts/dela-gothic-one';
import {
  Geist_400Regular,
  Geist_500Medium,
  Geist_600SemiBold,
} from '@expo-google-fonts/geist';
import {
  JetBrainsMono_500Medium,
} from '@expo-google-fonts/jetbrains-mono';
import {
  Yellowtail_400Regular,
} from '@expo-google-fonts/yellowtail';

export const FontMap = {
  'DelaGothicOne-Regular': DelaGothicOne_400Regular,
  'Geist-Regular': Geist_400Regular,
  'Geist-Medium': Geist_500Medium,
  'Geist-SemiBold': Geist_600SemiBold,
  'JetBrainsMono-Medium': JetBrainsMono_500Medium,
  'Yellowtail-Regular': Yellowtail_400Regular,
} as const;

export function useAppFonts() {
  return useFonts(FontMap);
}

// Semantic font families
export const FontFamily = {
  display: 'DelaGothicOne-Regular',
  sans: 'Geist-Regular',
  sansMedium: 'Geist-Medium',
  sansSemiBold: 'Geist-SemiBold',
  mono: 'JetBrainsMono-Medium',
  script: 'Yellowtail-Regular',
} as const;
