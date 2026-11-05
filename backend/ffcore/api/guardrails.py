"""Guardrail and PII policies, the test panel and the internal evaluation endpoint (08-lite)."""

import uuid
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, select

from ffcore.api.common import (
    ERROR_RESPONSES,
    SessionDep,
    conflict,
    not_found,
    path_resource,
)
from ffcore.core.audit import audited
from ffcore.core.auth import Actor, require_role, resolve_actor
from ffcore.core.errors import ApiError
from ffcore.guardrails import service
from ffcore.guardrails.api_schemas import (
    DecisionOut,
    EvaluateRequest,
    EventOut,
    FindingOut,
    GuardrailPolicyCreate,
    GuardrailPolicyList,
    GuardrailPolicyOut,
    GuardrailPolicyUpdate,
    GuardrailTestRequest,
    GuardrailTestResult,
    NerFindingOut,
    NerRequest,
    NerResponse,
    PiiPolicyCreate,
    PiiPolicyList,
    PiiPolicyOut,
    PiiPolicyUpdate,
)
from ffcore.guardrails.builtin import (
    BUILTIN_DEFAULT,
    BUILTIN_KEY,
    BUILTIN_VERSION,
    DEFAULT_PII,
    EGRESS_PII_KEY,
)
from ffcore.guardrails.engine import (
    Decision,
    EgressStageDisabled,
    EvalContext,
    TextTooLong,
    evaluate,
)
from ffcore.guardrails.masking import MemoryTokenStore
from ffcore.guardrails.recognizers.ner import NerConfigError, local_ner
from ffcore.guardrails.schemas import (
    GuardrailConfigError,
    PiiPolicySpec,
    PolicySpec,
    ResolvedPolicy,
    Rule,
    validate_pii_policy,
    validate_policy,
)
from ffcore.knowledge.models import ModelMissing
from ffcore.models.guardrails import GuardrailPolicy, PiiPolicy
from ffcore.models.identity import Project

router = APIRouter(tags=["guardrails"], responses=ERROR_RESPONSES)

Reader = Annotated[Actor, Depends(require_role("analyst"))]
Admin = Annotated[Actor, Depends(require_role("admin", write=True))]
PolicyIdDep = Annotated[str, Depends(path_resource("policy_id"))]

PII_BASE = "/projects/{project_id}/pii-policies"
POLICY_BASE = "/projects/{project_id}/guardrail-policies"


async def service_actor(actor: Annotated[Actor, Depends(resolve_actor)]) -> Actor:
    # Same rule as 04a's /internal/embed; one shared helper once both packages are merged.
    if not (actor.actor_type == "system" and actor.actor_id == "service"):
        raise ApiError(403, "permission_error", "service_account_required", "Internal endpoint.")
    return actor


ServiceActor = Annotated[Actor, Depends(service_actor)]


def _engine_error(exc: Exception) -> ApiError:
    if isinstance(exc, GuardrailConfigError):
        return service.config_error(exc)
    if isinstance(exc, EgressStageDisabled):
        return ApiError(
            409, "conflict_error", "egress_stage_disabled", "The egress stage is disabled."
        )
    return ApiError(422, "invalid_request_error", "text_too_long", str(exc))


# --- PII policies ---


def pii_out(row: PiiPolicy) -> PiiPolicyOut:
    return PiiPolicyOut.model_validate({**row.__dict__, "builtin": False})


def builtin_pii_out(
    project_id: UUID, key: str = BUILTIN_KEY, spec: PiiPolicySpec = DEFAULT_PII
) -> PiiPolicyOut:
    return PiiPolicyOut(
        id=None,
        project_id=project_id,
        key=key,
        name="Built-in default" if key == BUILTIN_KEY else "Built-in egress default",
        is_default=False,
        builtin=True,
        created_at=None,
        updated_at=None,
        **spec.model_dump(),
    )


