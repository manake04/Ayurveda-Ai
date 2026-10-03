"""Answer languages. English and Hindi are handled by the LLM directly; the others go
through Bhashini translation when it is configured."""

NATIVE_LANGUAGES = {"en": "English", "hi": "हिंदी"}

# Scheduled Indian languages offered through Bhashini (ISO 639 codes as Bhashini uses them).
BHASHINI_LANGUAGES = {
    "as": "অসমীয়া",
    "bn": "বাংলা",
    "gu": "ગુજરાતી",
    "kn": "ಕನ್ನಡ",
    "ml": "മലയാളം",
    "mr": "मराठी",
    "or": "ଓଡ଼ିଆ",
    "pa": "ਪੰਜਾਬੀ",
    "ta": "தமிழ்",
    "te": "తెలుగు",
    "ur": "اردو",
}
