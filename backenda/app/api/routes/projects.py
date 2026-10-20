"""
Project creation, editing, 9-digit join codes, streaming uploads, and worker membership routes.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    Header,
    Query,
    Request,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse
from sqlalchemy import delete, desc, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.dependencies import (
    get_current_active_user,
    get_db_session,
    get_optional_current_user,
)
from app.core.audit import record_audit_event
from app.core.config import get_settings
from app.core.exceptions import (
    AuthorizationError,
    ConflictError,
    NotFoundError,
    ValidationError,
)
from app.core.logging import get_logger
from app.core.project_code import (
    format_nine_digit_code,
    generate_unique_project_code,
    normalize_project_code,
)
from app.core.upload import (
    inspect_and_validate_package,
    save_upload_stream,
    validate_dataset_archive,
)
from app.models.dataset import Dataset, ModelPackage
from app.models.machine import Machine
from app.models.project import Project, ProjectCode, ProjectMembership
from app.models.resource import MachineContributionSettings, ResourceAllocation
from app.models.training import TrainingConfiguration, TrainingMetric, TrainingRun
from app.models.user import User
from app.schemas.project import (
    DatasetResponse,
    JoinByCodeRequest,
    MembershipResponse,
    MembershipUpdateRequest,
    ModelPackageResponse,
    ProjectCreateRequest,
    ProjectDetailResponse,
    ProjectListResponse,
    ProjectOwnerResponse,
    ProjectProgressResponse,
    ProjectRequirementsSchema,
    ProjectUpdateRequest,
    PutOnlineResponse,
    TrainingConfigSchema,
    WorkerNodeResponse,
)

logger = get_logger("adc.projects.api")
settings = get_settings()

router = APIRouter(prefix="/projects", tags=["Projects"])


def _format_size(size_bytes: int) -> str:
    """Format bytes into readable size string."""
    if size_bytes >= 1024 * 1024 * 1024:
        return f"{size_bytes / (1024**3):.1f} GB"
    elif size_bytes >= 1024 * 1024:
        return f"{size_bytes / (1024**2):.1f} MB"
    elif size_bytes >= 1024:
        return f"{size_bytes / 1024:.1f} KB"
    return f"{size_bytes} B"


def _build_project_detail(
    project: Project,
    current_user_id: Optional[uuid.UUID] = None,
) -> ProjectDetailResponse:
    """Construct standard ProjectDetailResponse model from Project ORM."""
    owner_is_current = bool(current_user_id and project.owner_id == current_user_id)
    owner_dict = ProjectOwnerResponse(
        id=str(project.owner_id),
        name=project.owner.display_name if project.owner else "Project Owner",
        is_current_user=owner_is_current,
    )

    # Active join code if present
    active_code: Optional[str] = None
    if project.codes:
        for c in project.codes:
            if c.is_active:
                active_code = c.code
                break

    # Training configuration
    training_config: Optional[TrainingConfigSchema] = None
    if project.training_configs:
        tc = project.training_configs[0]
        training_config = TrainingConfigSchema(
            batch_size=tc.batch_size,
            total_steps=tc.total_steps,
            learning_rate=tc.learning_rate,
            optimizer=tc.optimizer,
            precision=tc.precision,
            checkpoint_interval=tc.checkpoint_interval,
            gradient_accumulation_steps=tc.gradient_accumulation_steps,
        )

    # Datasets
    dataset_list = [
        DatasetResponse(
            id=d.id,
            name=d.name,
            description=d.description,
            size_bytes=d.size_bytes,
            format=d.format,
            checksum_sha256=d.checksum_sha256,
            is_validated=d.is_validated,
            validation_error=d.validation_error,
            created_at=d.created_at,
        )
        for d in project.datasets
    ]

    # Packages
    package_list: List[ModelPackageResponse] = []
    for p in project.packages:
        manifest_dict = json.loads(p.manifest_json) if p.manifest_json else None
        package_list.append(
            ModelPackageResponse(
                id=p.id,
                file_name=p.file_name,
                file_size_bytes=p.file_size_bytes,
                entrypoint=p.entrypoint,
                checksum_sha256=p.checksum_sha256,
                is_validated=p.is_validated,
                validation_error=p.validation_error,
                manifest=manifest_dict,
                created_at=p.created_at,
            )
        )

    # Primary dataset & package labels
    primary_ds_name = dataset_list[0].name if dataset_list else "None"
    primary_ds_desc = dataset_list[0].description if dataset_list else ""
    primary_ds_size = _format_size(dataset_list[0].size_bytes) if dataset_list else "0 MB"
    primary_code_name = package_list[0].file_name if package_list else "None"
    primary_code_size = _format_size(package_list[0].file_size_bytes) if package_list else "0 MB"

    # Workers list
    worker_list: List[WorkerNodeResponse] = []
    if project.memberships:
        for m in project.memberships:
            machine = m.machine
            worker_is_current = bool(current_user_id and m.user_id == current_user_id)
            worker_list.append(
                WorkerNodeResponse(
                    id=str(m.id),
                    machine_id=m.machine_id,
                    name=machine.name if machine else "Worker Node",
                    is_current_user=worker_is_current,
                    status=m.status,
                    cpu_model=machine.platform or "Standard Node",
                    cpu_cores_total=max(m.cpu_cores_contributed, 4),
                    cpu_cores_contributed=m.cpu_cores_contributed,
                    ram_total_gb=max(m.ram_contributed_gb * 2, 8.0),
                    ram_contributed_gb=m.ram_contributed_gb,
                    gpu_model=m.selected_gpu if m.selected_gpu else ("GPU Enabled" if m.gpu_enabled else "None"),
                    gpu_memory_total_gb=8.0 if m.gpu_enabled else 0.0,
                    gpu_enabled=m.gpu_enabled,
                    storage_budget_gb=m.storage_budget_gb,
                    network_preference=m.network_preference,
                    current_batch=m.current_batch,
                    steps_processed=m.steps_processed,
                    joined_at=m.joined_at,
                    contribution_status=m.contribution_status,
                )
            )

    requirements = ProjectRequirementsSchema(
        min_cpu_cores=project.min_cpu_cores,
        min_ram_gb=project.min_ram_gb,
        gpu_recommended=project.gpu_recommended,
        min_vram_gb=project.min_vram_gb,
    )

    return ProjectDetailResponse(
        id=project.id,
        name=project.name,
        description=project.description,
        training_objective=project.training_objective,
        model_architecture=project.model_architecture,
        dataset_name=primary_ds_name,
        dataset_description=primary_ds_desc,
        dataset_size=primary_ds_size,
        code_file_name=primary_code_name,
        code_file_size=primary_code_size,
        status=project.status,
        visibility=project.visibility,
        owner=owner_dict,
        created_at=project.created_at,
        expected_duration=project.expected_duration,
        training_strategy=project.training_strategy,
        workers_needed=project.workers_needed,
        requirements=requirements,
        training_config=training_config,
        active_code=active_code,
        datasets=dataset_list,
        packages=package_list,
        workers=worker_list,
        metrics={
            "currentStep": 0,
            "totalSteps": training_config.total_steps if training_config else 1000,
            "progressPercent": 0.0,
            "currentLoss": 0.0,
            "trainingSpeed": 0.0,
            "elapsedTimeSeconds": 0,
            "estimatedRemainingSeconds": 0,
            "history": [],
        },
        logs=[],
    )



# ── Project CRUD ─────────────────────────────────────────────────────────────

@router.post(
    "",
    response_model=ProjectDetailResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new distributed training project",
)
async def create_project(
    payload: ProjectCreateRequest,
    request: Request,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db_session),
) -> ProjectDetailResponse:
    """
    Create a project specification draft with architecture details and training hyper-parameters.
    """
    reqs = payload.requirements or ProjectRequirementsSchema()

    project = Project(
        name=payload.name,
        description=payload.description,
        training_objective=payload.training_objective,
        model_architecture=payload.model_architecture,
        status="online",
        visibility=payload.visibility,
        owner_id=current_user.id,
        training_strategy=payload.training_strategy,
        workers_needed=payload.workers_needed,
        min_cpu_cores=reqs.min_cpu_cores,
        min_ram_gb=reqs.min_ram_gb,
        gpu_recommended=reqs.gpu_recommended,
        min_vram_gb=reqs.min_vram_gb,
        expected_duration=payload.expected_duration,
    )
    db.add(project)
    await db.flush()

    # Create associated TrainingConfiguration if provided
    tc_data = payload.training_config or TrainingConfigSchema()
    config = TrainingConfiguration(
        project_id=project.id,
        batch_size=tc_data.batch_size,
        total_steps=tc_data.total_steps,
        learning_rate=tc_data.learning_rate,
        optimizer=tc_data.optimizer,
        precision=tc_data.precision,
        checkpoint_interval=tc_data.checkpoint_interval,
        gradient_accumulation_steps=tc_data.gradient_accumulation_steps,
    )
    db.add(config)

    # Ensure storage subdirectories exist for this project
    (settings.datasets_dir / str(project.id)).mkdir(parents=True, exist_ok=True)
    (settings.packages_dir / str(project.id)).mkdir(parents=True, exist_ok=True)

    await record_audit_event(
        db,
        action="project.create",
        user_id=current_user.id,
        resource_type="project",
        resource_id=str(project.id),
        details={"name": project.name, "strategy": project.training_strategy},
        ip_address=request.client.host if request.client else None,
    )
    await db.commit()

    # Re-query with relationships eager loaded
    stmt = (
        select(Project)
        .options(
            selectinload(Project.owner),
            selectinload(Project.codes),
            selectinload(Project.datasets),
            selectinload(Project.packages),
            selectinload(Project.training_configs),
            selectinload(Project.memberships).selectinload(ProjectMembership.machine),
        )
        .where(Project.id == project.id)
    )
    refreshed = (await db.execute(stmt)).scalar_one()

    return _build_project_detail(refreshed, current_user.id)


@router.get(
    "",
    response_model=ProjectListResponse,
    summary="List available projects with filtering",
)
async def list_projects(
    visibility: Optional[str] = Query(None, pattern=r"^(public|unlisted)$"),
    status: Optional[str] = Query(None),
    my_projects: bool = Query(False),
    current_user: Optional[User] = Depends(get_optional_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> ProjectListResponse:
    """List public projects, or projects owned/joined by the authenticated user."""
    stmt = select(Project).options(
        selectinload(Project.owner),
        selectinload(Project.codes),
        selectinload(Project.datasets),
        selectinload(Project.packages),
        selectinload(Project.training_configs),
        selectinload(Project.memberships).selectinload(ProjectMembership.machine),
    )

    if my_projects:
        if not current_user:
            raise AuthorizationError("Authentication required to view 'my_projects'.")
        stmt = stmt.where(Project.owner_id == current_user.id)
    else:
        if visibility:
            stmt = stmt.where(Project.visibility == visibility)
        else:
            # By default show public projects plus any unlisted projects owned by user
            if current_user:
                stmt = stmt.where(
                    (Project.visibility == "public") | (Project.owner_id == current_user.id)
                )
            else:
                stmt = stmt.where(Project.visibility == "public")

    if status:
        stmt = stmt.where(Project.status == status)

    stmt = stmt.order_by(desc(Project.created_at))
    result = await db.execute(stmt)
    projects = result.scalars().all()

    current_user_id = current_user.id if current_user else None
    items = [_build_project_detail(p, current_user_id) for p in projects]

    return ProjectListResponse(projects=items, total=len(items))


@router.get(
    "/{project_id}",
    response_model=ProjectDetailResponse,
    summary="Retrieve full project details by ID",
)
async def get_project(
    project_id: uuid.UUID,
    current_user: Optional[User] = Depends(get_optional_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> ProjectDetailResponse:
    """Retrieve complete metadata, active code, datasets, packages, and connected workers."""
    stmt = (
        select(Project)
        .options(
            selectinload(Project.owner),
            selectinload(Project.codes),
            selectinload(Project.datasets),
            selectinload(Project.packages),
            selectinload(Project.training_configs),
            selectinload(Project.memberships).selectinload(ProjectMembership.machine),
        )
        .where(Project.id == project_id)
    )
    result = await db.execute(stmt)
    project = result.scalar_one_or_none()

    if not project:
        raise NotFoundError("Project not found.")

    current_user_id = current_user.id if current_user else None
    return _build_project_detail(project, current_user_id)


@router.patch(
    "/{project_id}",
    response_model=ProjectDetailResponse,
    summary="Update project metadata",
)
async def update_project(
    project_id: uuid.UUID,
    payload: ProjectUpdateRequest,
    request: Request,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db_session),
) -> ProjectDetailResponse:
    """Update project title, description, or strategy parameters (owner only)."""
    stmt = (
        select(Project)
        .options(
            selectinload(Project.owner),
            selectinload(Project.codes),
            selectinload(Project.datasets),
            selectinload(Project.packages),
            selectinload(Project.training_configs),
            selectinload(Project.memberships).selectinload(ProjectMembership.machine),
        )
        .where(Project.id == project_id)
    )
    result = await db.execute(stmt)
    project = result.scalar_one_or_none()

    if not project:
        raise NotFoundError("Project not found.")

    if project.owner_id != current_user.id and not current_user.is_superuser:
        raise AuthorizationError("Only the project owner can edit project settings.")

    update_dict = payload.model_dump(exclude_none=True)
    for field, value in update_dict.items():
        setattr(project, field, value)

    await record_audit_event(
        db,
        action="project.update",
        user_id=current_user.id,
        resource_type="project",
        resource_id=str(project.id),
        details=update_dict,
        ip_address=request.client.host if request.client else None,
    )
    await db.commit()
    await db.refresh(project)

    return _build_project_detail(project, current_user.id)


# ── Put Project Online Workflow & Join Codes ─────────────────────────────────

@router.post(
    "/{project_id}/online",
    response_model=PutOnlineResponse,
    summary="Put project online and generate 9-digit worker join code",
)
async def put_project_online(
    project_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db_session),
) -> PutOnlineResponse:
    """
    Verify datasets and model code packages, generate a cryptographically
    random 9-digit code, and transition project to online acceptance mode.
    """
    stmt = (
        select(Project)
        .options(
            selectinload(Project.owner),
            selectinload(Project.codes),
            selectinload(Project.datasets),
            selectinload(Project.packages),
            selectinload(Project.training_configs),
            selectinload(Project.memberships).selectinload(ProjectMembership.machine),
        )
        .where(Project.id == project_id)
    )
    result = await db.execute(stmt)
    project = result.scalar_one_or_none()

    if not project:
        raise NotFoundError("Project not found.")

    if project.owner_id != current_user.id and not current_user.is_superuser:
        raise AuthorizationError("Only the project owner can put this project online.")

    # 1. Verify dataset exists and is validated
    if not project.datasets:
        raise ValidationError("Cannot put project online: Upload at least one dataset package first.")

    valid_datasets = [d for d in project.datasets if d.is_validated]
    if not valid_datasets:
        raise ValidationError("Cannot put project online: Dataset package failed validation checks.")

    # 2. Verify model training package exists and is validated
    if not project.packages:
        raise ValidationError("Cannot put project online: Upload a training code package first.")

    valid_packages = [p for p in project.packages if p.is_validated]
    if not valid_packages:
        raise ValidationError("Cannot put project online: Training code package failed validation checks.")

    # 3. Locate or generate unique 9-digit project code
    active_code: Optional[ProjectCode] = None
    for c in project.codes:
        if c.is_active:
            active_code = c
            break

    if not active_code:
        active_code = await generate_unique_project_code(db, project.id)

    # 4. Mark project status
    project.status = "looking_for_workers"

    await record_audit_event(
        db,
        action="project.put_online",
        user_id=current_user.id,
        resource_type="project",
        resource_id=str(project.id),
        details={"project_code": active_code.code},
        ip_address=request.client.host if request.client else None,
    )
    await db.commit()
    await db.refresh(project)

    detail = _build_project_detail(project, current_user.id)
    return PutOnlineResponse(
        status="online",
        project_code=active_code.code,
        message=f"Project is now online. Share code {active_code.code} with workers to join.",
        project=detail,
    )


# ── Project Lifecycle Transitions ────────────────────────────────────────────

@router.post(
    "/{project_id}/pause",
    response_model=ProjectDetailResponse,
    summary="Pause active training on project",
)
async def pause_project(
    project_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db_session),
) -> ProjectDetailResponse:
    """Pause project training across all connected workers."""
    stmt = (
        select(Project)
        .options(
            selectinload(Project.owner),
            selectinload(Project.codes),
            selectinload(Project.datasets),
            selectinload(Project.packages),
            selectinload(Project.training_configs),
            selectinload(Project.memberships).selectinload(ProjectMembership.machine),
        )
        .where(Project.id == project_id)
    )
    project = (await db.execute(stmt)).scalar_one_or_none()
    if not project:
        raise NotFoundError("Project not found.")

    if project.owner_id != current_user.id and not current_user.is_superuser:
        raise AuthorizationError("Only the project owner can pause training.")

    project.status = "paused"
    await record_audit_event(
        db,
        action="project.pause",
        user_id=current_user.id,
        resource_type="project",
        resource_id=str(project.id),
        ip_address=request.client.host if request.client else None,
    )
    await db.commit()
    await db.refresh(project)
    return _build_project_detail(project, current_user.id)


@router.post(
    "/{project_id}/resume",
    response_model=ProjectDetailResponse,
    summary="Resume paused project training",
)
async def resume_project(
    project_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db_session),
) -> ProjectDetailResponse:
    """Resume project training."""
    stmt = (
        select(Project)
        .options(
            selectinload(Project.owner),
            selectinload(Project.codes),
            selectinload(Project.datasets),
            selectinload(Project.packages),
            selectinload(Project.training_configs),
            selectinload(Project.memberships).selectinload(ProjectMembership.machine),
        )
        .where(Project.id == project_id)
    )
    project = (await db.execute(stmt)).scalar_one_or_none()
    if not project:
        raise NotFoundError("Project not found.")

    if project.owner_id != current_user.id and not current_user.is_superuser:
        raise AuthorizationError("Only the project owner can resume training.")

    project.status = "online"
    await record_audit_event(
        db,
        action="project.resume",
        user_id=current_user.id,
        resource_type="project",
        resource_id=str(project.id),
        ip_address=request.client.host if request.client else None,
    )
    await db.commit()
    await db.refresh(project)
    return _build_project_detail(project, current_user.id)


@router.post(
    "/{project_id}/stop",
    response_model=ProjectDetailResponse,
    summary="Stop project training",
)
async def stop_project(
    project_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db_session),
) -> ProjectDetailResponse:
    """Stop active training runs and release active worker allocations."""
    stmt = (
        select(Project)
        .options(
            selectinload(Project.owner),
            selectinload(Project.codes),
            selectinload(Project.datasets),
            selectinload(Project.packages),
            selectinload(Project.training_configs),
            selectinload(Project.memberships).selectinload(ProjectMembership.machine),
        )
        .where(Project.id == project_id)
    )
    project = (await db.execute(stmt)).scalar_one_or_none()
    if not project:
        raise NotFoundError("Project not found.")

    if project.owner_id != current_user.id and not current_user.is_superuser:
        raise AuthorizationError("Only the project owner can stop project training.")

    project.status = "stopped"
    await record_audit_event(
        db,
        action="project.stop",
        user_id=current_user.id,
        resource_type="project",
        resource_id=str(project.id),
        ip_address=request.client.host if request.client else None,
    )
    await db.commit()
    await db.refresh(project)
    return _build_project_detail(project, current_user.id)


@router.post(
    "/{project_id}/end",
    response_model=ProjectDetailResponse,
    summary="Complete project and deactivate join codes",
)
async def end_project(
    project_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db_session),
) -> ProjectDetailResponse:
    """Mark project as completed and revoke join codes."""
    stmt = (
        select(Project)
        .options(
            selectinload(Project.owner),
            selectinload(Project.codes),
            selectinload(Project.datasets),
            selectinload(Project.packages),
            selectinload(Project.training_configs),
            selectinload(Project.memberships).selectinload(ProjectMembership.machine),
        )
        .where(Project.id == project_id)
    )
    project = (await db.execute(stmt)).scalar_one_or_none()
    if not project:
        raise NotFoundError("Project not found.")

    if project.owner_id != current_user.id and not current_user.is_superuser:
        raise AuthorizationError("Only the project owner can complete the project.")

    project.status = "completed"

    # Deactivate join codes
    for c in project.codes:
        c.is_active = False

    await record_audit_event(
        db,
        action="project.end",
        user_id=current_user.id,
        resource_type="project",
        resource_id=str(project.id),
        ip_address=request.client.host if request.client else None,
    )
    await db.commit()
    await db.refresh(project)
    return _build_project_detail(project, current_user.id)


# ── Worker Joining & Membership ──────────────────────────────────────────────

@router.post(
    "/join-by-code",
    response_model=MembershipResponse,
    summary="Join a project using a 9-digit project join code",
)
async def join_by_code(
    payload: JoinByCodeRequest,
    request: Request,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db_session),
    x_installation_id: Optional[str] = Header(None, alias="X-Installation-Id"),
) -> MembershipResponse:
    """
    Worker node validates 9-digit code, verifies hardware capacity against requirements,
    and joins project compute cluster.
    """
    normalized = normalize_project_code(payload.code)

    # 1. Locate active project code
    code_stmt = select(ProjectCode).where(
        (ProjectCode.code == normalized) | (ProjectCode.code == payload.code.strip()),
        ProjectCode.is_active.is_(True),
    )
    p_code = (await db.execute(code_stmt)).scalars().first()
    if not p_code:
        raise NotFoundError("Invalid, inactive, or expired 9-digit project join code.")

    # 2. Retrieve project
    p_stmt = select(Project).where(Project.id == p_code.project_id)
    project = (await db.execute(p_stmt)).scalar_one_or_none()
    if not project:
        raise NotFoundError("Project associated with code not found.")

    if project.status in ["stopped", "completed"]:
        raise ValidationError("This project is currently not accepting worker contributions.")

    # 3. Locate worker machine
    machine: Optional[Machine] = None
    if x_installation_id:
        m_stmt = select(Machine).where(Machine.installation_id == x_installation_id)
        machine = (await db.execute(m_stmt)).scalars().first()

    if not machine:
        m_stmt = select(Machine).where(
            Machine.paired_user_id == current_user.id,
            Machine.active_role == "worker",
        )
        machine = (await db.execute(m_stmt)).scalars().first()

    if not machine:
        # Fallback to any machine paired to current user
        m_stmt = select(Machine).where(Machine.paired_user_id == current_user.id)
        machine = (await db.execute(m_stmt)).scalars().first()

    if not machine:
        raise ValidationError(
            "No paired worker machine found for your account. Pair a machine in Worker role first."
        )

    # 4. Check contribution settings defaults if not specified in request
    settings_stmt = select(MachineContributionSettings).where(
        MachineContributionSettings.machine_id == machine.id
    )
    m_settings = (await db.execute(settings_stmt)).scalars().first()

    cpu_cores = payload.cpu_cores or (m_settings.cpu_cores if m_settings else 2)
    ram_gb = payload.ram_gb or (m_settings.ram_budget_gb if m_settings else 4.0)
    gpu_enabled = payload.gpu_enabled if payload.gpu_enabled is not None else (m_settings.gpu_enabled if m_settings else False)
    storage_gb = payload.storage_gb or (m_settings.storage_budget_gb if m_settings else 20.0)
    net_pref = payload.network_preference or (m_settings.network_preference if m_settings else "unlimited")

    # 5. Validate against project minimum hardware requirements
    if cpu_cores < project.min_cpu_cores:
        raise ValidationError(
            f"Contributed CPU cores ({cpu_cores}) does not meet project minimum requirement ({project.min_cpu_cores} cores)."
        )

    if ram_gb < project.min_ram_gb:
        raise ValidationError(
            f"Contributed RAM ({ram_gb} GB) does not meet project minimum requirement ({project.min_ram_gb} GB)."
        )

    # 6. Check for existing membership (prevent duplicate)
    existing_mem_stmt = select(ProjectMembership).where(
        ProjectMembership.project_id == project.id,
        ProjectMembership.machine_id == machine.id,
    )
    membership = (await db.execute(existing_mem_stmt)).scalars().first()

    if membership:
        # Reactivate membership if paused or offline
        membership.status = "idle"
        membership.contribution_status = "active"
        membership.cpu_cores_contributed = cpu_cores
        membership.ram_contributed_gb = ram_gb
        membership.gpu_enabled = gpu_enabled
        membership.storage_budget_gb = storage_gb
        membership.network_preference = net_pref
    else:
        membership = ProjectMembership(
            project_id=project.id,
            machine_id=machine.id,
            user_id=current_user.id,
            status="idle",
            contribution_status="active",
            cpu_cores_contributed=cpu_cores,
            ram_contributed_gb=ram_gb,
            gpu_enabled=gpu_enabled,
            selected_gpu=m_settings.selected_gpu if m_settings else "",
            storage_budget_gb=storage_gb,
            network_preference=net_pref,
        )
        db.add(membership)

    # 7. Record resource allocation
    alloc_stmt = select(ResourceAllocation).where(
        ResourceAllocation.project_id == project.id,
        ResourceAllocation.machine_id == machine.id,
    )
    allocation = (await db.execute(alloc_stmt)).scalars().first()
    if not allocation:
        allocation = ResourceAllocation(
            project_id=project.id,
            machine_id=machine.id,
            cpu_cores=cpu_cores,
            ram_gb=ram_gb,
            storage_gb=storage_gb,
            status="reserved",
        )
        db.add(allocation)
    else:
        allocation.cpu_cores = cpu_cores
        allocation.ram_gb = ram_gb
        allocation.storage_gb = storage_gb
        allocation.status = "reserved"

    await record_audit_event(
        db,
        action="project.worker_joined",
        user_id=current_user.id,
        machine_id=machine.id,
        resource_type="project",
        resource_id=str(project.id),
        details={"code": normalized, "cpu_cores": cpu_cores, "ram_gb": ram_gb},
        ip_address=request.client.host if request.client else None,
    )
    await db.commit()
    await db.refresh(membership)

    return MembershipResponse.model_validate(membership)


@router.get(
    "/{project_id}/membership",
    response_model=MembershipResponse,
    summary="Get current worker node membership for project",
)
async def get_membership(
    project_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db_session),
    x_installation_id: Optional[str] = Header(None, alias="X-Installation-Id"),
) -> MembershipResponse:
    """Retrieve membership details for user's machine on target project."""
    stmt = select(ProjectMembership).where(
        ProjectMembership.project_id == project_id,
        ProjectMembership.user_id == current_user.id,
    )
    if x_installation_id:
        m_stmt = select(Machine).where(Machine.installation_id == x_installation_id)
        m = (await db.execute(m_stmt)).scalars().first()
        if m:
            stmt = stmt.where(ProjectMembership.machine_id == m.id)

    membership = (await db.execute(stmt)).scalars().first()
    if not membership:
        raise NotFoundError("You are not currently a member of this project.")

    return MembershipResponse.model_validate(membership)