async def _pii(session, project_id: UUID, policy_id: UUID) -> PiiPolicy:
    row = await session.scalar(
        select(PiiPolicy).where(
            PiiPolicy.id == policy_id,
            PiiPolicy.project_id == project_id,
            PiiPolicy.deleted_at.is_(None),
        )
    )
    if row is None:
        raise not_found("pii_policy")
    return row


async def _pii_before(session, project_id: UUID, policy_id: UUID, **_) -> PiiPolicyOut:
    return pii_out(await _pii(session, project_id, policy_id))


def _check_pii(spec: PiiPolicySpec) -> None:
    try:
        validate_pii_policy(spec)
    except GuardrailConfigError as exc:
        raise service.config_error(exc) from None


async def _ensure_single_default(session, model, project_id: UUID, exclude_id=None) -> None:
    query = select(model.id).where(
        model.project_id == project_id, model.is_default, model.deleted_at.is_(None)
    )
    if exclude_id is not None:
        query = query.where(model.id != exclude_id)
    if await session.scalar(query) is not None:
        raise conflict("default_policy_exists", "Another policy is already the project default.")


@router.get(PII_BASE, response_model=PiiPolicyList, summary="List PII policies")
async def list_pii_policies(project_id: UUID, actor: Reader, session: SessionDep):
    rows = list(
        await session.scalars(
            select(PiiPolicy)
            .where(PiiPolicy.project_id == project_id, PiiPolicy.deleted_at.is_(None))
            .order_by(PiiPolicy.key)
        )
    )
    data = [pii_out(r) for r in rows]
    stored = {r.key for r in rows}
    if EGRESS_PII_KEY not in stored:
        # r1 MINOR-4: the egress rule's built-in PII, as resolve_pii gives it (MAJOR-1).
        egress = await service.resolve_pii(session, project_id, EGRESS_PII_KEY)
        data.insert(0, builtin_pii_out(project_id, EGRESS_PII_KEY, egress))
    if BUILTIN_KEY not in stored:
        data.insert(0, builtin_pii_out(project_id))
    return PiiPolicyList(data=data)


@router.post(PII_BASE, response_model=PiiPolicyOut, status_code=201, summary="Create a PII policy")
@audited("create_pii_policy", "pii_policy")
async def create_pii_policy(
    project_id: UUID, body: PiiPolicyCreate, request: Request, actor: Admin, session: SessionDep
):
    """Enabled categories need a recognizer (built-in regex or a custom pattern): 422
    `category_unsupported`; `engine=ner` is 422 `engine_unsupported` until 08 full."""
    data = body.model_dump(mode="json")
    _check_pii(PiiPolicySpec.model_validate({k: data[k] for k in PiiPolicySpec.model_fields}))
    if await service.stored_pii(session, project_id, body.key) is not None:
        raise conflict("pii_policy_key_taken", "This PII policy key is already used.")
    if body.is_default:
        await _ensure_single_default(session, PiiPolicy, project_id)
    row = PiiPolicy(**data, project_id=project_id, created_by=actor.actor_id)
    session.add(row)
    await session.flush()
    await session.refresh(row)
    return pii_out(row)


@router.get(PII_BASE + "/{policy_id}", response_model=PiiPolicyOut, summary="Get a PII policy")
async def get_pii_policy(project_id: UUID, policy_id: UUID, actor: Reader, session: SessionDep):
    return pii_out(await _pii(session, project_id, policy_id))


@router.patch(PII_BASE + "/{policy_id}", response_model=PiiPolicyOut, summary="Update a PII policy")
@audited("update_pii_policy", "pii_policy", load_before=_pii_before)
async def update_pii_policy(
    project_id: UUID,
    policy_id: UUID,
    body: PiiPolicyUpdate,
    request: Request,
    actor: Admin,
    session: SessionDep,
):
    row = await _pii(session, project_id, policy_id)
    changes = body.model_dump(mode="json", exclude_unset=True)
    merged = {**pii_out(row).model_dump(mode="json"), **changes}
    _check_pii(PiiPolicySpec.model_validate({k: merged[k] for k in PiiPolicySpec.model_fields}))
    if changes.get("is_default"):
        await _ensure_single_default(session, PiiPolicy, project_id, exclude_id=row.id)
    for field, value in changes.items():
        setattr(row, field, value)
    await session.flush()
    await session.refresh(row)
    return pii_out(row)


