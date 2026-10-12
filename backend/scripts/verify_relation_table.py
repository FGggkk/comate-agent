"""只读验证：company_knowledge_relations 建表迁移是否成功（不写入任何数据）。

用法（在拥有 DATABASE_URL 的环境下）：
    cd backend
    ./.venv/Scripts/python.exe scripts/verify_relation_table.py
"""

import asyncio

from sqlalchemy import text

from app.db.session import async_session_factory


async def main() -> None:
    async with async_session_factory() as db:
        table_count = await db.scalar(
            text(
                "SELECT count(*) FROM information_schema.tables "
                "WHERE table_name = 'company_knowledge_relations'"
            )
        )
        print(f"company_knowledge_relations 表数量: {table_count}")
        if not table_count:
            print("❌ 表不存在，迁移未执行")
            return
        indexes = (
            await db.scalars(
                text(
                    "SELECT indexname FROM pg_indexes "
                    "WHERE tablename = 'company_knowledge_relations' ORDER BY indexname"
                )
            )
        ).all()
        print("✅ 表已创建")
        print("索引:", indexes or "（无）")
        columns = (
            await db.scalars(
                text(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_name = 'company_knowledge_relations' ORDER BY ordinal_position"
                )
            )
        ).all()
        print("字段:", list(columns))


if __name__ == "__main__":
    asyncio.run(main())