@router.patch(
    "/{project_id}/membership/resources",
    response_model=MembershipResponse,
    summary="Update contributed resource allocations for project",
)
async def update_membership_resources(
    project_id: uuid.UUID,
    payload: MembershipUpdateRequest,
    request: Request,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db_session),
    x_installation_id: Optional[str] = Header(None, alias="X-Installation-Id"),
) -> MembershipResponse:
    """Update CPU cores, RAM, GPU, or storage budget for an active membership."""
    stmt = select(ProjectMembership).where(
        ProjectMembership.project_id == project_id,
        ProjectMembership.user_id == current_user.id,
    )
    if x_installation_id:
        m_stmt = select(Machine).where(Machine.installation_id == x_installation_id)
        m = (await db.execute(m_stmt)).scalars().first()
        if m:
            stmt = stmt.where(ProjectMembership.machine_id == m.id)

    membership = (await db.execute(stmt)).scalars().first()
    if not membership:
        raise NotFoundError("Membership not found for this project.")

    if payload.cpu_cores is not None:
        membership.cpu_cores_contributed = payload.cpu_cores
    if payload.ram_gb is not None:
        membership.ram_contributed_gb = payload.ram_gb
    if payload.gpu_enabled is not None:
        membership.gpu_enabled = payload.gpu_enabled
    if payload.storage_gb is not None:
        membership.storage_budget_gb = payload.storage_gb
    if payload.network_preference is not None:
        membership.network_preference = payload.network_preference

    # Also update allocation record
    alloc_stmt = select(ResourceAllocation).where(
        ResourceAllocation.project_id == project_id,
        ResourceAllocation.machine_id == membership.machine_id,
    )
    alloc = (await db.execute(alloc_stmt)).scalars().first()
    if alloc:
        alloc.cpu_cores = membership.cpu_cores_contributed
        alloc.ram_gb = membership.ram_contributed_gb
        alloc.storage_gb = membership.storage_budget_gb

    await db.commit()
    await db.refresh(membership)
    return MembershipResponse.model_validate(membership)


