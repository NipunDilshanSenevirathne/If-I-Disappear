from datetime import date

from app.domain.claims import Claim, Entity, EvidenceRef, HouseholdSettings, Source
from app.domain.compile import compile_household, normalise_identifier
from app.domain.household import load_household
from app.engine.model import Freq, Policy
from app.verify.quotes import check_claim, find, normalise


def _settings(**kw):
    data = {"id": "t", "name": "T", "leaver": "amma", "departure": date(2026, 11, 1), "assessment_date": date(2026, 10, 25)}
    data.update(kw)
    return HouseholdSettings(**data)


ENTITIES = [
    Entity(id="amma", kind="person", name="Amma", role="leaver"),
    Entity(id="appa", kind="person", name="Appa", role="backup"),
    Entity(id="r", kind="responsibility", name="renew the permit"),
    Entity(id="rt", kind="route", name="at the office"),
    Entity(id="permit", kind="resource", resource_kind="permit", name="the permit"),
]


def _claim(cid, predicate, subject, obj=None, **kw):
    return Claim(id=cid, predicate=predicate, subject=subject, object=obj, review=kw.pop("review", "accepted"), **kw)


def test_unknown_entities_are_reported_not_guessed():
    c = compile_household(_settings(), ENTITIES, [_claim("x1", "DOES", "ghost", "r"), _claim("x2", "ROUTE_NEEDS", "nope", "permit")])
    assert any("unknown subject 'ghost'" in d for d in c.diagnostics)
    assert any("unknown route 'nope'" in d for d in c.diagnostics)


def test_only_accepted_claims_compile():
    c = compile_household(_settings(), ENTITIES, [_claim("x1", "DOES", "appa", "r", review="unreviewed")])
    assert c.world.responsibilities["r"].owners == []


def test_renewal_becomes_a_dated_task_and_critical_needs_a_key_step():
    claims = [
        _claim("c1", "ROUTE", "r", "rt"),
        _claim("c2", "VALID_UNTIL", "permit", date=date(2026, 11, 20)),
        _claim("c3", "RENEWS", "r", "permit"),
        _claim("c4", "IMPORTANCE", "r", value="3"),
    ]
    c = compile_household(_settings(), ENTITIES, claims)
    r = c.world.responsibilities["r"]
    assert r.recurrence.freq is Freq.ONCE and r.recurrence.anchor == date(2026, 11, 20)
    assert r.policy is Policy.STANDARD  # critical without a key step falls back to standard
    assert r.awareness_required
    c = compile_household(_settings(), ENTITIES, claims + [_claim("c5", "KEY_STEP", "r", value="show it")])
    assert c.world.responsibilities["r"].policy is Policy.CRITICAL


def test_household_can_override_the_handover_level():
    claims = [
        _claim("c1", "ROUTE", "r", "rt"),
        _claim("c4", "IMPORTANCE", "r", value="3"),
        _claim("c5", "HANDOVER_LEVEL", "r", value="light"),
    ]
    c = compile_household(_settings(), ENTITIES, claims)
    assert c.world.responsibilities["r"].policy is Policy.LIGHT


def test_amount_contradiction_is_kept_not_averaged():
    claims = [_claim("a1", "AMOUNT", "r", value="Rs 6,000"), _claim("a2", "AMOUNT", "r", value="Rs 6,500")]
    c = compile_household(_settings(), ENTITIES, claims)
    assert len(c.contradictions) == 1
    assert [v for v, _ in c.contradictions[0].values] == ["Rs 6,000", "Rs 6,500"]


def test_identifiers_are_normalised():
    assert normalise_identifier("+94 77 123 4567") == "0771234567"
    assert normalise_identifier("077-XXX-0101") == "077XXX0101"


# ---------------------------------------------------------------- quotes


def test_quote_matching_is_exact_after_light_normalisation():
    text = "The app sends a code to my number   every time.\nIt’s quick."
    assert find(text, "sends a code to my number every time.") is not None
    assert find(text, "It's quick.") is not None  # curly apostrophe
    assert find(text, "sends a code to my phone") is None  # no fuzzy matching
    assert normalise("  a \n b ") == "a b"


def test_claims_without_support_are_flagged():
    src = Source(id="S1", kind="voice", title="t", text="I pay it by the 10th. I use the app.")
    ok = Claim(id="c1", predicate="DOES", subject="amma", object="r", evidence=[EvidenceRef(source_id="S1", quote="I pay it by the 10th.")])
    bad = Claim(
        id="c2", predicate="DOES", subject="amma", object="r", evidence=[EvidenceRef(source_id="S1", quote="I pay it on the 15th.")]
    )
    none = Claim(id="c3", predicate="DOES", subject="amma", object="r")
    review = Claim(id="c4", predicate="HANDOVER_LEVEL", subject="r", value="light", derivation="household_review")
    sources = {"S1": src}
    r_ok, r_bad = check_claim(ok, sources), check_claim(bad, sources)
    assert r_ok.supported and r_ok.checks[0].locator == "sentence 1"
    assert not r_bad.supported and r_bad.checks[0].closest
    assert not check_claim(none, sources).supported
    assert check_claim(review, sources).supported


def test_locators_for_documents_and_pdfs():
    doc = Source(id="D", kind="image", title="bill", text="LANKA POWER\nDue date: 10 Nov 2026\nPay at any post office.")
    pdf = Source(id="P", kind="pdf", title="schedule", text="[Page 1]\nPolicy\n[Page 2]\nHow to renew\nRenew early.")
    sources = {"D": doc, "P": pdf}
    c1 = Claim(id="a", predicate="FACT", subject="x", evidence=[EvidenceRef(source_id="D", quote="Due date: 10 Nov 2026")])
    c2 = Claim(id="b", predicate="FACT", subject="x", evidence=[EvidenceRef(source_id="P", quote="Renew early.")])
    assert check_claim(c1, sources).checks[0].locator == "line 2"
    assert check_claim(c2, sources).checks[0].locator == "page 2, line 2"


def test_every_demo_claim_quotes_its_source_exactly():
    h = load_household("perera")
    sources = h.source_map()
    for claim in h.claims:
        result = check_claim(claim, sources)
        assert result.supported, (claim.id, result.issues)


def test_a_value_in_the_wrong_field_is_moved_not_guessed():
    from app.ai.schemas import ProposedClaim
    from app.workflows.ingest import tidy

    # a date written in `object` for VALID_UNTIL goes to `date`
    pc = tidy(ProposedClaim(predicate="VALID_UNTIL", subject="insurance", object="2026-11-20", quotes=["to 20 Nov 2026"]))
    assert (pc.date, pc.object) == ("2026-11-20", None)
    # a number written in `object` for LEAD_TIME goes to `value`
    pc = tidy(ProposedClaim(predicate="LEAD_TIME", subject="r_insurance", object="7", quotes=["at least 7 days"]))
    assert (pc.value, pc.object) == ("7", None)
    # nothing moves when the right field is already filled, or when `object` is used
    pc = tidy(ProposedClaim(predicate="VALID_UNTIL", subject="insurance", object="x", date="2026-11-20", quotes=["q"]))
    assert (pc.date, pc.object) == ("2026-11-20", "x")
    pc = tidy(ProposedClaim(predicate="CAN_DO", subject="sunil", object="r_bill", quotes=["q"]))
    assert (pc.object, pc.value) == ("r_bill", None)
    # a name in `object` for VALID_UNTIL is not a date, so it stays (and is reported later)
    pc = tidy(ProposedClaim(predicate="VALID_UNTIL", subject="insurance", object="next year", quotes=["q"]))
    assert (pc.date, pc.object) == (None, "next year")
