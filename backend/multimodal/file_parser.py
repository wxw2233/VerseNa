from pathlib import Path

class FileParser:
    SUPPORTED = {".txt", ".md", ".py", ".js", ".json", ".csv", ".html", ".css", ".xml", ".yaml", ".yml"}

    @staticmethod
    def parse(file_path: str) -> str:
        ext = Path(file_path).suffix.lower()
        if ext in FileParser.SUPPORTED:
            return Path(file_path).read_text(encoding="utf-8", errors="replace")[:10000]
        return f"[不支持的文件类型: {ext}]"
