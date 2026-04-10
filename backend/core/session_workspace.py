"""会话工作区管理。

负责把用户上传文件整理到每次分析的隔离目录中。
"""

import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

DATA_EXTENSIONS = {".csv", ".xlsx", ".xls", ".json", ".parquet", ".feather", ".txt"}


@dataclass
class SessionWorkspace:
    """单次会话的文件工作区。"""

    session_id: str
    root_dir: Path
    input_dir: Path
    workspace_dir: Path
    output_dir: Path
    input_files: list[Path] = field(default_factory=list)

    def to_context(self) -> dict[str, Any]:
        """转换为可注入 Agent 的上下文字典。"""
        return {
            "session_id": self.session_id,
            "root_dir": str(self.root_dir),
            "input_dir": str(self.input_dir),
            "workspace_dir": str(self.workspace_dir),
            "output_dir": str(self.output_dir),
            "input_files": [str(path) for path in self.input_files],
        }


class SessionWorkspaceManager:
    """会话工作区管理器。"""

    def __init__(
        self,
        sessions_root: str | Path = "data/sessions",
        uploads_dir: str | Path = "data/uploads",
    ) -> None:
        self.sessions_root = Path(sessions_root)
        self.uploads_dir = Path(uploads_dir)

    def prepare(
        self,
        session_id: str,
        user_query: str = "",
        user_context: dict[str, Any] | None = None,
    ) -> SessionWorkspace:
        """准备会话目录并复制用户数据文件。"""
        safe_session_id = self._safe_name(session_id or "default")
        root_dir = self.sessions_root / safe_session_id
        input_dir = root_dir / "input"
        workspace_dir = root_dir / "workspace"
        output_dir = root_dir / "output"

        for directory in (input_dir, workspace_dir, output_dir):
            directory.mkdir(parents=True, exist_ok=True)

        source_files = self._collect_source_files(user_query, user_context or {})
        input_files = self._copy_inputs(source_files, input_dir)

        return SessionWorkspace(
            session_id=safe_session_id,
            root_dir=root_dir,
            input_dir=input_dir,
            workspace_dir=workspace_dir,
            output_dir=output_dir,
            input_files=input_files,
        )

    def _collect_source_files(self, user_query: str, user_context: dict[str, Any]) -> list[Path]:
        """从上下文、文本路径和上传目录中收集候选文件。"""
        candidates: list[Path] = []

        for key in ("file_paths", "files", "uploaded_files"):
            value = user_context.get(key)
            if isinstance(value, str):
                candidates.append(Path(value))
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, str):
                        candidates.append(Path(item))
                    elif isinstance(item, dict):
                        path_value = item.get("path") or item.get("file_path")
                        file_id = item.get("id") or item.get("file_id")
                        if path_value:
                            candidates.append(Path(str(path_value)))
                        elif file_id:
                            candidates.extend(self._find_by_file_id(str(file_id)))

        file_id = user_context.get("file_id")
        if file_id:
            candidates.extend(self._find_by_file_id(str(file_id)))

        candidates.extend(self._extract_paths_from_text(user_query))

        resolved = []
        for candidate in candidates:
            source = self._resolve_user_file(candidate)
            if source and source not in resolved:
                resolved.append(source)

        if resolved:
            return resolved

        latest = self._latest_uploaded_data_file()
        return [latest] if latest else []

    def _copy_inputs(self, source_files: list[Path], input_dir: Path) -> list[Path]:
        """复制输入文件到会话 input 目录。"""
        copied: list[Path] = []
        for source in source_files:
            target = input_dir / source.name
            if source.resolve() != target.resolve():
                shutil.copy2(source, target)
            copied.append(target)
        return copied

    def _resolve_user_file(self, path: Path) -> Path | None:
        """解析用户文件，限制在上传目录或项目数据目录内。"""
        if not path.is_absolute():
            upload_candidate = self.uploads_dir / path
            path = upload_candidate if upload_candidate.exists() else Path(path)

        try:
            resolved = path.resolve()
        except OSError:
            return None

        allowed_roots = [self.uploads_dir.resolve(), Path("data").resolve()]
        if not resolved.exists() or not resolved.is_file():
            return None
        if resolved.suffix.lower() not in DATA_EXTENSIONS:
            return None

        for root in allowed_roots:
            try:
                resolved.relative_to(root)
                return resolved
            except ValueError:
                continue
        return None

    def _find_by_file_id(self, file_id: str) -> list[Path]:
        """按上传文件 ID 查找文件。"""
        if not self.uploads_dir.exists():
            return []
        return [path.resolve() for path in self.uploads_dir.glob(f"{file_id}_*") if path.is_file()]

    def _extract_paths_from_text(self, text: str) -> list[Path]:
        """从用户文本中提取数据文件路径。"""
        if not text:
            return []

        pattern = r"([A-Za-z]:\\[^\s\"']+\.(?:csv|xlsx|xls|json|parquet|feather|txt)|[^\s\"']+\.(?:csv|xlsx|xls|json|parquet|feather|txt))"
        return [Path(match.group(1).strip("。；，,;")) for match in re.finditer(pattern, text)]

    def _latest_uploaded_data_file(self) -> Path | None:
        """获取最近上传的数据文件。"""
        if not self.uploads_dir.exists():
            return None

        files = [
            path
            for path in self.uploads_dir.glob("*")
            if path.is_file() and path.suffix.lower() in DATA_EXTENSIONS and path.stat().st_size > 0
        ]
        if not files:
            return None
        return max(files, key=lambda path: path.stat().st_mtime).resolve()

    def _safe_name(self, value: str) -> str:
        """生成安全目录名。"""
        safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", value)
        return safe[:80] or "default"
