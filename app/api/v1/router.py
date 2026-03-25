"""
app/api/v1/router.py
────────────────────
Aggregates all v1 endpoint routers into a single APIRouter.

Adding a new domain (e.g. notifications) requires only one line here.
"""

from fastapi import APIRouter

from app.api.v1.endpoints import analytics, auth, polls, votes

api_router = APIRouter(prefix="/api")

api_router.include_router(auth.router)
api_router.include_router(polls.router)
api_router.include_router(votes.router)
api_router.include_router(analytics.router)
