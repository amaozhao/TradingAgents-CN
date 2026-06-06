from __future__ import annotations

import asyncio

from sqlalchemy import text

from app.core.session import get_session_factory, init_postgres


async def main() -> None:
    await init_postgres()
    async with get_session_factory()() as session:
        structured_result = await session.execute(
            text(
                """
                with source_industries as (
                    select code, max(trim(industry)) as industry
                    from stock_basic_info
                    where source = 'baostock'
                      and industry is not null
                      and trim(industry) <> ''
                      and lower(trim(industry)) not in ('-', '未知', 'nan', 'none', 'null')
                    group by code
                )
                update stock_basic_info target
                set industry = source_industries.industry,
                    payload = jsonb_set(
                        coalesce(target.payload, '{}'::jsonb),
                        '{industry}',
                        to_jsonb(source_industries.industry),
                        true
                    ),
                    updated_at = now()
                from source_industries
                where target.source = 'akshare'
                  and target.code = source_industries.code
                  and (
                    target.industry is null
                    or trim(target.industry) = ''
                    or lower(trim(target.industry)) in ('-', '未知', 'nan', 'none', 'null')
                  )
                """
            )
        )

        document_result = await session.execute(
            text(
                """
                with source_industries as (
                    select code, max(trim(industry)) as industry
                    from stock_basic_info
                    where source = 'baostock'
                      and industry is not null
                      and trim(industry) <> ''
                      and lower(trim(industry)) not in ('-', '未知', 'nan', 'none', 'null')
                    group by code
                )
                update postgres_documents target
                set payload = jsonb_set(
                        target.payload,
                        '{industry}',
                        to_jsonb(source_industries.industry),
                        true
                    ),
                    updated_at = now()
                from source_industries
                where target.collection = 'stock_basic_info'
                  and target.payload->>'source' = 'akshare'
                  and target.payload->>'code' = source_industries.code
                  and (
                    target.payload->>'industry' is null
                    or trim(target.payload->>'industry') = ''
                    or lower(trim(target.payload->>'industry')) in ('-', '未知', 'nan', 'none', 'null')
                  )
                """
            )
        )
        await session.commit()

    print(
        "backfilled",
        {
            "stock_basic_info": int(structured_result.rowcount or 0),
            "postgres_documents": int(document_result.rowcount or 0),
        },
    )


if __name__ == "__main__":
    asyncio.run(main())
