"""文件管理路由

提供文件上传、列表、删除等接口。
"""

import uuid
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel

from backend.api.deps import UploadDir, ValidatedUploadFile, get_upload_dir

router = APIRouter()


class FileInfo(BaseModel):
    """文件信息"""

    id: str
    filename: str
    size: int
    content_type: str
    upload_time: str
    path: str


class FileListResponse(BaseModel):
    """文件列表响应"""

    files: list[FileInfo]
    total: int


def get_file_info(file_path: Path, base_dir: Path) -> FileInfo:
    """获取文件信息"""
    stat = file_path.stat()
    return FileInfo(
        id=file_path.stem.split("_")[0] if "_" in file_path.stem else file_path.stem,
        filename=file_path.name.split("_", 1)[-1] if "_" in file_path.name else file_path.name,
        size=stat.st_size,
        content_type=_get_content_type(file_path.suffix),
        upload_time=datetime.fromtimestamp(stat.st_ctime).isoformat(),
        path=str(file_path.relative_to(base_dir)),
    )


def _get_content_type(suffix: str) -> str:
    """根据文件后缀获取内容类型"""
    content_types: dict[str, str] = {
        ".csv": "text/csv",
        ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ".xls": "application/vnd.ms-excel",
        ".json": "application/json",
        ".txt": "text/plain",
        ".parquet": "application/octet-stream",
        ".feather": "application/octet-stream",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
        ".svg": "image/svg+xml",
        ".pdf": "application/pdf",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".doc": "application/msword",
    }
    return content_types.get(suffix.lower(), "application/octet-stream")


@router.post("/upload", response_model=FileInfo, status_code=status.HTTP_201_CREATED)
async def upload_file(
    file: ValidatedUploadFile,
    upload_dir: UploadDir,
) -> FileInfo:
    """上传单个文件

    Args:
        file: 上传的文件
        upload_dir: 上传目录

    Returns:
        文件信息
    """
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="文件名不能为空",
        )

    file_id = str(uuid.uuid4())[:8]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_filename = f"{file_id}_{timestamp}_{file.filename}"
    file_path = upload_dir / safe_filename

    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)

    return get_file_info(file_path, upload_dir)


@router.post("/upload/multiple", response_model=list[FileInfo], status_code=status.HTTP_201_CREATED)
async def upload_multiple_files(
    files: list[UploadFile] = File(...),
    upload_dir: Path = Depends(get_upload_dir),
) -> list[FileInfo]:
    """上传多个文件

    Args:
        files: 上传的文件列表
        upload_dir: 上传目录

    Returns:
        文件信息列表
    """
    results = []
    for file in files:
        if file.filename:
            file_id = str(uuid.uuid4())[:8]
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_filename = f"{file_id}_{timestamp}_{file.filename}"
            file_path = upload_dir / safe_filename

            content = await file.read()
            with open(file_path, "wb") as f:
                f.write(content)

            results.append(get_file_info(file_path, upload_dir))

    return results


@router.get("/files", response_model=FileListResponse)
async def list_files(
    upload_dir: UploadDir,
    page: int = 1,
    page_size: int = 20,
    extension: str | None = None,
) -> FileListResponse:
    """获取文件列表

    Args:
        upload_dir: 上传目录
        page: 页码
        page_size: 每页数量
        extension: 按扩展名过滤

    Returns:
        文件列表
    """
    all_files = list(upload_dir.glob("*"))
    all_files = [f for f in all_files if f.is_file()]

    if extension:
        all_files = [f for f in all_files if f.suffix.lower() == f".{extension.lower()}"]

    all_files.sort(key=lambda x: x.stat().st_ctime, reverse=True)

    total = len(all_files)
    start = (page - 1) * page_size
    end = start + page_size
    paginated_files = all_files[start:end]

    files_info = [get_file_info(f, upload_dir) for f in paginated_files]

    return FileListResponse(files=files_info, total=total)


@router.get("/files/{file_id}", response_model=FileInfo)
async def get_file(
    file_id: str,
    upload_dir: UploadDir,
) -> FileInfo:
    """获取文件详情

    Args:
        file_id: 文件 ID
        upload_dir: 上传目录

    Returns:
        文件信息
    """
    matching_files = list(upload_dir.glob(f"{file_id}_*"))

    if not matching_files:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"文件不存在: {file_id}",
        )

    return get_file_info(matching_files[0], upload_dir)


@router.delete("/files/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_file(
    file_id: str,
    upload_dir: UploadDir,
) -> None:
    """删除文件

    Args:
        file_id: 文件 ID
        upload_dir: 上传目录
    """
    matching_files = list(upload_dir.glob(f"{file_id}_*"))

    if not matching_files:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"文件不存在: {file_id}",
        )

    for file_path in matching_files:
        file_path.unlink()