@router.delete(PII_BASE + "/{policy_id}", status_code=204, summary="Delete a PII policy")
@audited("delete_pii_policy", "pii_policy", load_before=_pii_before)
async def delete_pii_policy(
    project_id: UUID,
    policy_id: UUID,
    request: Request,
    actor: Admin,
    session: SessionDep,
    resource_id: PolicyIdDep,
) -> None:
    row = await _pii(session, project_id, policy_id)
    users = await session.scalars(
        select(GuardrailPolicy).where(
            GuardrailPolicy.project_id == project_id, GuardrailPolicy.deleted_at.is_(None)
        )
    )
    if any(rule.get("pii_policy_key") == row.key for policy in users for rule in policy.rules):
        raise conflict("pii_policy_in_use", "A guardrail policy still references this policy.")
    row.deleted_at = func.now()


# --- Guardrail policies ---


def policy_out(row: GuardrailPolicy) -> GuardrailPolicyOut:
    return GuardrailPolicyOut.model_validate({**row.__dict__, "builtin": False})


def builtin_policy_out(project_id: UUID) -> GuardrailPolicyOut:
    return GuardrailPolicyOut(
        id=None,
        project_id=project_id,
        key=BUILTIN_KEY,
        name="Built-in default",
        is_default=False,
        builtin=True,
        builtin_version=BUILTIN_VERSION,
        created_at=None,
        updated_at=None,
        **BUILTIN_DEFAULT.spec.model_dump(),
    )


async def _policy(session, project_id: UUID, policy_id: UUID) -> GuardrailPolicy:
    row = await session.scalar(
        select(GuardrailPolicy).where(
            GuardrailPolicy.id == policy_id,
            GuardrailPolicy.project_id == project_id,
            GuardrailPolicy.deleted_at.is_(None),
        )
    )
    if row is None:
        raise not_found("guardrail_policy")
    return row


async def _policy_before(session, project_id: UUID, policy_id: UUID, **_) -> GuardrailPolicyOut:
    return policy_out(await _policy(session, project_id, policy_id))


async def _check_policy(session, project_id: UUID, spec: PolicySpec) -> None:
    try:
        validate_policy(spec, await service.available_pii_keys(session, project_id))
    except GuardrailConfigError as exc:
        raise service.config_error(exc) from None


def _spec(data: dict) -> PolicySpec:
    return PolicySpec.model_validate({k: data[k] for k in PolicySpec.model_fields})


@router.get(POLICY_BASE, response_model=GuardrailPolicyList, summary="List guardrail policies")
async def list_guardrail_policies(project_id: UUID, actor: Reader, session: SessionDep):
    """Includes the built-in `default` (monitor mode) unless a stored policy uses that key."""
    rows = list(
        await session.scalars(
            select(GuardrailPolicy)
            .where(GuardrailPolicy.project_id == project_id, GuardrailPolicy.deleted_at.is_(None))
            .order_by(GuardrailPolicy.key)
        )
    )
    data = [policy_out(r) for r in rows]
    if not any(r.key == BUILTIN_KEY for r in rows):
        data.insert(0, builtin_policy_out(project_id))
    return GuardrailPolicyList(data=data)


@router.post(
    POLICY_BASE,
    response_model=GuardrailPolicyOut,
    status_code=201,
    summary="Create a guardrail policy",
)
@audited("create_guardrail_policy", "guardrail_policy")
async def create_guardrail_policy(
    project_id: UUID,
    body: GuardrailPolicyCreate,
    request: Request,
    actor: Admin,
    session: SessionDep,
):
    """Rules are checked on save: unsupported type or stage, missing action, unknown
    `pii_policy_key` and invalid patterns are 422 with a specific code."""
    data = body.model_dump(mode="json")
    await _check_policy(session, project_id, _spec(data))
    if await service.stored_policy(session, project_id, body.key) is not None:
        raise conflict("guardrail_policy_key_taken", "This guardrail policy key is already used.")
    if body.is_default:
        await _ensure_single_default(session, GuardrailPolicy, project_id)
    row = GuardrailPolicy(**data, project_id=project_id, created_by=actor.actor_id)
    session.add(row)
    await session.flush()
    await session.refresh(row)
    return policy_out(row)


