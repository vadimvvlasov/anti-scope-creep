"""Demo data for local development, following docs/spec.md "Mock seed data".

Enabled with SEED_DEMO_DATA (default true). Seeding goes through the same store
operations as real analyses (start -> complete/fail), so seeded rows obey the same
status rules. Demo login: demo@example.com / password123.
"""

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID, uuid4

from starlette.concurrency import run_in_threadpool

from app.analyzer import STUB_EMAIL, STUB_FINDINGS, EmailDraftContent, FindingDraft
from app.auth import hash_password
from app.context import AppContext
from app.models import (
    ContractRecord,
    ContractStatus,
    EmailDraftRecord,
    FileType,
    FindingRecord,
    RiskCategory,
    RiskLevel,
    UserRecord,
)
from app.runner import run_analysis

DEMO_EMAIL = "demo@example.com"
OTHER_EMAIL = "other@example.com"
DEMO_PASSWORD = "password123"
PENDING_ANALYSIS_DELAY_SECONDS = 5

C, L = RiskCategory, RiskLevel

_CLAUSES: dict[tuple[RiskCategory, RiskLevel], tuple[str, str]] = {
    (C.SCOPE_CREEP, L.HIGH): (
        "The Contractor shall perform the services described in Exhibit A together with any additional work the Client considers necessary to complete the project.",
        "The Client can add work at will without a change order or extra fee, so the amount of work you owe is effectively open-ended.",
    ),
    (C.SCOPE_CREEP, L.MEDIUM): (
        "Deliverables include all materials reasonably required for a successful launch of the website.",
        "The deliverables are described by outcome rather than by a fixed list, which invites disputes about what is included in the price.",
    ),
    (C.SCOPE_CREEP, L.LOW): (
        "Minor adjustments requested during the review period shall be accommodated where practicable.",
        "Small extra tasks are expected on top of the agreed scope, though they are limited to what is practicable.",
    ),
    (C.UNLIMITED_REVISIONS, L.HIGH): (
        "The Client may request revisions to the deliverables until the Client is fully satisfied, at no additional cost.",
        "There is no cap on revision rounds and satisfaction is judged by the Client alone, so the work can continue indefinitely for the same fee.",
    ),
    (C.UNLIMITED_REVISIONS, L.MEDIUM): (
        "Revision rounds shall continue until the deliverables meet the Client's brand standards.",
        "Revisions are tied to a standard the Client controls, so the number of rounds is unpredictable.",
    ),
    (C.UNLIMITED_REVISIONS, L.LOW): (
        "The Client may request reasonable revisions to the deliverables during the project.",
        "The number of revision rounds is not stated, which leaves some room for extra work, although revisions are limited to what is reasonable.",
    ),
    (C.ONE_SIDED_TERMINATION, L.HIGH): (
        "The Client may terminate this Agreement at any time, with immediate effect and without payment for work in progress.",
        "The Client can end the engagement instantly and owe nothing for unfinished work you have already carried out.",
    ),
    (C.ONE_SIDED_TERMINATION, L.MEDIUM): (
        "The Client may terminate this Agreement on three days' written notice; the Contractor may terminate only for material breach.",
        "Only the Client has a convenient exit route, which leaves you committed while the Client is not.",
    ),
    (C.ONE_SIDED_TERMINATION, L.LOW): (
        "Either party may terminate this Agreement on fourteen days' written notice; fees for completed milestones remain payable.",
        "The notice period is short for a project of this size, although completed work is still paid for.",
    ),
    (C.IP_TRANSFER_BEFORE_PAYMENT, L.HIGH): (
        "All intellectual property rights in the deliverables shall vest in the Client upon creation, irrespective of payment.",
        "You lose ownership of the work the moment it is created, so unpaid invoices leave you with no leverage and nothing to withhold.",
    ),
    (C.IP_TRANSFER_BEFORE_PAYMENT, L.MEDIUM): (
        "Ownership of each milestone's deliverables transfers to the Client once that milestone is invoiced.",
        "Rights move to the Client on a partial payment step, before the full fee has been paid.",
    ),
    (C.IP_TRANSFER_BEFORE_PAYMENT, L.LOW): (
        "Ownership of the deliverables transfers to the Client on completion of the project.",
        "The clause does not say whether completion means delivery or final payment, which leaves the transfer timing slightly unclear.",
    ),
    (C.UNCAPPED_LIABILITY, L.HIGH): (
        "Contractor shall be liable for all losses, damages, costs, and claims arising from the services, without limitation.",
        "You would be responsible for any loss connected to the work with no upper limit, so a single claim could exceed the total contract value.",
    ),
    (C.UNCAPPED_LIABILITY, L.MEDIUM): (
        "Liability under this Agreement is limited to five times the total fees paid, excluding claims relating to data loss.",
        "The cap is several times the fee and data-loss claims are excluded from it, so your exposure can far exceed what you earn.",
    ),
    (C.UNCAPPED_LIABILITY, L.LOW): (
        "The Contractor shall be responsible for correcting any errors in the deliverables at its own cost.",
        "Fixing your own errors is normal, but the clause sets no time limit for raising them.",
    ),
    (C.UNFAVORABLE_PAYMENT_TERMS, L.HIGH): (
        "Contractor will be paid when Client receives payment from its customer.",
        "Your payment depends on a third party paying the Client, so it may be delayed indefinitely or never arrive.",
    ),
    (C.UNFAVORABLE_PAYMENT_TERMS, L.MEDIUM): (
        "Invoices are payable within 45 days of receipt.",
        "Net 45 is well beyond the common 30-day standard and delays your cash flow by several weeks.",
    ),
    (C.UNFAVORABLE_PAYMENT_TERMS, L.LOW): (
        "Invoices are payable within 40 days of receipt.",
        "Net 40 is a little slower than the common 30-day standard and stretches your cash flow slightly.",
    ),
}