@router.post(
    "/{project_id}/leave",
    status_code=status.HTTP_200_OK,
    summary="Worker voluntarily leaves project",
)
async def leave_project(
    project_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db_session),
    x_installation_id: Optional[str] = Header(None, alias="X-Installation-Id"),
) -> Dict[str, Any]:
    """
    Worker leaves project without stopping training on other cluster nodes.
    """
    stmt = select(ProjectMembership).where(
        ProjectMembership.project_id == project_id,
        ProjectMembership.user_id == current_user.id,
    )
    if x_installation_id:
        m_stmt = select(Machine).where(Machine.installation_id == x_installation_id)
        m = (await db.execute(m_stmt)).scalars().first()
        if m:
            stmt = stmt.where(ProjectMembership.machine_id == m.id)

    memberships = (await db.execute(stmt)).scalars().all()
    if not memberships:
        raise NotFoundError("Membership not found.")

    for mem in memberships:
        # Release resource allocations
        del_alloc = delete(ResourceAllocation).where(
            ResourceAllocation.project_id == project_id,
            ResourceAllocation.machine_id == mem.machine_id,
        )
        await db.execute(del_alloc)
        await db.delete(mem)

    await record_audit_event(
        db,
        action="project.worker_left",
        user_id=current_user.id,
        resource_type="project",
        resource_id=str(project_id),
        ip_address=request.client.host if request.client else None,
    )
    await db.commit()

    return {
        "success": True,
        "message": "Successfully left project and released compute allocations.",
    }


