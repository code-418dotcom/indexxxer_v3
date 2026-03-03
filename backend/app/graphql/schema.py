"""
Strawberry GraphQL schema + FastAPI router.

Mounted at /api/v1/graphql — GraphiQL playground enabled at GET /api/v1/graphql.

Auth: resolvers call _require_auth(info) which reads Authorization / X-API-Token from request.
DB:   resolvers call _get_db(info) which reads an AsyncSession from context.
"""

from __future__ import annotations

from typing import Optional

import strawberry
from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from strawberry.fastapi import GraphQLRouter

from app.database import get_db
from app.graphql.resolvers import (
    resolve_analytics_overview,
    resolve_create_tag,
    resolve_delete_tag,
    resolve_media,
    resolve_search,
    resolve_sources,
)
from app.graphql.types import (
    AnalyticsOverviewGQL,
    MediaItemGQL,
    MediaSourceGQL,
    SearchInput,
    SearchResultGQL,
    TagGQL,
)


@strawberry.type
class Query:
    media: Optional[MediaItemGQL] = strawberry.field(resolver=resolve_media)
    search: SearchResultGQL = strawberry.field(resolver=resolve_search)
    sources: list[MediaSourceGQL] = strawberry.field(resolver=resolve_sources)
    analytics_overview: AnalyticsOverviewGQL = strawberry.field(
        resolver=resolve_analytics_overview
    )


@strawberry.type
class Mutation:
    create_tag: TagGQL = strawberry.mutation(resolver=resolve_create_tag)
    delete_tag: bool = strawberry.mutation(resolver=resolve_delete_tag)


async def get_context(request: Request, db: AsyncSession = Depends(get_db)):
    return {"request": request, "db": db}


schema = strawberry.Schema(query=Query, mutation=Mutation)
graphql_router = GraphQLRouter(schema, context_getter=get_context, graphql_ide="graphiql")