_EMAIL_BULLETS: dict[RiskCategory, str] = {
    C.SCOPE_CREEP: "Scope: the relevant clause allows additional work to be added without a change order. I propose listing the deliverables and handling extra work through written change requests at an agreed rate.",
    C.UNLIMITED_REVISIONS: "Revisions: the agreement does not set a clear limit on revision rounds. I propose including two rounds of revisions, with further rounds billed at the hourly rate.",
    C.ONE_SIDED_TERMINATION: "Termination: the relevant clause lets the agreement end without fair notice or payment for work already done. I propose mutual termination on written notice, with payment for all work completed up to the termination date.",
    C.IP_TRANSFER_BEFORE_PAYMENT: "Intellectual property: ownership of the deliverables transfers before payment is received. I propose that ownership transfers once all invoices have been paid in full.",
    C.UNCAPPED_LIABILITY: "Liability: the relevant clause leaves my liability for losses without a reasonable cap. I propose capping total liability at the fees paid under the agreement.",
    C.UNFAVORABLE_PAYMENT_TERMS: "Payment terms: the payment period in the agreement is longer than usual. I propose payment within 30 days of the invoice date.",
}


@dataclass(frozen=True)
class SeedContract:
    title: str
    input: str  # "pdf", "txt", or "text" (pasted)
    status: ContractStatus
    days_ago: int
    findings: tuple[tuple[RiskCategory, RiskLevel], ...] = ()
    previous_success: bool = False  # for failed contracts: an earlier run succeeded
    stub: bool = False  # results are exactly the stub analyzer fixture