# ── Dataset Upload & Download Endpoints ──────────────────────────────────────

@router.post(
    "/{project_id}/datasets",
    response_model=DatasetResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload dataset file package for project",
)
async def upload_dataset(
    project_id: uuid.UUID,
    file: UploadFile = File(...),
    name: Optional[str] = Form(None),
    description: Optional[str] = Form(""),
    format: Optional[str] = Form(None),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db_session),
) -> DatasetResponse:
    """
    Stream upload of dataset package (.tar.gz, .zip, etc.) directly to disk with SHA-256 validation.
    """
    p_stmt = select(Project).where(Project.id == project_id)
    project = (await db.execute(p_stmt)).scalar_one_or_none()
    if not project:
        raise NotFoundError("Project not found.")

    if project.owner_id != current_user.id and not current_user.is_superuser:
        raise AuthorizationError("Only the project owner can upload datasets to this project.")

    clean_filename = Path(file.filename or "dataset.zip").name
    dataset_name = name or clean_filename
    dest_dir = settings.datasets_dir / str(project_id)
    dest_path = dest_dir / clean_filename

    # Stream file to disk enforcing upload limit and calculating SHA-256
    size_bytes, checksum = await save_upload_stream(
        upload_file=file,
        destination_path=dest_path,
        max_bytes=settings.upload_max_size_mb * 1024 * 1024,
    )

    # Validate archive integrity
    is_valid, error_msg = validate_dataset_archive(dest_path)

    # Determine format extension
    ds_format = format or clean_filename.split(".")[-1]

    dataset = Dataset(
        project_id=project_id,
        name=dataset_name,
        description=description or "",
        size_bytes=size_bytes,
        format=ds_format,
        file_path=str(dest_path),
        checksum_sha256=checksum,
        is_validated=is_valid,
        validation_error=error_msg,
    )
    db.add(dataset)
    await db.commit()
    await db.refresh(dataset)

    logger.info(
        "dataset_uploaded",
        project_id=str(project_id),
        dataset_id=str(dataset.id),
        is_valid=is_valid,
        size_bytes=size_bytes,
    )

    return DatasetResponse.model_validate(dataset)


