# ruff: noqa: F401,F403,F405,F821
def create_database() -> PostgresDocumentDatabase:
    return PostgresDocumentDatabase()


def create_sync_database() -> SyncPostgresDocumentDatabase:
    return SyncPostgresDocumentDatabase()


def create_client() -> PostgresDocumentClient:
    return PostgresDocumentClient()


def create_sync_client() -> SyncPostgresDocumentClient:
    return SyncPostgresDocumentClient()


def build_document_upsert(collection: str, document: dict[str, Any]):
    document = normalize_payload(_ensure_document_id(document))
    now = datetime.now(timezone.utc)
    statement = insert(PostgresDocument).values(
        collection=collection,
        document_id=str(document["_id"]),
        payload=document,
        updated_at=now,
    )
    return statement.on_conflict_do_update(
        index_elements=[PostgresDocument.collection, PostgresDocument.document_id],
        set_={"payload": document, "updated_at": now},
    )


async def _ensure_postgres() -> None:
    try:
        get_session_factory()
    except RuntimeError:
        await init_postgres()


async def _write_specialized_table(collection: str, document: dict[str, Any]) -> None:
    if _model_for_collection(collection) is None:
        return
    try:
        await getattr(
            importlib.import_module("app.db.dual"), "dual_write_hot_document"
        )(collection, document, enabled=True, fail_open=True)
    except Exception:
        return


def _model_for_collection(collection: str) -> Any | None:
    if collection in CONFIG_COLLECTIONS:
        return SystemConfigDocument
    return SPECIALIZED_MODELS.get(collection)


def _build_specialized_select(collection: str, model: Any):
    statement = select(model)
    if collection in CONFIG_COLLECTIONS:
        return statement.where(model.config_type == collection)
    return statement
