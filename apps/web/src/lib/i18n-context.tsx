"use client";

import React, { createContext, useContext, useEffect, useState } from "react";
import { DEFAULT_LOCALE, DICTIONARIES, Locale, getDir } from "@/lib/i18n";

const STORAGE_KEY = "wallet-agent-locale";

interface Ctx {
  locale: Locale;
  setLocale: (l: Locale) => void;
  t: (typeof DICTIONARIES)[Locale];
  dir: "ltr" | "rtl";
}

const I18nContext = createContext<Ctx | null>(null);

export function I18nProvider({ children }: { children: React.ReactNode }) {
  const [locale, setLocaleState] = useState<Locale>(DEFAULT_LOCALE);

  useEffect(() => {
    try {
      const stored = window.localStorage.getItem(STORAGE_KEY) as Locale | null;
      if (stored && stored in DICTIONARIES) {
        setLocaleState(stored);
      } else {
        const nav = (typeof navigator !== "undefined" ? navigator.language : "")
          .slice(0, 2)
          .toLowerCase();
        if (nav && nav in DICTIONARIES) {
          setLocaleState(nav as Locale);
        }
      }
    } catch {
      /* ignore */
    }
  }, []);

  useEffect(() => {
    if (typeof document !== "undefined") {
      document.documentElement.lang = locale;
      document.documentElement.dir = getDir(locale);
    }
  }, [locale]);

  const setLocale = (l: Locale) => {
    setLocaleState(l);
    try {
      window.localStorage.setItem(STORAGE_KEY, l);
    } catch {
      /* ignore */
    }
  };

  const value: Ctx = {
    locale,
    setLocale,
    t: DICTIONARIES[locale],
    dir: getDir(locale),
  };
  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n(): Ctx {
  const c = useContext(I18nContext);
  if (!c) {
    // Provider 外で呼ばれた場合（テスト時等）はデフォルト辞書を返す
    return {
      locale: DEFAULT_LOCALE,
      setLocale: () => undefined,
      t: DICTIONARIES[DEFAULT_LOCALE],
      dir: "ltr",
    };
  }
  return c;
}
