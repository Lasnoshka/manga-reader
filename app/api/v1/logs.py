from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pathlib import Path
from datetime import datetime
import re

router = APIRouter(prefix="/logs", tags=["logs"])

LOG_DIR = Path("logs")
LOG_PATTERN = re.compile(r"Logs_(\d{4})_(\d{2})_(\d{2})\.log")


@router.get("/download/")
async def download_log_by_date(date: str):
    """
    Скачать лог-файл за указанную дату.
    Формат date: YYYY-MM-DD (например 2026-04-16)
    """
    # Парсим дату
    try:
        year, month, day = map(int, date.split('-'))
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")

    # Ищем файл (прямое совпадение)
    expected_filename = f"Logs_{year:04d}_{month:02d}_{day:02d}.log"
    file_path = LOG_DIR / expected_filename

    if not file_path.exists():
        # Проверяем файлы с точкой (от старого handler)
        alt_filename = f"Logs.{year:04d}_{month:02d}_{day:02d}.log"
        alt_path = LOG_DIR / alt_filename
        if alt_path.exists():
            file_path = alt_path
        else:
            # Получаем список всех доступных дат для подсказки
            available = _get_available_dates()
            raise HTTPException(
                status_code=404,
                detail=f"No log file found for date {date}. Available dates: {available}"
            )

    return FileResponse(
        path=str(file_path),
        filename=file_path.name,
        media_type="text/plain"
    )


@router.get("/available/")
async def get_available_log_dates():
    """Получить список дат, за которые есть лог-файлы"""
    dates = _get_available_dates()
    return {
        "available_dates": dates,
        "count": len(dates)
    }


def _get_available_dates() -> list:
    """Возвращает отсортированный список доступных дат"""
    dates = set()

    # Ищем файлы с подчёркиванием (новый формат)
    for file in LOG_DIR.glob("Logs_*.log"):
        match = LOG_PATTERN.match(file.name)
        if match:
            year, month, day = match.groups()
            dates.add(f"{year}-{month}-{day}")

    # Ищем файлы с точкой (старый формат)
    for file in LOG_DIR.glob("Logs.*.log"):
        name = file.name
        # Logs.2026_04_16.log
        parts = name.replace("Logs.", "").replace(".log", "").split("_")
        if len(parts) == 3:
            dates.add(f"{parts[0]}-{parts[1]}-{parts[2]}")

    # Текущий файл Logs (если есть)
    current_file = LOG_DIR / "Logs"
    if current_file.exists():
        # Берём дату модификации файла
        mtime = datetime.fromtimestamp(current_file.stat().st_mtime)
        dates.add(mtime.strftime("%Y-%m-%d"))

    return sorted(dates, reverse=True)


@router.get("/view/")
async def view_log_by_date(date: str, lines: int = 100):
    """
    Просмотреть содержимое лог-файла за указанную дату.
    Возвращает последние N строк.
    """
    try:
        year, month, day = map(int, date.split('-'))
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")

    expected_filename = f"Logs_{year:04d}_{month:02d}_{day:02d}.log"
    file_path = LOG_DIR / expected_filename

    if not file_path.exists():
        alt_path = LOG_DIR / f"Logs.{year:04d}_{month:02d}_{day:02d}.log"
        if alt_path.exists():
            file_path = alt_path
        else:
            raise HTTPException(status_code=404, detail=f"No log file found for date {date}")

    # Читаем последние N строк
    with open(file_path, "r", encoding="utf-8") as f:
        all_lines = f.readlines()
        last_lines = all_lines[-lines:] if len(all_lines) > lines else all_lines

    return {
        "date": date,
        "filename": file_path.name,
        "total_lines": len(all_lines),
        "content": "".join(last_lines)
    }
