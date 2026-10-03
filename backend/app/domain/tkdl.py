"""TKDL / prior-art pointer.

TKDL itself is not a public API (it is accessed by patent examiners under non-disclosure
agreements), so this module cannot query it live. What it CAN honestly do -- and what the
problem statement asks for -- is act as a *pointer*: explain what TKDL is, tell the user
what to go search and where, and hand back complementary public prior-art search links a
user or their agent can actually run themselves today.
"""

from app.schemas.tools import SearchLink, TKDLPointerResponse

TKDL_URL = "http://www.tkdl.res.in/"


def build_pointer(query: str) -> TKDLPointerResponse:
    guidance = (
        f"TKDL itself is not publicly searchable (it's shared with patent examiners under "
        f"non-disclosure agreements), so I can't run a live TKDL search for '{query}' here. "
        "What I can tell you: if your formulation or a close variant already appears in "
        "classical texts, expect examiners at the Indian Patent Office and major foreign "
        "offices (EPO, USPTO, JPO, UKIPO and others with TKDL access agreements) to have it "
        "available as prior art -- which is exactly the point of TKDL as a *defensive* tool "
        "against biopiracy. Practically: (1) ask a registered patent agent to run a formal "
        "TKDL search as part of a patentability/freedom-to-operate opinion; (2) in parallel, "
        "run the public prior-art searches below yourself to get an early signal; (3) if your "
        "formulation is squarely classical/known, plan your IP strategy around GI/trademark/"
        "trade-secret protection rather than a patent, since Section 3(p) will likely apply."
    )

    search_links = [
        SearchLink(
            name="Indian Patent Office -- InPASS public search",
            url="https://ipindiaservices.gov.in/publicsearch",
            note="Search granted/published Indian patents and applications for similar formulations.",
        ),
        SearchLink(
            name="Espacenet (EPO)",
            url="https://worldwide.espacenet.com/",
            note="Free global patent prior-art search, widely used alongside TKDL by examiners.",
        ),
        SearchLink(
            name="Google Patents",
            url="https://patents.google.com/",
            note="Fast free-text search across global patent literature, good for an initial scan.",
        ),
        SearchLink(
            name="WIPO PATENTSCOPE",
            url="https://patentscope.wipo.int/",
            note="Search PCT international applications and many national collections.",
        ),
    ]

    return TKDLPointerResponse(
        query=query,
        guidance=guidance,
        search_links=search_links,
        tkdl_source_url=TKDL_URL,
    )