S = ContractStatus
DEMO_CONTRACTS = (
    SeedContract("Illustration License Agreement.pdf", "pdf", S.ANALYZING, 0),
    SeedContract("Website Redesign Agreement.pdf", "pdf", S.DONE, 2, stub=True),
    SeedContract("Brand Identity SOW.txt", "txt", S.DONE, 5, ((C.UNFAVORABLE_PAYMENT_TERMS, L.MEDIUM), (C.SCOPE_CREEP, L.LOW))),
    SeedContract("Mobile App Maintenance Contract.pdf", "pdf", S.DONE, 9, ((C.ONE_SIDED_TERMINATION, L.LOW),)),
    SeedContract("Copywriting Retainer", "text", S.DONE, 12),
    SeedContract("Consulting Agreement Q3.pdf", "pdf", S.FAILED, 15),
    SeedContract("Video Production Contract.pdf", "pdf", S.FAILED, 18, ((C.IP_TRANSFER_BEFORE_PAYMENT, L.HIGH),), previous_success=True),
    SeedContract("Logo Design Agreement.pdf", "pdf", S.DONE, 3, ((C.UNCAPPED_LIABILITY, L.HIGH), (C.SCOPE_CREEP, L.MEDIUM))),
    SeedContract("SEO Services Contract.txt", "txt", S.DONE, 6, ((C.UNCAPPED_LIABILITY, L.HIGH), (C.UNFAVORABLE_PAYMENT_TERMS, L.MEDIUM))),
    SeedContract("Data Migration SOW.pdf", "pdf", S.DONE, 21, ((C.SCOPE_CREEP, L.HIGH), (C.ONE_SIDED_TERMINATION, L.MEDIUM))),
    SeedContract("Newsletter Design Agreement.txt", "txt", S.DONE, 24, ((C.UNLIMITED_REVISIONS, L.HIGH),)),
    SeedContract("Product Photography Contract.pdf", "pdf", S.DONE, 27, ((C.IP_TRANSFER_BEFORE_PAYMENT, L.MEDIUM), (C.UNFAVORABLE_PAYMENT_TERMS, L.LOW))),
    SeedContract("Motion Graphics SOW", "text", S.DONE, 31, ((C.UNFAVORABLE_PAYMENT_TERMS, L.HIGH),)),
    SeedContract("Packaging Design Agreement.pdf", "pdf", S.DONE, 35, ((C.ONE_SIDED_TERMINATION, L.HIGH), (C.UNLIMITED_REVISIONS, L.MEDIUM))),
    SeedContract("CRM Integration Contract.pdf", "pdf", S.DONE, 39, ((C.SCOPE_CREEP, L.LOW),)),
    SeedContract("Editorial Retainer Agreement.txt", "txt", S.DONE, 43, ((C.UNFAVORABLE_PAYMENT_TERMS, L.MEDIUM), (C.SCOPE_CREEP, L.LOW))),
    SeedContract("Podcast Editing Contract.pdf", "pdf", S.DONE, 47, ((C.IP_TRANSFER_BEFORE_PAYMENT, L.HIGH),)),
    SeedContract("Landing Page Sprint SOW", "text", S.DONE, 52, ((C.UNLIMITED_REVISIONS, L.MEDIUM),)),
    SeedContract("Annual Report Layout Agreement.pdf", "pdf", S.DONE, 57, ((C.UNCAPPED_LIABILITY, L.MEDIUM), (C.ONE_SIDED_TERMINATION, L.LOW))),
    SeedContract("Technical Writing Contract.txt", "txt", S.DONE, 63, ((C.SCOPE_CREEP, L.MEDIUM),)),
    SeedContract("E-commerce Build Agreement.pdf", "pdf", S.DONE, 70, ((C.UNCAPPED_LIABILITY, L.HIGH), (C.IP_TRANSFER_BEFORE_PAYMENT, L.MEDIUM), (C.UNLIMITED_REVISIONS, L.LOW))),
    SeedContract("Social Campaign SOW.pdf", "pdf", S.DONE, 78, ((C.ONE_SIDED_TERMINATION, L.MEDIUM),)),
    SeedContract("Localization Services Contract.txt", "txt", S.DONE, 86, ((C.UNFAVORABLE_PAYMENT_TERMS, L.LOW), (C.UNLIMITED_REVISIONS, L.LOW))),
)
OTHER_CONTRACTS = (
    SeedContract("Partner Reseller Agreement.pdf", "pdf", S.DONE, 3, ((C.UNCAPPED_LIABILITY, L.HIGH),)),
)


def seed_demo_data(context: AppContext) -> list[tuple[UUID, UUID]]:
    """Create the demo users and contracts. Returns (contract_id, run_id) of pending runs.

    Runs on every startup; with a persistent database it seeds only once.
    """
    if context.store.get_user_by_email(DEMO_EMAIL) is not None:
        return []
    now = context.clock()
    password_hash = hash_password(DEMO_PASSWORD)
    pending: list[tuple[UUID, UUID]] = []
    for email, days_ago, contracts in (
        (DEMO_EMAIL, 120, DEMO_CONTRACTS),
        (OTHER_EMAIL, 90, OTHER_CONTRACTS),
    ):
        user = UserRecord(id=uuid4(), email=email, password_hash=password_hash, created_at=now - timedelta(days=days_ago))
        context.store.add_user(user)
        for spec in contracts:
            run = _seed_contract(context, user.id, spec, now)
            if run:
                pending.append(run)
    return pending