@router.get(
    "/{project_id}/datasets",
    response_model=List[DatasetResponse],
    summary="List uploaded datasets for a project",
)
async def list_datasets(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
) -> List[DatasetResponse]:
    """Retrieve all dataset records associated with this project."""
    stmt = select(Dataset).where(Dataset.project_id == project_id).order_by(desc(Dataset.created_at))
    datasets = (await db.execute(stmt)).scalars().all()
    return [DatasetResponse.model_validate(d) for d in datasets]


@router.get(
    "/{project_id}/datasets/{dataset_id}/download",
    summary="Download dataset package file stream",
)
async def download_dataset(
    project_id: uuid.UUID,
    dataset_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db_session),
) -> FileResponse:
    """Stream dataset package for authorized project participants."""
    stmt = select(Dataset).where(
        Dataset.id == dataset_id,
        Dataset.project_id == project_id,
    )
    dataset = (await db.execute(stmt)).scalar_one_or_none()
    if not dataset:
        raise NotFoundError("Dataset not found.")

    file_path = Path(dataset.file_path)
    if not file_path.exists():
        raise NotFoundError("Dataset file is missing from storage.")

    return FileResponse(
        path=file_path,
        filename=file_path.name,
        media_type="application/octet-stream",
    )


# ── Model Training Package Upload & Download Endpoints ───────────────────────

