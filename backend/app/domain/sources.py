"""Authoritative sources a user can go to directly, and paid sources that need consent."""

FREE_SOURCES = [
    {
        "name": "India Code",
        "url": "https://www.indiacode.nic.in/",
        "description": "Official text of central Acts and rules: Patents, Trade Marks, GI, Designs, "
        "Biological Diversity, Drugs and Cosmetics.",
    },
    {
        "name": "IP India",
        "url": "https://ipindia.gov.in/",
        "description": "Patent, trade mark, design and GI registries, public search and e-filing forms.",
    },
    {
        "name": "National Biodiversity Authority",
        "url": "https://nbaindia.org/",
        "description": "Access-and-benefit-sharing approvals and forms under the Biological Diversity Act.",
    },
    {
        "name": "Traditional Knowledge Digital Library",
        "url": "http://www.tkdl.res.in/",
        "description": "India's defensive prior-art database of traditional knowledge (examiner access).",
    },
    {
        "name": "Ministry of Ayush",
        "url": "https://ayush.gov.in/",
        "description": "Policy, notifications and regulatory updates for Ayurveda and other AYUSH systems.",
    },
    {
        "name": "FSSAI",
        "url": "https://www.fssai.gov.in/",
        "description": "Food regulations, including the Ayurveda Aahara regulations.",
    },
    {
        "name": "WIPO PATENTSCOPE",
        "url": "https://patentscope.wipo.int/",
        "description": "Search international (PCT) patent applications and national collections.",
    },
    {
        "name": "WIPO Lex",
        "url": "https://www.wipo.int/wipolex/",
        "description": "Treaties and IP laws of WIPO member states.",
    },
]

# Subscription databases. Nothing is connected yet: consent is recorded so that a future
# connector can only be used for sessions that explicitly allowed it.
PAID_CONNECTORS = [
    {
        "id": "manupatra",
        "name": "Manupatra",
        "url": "https://www.manupatra.com/",
        "description": "Indian case law, statutes and commentary (your own subscription).",
    },
    {
        "id": "scc-online",
        "name": "SCC Online",
        "url": "https://www.scconline.com/",
        "description": "Indian and international case law (your own subscription).",
    },
]
PAID_CONNECTOR_IDS = {c["id"] for c in PAID_CONNECTORS}
