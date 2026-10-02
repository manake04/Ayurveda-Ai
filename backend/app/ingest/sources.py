"""Registry of the authoritative public sources the corpus is built from.

Each :class:`Source` describes one primary source: how to turn a short *locator*
(a handle id, a CELEX id, a full URL) into a canonical ``source_url``, what
``source_name`` string entries from it carry (kept consistent with the convention
already used in ``corpus/*.json`` so the two never drift), and whether it can be
fetched programmatically at all.

``fetch_kind``:
    ``"html"``            – a normal web page; fetch + parse works.
    ``"pdf"``             – the primary document is a PDF; body-text verification
                            needs the optional ``pypdf`` extra, otherwise the
                            entry verifies by reachability only.
    ``"not_automatable"`` – the source cannot honestly be queried by a script
                            (captcha-gated search, or shared only under NDA).
                            ``scaffold`` refuses these; ``verify`` reports them as
                            ``unverifiable`` rather than guessing.

``name_style``:
    ``"exact"``    – a corpus entry's ``source_name`` equals :attr:`Source.name`.
    ``"prefixed"`` – it is ``name`` or ``f"{name} – <instrument>"`` (the India
                     Code / e-Gazette / WIPO-sub-treaty convention).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from urllib.parse import urlparse

FetchKind = str  # "html" | "pdf" | "not_automatable"


@dataclass(frozen=True)
class Source:
    id: str
    name: str  # the `source_name` (or its prefix) a corpus entry from here carries
    display_name: str  # fuller human description, for docs
    jurisdiction: str  # "India" | "International"
    homepage: str
    fetch_kind: FetchKind
    default_instrument_type: str  # statute | rule | treaty | regulation | registry | guidance
    locator_help: str
    url_template: Optional[str] = None  # uses `{locator}`; None ⇒ the locator is the full URL
    name_style: str = "exact"  # "exact" | "prefixed"
    access_notes: str = ""
    allowed_hosts: List[str] = field(default_factory=list)
    # other `source_name` prefixes seen in the existing hand-curated corpus for this source
    name_aliases: List[str] = field(default_factory=list)

    def build_url(self, locator: str) -> str:
        locator = locator.strip()
        if self.url_template is None:
            return locator
        return self.url_template.format(locator=locator)

    def source_name_for(self, instrument: Optional[str]) -> str:
        if self.name_style == "prefixed" and instrument:
            return f"{self.name} – {instrument}"
        return self.name

    def name_matches(self, source_name: str) -> bool:
        for base in (self.name, *self.name_aliases):
            if source_name == base:
                return True
            # tolerate en-dash / em-dash / hyphen as the "<base> <sep> <instrument>" separator
            if any(source_name.startswith(f"{base} {sep} ") for sep in ("–", "—", "-")):
                return True
        return False

    @property
    def automatable(self) -> bool:
        return self.fetch_kind != "not_automatable"


_SOURCES: List[Source] = [
    # ---- India ----
    Source(
        id="india-code",
        name="India Code",
        display_name="India Code (Ministry of Law & Justice)",
        jurisdiction="India",
        homepage="https://www.indiacode.nic.in/",
        fetch_kind="html",
        default_instrument_type="statute",
        name_style="prefixed",
        locator_help="A India Code handle, e.g. '123456789/1388' (the Patents Act, 1970), taken "
        "from the handle URL of the Act's landing page. A full indiacode.nic.in URL also works.",
        url_template="https://www.indiacode.nic.in/handle/{locator}",
        allowed_hosts=["indiacode.nic.in", "www.indiacode.nic.in"],
        name_aliases=["India Code / Department of Consumer Affairs"],
    ),
    Source(
        id="egazette",
        name="e-Gazette of India",
        display_name="e-Gazette of India (Department of Publication)",
        jurisdiction="India",
        homepage="https://egazette.gov.in/",
        fetch_kind="pdf",
        default_instrument_type="statute",
        name_style="prefixed",
        locator_help="The full https://egazette.gov.in/.../<file>.pdf URL of the gazette notification.",
        allowed_hosts=["egazette.gov.in", "www.egazette.gov.in"],
        access_notes="Notifications are PDFs; excerpt verification needs the optional `pypdf` extra.",
    ),
    Source(
        id="ipindia",
        name="Office of the Controller General of Patents, Designs & Trade Marks (IPO)",
        display_name="Office of the Controller General of Patents, Designs & Trade Marks",
        jurisdiction="India",
        homepage="https://www.ipindia.gov.in/",
        fetch_kind="pdf",
        default_instrument_type="rule",
        locator_help="The full https://www.ipindia.gov.in/... URL of the rules / manual / notice.",
        allowed_hosts=["ipindia.gov.in", "www.ipindia.gov.in"],
        access_notes="Rules and office manuals are mostly PDFs.",
    ),
    Source(
        id="inpass",
        name="Indian Patent Office – InPASS public search",
        display_name="Indian Patent Office public patent search (InPASS)",
        jurisdiction="India",
        homepage="https://ipindiaservices.gov.in/publicsearch",
        fetch_kind="not_automatable",
        default_instrument_type="registry",
        locator_help="(not automatable)",
        allowed_hosts=["ipindiaservices.gov.in"],
        access_notes="InPASS and the GI / Trade Marks / Designs registers are captcha-gated search "
        "front-ends with no public API — they cannot be scraped honestly. Look a record up by hand "
        "and add the entry with `scaffold --source india-code` or a hand-written entry.",
    ),
    Source(
        id="tkdl",
        name="Traditional Knowledge Digital Library (CSIR)",
        display_name="Traditional Knowledge Digital Library (CSIR & Ministry of Ayush)",
        jurisdiction="India",
        homepage="http://www.tkdl.res.in/",
        fetch_kind="not_automatable",
        default_instrument_type="registry",
        locator_help="(not automatable)",
        allowed_hosts=["tkdl.res.in", "www.tkdl.res.in"],
        access_notes="The TKDL database is shared with patent examiners under non-disclosure "
        "agreements and is not publicly queryable. Only its public 'about' pages can be fetched — "
        "see `app/tkdl.py`, the honest pointer this project ships.",
    ),
    Source(
        id="nba-abs",
        name="National Biodiversity Authority (NBA)",
        display_name="National Biodiversity Authority / ABS portal",
        jurisdiction="India",
        homepage="http://nbaindia.org/",
        fetch_kind="html",
        default_instrument_type="guidance",
        locator_help="The full http://nbaindia.org/... page URL (ABS guidelines, notifications, FAQs).",
        allowed_hosts=["nbaindia.org", "www.nbaindia.org"],
    ),
    Source(
        id="moefcc",
        name="Ministry of Environment, Forest and Climate Change (MoEFCC)",
        display_name="Ministry of Environment, Forest and Climate Change",
        jurisdiction="India",
        homepage="https://moef.gov.in/",
        fetch_kind="html",
        default_instrument_type="rule",
        locator_help="The full https://moef.gov.in/... page or PDF URL.",
        allowed_hosts=["moef.gov.in", "www.moef.gov.in"],
    ),
    Source(
        id="cdsco",
        name="Central Drugs Standard Control Organisation (CDSCO)",
        display_name="Central Drugs Standard Control Organisation",
        jurisdiction="India",
        homepage="https://cdsco.gov.in/",
        fetch_kind="pdf",
        default_instrument_type="rule",
        locator_help="The full https://cdsco.gov.in/... URL of the Act / Rules / guidance PDF.",
        allowed_hosts=["cdsco.gov.in", "www.cdsco.gov.in"],
    ),
    Source(
        id="fssai",
        name="Food Safety and Standards Authority of India (FSSAI)",
        display_name="Food Safety and Standards Authority of India",
        jurisdiction="India",
        homepage="https://www.fssai.gov.in/",
        fetch_kind="html",
        default_instrument_type="regulation",
        locator_help="The full https://www.fssai.gov.in/... page or gazette-PDF URL.",
        allowed_hosts=["fssai.gov.in", "www.fssai.gov.in"],
    ),
    Source(
        id="dpiit",
        name="Department for Promotion of Industry and Internal Trade (DPIIT)",
        display_name="Department for Promotion of Industry and Internal Trade",
        jurisdiction="India",
        homepage="https://dpiit.gov.in/",
        fetch_kind="html",
        default_instrument_type="guidance",
        locator_help="The full https://dpiit.gov.in/... policy page URL.",
        allowed_hosts=["dpiit.gov.in", "www.dpiit.gov.in"],
    ),
    # ---- International ----
    Source(
        id="wipo",
        name="World Intellectual Property Organization (WIPO)",
        display_name="World Intellectual Property Organization",
        jurisdiction="International",
        homepage="https://www.wipo.int/",
        fetch_kind="html",
        default_instrument_type="treaty",
        name_style="prefixed",
        locator_help="The full https://www.wipo.int/... treaty-text or summary URL.",
        allowed_hosts=["wipo.int", "www.wipo.int", "patentscope.wipo.int"],
    ),
    Source(
        id="wto-trips",
        name="World Trade Organization – TRIPS Agreement text",
        display_name="World Trade Organization, TRIPS Agreement legal texts",
        jurisdiction="International",
        homepage="https://www.wto.org/english/tratop_e/trips_e/trips_e.htm",
        fetch_kind="html",
        default_instrument_type="treaty",
        locator_help="The full https://www.wto.org/english/... URL of the TRIPS article / legal text.",
        allowed_hosts=["wto.org", "www.wto.org"],
    ),
    Source(
        id="cbd",
        name="Convention on Biological Diversity (CBD) Secretariat",
        display_name="Convention on Biological Diversity Secretariat",
        jurisdiction="International",
        homepage="https://www.cbd.int/",
        fetch_kind="html",
        default_instrument_type="treaty",
        name_style="prefixed",
        locator_help="The full https://www.cbd.int/... article or protocol-text URL.",
        allowed_hosts=["cbd.int", "www.cbd.int"],
        name_aliases=["CBD Secretariat"],
    ),
    Source(
        id="eur-lex",
        name="EUR-Lex – Official Journal of the European Union",
        display_name="EUR-Lex, Official Journal of the European Union",
        jurisdiction="International",
        homepage="https://eur-lex.europa.eu/",
        fetch_kind="html",
        default_instrument_type="regulation",
        locator_help="A CELEX id, e.g. '32004L0024' (the Traditional Herbal Medicinal Products "
        "Directive), or the full legal-content URL.",
        url_template="https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:{locator}",
        allowed_hosts=["eur-lex.europa.eu"],
    ),
    Source(
        id="who",
        name="World Health Organization (WHO)",
        display_name="World Health Organization",
        jurisdiction="International",
        homepage="https://www.who.int/",
        fetch_kind="html",
        default_instrument_type="guidance",
        locator_help="The full https://www.who.int/... publication or page URL.",
        allowed_hosts=["who.int", "www.who.int"],
    ),
    Source(
        id="upov",
        name="International Union for the Protection of New Varieties of Plants (UPOV)",
        display_name="International Union for the Protection of New Varieties of Plants",
        jurisdiction="International",
        homepage="https://www.upov.int/",
        fetch_kind="html",
        default_instrument_type="treaty",
        locator_help="The full https://www.upov.int/... convention-text or page URL.",
        allowed_hosts=["upov.int", "www.upov.int"],
    ),
    Source(
        id="us-fda",
        name="U.S. Food and Drug Administration (FDA)",
        display_name="United States Food and Drug Administration",
        jurisdiction="International",
        homepage="https://www.fda.gov/",
        fetch_kind="html",
        default_instrument_type="statute",
        locator_help="The full https://www.fda.gov/... page URL.",
        allowed_hosts=["fda.gov", "www.fda.gov"],
    ),
    Source(
        id="tga-australia",
        name="Australian Government — Therapeutic Goods Administration (TGA)",
        display_name="Australian Therapeutic Goods Administration",
        jurisdiction="International",
        homepage="https://www.tga.gov.au/",
        fetch_kind="html",
        default_instrument_type="regulation",
        locator_help="The full https://www.tga.gov.au/... page URL.",
        allowed_hosts=["tga.gov.au", "www.tga.gov.au"],
    ),
    Source(
        id="health-canada",
        name="Health Canada",
        display_name="Health Canada, Natural and Non-prescription Health Products Directorate",
        jurisdiction="International",
        homepage="https://www.canada.ca/en/health-canada.html",
        fetch_kind="html",
        default_instrument_type="regulation",
        locator_help="The full https://www.canada.ca/... page URL.",
        allowed_hosts=["canada.ca", "www.canada.ca"],
    ),
]

SOURCE_REGISTRY: Dict[str, Source] = {s.id: s for s in _SOURCES}


def get_source(source_id: str) -> Source:
    try:
        return SOURCE_REGISTRY[source_id]
    except KeyError:
        known = ", ".join(sorted(SOURCE_REGISTRY))
        raise KeyError(f"Unknown source id {source_id!r}. Known sources: {known}") from None


def source_for_url(url: str) -> Optional[Source]:
    """The registered source whose `allowed_hosts` contains this URL's host, if any."""
    host = (urlparse(url).hostname or "").lower()
    for s in _SOURCES:
        if host in s.allowed_hosts:
            return s
    return None