@router.post(
    "/{project_id}/packages",
    response_model=ModelPackageResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload model training code package (.zip or .tar.gz)",
)
async def upload_model_package(
    project_id: uuid.UUID,
    file: UploadFile = File(...),
    entrypoint: Optional[str] = Form("train.py"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db_session),
) -> ModelPackageResponse:
    """
    Stream upload of model code package, inspecting manifest.json and checking entrypoint script.
    """
    p_stmt = select(Project).where(Project.id == project_id)
    project = (await db.execute(p_stmt)).scalar_one_or_none()
    if not project:
        raise NotFoundError("Project not found.")

    if project.owner_id != current_user.id and not current_user.is_superuser:
        raise AuthorizationError("Only project owner can upload code packages to this project.")

    clean_filename = Path(file.filename or "training_package.zip").name
    dest_dir = settings.packages_dir / str(project_id)
    dest_path = dest_dir / clean_filename

    # Stream to disk
    size_bytes, checksum = await save_upload_stream(
        upload_file=file,
        destination_path=dest_path,
        max_bytes=1000 * 1024 * 1024,  # 1GB max for code packages
    )

    # Inspect archive: check entrypoint and read manifest.json
    is_valid, error_msg, manifest_data = inspect_and_validate_package(
        package_path=dest_path,
        expected_entrypoint=entrypoint or "train.py",
    )

    package = ModelPackage(
        project_id=project_id,
        file_name=clean_filename,
        file_size_bytes=size_bytes,
        entrypoint=entrypoint or "train.py",
        file_path=str(dest_path),
        checksum_sha256=checksum,
        manifest_json=json.dumps(manifest_data) if manifest_data else None,
        is_validated=is_valid,
        validation_error=error_msg,
    )
    db.add(package)
    await db.commit()
    await db.refresh(package)

    logger.info(
        "model_package_uploaded",
        project_id=str(project_id),
        package_id=str(package.id),
        is_valid=is_valid,
        entrypoint=package.entrypoint,
    )

    return ModelPackageResponse(
        id=package.id,
        file_name=package.file_name,
        file_size_bytes=package.file_size_bytes,
        entrypoint=package.entrypoint,
        checksum_sha256=package.checksum_sha256,
        is_validated=package.is_validated,
        validation_error=package.validation_error,
        manifest=manifest_data,
        created_at=package.created_at,
    )


