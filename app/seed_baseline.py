from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import (
    Role,
    WorkflowDefinition,
    WorkflowDefinitionVersion,
    WorkflowState,
    WorkflowTransition,
    WorkflowTransitionRole,
)


@dataclass(frozen=True)
class TransitionSeed:
    code: str
    from_state: str
    to_state: str
    roles: tuple[str, ...]
    requires_comment: bool = False


@dataclass(frozen=True)
class WorkflowSeed:
    module_code: str
    entity_type: str
    name: str
    states: tuple[tuple[str, str, bool, bool], ...]  # code, display_name, is_initial, is_terminal
    transitions: tuple[TransitionSeed, ...]


ROLE_CODES: tuple[str, ...] = (
    "application_admin",
    "tenant_admin",
    "read_only_audit",
    "red_flag_analyst",
    "red_flag_approver",
    "tm_control_developer",
    "tm_control_reviewer",
    "tm_control_approver",
)


WORKFLOW_SEEDS: tuple[WorkflowSeed, ...] = (
    WorkflowSeed(
        module_code="red_flags",
        entity_type="tenant_red_flag_selection",
        name="Baseline Red Flag Selection Workflow",
        states=(
            ("draft", "Draft", True, False),
            ("pending_approval", "Pending Approval", False, False),
            ("approved", "Approved", False, True),
            ("rejected", "Rejected", False, True),
            ("returned", "Returned", False, False),
        ),
        transitions=(
            TransitionSeed("submit", "draft", "pending_approval", ("red_flag_analyst",)),
            TransitionSeed(
                "approve",
                "pending_approval",
                "approved",
                ("red_flag_approver",),
                requires_comment=True,
            ),
            TransitionSeed(
                "reject",
                "pending_approval",
                "rejected",
                ("red_flag_approver",),
                requires_comment=True,
            ),
            TransitionSeed(
                "return",
                "pending_approval",
                "returned",
                ("red_flag_approver",),
                requires_comment=True,
            ),
            TransitionSeed("resubmit", "returned", "pending_approval", ("red_flag_analyst",)),
        ),
    ),
    WorkflowSeed(
        module_code="transaction_monitoring",
        entity_type="tm_control",
        name="Baseline TM Control Lifecycle Workflow",
        states=(
            ("draft", "Draft", True, False),
            ("in_review", "In Review", False, False),
            ("approved", "Approved", False, False),
            ("rejected", "Rejected", False, False),
            ("retired", "Retired", False, True),
        ),
        transitions=(
            TransitionSeed("submit_review", "draft", "in_review", ("tm_control_developer",)),
            TransitionSeed(
                "approve",
                "in_review",
                "approved",
                ("tm_control_approver",),
                requires_comment=True,
            ),
            TransitionSeed(
                "reject",
                "in_review",
                "rejected",
                ("tm_control_approver",),
                requires_comment=True,
            ),
            TransitionSeed(
                "return_for_rework",
                "in_review",
                "draft",
                ("tm_control_reviewer",),
                requires_comment=True,
            ),
            TransitionSeed("revise", "rejected", "draft", ("tm_control_developer",)),
            TransitionSeed(
                "retire",
                "approved",
                "retired",
                ("tm_control_approver",),
                requires_comment=True,
            ),
        ),
    ),
    WorkflowSeed(
        module_code="transaction_monitoring",
        entity_type="tm_control_red_flag_map",
        name="Baseline TM Control to Red Flag Mapping Workflow",
        states=(
            ("draft", "Draft", True, False),
            ("pending_approval", "Pending Approval", False, False),
            ("approved", "Approved", False, True),
            ("rejected", "Rejected", False, True),
            ("returned", "Returned", False, False),
        ),
        transitions=(
            TransitionSeed("submit", "draft", "pending_approval", ("tm_control_developer",)),
            TransitionSeed(
                "approve",
                "pending_approval",
                "approved",
                ("tm_control_approver",),
                requires_comment=True,
            ),
            TransitionSeed(
                "reject",
                "pending_approval",
                "rejected",
                ("tm_control_approver",),
                requires_comment=True,
            ),
            TransitionSeed(
                "return",
                "pending_approval",
                "returned",
                ("tm_control_approver",),
                requires_comment=True,
            ),
            TransitionSeed("resubmit", "returned", "pending_approval", ("tm_control_developer",)),
        ),
    ),
)