@router.get(POLICY_BASE + "/{policy_id}", response_model=GuardrailPolicyOut, summary="Get a policy")
async def get_guardrail_policy(
    project_id: UUID, policy_id: UUID, actor: Reader, session: SessionDep
):
    return policy_out(await _policy(session, project_id, policy_id))


@router.patch(
    POLICY_BASE + "/{policy_id}",
    response_model=GuardrailPolicyOut,
    summary="Update a guardrail policy",
)
@audited("update_guardrail_policy", "guardrail_policy", load_before=_policy_before)
async def update_guardrail_policy(
    project_id: UUID,
    policy_id: UUID,
    body: GuardrailPolicyUpdate,
    request: Request,
    actor: Admin,
    session: SessionDep,
):
    """Switching `mode` to enforce is recorded in the audit trail with the before state."""
    row = await _policy(session, project_id, policy_id)
    changes = body.model_dump(mode="json", exclude_unset=True)
    await _check_policy(
        session, project_id, _spec({**policy_out(row).model_dump(mode="json"), **changes})
    )
    if changes.get("is_default"):
        await _ensure_single_default(session, GuardrailPolicy, project_id, exclude_id=row.id)
    for field, value in changes.items():
        setattr(row, field, value)
    await session.flush()
    await session.refresh(row)
    return policy_out(row)


@router.delete(POLICY_BASE + "/{policy_id}", status_code=204, summary="Delete a policy")
@audited("delete_guardrail_policy", "guardrail_policy", load_before=_policy_before)
async def delete_guardrail_policy(
    project_id: UUID,
    policy_id: UUID,
    request: Request,
    actor: Admin,
    session: SessionDep,
    resource_id: PolicyIdDep,
) -> None:
    row = await _policy(session, project_id, policy_id)
    row.deleted_at = func.now()


# --- Test panel and internal evaluation ---


def _findings(decision: Decision) -> list[FindingOut]:
    out = []
    for event in decision.events:
        matches = iter(event.matches)
        for finding in event.findings:
            match = next(matches, {}) if finding.get("category") != "rule_error" else {}
            out.append(
                FindingOut(
                    rule=event.rule,
                    category=finding["category"],
                    start=match.get("start"),
                    end=match.get("end"),
                    masked_value=match.get("masked_value"),
                    score=finding.get("score"),
                    severity=finding.get("severity"),
                    evidence=finding["evidence"],
                    action=finding.get("action"),
                )
            )
    return out


@router.post(
    "/projects/{project_id}/guardrails/test",
    response_model=GuardrailTestResult,
    summary="Try a policy on a text (dry run)",
)
async def test_guardrails(
    project_id: UUID, body: GuardrailTestRequest, actor: Reader, session: SessionDep
):
    """Nothing is stored: no guardrail events, no tokenize mapping outside this call. Every
    finding carries its evidence and offsets; values are masked."""
    if body.action is not None:
        pii = await service.resolve_pii(session, project_id, body.policy_key)
        if pii is None:
            raise not_found("pii_policy")
        action = "log" if body.action == "detect" else body.action
        rule = Rule(type="pii", action=action, stages=[body.stage], pii_policy_key="panel")
        policy = ResolvedPolicy(
            key=body.policy_key,
            spec=PolicySpec(rules=[rule], mode="enforce"),
            pii_policies={"panel": pii},
            # Not stored under that key: the built-in one (`default` or `default-egress`).
            builtin=await service.stored_pii(session, project_id, body.policy_key) is None,
        )
        stored_mode = None
    else:
        resolved = await service.resolve_policy(session, project_id, body.policy_key)
        policy = ResolvedPolicy(
            key=resolved.key,
            spec=resolved.spec.model_copy(update={"mode": "enforce"}),
            pii_policies=resolved.pii_policies,
            builtin=resolved.builtin,
        )
        stored_mode = resolved.spec.mode
    ctx = EvalContext(
        run_id=f"panel-{uuid.uuid4().hex}",
        project_id=str(project_id),
        source="agent-playground",
        locale=body.locale,
        tool=body.tool,
        token_store=MemoryTokenStore(),
        ner=local_ner(),
    )
    try:
        decision = await evaluate(body.text, body.stage, policy, ctx=ctx)
    except (GuardrailConfigError, EgressStageDisabled, TextTooLong) as exc:
        raise _engine_error(exc) from None
    return GuardrailTestResult(
        action=decision.action,
        text_out=decision.text_out,
        message=decision.message,
        findings=_findings(decision),
        policy_mode=stored_mode,
        builtin=policy.builtin,
    )