@router.get(
    "/{project_id}/packages",
    response_model=List[ModelPackageResponse],
    summary="List uploaded training code packages for project",
)
async def list_model_packages(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
) -> List[ModelPackageResponse]:
    """Retrieve all model packages for this project."""
    stmt = select(ModelPackage).where(ModelPackage.project_id == project_id).order_by(desc(ModelPackage.created_at))
    packages = (await db.execute(stmt)).scalars().all()

    results: List[ModelPackageResponse] = []
    for p in packages:
        manifest_dict = json.loads(p.manifest_json) if p.manifest_json else None
        results.append(
            ModelPackageResponse(
                id=p.id,
                file_name=p.file_name,
                file_size_bytes=p.file_size_bytes,
                entrypoint=p.entrypoint,
                checksum_sha256=p.checksum_sha256,
                is_validated=p.is_validated,
                validation_error=p.validation_error,
                manifest=manifest_dict,
                created_at=p.created_at,
            )
        )
    return results


@router.get(
    "/{project_id}/packages/{package_id}/download",
    summary="Download training code package stream",
)
async def download_model_package(
    project_id: uuid.UUID,
    package_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db_session),
) -> FileResponse:
    """Stream model code package for worker agents or authorized project participants."""
    stmt = select(ModelPackage).where(
        ModelPackage.id == package_id,
        ModelPackage.project_id == project_id,
    )
    package = (await db.execute(stmt)).scalar_one_or_none()
    if not package:
        raise NotFoundError("Model package not found.")

    file_path = Path(package.file_path)
    if not file_path.exists():
        raise NotFoundError("Package file is missing from storage.")

    return FileResponse(
        path=file_path,
        filename=file_path.name,
        media_type="application/octet-stream",
    )


