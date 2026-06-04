# ruff: noqa: F401,F403,F405,F821
def _coerce_datetime(value: Any) -> Optional[datetime]:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        text = value.strip()
        if text.endswith("Z"):
            text = f"{text[:-1]}+00:00"
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError:
            return None
    else:
        return None

    if parsed.tzinfo is not None:
        return parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed


async def _get_analysis_task_for_read(task_id: str) -> Optional[Dict[str, Any]]:
    if settings.POSTGRES_READ_ENABLED:
        try:
            get_analysis_task_by_task_id = getattr(
                importlib.import_module("app.db.analysis"),
                "get_analysis_task_by_task_id",
            )
            get_session_factory = getattr(
                importlib.import_module("app.core.session"), "get_session_factory"
            )

            async with get_session_factory()() as session:
                document = await get_analysis_task_by_task_id(session, task_id)
            if document:
                return document
        except Exception as e:
            logger.warning("PostgreSQL分析任务查询失败，回退PostgreSQL: %s", e)

    get_postgres_db = getattr(
        importlib.import_module("app.core.database"), "get_postgres_db"
    )
    db = get_postgres_db()
    return await db.analysis_tasks.find_one({"task_id": task_id})


async def _get_analysis_report_by_task_id_for_read(
    task_id: str,
) -> Optional[Dict[str, Any]]:
    if settings.POSTGRES_READ_ENABLED:
        try:
            get_analysis_report_by_task_id = getattr(
                importlib.import_module("app.db.analysis"),
                "get_analysis_report_by_task_id",
            )
            get_session_factory = getattr(
                importlib.import_module("app.core.session"), "get_session_factory"
            )

            async with get_session_factory()() as session:
                document = await get_analysis_report_by_task_id(session, task_id)
            if document:
                return document
        except Exception as e:
            logger.warning("PostgreSQL分析报告按task_id查询失败，回退PostgreSQL: %s", e)

    get_postgres_db = getattr(
        importlib.import_module("app.core.database"), "get_postgres_db"
    )
    db = get_postgres_db()
    return await db.analysis_reports.find_one({"task_id": task_id})


async def _get_analysis_report_by_analysis_id_for_read(
    analysis_id: str,
) -> Optional[Dict[str, Any]]:
    if settings.POSTGRES_READ_ENABLED:
        try:
            get_analysis_report_by_analysis_id = getattr(
                importlib.import_module("app.db.analysis"),
                "get_analysis_report_by_analysis_id",
            )
            get_session_factory = getattr(
                importlib.import_module("app.core.session"), "get_session_factory"
            )

            async with get_session_factory()() as session:
                document = await get_analysis_report_by_analysis_id(
                    session, analysis_id
                )
            if document:
                return document
        except Exception as e:
            logger.warning(
                "PostgreSQL分析报告按analysis_id查询失败，回退PostgreSQL: %s", e
            )

    get_postgres_db = getattr(
        importlib.import_module("app.core.database"), "get_postgres_db"
    )
    db = get_postgres_db()
    return await db.analysis_reports.find_one({"analysis_id": analysis_id})


# 兼容性：保留原有的请求模型
class SingleAnalyzeRequest(BaseModel):
    symbol: str
    parameters: dict = Field(default_factory=dict)


class BatchAnalyzeRequest(BaseModel):
    symbols: List[str]
    parameters: dict = Field(default_factory=dict)
    title: str = Field(default="批量分析", description="批次标题")
    description: Optional[str] = Field(None, description="批次描述")


class AnalysisTestRouteResponse(BaseModel):
    message: str
    timestamp: float


class AnalysisQueueTaskResponse(BaseModel):
    task_id: str
    status: str


class AnalysisQueueBatchResponse(BaseModel):
    batch_id: str
    submitted: int


class AnalysisLooseObjectResponse(BaseModel):
    model_config = ConfigDict(extra="allow")


class AnalysisOperationResponse(BaseModel):
    success: bool
    message: str


class AnalysisDataResponse(BaseModel):
    success: bool
    data: Any
    message: Optional[str] = None


class ZombieTasksResponse(BaseModel):
    success: bool
    data: List[Dict[str, Any]]
    total: int
    max_running_hours: int