def _seed_roles(db: Session) -> int:
    created = 0
    for code in ROLE_CODES:
        exists = db.query(Role).filter(Role.code == code).first()
        if exists is None:
            scope = "platform" if code == "application_admin" else "tenant"
            db.add(Role(code=code, scope=scope, description=f"Seeded role: {code}"))
            created += 1
    return created


def _seed_workflow_definition(db: Session, seed: WorkflowSeed) -> int:
    created = 0
    definition = (
        db.query(WorkflowDefinition)
        .filter(
            WorkflowDefinition.module_code == seed.module_code,
            WorkflowDefinition.entity_type == seed.entity_type,
            WorkflowDefinition.name == seed.name,
            WorkflowDefinition.is_system_template.is_(True),
        )
        .first()
    )
    if definition is None:
        definition = WorkflowDefinition(
            module_code=seed.module_code,
            entity_type=seed.entity_type,
            name=seed.name,
            is_system_template=True,
        )
        db.add(definition)
        db.flush()
        created += 1

    version = (
        db.query(WorkflowDefinitionVersion)
        .filter(
            WorkflowDefinitionVersion.workflow_definition_id == definition.id,
            WorkflowDefinitionVersion.version_no == 1,
        )
        .first()
    )
    if version is None:
        version = WorkflowDefinitionVersion(
            workflow_definition_id=definition.id,
            version_no=1,
            status="published",
            is_active=True,
            published_at=datetime.now(timezone.utc),
        )
        db.add(version)
        db.flush()
        created += 1

    for state_code, display_name, is_initial, is_terminal in seed.states:
        state = (
            db.query(WorkflowState)
            .filter(
                WorkflowState.workflow_version_id == version.id,
                WorkflowState.state_code == state_code,
            )
            .first()
        )
        if state is None:
            db.add(
                WorkflowState(
                    workflow_version_id=version.id,
                    state_code=state_code,
                    display_name=display_name,
                    is_initial=is_initial,
                    is_terminal=is_terminal,
                )
            )
            created += 1

    db.flush()

    for transition_seed in seed.transitions:
        transition = (
            db.query(WorkflowTransition)
            .filter(
                WorkflowTransition.workflow_version_id == version.id,
                WorkflowTransition.transition_code == transition_seed.code,
            )
            .first()
        )
        if transition is None:
            transition = WorkflowTransition(
                workflow_version_id=version.id,
                transition_code=transition_seed.code,
                from_state_code=transition_seed.from_state,
                to_state_code=transition_seed.to_state,
                requires_comment=transition_seed.requires_comment,
            )
            db.add(transition)
            db.flush()
            created += 1

        for role_code in transition_seed.roles:
            role_link = (
                db.query(WorkflowTransitionRole)
                .filter(
                    WorkflowTransitionRole.workflow_transition_id == transition.id,
                    WorkflowTransitionRole.role_code == role_code,
                )
                .first()
            )
            if role_link is None:
                db.add(
                    WorkflowTransitionRole(
                        workflow_transition_id=transition.id,
                        role_code=role_code,
                    )
                )
                created += 1

    return created


def seed_baseline_data(db: Session) -> dict[str, int]:
    roles_created = _seed_roles(db)
    workflow_rows_created = 0
    for workflow_seed in WORKFLOW_SEEDS:
        workflow_rows_created += _seed_workflow_definition(db, workflow_seed)
    db.commit()
    return {
        "roles_created": roles_created,
        "workflow_rows_created": workflow_rows_created,
    }


def main() -> None:
    db = SessionLocal()
    try:
        result = seed_baseline_data(db)
        print(
            "Baseline seed complete. "
            f"roles_created={result['roles_created']} "
            f"workflow_rows_created={result['workflow_rows_created']}"
        )
    finally:
        db.close()


if __name__ == "__main__":
    main()
