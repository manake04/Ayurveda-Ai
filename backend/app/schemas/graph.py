"""Knowledge-graph response models."""

from pydantic import BaseModel


class GraphNode(BaseModel):
    id: str
    node_type: str
    label: str
    jurisdiction: str | None = None
    regime: str | None = None
    source_url: str | None = None


class GraphEdge(BaseModel):
    source: str
    target: str
    relation: str | None = None


class GraphExport(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]


class RelatedNode(GraphNode):
    relation: str | None = None
    hops: int = 0


class RelatedNodes(BaseModel):
    node_id: str
    related: list[RelatedNode]
