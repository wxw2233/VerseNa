from pathlib import Path

class FileParser:
    # 文件类型分类
    TEXT_TYPES = {
        ".txt", ".md", ".py", ".js", ".ts", ".jsx", ".tsx", ".json", ".csv",
        ".html", ".htm", ".css", ".scss", ".xml", ".yaml", ".yml", ".toml",
        ".ini", ".cfg", ".conf", ".env", ".sh", ".bash", ".bat", ".ps1",
        ".sql", ".r", ".rb", ".go", ".rs", ".java", ".c", ".cpp", ".h",
        ".hpp", ".cs", ".swift", ".kt", ".php", ".lua", ".zig", ".vue",
        ".svelte", ".log", ".gitignore", ".dockerfile", ".makefile",
    }

    @staticmethod
    def parse(file_path: str) -> str:
        path = Path(file_path)
        ext = path.suffix.lower()
        name = path.name.lower()

        # 已知文本类型 → 直接读
        if ext in FileParser.TEXT_TYPES:
            return FileParser._read_text(path)

        # 无扩展名的常见文本文件
        if not ext and name in {"makefile", "dockerfile", "readme", "license", "changelog"}:
            return FileParser._read_text(path)

        # PDF（需要 PyPDF2，可选）
        if ext == ".pdf":
            try:
                from PyPDF2 import PdfReader
                reader = PdfReader(str(path))
                text = "\n".join(page.extract_text() or "" for page in reader.pages)
                return text[:10000] or "[PDF 无法提取文本]"
            except ImportError:
                return "[需要安装 PyPDF2: pip install PyPDF2]"
            except Exception as e:
                return f"[PDF 解析失败: {e}]"

        # Word（需要 python-docx，可选）
        if ext in (".docx", ".doc"):
            try:
                from docx import Document
                doc = Document(str(path))
                text = "\n".join(p.text for p in doc.paragraphs)
                return text[:10000] or "[文档为空]"
            except ImportError:
                return "[需要安装 python-docx: pip install python-docx]"
            except Exception as e:
                return f"[文档解析失败: {e}]"

        # 兜底：尝试当文本读，但过滤掉二进制文件
        try:
            raw = path.read_bytes()
            if b"\x00" in raw[:1024]:
                return f"[不支持的文件类型: {ext}（二进制文件）]"
            return raw.decode("utf-8", errors="replace")[:10000]
        except Exception:
            return f"[不支持的文件类型: {ext}]"

    @staticmethod
    def _read_text(path: Path) -> str:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
            return text[:10000]
        except Exception as e:
            return f"[读取失败: {e}]"
