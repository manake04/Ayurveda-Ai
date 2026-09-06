"""Access-and-Benefit-Sharing (ABS) compliance helper.

A guided checklist, not a legal determination: it turns a handful of yes/no facts about
the user's situation into a plain list of which ABS-related duties are likely to apply
and which corpus sources explain them, so the user knows what to go verify.
"""
from typing import List

from app.models import ABSRequest, ABSResponseItem


def build_checklist(req: ABSRequest) -> List[ABSResponseItem]:
    items: List[ABSResponseItem] = []

    items.append(
        ABSResponseItem(
            step="Does the Biological Diversity Act's ABS regime apply at all?",
            applies=req.uses_biological_material and req.sourced_from_india,
            detail=(
                "Applies because the formulation uses biological material sourced from India."
                if (req.uses_biological_material and req.sourced_from_india)
                else "Does not apply on the facts given -- either no biological material is used, "
                "or it was not sourced from India. Re-check if sourcing changes."
            ),
            citation_ids=["in-biodiversity-act-2002-2023-amendment"],
        )
    )

    ayush_exempt = req.user_is_registered_ayush_practitioner and req.knowledge_is_codified_traditional_knowledge
    items.append(
        ABSResponseItem(
            step="Does the 2023 AYUSH / codified-traditional-knowledge exemption likely help?",
            applies=ayush_exempt,
            detail=(
                "You may qualify for the simplified/exempted treatment the 2023 amendment "
                "introduced for registered AYUSH practitioners using codified traditional "
                "knowledge -- confirm the exact scope with the NBA/State Biodiversity Board, "
                "this is not automatic for every product a practitioner sells."
                if ayush_exempt
                else "On the facts given, this exemption route does not clearly apply -- assume "
                "full NBA approval is needed before IP filing or commercialisation."
            ),
            citation_ids=["in-biodiversity-act-2002-2023-amendment", "in-biodiversity-rules-2024"],
        )
    )

    items.append(
        ABSResponseItem(
            step="Is NBA prior approval likely needed before seeking IP or commercialising?",
            applies=req.uses_biological_material
            and req.sourced_from_india
            and req.ip_or_commercialisation_sought
            and not ayush_exempt,
            detail=(
                "Seek National Biodiversity Authority approval (via the simplified Biological "
                "Diversity Rules, 2024 procedure) BEFORE filing for IP rights or commercialising, "
                "and fix benefit-sharing terms with the NBA."
                if (req.uses_biological_material and req.sourced_from_india and req.ip_or_commercialisation_sought and not ayush_exempt)
                else "Based on the facts given, mandatory prior NBA approval before IP/commercialisation "
                "does not clearly apply -- but re-check if any fact changes."
            ),
            citation_ids=["in-biodiversity-rules-2024", "in-patents-form1-source-disclosure"],
        )
    )

    items.append(
        ABSResponseItem(
            step="Will a patent application need source-of-biological-material disclosure?",
            applies=req.uses_biological_material and req.sourced_from_india,
            detail=(
                "Any Indian patent application must disclose the source and geographical origin "
                "of biological material used, in the specification/Form 1 -- separate from, and "
                "in addition to, NBA approval."
                if (req.uses_biological_material and req.sourced_from_india)
                else "Not clearly triggered on the facts given."
            ),
            citation_ids=["in-patents-form1-source-disclosure"],
        )
    )

    items.append(
        ABSResponseItem(
            step="Do international ABS duties (Nagoya Protocol / CBD) also apply?",
            applies=req.exporting_or_partnering_abroad and req.uses_biological_material,
            detail=(
                "If you are exporting to, or partnering with, an entity in another Nagoya "
                "Protocol party state, that state's own ABS compliance measures can apply on top "
                "of India's domestic regime -- check the destination country's ABS checkpoint "
                "requirements separately."
                if (req.exporting_or_partnering_abroad and req.uses_biological_material)
                else "Not clearly triggered on the facts given."
            ),
            citation_ids=["intl-cbd-1992", "intl-nagoya-protocol-2010"],
        )
    )

    items.append(
        ABSResponseItem(
            step="Will an international patent filing need genetic-resource / TK origin disclosure?",
            applies=req.exporting_or_partnering_abroad and req.uses_biological_material,
            detail=(
                "Once the WIPO Treaty on IP, Genetic Resources and Associated Traditional "
                "Knowledge (2024) is in force for your filing destination, patent applications "
                "there based on genetic resources or associated TK must disclose the country of "
                "origin/source, or declare it is unknown."
                if (req.exporting_or_partnering_abroad and req.uses_biological_material)
                else "Not clearly triggered on the facts given."
            ),
            citation_ids=["intl-wipo-gratk-treaty-2024"],
        )
    )

    return items
