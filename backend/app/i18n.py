"""Multilingual delivery -- staged, per the problem statement's own build plan.

Stage 1 (this MVP): the corpus and generated answers are English; the UI chrome (labels,
buttons, disclaimer) ships in English + Hindi as a proof of the i18n plumbing.

Stage 4 (roadmap): full multilingual retrieval + generation + voice via Bhashini
(National Language Translation Mission) -- `translate_via_bhashini` below is a real,
guarded integration point: it only activates if BHASHINI_API_KEY etc. are configured,
and otherwise returns the original text unchanged with `translated=False` so the caller
can show an honest "translation not configured" state instead of silently mistranslating.
"""
from typing import Dict

import requests

from app import config

UI_STRINGS: Dict[str, Dict[str, str]] = {
    "en": {
        "app_title": "IP-SAKTI Sahayak",
        "tagline": "Multilingual, source-cited IP & regulatory guidance for Ayurveda",
        "jurisdiction_india": "India",
        "jurisdiction_international": "International",
        "jurisdiction_both": "Both (kept separate)",
        "ask_placeholder": "Ask an IP or regulatory question about your Ayurvedic product…",
        "disclaimer": config.DISCLAIMER,
        "classify_cta": "Not sure how your product is classified? Start here.",
        "escalate_cta": "Escalate to a human IP facilitator",
    },
    "hi": {
        "app_title": "आईपी-शक्ति सहायक",
        "tagline": "आयुर्वेद के लिए बहुभाषी, स्रोत-उद्धृत आईपी और नियामक मार्गदर्शन",
        "jurisdiction_india": "भारत",
        "jurisdiction_international": "अंतर्राष्ट्रीय",
        "jurisdiction_both": "दोनों (अलग-अलग रखे गए)",
        "ask_placeholder": "अपने आयुर्वेदिक उत्पाद के बारे में आईपी या नियामक प्रश्न पूछें…",
        "disclaimer": (
            "आईपी-शक्ति सहायक सामान्य जानकारी देता है, यह कानूनी सलाह नहीं है। "
            "किसी भी निर्णय से पहले उद्धृत स्रोत की पुष्टि करें और योग्य आईपी वकील से परामर्श लें।"
        ),
        "classify_cta": "अपने उत्पाद का वर्गीकरण नहीं पता? यहाँ से शुरू करें।",
        "escalate_cta": "मानव आईपी सहायक से संपर्क करें",
    },
}


def get_ui_strings(language: str) -> Dict[str, str]:
    return UI_STRINGS.get(language, UI_STRINGS["en"])


def translate_via_bhashini(text: str, target_lang: str) -> dict:
    """Best-effort call to a Bhashini-style translation pipeline.

    Returns {"text": ..., "translated": bool, "note": str}. Never raises -- a translation
    failure must degrade to showing the original text, not break the assistant.
    """
    if not (config.BHASHINI_API_KEY and config.BHASHINI_USER_ID and config.BHASHINI_PIPELINE_ID):
        return {
            "text": text,
            "translated": False,
            "note": "Bhashini not configured in this deployment -- showing original text. "
            "See .env.example to wire up a real pipeline id/key.",
        }
    try:
        # Placeholder for the real Bhashini pipeline call (NLTM ULCA compute endpoint).
        # Left unimplemented in this MVP by design -- wire this up in Stage 4 of the roadmap.
        resp = requests.post(
            "https://meity-auth.ulcacontrib.org/ulca/apis/v0/model/compute",
            headers={"Authorization": config.BHASHINI_API_KEY},
            json={"pipelineId": config.BHASHINI_PIPELINE_ID, "input": [{"source": text}], "target": target_lang},
            timeout=8,
        )
        resp.raise_for_status()
        data = resp.json()
        translated_text = data.get("pipelineResponse", [{}])[0].get("output", [{}])[0].get("target", text)
        return {"text": translated_text, "translated": True, "note": "Translated via Bhashini."}
    except Exception as exc:  # noqa: BLE001
        return {"text": text, "translated": False, "note": f"Bhashini call failed, showing original text: {exc}"}