def registry_markdown() -> str:
    """Render the registry as the body of `docs/SOURCES.md`."""
    lines = [
        "# Corpus sources",
        "",
        "_Generated by `python scripts/ingest.py sources --markdown` — do not edit by hand._",
        "",
        "The corpus (`corpus/india.json`, `corpus/international.json`) is assembled from the open,",
        "authoritative primary sources below. `scaffold` can fetch from the ones marked",
        "**automatable**; the others must be transcribed by hand from the primary text.",
        "",
    ]
    for jurisdiction in ("India", "International"):
        lines += [f"## {jurisdiction}", ""]
        for s in _SOURCES:
            if s.jurisdiction != jurisdiction:
                continue
            lines += [
                f"### `{s.id}` — {s.display_name}",
                "",
                f"- **Homepage:** {s.homepage}",
                f"- **`source_name`:** `{s.name}`"
                + ("  (+ ` – <instrument>` suffix)" if s.name_style == "prefixed" else ""),
                f"- **Fetch:** {s.fetch_kind} "
                + ("(**automatable**)" if s.automatable else "(**not automatable**)"),
                f"- **Locator:** {s.locator_help}",
            ]
            if s.access_notes:
                lines.append(f"- **Notes:** {s.access_notes}")
            if s.automatable:
                example = "123456789/1388" if s.id == "india-code" else "<locator-or-url>"
                lines.append(
                    "- **Scaffold:** "
                    f"`python scripts/ingest.py scaffold --source {s.id} "
                    f"--locator {example} --regime <regime> --id <slug>`"
                )
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"
