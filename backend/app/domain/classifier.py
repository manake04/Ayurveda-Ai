"""Formulation-classification flow.

Implements the decision tree the problem statement describes: ask the minimum
clarifying questions to determine whether a product is a classical/generic medicine, a
patent-or-proprietary medicine, a new/non-classical drug, a phytopharmaceutical, an
Ayurveda-Aahar/nutraceutical, or a cosmetic -- then states each category's requirements
and its IP/ABS posture.

The tree is expressed as a simple dict-based state machine keyed by node id so the
frontend can drive it one question at a time (`POST /classify` with the list of answers
given so far). This keeps the flow stateless on the backend (no session storage needed)
and trivially testable.
"""

# Each node is either a question node {"type": "question", ...} or a leaf result node
# {"type": "result", ...}. `yes`/`no` point to the next node id.
TREE: dict[str, dict] = {
    "q1_classical": {
        "type": "question",
        "text": (
            "Is the formulation AND its method of preparation described exactly as-is in an "
            "authoritative text listed in the First Schedule to the Drugs and Cosmetics Act "
            "(e.g. Charaka Samhita, Sushruta Samhita, Bhaishajya Ratnavali, Ashtanga Hridaya, etc.)?"
        ),
        "yes": "r_classical",
        "no": "q2_only_first_schedule_ingredients",
    },
    "q2_only_first_schedule_ingredients": {
        "type": "question",
        "text": (
            "Does it use ONLY ingredients that are named in First-Schedule authoritative texts, "
            "just combined, dosed, or processed differently from any single classical formula?"
        ),
        "yes": "q2b_schedule_e1",
        "no": "q3_phytopharmaceutical",
    },
    "q2b_schedule_e1": {
        "type": "question",
        "text": "Does any ingredient fall under Schedule E(1) of the Drugs and Cosmetics Rules (potent/restricted ingredients)?",
        "yes": "r_proprietary_e1",
        "no": "r_proprietary_standard",
    },
    "q3_phytopharmaceutical": {
        "type": "question",
        "text": (
            "Is it a purified, standardised fraction of a plant/botanical with quantified marker "
            "or bio-active compounds, intended to be developed with pre-clinical and clinical "
            "safety/efficacy data (even though the source plant is traditionally used)?"
        ),
        "yes": "r_phytopharmaceutical",
        "no": "q4_food",
    },
    "q4_food": {
        "type": "question",
        "text": (
            "Is it meant to be sold as a food / nutritional product prepared per classical "
            "Ayurvedic texts, with NO disease-diagnosis, treatment or cure claim?"
        ),
        "yes": "r_ayurveda_aahar",
        "no": "q5_cosmetic",
    },
    "q5_cosmetic": {
        "type": "question",
        "text": (
            "Is it applied externally purely for cleansing, beautifying, or altering appearance, "
            "with no therapeutic or disease claim?"
        ),
        "yes": "r_cosmetic",
        "no": "r_new_drug",
    },
    "r_classical": {
        "type": "result",
        "category": "Classical / generic Ayurvedic medicine",
        "requires": (
            "No fresh safety/efficacy studies -- licensing needs Good Manufacturing Practice "
            "(Schedule T) compliance and the classical text reference itself (Drugs & Cosmetics "
            "Act, Section 3(a)/(h), First Schedule)."
        ),
        "ip_abs_posture": (
            "Largely undivided traditional knowledge. Faces the Section 3(p) Patents Act bar -- "
            "not patentable as such. Defended mainly DEFENSIVELY, through the Traditional "
            "Knowledge Digital Library (TKDL) and, for a place-linked variant, a Geographical "
            "Indication. If sourced from Indian biological material, Biological Diversity Act "
            "ABS duties can still apply when commercialised or exported, though the 2023 "
            "amendment eases this for registered AYUSH practitioners using codified TK."
        ),
        "relevant_corpus_ids": [
            "in-patents-3p",
            "in-dc-act-classical-drugs",
            "in-tkdl",
            "in-gi-act-1999",
            "in-biodiversity-act-2002-2023-amendment",
        ],
    },
    "r_proprietary_standard": {
        "type": "result",
        "category": "Patent-or-proprietary Ayurvedic medicine (standard route)",
        "requires": (
            "Published literature / pilot-study evidence of the ingredients' effectiveness in "
            "the new combination, plus GMP compliance (D&C Rules, Rule 158-B)."
        ),
        "ip_abs_posture": (
            "The specific combination/ratio/process can potentially be protected (trade secret, "
            "or a narrow patent claim if a genuine inventive step over the traditional "
            "combination can be shown -- often difficult under Section 3(p)). Branding is "
            "protectable via trademark. Biological-material source disclosure and possible NBA "
            "approval still apply if Indian biological resources are used and IP/commercialisation "
            "is sought."
        ),
        "relevant_corpus_ids": [
            "in-dc-act-classical-drugs",
            "in-patents-3p",
            "in-trademarks-act-1999",
            "in-patents-form1-source-disclosure",
        ],
    },
    "r_proprietary_e1": {
        "type": "result",
        "category": "Patent-or-proprietary Ayurvedic medicine (Schedule E(1) route)",
        "requires": (
            "Full safety studies, effectiveness proof and clinical evidence are mandatory before "
            "licensing, because a Schedule E(1) (potent/restricted) ingredient is present."
        ),
        "ip_abs_posture": (
            "Same posture as the standard proprietary route, but the mandatory clinical/safety "
            "data package also strengthens a genuine patent case (more inventive-step and "
            "efficacy evidence to point to) -- discuss with a patent agent whether the added "
            "data supports a defensible claim beyond the known combination."
        ),
        "relevant_corpus_ids": [
            "in-dc-act-classical-drugs",
            "in-patents-3p",
            "in-trademarks-act-1999",
        ],
    },
    "r_phytopharmaceutical": {
        "type": "result",
        "category": "Phytopharmaceutical drug",
        "requires": (
            "Pre-clinical and clinical safety/efficacy data, defined qualitative and quantitative "
            "composition of the bio-active fraction, under the New Drugs and Clinical Trials "
            "Rules, 2019 phytopharmaceutical chapter."
        ),
        "ip_abs_posture": (
            "Genuine, strong patent potential -- this is new, non-traditional data and "
            "characterisation, not just the known plant. Still requires biological-material "
            "source disclosure (Patents Act Section 10(4)(ii)(D)) and, if the source plant is "
            "Indian, Biological Diversity Act / NBA approval before IP filing or commercialisation. "
            "International filings should budget for the WIPO GRATK Treaty's genetic-resource / "
            "TK origin disclosure once it is in force for the target country."
        ),
        "relevant_corpus_ids": [
            "in-ndct-rules-phytopharmaceutical",
            "in-patents-form1-source-disclosure",
            "in-biodiversity-act-2002-2023-amendment",
            "intl-wipo-gratk-treaty-2024",
        ],
    },
    "r_ayurveda_aahar": {
        "type": "result",
        "category": "Ayurveda-Aahar / nutraceutical",
        "requires": (
            "FSSAI licensing under the Ayurveda Aahara Regulations, 2022 (Category A, matched to "
            "a Schedule A classical text); strictly no disease-cure claims."
        ),
        "ip_abs_posture": (
            "Brand and packaging are protectable (trademark, design); the recipe itself, if "
            "purely classical, sits in the same traditional-knowledge posture as a classical "
            "medicine. Advertising must stay within the Drugs and Magic Remedies Act's limits -- "
            "a disease-cure claim would also pull the product out of the food category entirely "
            "and into drug regulation."
        ),
        "relevant_corpus_ids": [
            "in-fssai-ayurveda-aahara-2022",
            "in-magic-remedies-act-1954",
            "in-trademarks-act-1999",
        ],
    },
    "r_cosmetic": {
        "type": "result",
        "category": "Cosmetic",
        "requires": (
            "Cosmetic licensing/registration under the Drugs and Cosmetics Act framework for "
            "cosmetics (not the drug provisions); no therapeutic claims permitted."
        ),
        "ip_abs_posture": (
            "Brand, packaging/bottle design, and any genuinely new formulation or delivery "
            "system are protectable (trademark, design, and potentially patent if inventive). "
            "Biological-material and ABS duties still apply if Indian plant/biological "
            "ingredients are used."
        ),
        "relevant_corpus_ids": ["in-trademarks-act-1999", "in-designs-act-2000"],
    },
    "r_new_drug": {
        "type": "result",
        "category": "New / non-classical Ayurvedic drug",
        "requires": (
            "Proof of safety and effectiveness under Rule 170 of the Drugs and Cosmetics Rules "
            "(a formulation not in any First-Schedule text, or a classical formulation repurposed "
            "for a new indication, route or dosage)."
        ),
        "ip_abs_posture": (
            "Genuine patent potential, similar to the phytopharmaceutical route, because real "
            "clinical evidence is generated. Source-disclosure and Biological Diversity Act / "
            "NBA obligations apply in full if Indian biological material or associated "
            "traditional knowledge was used in developing it."
        ),
        "relevant_corpus_ids": [
            "in-ndct-rules-phytopharmaceutical",
            "in-patents-form1-source-disclosure",
            "in-biodiversity-act-2002-2023-amendment",
        ],
    },
}

START_NODE = "q1_classical"


def step(answers: list[str]) -> dict:
    """Walk the tree using the answers given so far ('yes'/'no', case-insensitive).

    Returns either the next question or, once a leaf is reached, the final result.
    """
    node_id = START_NODE
    for ans in answers:
        node = TREE[node_id]
        if node["type"] != "question":
            break  # already reached a result; extra answers are ignored
        normalised = ans.strip().lower()
        if normalised not in ("yes", "no"):
            raise ValueError(f"Answer must be 'yes' or 'no', got: {ans!r}")
        node_id = node[normalised]

    node = TREE[node_id]
    if node["type"] == "question":
        return {
            "done": False,
            "question_id": node_id,
            "question_text": node["text"],
            "options": ["yes", "no"],
            "result": None,
        }
    return {
        "done": True,
        "question_id": None,
        "question_text": None,
        "options": None,
        "result": {
            "category": node["category"],
            "requires": node["requires"],
            "ip_abs_posture": node["ip_abs_posture"],
            "relevant_corpus_ids": node["relevant_corpus_ids"],
        },
    }
