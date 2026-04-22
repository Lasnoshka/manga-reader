def manga_list_key(
    page: int,
    size: int,
    sort_by: str,
    sort_desc: bool,
    title_contains: str | None,
    author_contains: str | None,
    genre: str | None = None,
) -> str:
    return (
        "manga:list:"
        f"page={page}:size={size}:sort={sort_by}:desc={int(sort_desc)}:"
        f"title={title_contains or ''}:author={author_contains or ''}:genre={genre or ''}"
    )


def manga_detail_key(manga_id: int) -> str:
    return f"manga:detail:{manga_id}"


def manga_popular_key(limit: int) -> str:
    return f"manga:popular:{limit}"


def manga_cache_pattern() -> str:
    return "manga:*"


def manga_views_key() -> str:
    return "stats:manga:views"


def chapter_pages_key(chapter_id: int) -> str:
    return f"chapter:{chapter_id}:pages"


def manga_chapters_key(manga_id: int) -> str:
    return f"manga:{manga_id}:chapters"


def search_results_key(query: str, genre: str | None, limit: int) -> str:
    return f"search:q={query}:genre={genre or ''}:limit={limit}"


def genres_list_key() -> str:
    return "genres:list"
