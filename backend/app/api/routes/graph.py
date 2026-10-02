"""Knowledge-graph browsing."""

from fastapi import APIRouter, HTTPException, Query

from app.api.deps import ContainerDep
from app.schemas.graph import GraphExport, RelatedNodes

router = APIRouter(prefix="/graph", tags=["graph"])


@router.get("", response_model=GraphExport)
def export_graph(c: ContainerDep):
    return c.graph.export()


@router.get("/nodes/{node_id}/related", response_model=RelatedNodes)
def related_nodes(node_id: str, c: ContainerDep, hops: int = Query(1, ge=1, le=3)):
    if c.graph.node(node_id) is None:
        raise HTTPException(status_code=404, detail=f"Unknown graph node: {node_id}")
    return RelatedNodes(node_id=node_id, related=c.graph.related(node_id, hops=hops))
