from . import chat, content, gpt, indexing, projects, settings, sources, veo

routers = [
    content.router,
    indexing.router,
    sources.router,
    chat.router,
    projects.router,
    gpt.router,
    settings.router,
    veo.router,
]

__all__ = [
    "routers",
    "chat",
    "content",
    "gpt",
    "indexing",
    "projects",
    "settings",
    "sources",
    "veo",
]