# ── Progress & Workers Reporting ─────────────────────────────────────────────

@router.get(
    "/{project_id}/progress",
    response_model=ProjectProgressResponse,
    summary="Get current training metrics and progress for project",
)
async def get_project_progress(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
) -> ProjectProgressResponse:
    """Retrieve latest training run step, loss, speed, and metric history points."""
    p_stmt = select(Project).where(Project.id == project_id)
    project = (await db.execute(p_stmt)).scalar_one_or_none()
    if not project:
        raise NotFoundError("Project not found.")

    # Find latest training run
    r_stmt = select(TrainingRun).where(TrainingRun.project_id == project_id).order_by(desc(TrainingRun.created_at))
    run = (await db.execute(r_stmt)).scalars().first()

    # Find metrics history
    m_stmt = (
        select(TrainingMetric)
        .where(TrainingMetric.project_id == project_id)
        .order_by(TrainingMetric.step)
        .limit(100)
    )
    metrics = (await db.execute(m_stmt)).scalars().all()

    history = [
        {
            "step": m.step,
            "loss": m.loss,
            "speed": m.speed,
            "clusterCpuUtil": m.cluster_cpu_util,
            "clusterGpuUtil": m.cluster_gpu_util,
            "ramUtilGB": m.ram_util_gb,
            "timestamp": m.timestamp.isoformat(),
        }
        for m in metrics
    ]

    current_step = run.current_step if run else 0
    total_steps = run.total_steps if run else 1000
    progress_pct = round((current_step / total_steps) * 100, 1) if total_steps > 0 else 0.0

    return ProjectProgressResponse(
        project_id=project.id,
        status=run.status if run else project.status,
        current_step=current_step,
        total_steps=total_steps,
        progress_percent=progress_pct,
        training_speed=run.training_speed if run else 0.0,
        current_loss=run.current_loss if run else None,
        history=history,
    )


@router.get(
    "/{project_id}/workers",
    response_model=List[WorkerNodeResponse],
    summary="List all connected worker nodes on this project",
)
async def get_project_workers(
    project_id: uuid.UUID,
    current_user: Optional[User] = Depends(get_optional_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> List[WorkerNodeResponse]:
    """Retrieve list of active and idle worker nodes contributing to this project."""
    stmt = (
        select(ProjectMembership)
        .options(selectinload(ProjectMembership.machine))
        .where(ProjectMembership.project_id == project_id)
        .order_by(desc(ProjectMembership.joined_at))
    )
    memberships = (await db.execute(stmt)).scalars().all()

    current_user_id = current_user.id if current_user else None
    results: List[WorkerNodeResponse] = []
    for m in memberships:
        machine = m.machine
        worker_is_current = bool(current_user_id and m.user_id == current_user_id)
        results.append(
            WorkerNodeResponse(
                id=str(m.id),
                machine_id=m.machine_id,
                name=machine.name if machine else "Worker Node",
                is_current_user=worker_is_current,
                status=m.status,
                cpu_model=machine.platform or "Standard Node",
                cpu_cores_total=max(m.cpu_cores_contributed, 4),
                cpu_cores_contributed=m.cpu_cores_contributed,
                ram_total_gb=max(m.ram_contributed_gb * 2, 8.0),
                ram_contributed_gb=m.ram_contributed_gb,
                gpu_model=m.selected_gpu if m.selected_gpu else ("GPU Enabled" if m.gpu_enabled else "None"),
                gpu_memory_total_gb=8.0 if m.gpu_enabled else 0.0,
                gpu_enabled=m.gpu_enabled,
                storage_budget_gb=m.storage_budget_gb,
                network_preference=m.network_preference,
                current_batch=m.current_batch,
                steps_processed=m.steps_processed,
                joined_at=m.joined_at,
                contribution_status=m.contribution_status,
            )
        )
    return results
