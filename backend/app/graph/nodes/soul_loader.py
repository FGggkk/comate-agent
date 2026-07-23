from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.graph.state import ChatState
from app.graph.schemas import status_event
from app.models.soul import UserSoul


async def load_soul_node(state: ChatState, db: AsyncSession):
    """Step 2: 加载用户当前 SOUL"""
    result = await db.execute(
        select(UserSoul).where(
            UserSoul.user_id == state.user_id,
            UserSoul.status == "active",
        )
    )
    user_soul = result.scalar_one_or_none()
    if user_soul:
        state.compiled_soul = user_soul.soul_markdown
        state.soul_id = str(user_soul.id)
    else:
        state.compiled_soul = "You are 伴行agent, a helpful AI companion."

    return [status_event("soul", "已加载你的专属伙伴风格")]
