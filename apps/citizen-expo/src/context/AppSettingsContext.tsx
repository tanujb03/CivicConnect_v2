import React, { createContext, useContext, useState, useEffect } from 'react';
import AsyncStorage from '@react-native-async-storage/async-storage';
import type { AccessibilityPrefs } from '../types';

interface AppSettings {
  language: string;
  darkMode: boolean;
  accessibility: AccessibilityPrefs;
}

const DEFAULT_SETTINGS: AppSettings = {
  language: 'en',
  darkMode: false,
  accessibility: {
    large_text: false,
    high_contrast: false,
    reduced_motion: false,
    simplified_language: false,
    voice_playback: false,
  },
};

const STORAGE_KEY = 'cc:app_settings';

interface AppSettingsContextValue {
  settings: AppSettings;
  setLanguage: (lang: string) => Promise<void>;
  setDarkMode: (v: boolean) => Promise<void>;
  setAccessibility: (prefs: Partial<AccessibilityPrefs>) => Promise<void>;
}

const AppSettingsContext = createContext<AppSettingsContextValue>({
  settings: DEFAULT_SETTINGS,
  setLanguage: async () => {},
  setDarkMode: async () => {},
  setAccessibility: async () => {},
});

export function AppSettingsProvider({ children }: { children: React.ReactNode }) {
  const [settings, setSettings] = useState<AppSettings>(DEFAULT_SETTINGS);

  useEffect(() => {
    AsyncStorage.getItem(STORAGE_KEY).then(raw => {
      if (raw) setSettings(JSON.parse(raw));
    });
  }, []);

  async function persist(next: AppSettings) {
    setSettings(next);
    await AsyncStorage.setItem(STORAGE_KEY, JSON.stringify(next));
  }

  const setLanguage = async (lang: string) => persist({ ...settings, language: lang });
  const setDarkMode = async (v: boolean) => persist({ ...settings, darkMode: v });
  const setAccessibility = async (prefs: Partial<AccessibilityPrefs>) =>
    persist({ ...settings, accessibility: { ...settings.accessibility, ...prefs } });

  return (
    <AppSettingsContext.Provider value={{ settings, setLanguage, setDarkMode, setAccessibility }}>
      {children}
    </AppSettingsContext.Provider>
  );
}

export function useAppSettings() {
  return useContext(AppSettingsContext);
}
