import { createContext, useContext } from "react";

/** Deployment settings from GET /api/config (languages, escalation contact, features). */
export const DEFAULT_CONFIG = {
  languages: [
    { code: "auto", label: "Auto" },
    { code: "en", label: "English" },
    { code: "hi", label: "हिंदी" },
  ],
  agentic: true,
  bhashini: false,
  escalation: { name: null, email: null, url: "https://ipindia.gov.in/", url_label: "IP India" },
};

export const ConfigContext = createContext(DEFAULT_CONFIG);
export const useConfig = () => useContext(ConfigContext);
