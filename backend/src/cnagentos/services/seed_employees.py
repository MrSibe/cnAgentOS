"""Default seed data for Phase 7 digital employees and built-in tools.

Called from bootstrap.py during first-time initialization.
"""

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from cnagentos.models.entities import DigitalEmployee, ModelConfig, Tool, utc_now
from cnagentos.services.tool import register_builtin

SEED_EMPLOYEES = [
    {
        "code": "sichuan_agri",
        "name": "川农小助手",
        "description": "回答四川农业大学相关问题",
        "system_prompt": (
            "你是四川农业大学的智能校园助手。你可以回答关于四川农业大学"
            "（简称川农）的各类问题，包括但不限于：学校概况、校区分布"
            "（成都校区、雅安校区、都江堰校区）、院系设置、专业介绍、"
            "招生政策、校园生活、社团活动、就业信息等。"
            "请用友好、热情的语气回答，展现川农学子的风采。"
            "如果你不确定某个具体信息，请如实告知用户，不要编造。"
        ),
        "trigger_type": "mention",
        "max_turns": 20,
    },
    {
        "code": "weather",
        "name": "天气小助手",
        "description": "查询全国各地实时天气",
        "system_prompt": (
            "你是天气小助手，可以帮助用户查询全国各地的实时天气信息。"
            "当用户提到城市名时，请查询该城市的天气数据并返回详细的天气信息，"
            "包括温度、天气状况、湿度、风向风速等。"
            "请用友好的语气与用户交流，并根据天气情况给出适当的建议"
            "（如带伞、防晒、增减衣物等）。"
        ),
        "trigger_type": "mention",
        "max_turns": 10,
    },
    {
        "code": "dark_chicken_soup",
        "name": "毒鸡汤助手",
        "description": "给你一碗清醒的毒鸡汤",
        "system_prompt": (
            "你是一名毒鸡汤大师，专门提供现实又扎心的\"毒鸡汤\"。"
            "你的风格特点是：简短、尖锐、幽默中带着清醒。"
            "不要安慰用户，而是要给出让人反思的犀利回击。"
            "每句话都要有\"毒性\"，但也要有道理。"
            "可以适度调侃，但不要恶意攻击。用中文回答，每条回复控制在100字以内。"
        ),
        "trigger_type": "mention",
        "max_turns": 10,
    },
    {
        "code": "general_ai",
        "name": "通用 AI 助手",
        "description": "通用知识问答助手",
        "system_prompt": (
            "你是一名通用 AI 助手，可以帮助用户回答各种问题。"
            "你的范围包括：百科知识、学习辅导、生活建议、技术咨询、"
            "创意灵感、文本处理等。请用专业、清晰、有条理的方式回答用户的问题。"
            "对于不确定的信息，请诚实告知用户。"
        ),
        "trigger_type": "mention",
        "max_turns": 30,
    },
]

SEED_TOOLS = [
    {
        "code": "weather_query",
        "name": "天气查询",
        "description": "查询指定城市的实时天气数据",
        "tool_type": "builtin_function",
        "config": {
            "api_url": "https://wttr.in/{city}?format=j1",
            "method": "GET",
            "timeout_seconds": 10,
        },
        "invocation_limit": 50,
        "invocation_window_seconds": 3600,
    },
]


async def seed_phase7_default_data(session: AsyncSession) -> None:
    """Seed default digital employees and built-in tools if they don't exist."""
    # Seed tools first (employees may reference them)
    for tool_data in SEED_TOOLS:
        existing = await session.scalar(
            select(Tool).where(Tool.code == tool_data["code"]),
        )
        if existing:
            continue
        tool = Tool(
            id=str(__import__("uuid").uuid4()),
            code=tool_data["code"],
            name=tool_data["name"],
            description=tool_data["description"],
            tool_type=tool_data["tool_type"],
            config=tool_data["config"],
            invocation_limit=tool_data["invocation_limit"],
            invocation_window_seconds=tool_data["invocation_window_seconds"],
            status="active",
        )
        session.add(tool)
        await session.flush()

    # Seed digital employees
    from cnagentos.models.entities import User
    from cnagentos.services.bootstrap import SYSTEM_TASK_USER_ID

    task_user = await session.get(User, SYSTEM_TASK_USER_ID)
    task_user_id = task_user.id if task_user else None

    for emp_data in SEED_EMPLOYEES:
        existing = await session.scalar(
            select(DigitalEmployee).where(DigitalEmployee.code == emp_data["code"]),
        )
        if existing:
            continue

        # Find default model if possible
        model_config_id = None
        default_model = await session.scalar(
            select(ModelConfig).where(
                ModelConfig.status == "active",
                ModelConfig.is_default == True,  # noqa: E712
            )
        )
        if default_model:
            model_config_id = default_model.id

        emp = DigitalEmployee(
            id=str(__import__("uuid").uuid4()),
            code=emp_data["code"],
            name=emp_data["name"],
            description=emp_data["description"],
            system_prompt=emp_data["system_prompt"],
            model_config_id=model_config_id,
            trigger_type=emp_data["trigger_type"],
            max_turns=emp_data["max_turns"],
            status="active",
            created_by=task_user_id,
        )
        session.add(emp)
        await session.flush()

    await session.commit()


# =============================================================================
# Built-in tool handler: weather_query
# =============================================================================


@register_builtin("weather_query")
async def handle_weather_query(params: dict) -> dict:
    """Handle weather query built-in tool.

    Expects ``{"city": "成都"}`` and returns structured weather data.
    """
    city = params.get("city", "")
    if not city:
        return {"error": "请提供城市名"}

    # URL-encode city name
    import urllib.parse
    encoded_city = urllib.parse.quote(city)

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(f"https://wttr.in/{encoded_city}?format=j1")
        resp.raise_for_status()
        data = resp.json()

    current = data.get("current_condition", [{}])[0]
    nearest_area = data.get("nearest_area", [{}])[0]
    area_name = nearest_area.get("areaName", [{}])[0].get("value", city)

    result = {
        "city": area_name,
        "temp_c": current.get("temp_C", "N/A"),
        "temp_f": current.get("temp_F", "N/A"),
        "humidity": current.get("humidity", "N/A"),
        "weather_desc": current.get("weatherDesc", [{}])[0].get("value", "N/A"),
        "wind_dir": current.get("winddir16Point", "N/A"),
        "wind_speed_kmph": current.get("windspeedKmph", "N/A"),
        "visibility": current.get("visibility", "N/A"),
        "pressure": current.get("pressure", "N/A"),
        "feels_like_c": current.get("FeelsLikeC", "N/A"),
    }
    return result