async def finish_pending_analyses(
    context: AppContext, runs: list[tuple[UUID, UUID]], delay: float = PENDING_ANALYSIS_DELAY_SECONDS
) -> None:
    """Let seeded `analyzing` contracts finish a few seconds after startup, like the mock."""
    await asyncio.sleep(delay)
    for contract_id, run_id in runs:
        await run_in_threadpool(run_analysis, context, contract_id, run_id)


def _seed_contract(
    context: AppContext, user_id: UUID, spec: SeedContract, now: datetime
) -> tuple[UUID, UUID] | None:
    store = context.store
    created = now if spec.status == S.ANALYZING else now - timedelta(days=spec.days_ago, hours=1)
    contract = _contract_record(user_id, spec, created)
    store.add_contract(contract)
    if spec.status == S.DONE or spec.previous_success:
        analyzed_at = created + timedelta(minutes=1)
        run_id = uuid4()
        store.start_analysis(user_id, contract.id, run_id, created)
        findings, email = _results(contract.id, spec, analyzed_at)
        store.complete_analysis(contract.id, run_id, findings, email, analyzed_at)
    run_id = uuid4()
    if spec.status == S.FAILED:
        store.start_analysis(user_id, contract.id, run_id, created + timedelta(minutes=2))
        store.fail_analysis(contract.id, run_id, created + timedelta(minutes=3))
    elif spec.status == S.ANALYZING:
        store.start_analysis(user_id, contract.id, run_id, created)
        return contract.id, run_id
    return None


def _contract_record(user_id: UUID, spec: SeedContract, created: datetime) -> ContractRecord:
    pasted = spec.input == "text"
    clauses = [_CLAUSES[key][0] for key in spec.findings]
    return ContractRecord(
        id=uuid4(),
        user_id=user_id,
        filename="" if pasted else spec.title,
        title=spec.title,
        file_type=FileType.PDF if spec.input == "pdf" else FileType.TXT,
        file_size=None if pasted else 120_000 + spec.days_ago * 517,
        source_text="\n\n".join([f"Sample contract: {spec.title}.", *clauses]),
        status=ContractStatus.UPLOADED,
        created_at=created,
        updated_at=created,
    )


def _results(
    contract_id: UUID, spec: SeedContract, analyzed_at: datetime
) -> tuple[list[FindingRecord], EmailDraftRecord | None]:
    drafts = list(STUB_FINDINGS) if spec.stub else [_finding_draft(*key) for key in spec.findings]
    findings = [FindingRecord(id=uuid4(), contract_id=contract_id, **d.model_dump()) for d in drafts]
    content = STUB_EMAIL if spec.stub else _email_content(drafts)
    if content is None:
        return findings, None
    email = EmailDraftRecord(id=uuid4(), contract_id=contract_id, created_at=analyzed_at, **content.model_dump())
    return findings, email


def _finding_draft(category: RiskCategory, level: RiskLevel) -> FindingDraft:
    quoted_text, explanation = _CLAUSES[(category, level)]
    return FindingDraft(category=category, risk_level=level, quoted_text=quoted_text, explanation=explanation)


def _email_content(findings: list[FindingDraft]) -> EmailDraftContent | None:
    """One bullet per high/medium finding; no email when there are none."""
    bullets = [f"- {_EMAIL_BULLETS[f.category]}" for f in findings if f.risk_level != RiskLevel.LOW]
    if not bullets:
        return None
    changes = "one change" if len(bullets) == 1 else "the following changes"
    body = "\n\n".join(
        [
            "Hello,",
            f"Thank you for sending over the agreement. Before signing, I would like to suggest {changes}:",
            "\n".join(bullets),
            "I am happy to discuss these points. Please let me know if these changes work for you.",
            "Best regards",
        ]
    )
    return EmailDraftContent(subject="Proposed changes to the agreement", body=body)
