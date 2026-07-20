from datetime import datetime, timezone, timedelta
from tools.base import BaseTool

WEEKDAYS = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]


class DateTimeTool(BaseTool):
    name = "datetime"
    description = "获取当前日期、时间、星期几等时间信息"
    parameters = {
        "type": "object",
        "properties": {
            "format": {"type": "string", "description": "输出格式，可选 'full' 或 'date' 或 'time'，默认 full"}
        },
        "required": []
    }

    async def execute(self, **kwargs) -> str:
        tz = timezone(timedelta(hours=8))
        now = datetime.now(tz)

        return (
            f"当前时间信息：\n"
            f"- 日期：{now.strftime('%Y年%m月%d日')}\n"
            f"- 时间：{now.strftime('%H:%M:%S')}\n"
            f"- 星期：{WEEKDAYS[now.weekday()]}\n"
            f"- 时区：UTC+8（北京时间）\n"
            f"- ISO 格式：{now.isoformat()}"
        )


def register(registry):
    registry.register(DateTimeTool())