@router.post(
    "/internal/guardrails/ner",
    response_model=NerResponse,
    tags=["guardrails-internal"],
    summary="Find person, organization and location names (service account only)",
)
async def internal_ner(body: NerRequest, actor: ServiceActor):
    """08 tam 1b: the API process holds the NER model; the agent and ingest workers ask here
    (the /internal/embed pattern). Spans only, never values. Without NER_MODEL / NER_REVISION
    503 `ner_not_configured`; a missing weight 503 `model_missing` (run `make models`)."""
    client = local_ner()
    try:
        findings = await client.find(body.text, body.categories)
    except NerConfigError as exc:
        raise ApiError(503, "api_error", exc.code, exc.message) from None
    except ModelMissing as exc:
        raise ApiError(503, "api_error", "model_missing", str(exc)) from None
    return NerResponse(
        model=client.model,
        revision=client.revision,
        findings=[
            NerFindingOut(
                category=f.category, start=f.start, end=f.end, score=f.score, evidence=f.evidence
            )
            for f in findings
        ],
    )


@router.post(
    "/internal/guardrails/evaluate",
    response_model=DecisionOut,
    tags=["guardrails-internal"],
    summary="Evaluate a text at a stage (service account only)",
)
async def evaluate_guardrails(body: EvaluateRequest, actor: ServiceActor, session: SessionDep):
    """CONTRACTS C4. Writes one guardrail event per evaluated rule. A `block` decision is a
    200 response with `action=block`; the caller fails the run (06a) or returns 400 (06b). A
    token scope whose placeholder numbers are used up (it would issue past 9999999) is 400
    `placeholder_out_of_range`, whatever the policy's `on_error` says (08-tam-1a r4/r5). At egress,
    an enforce rule whose NER cannot answer is 503 `ner_unavailable`, also whatever `on_error`
    says (08-tam-1b r1 MINOR-1)."""
    project = await session.scalar(
        select(Project.id).where(Project.id == body.project_id, Project.deleted_at.is_(None))
    )
    if project is None:
        raise not_found("project")
    policy = await service.resolve_policy(session, body.project_id, body.policy_key)

    async def run(store):
        ctx = EvalContext(
            run_id=str(body.run_id) if body.run_id else None,
            project_id=str(body.project_id),
            source=body.source,
            locale=body.locale,
            tool=body.tool,
            token_store=store,
            ner=local_ner(),
        )
        return await evaluate(body.text, body.stage, policy, ctx=ctx)

    try:
        if body.run_id is None:
            decision = await run(None)
        else:
            async with service.redis_token_store() as store:
                decision = await run(store)
    except (GuardrailConfigError, EgressStageDisabled, TextTooLong) as exc:
        raise _engine_error(exc) from None
    service.record_events(session, body.project_id, decision.events, decision.reference_id)
    await session.commit()
    return DecisionOut(
        action=decision.action,
        text_out=decision.text_out,
        message=decision.message,
        reference_id=decision.reference_id,
        policy_key=policy.key,
        builtin=policy.builtin,
        events=[
            EventOut(**{f: getattr(e, f) for f in EventOut.model_fields}) for e in decision.events
        ],
    )
