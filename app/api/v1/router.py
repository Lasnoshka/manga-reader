from fastapi import APIRouter

from app.api.v1 import logs
from app.api.v1.bookmark import router as bookmark_router
from app.api.v1.chapter_routes import router as chapter_router
from app.api.v1.comment import router as comment_router
from app.api.v1.like import router as like_router
from app.api.v1.manga_routes import router as manga_router
from app.api.v1.page_routes import router as page_router
from app.api.v1.progress import router as progress_router
from app.api.v1.rating import router as rating_router
from app.api.v1.reader_routes import router as reader_router
from app.api.v1.user import router as auth_router

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(manga_router)
api_router.include_router(chapter_router)
api_router.include_router(page_router)
api_router.include_router(reader_router)
api_router.include_router(progress_router)
api_router.include_router(bookmark_router)
api_router.include_router(like_router)
api_router.include_router(rating_router)
api_router.include_router(comment_router)
api_router.include_router(logs.router)
