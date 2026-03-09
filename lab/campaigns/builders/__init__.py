from .base_2k import collect_split_documents as collect_base_2k_documents
from .long_4k import collect_split_documents as collect_long_4k_documents
from .stories_2k import collect_split_documents as collect_stories_2k_documents

__all__ = [
    "collect_base_2k_documents",
    "collect_long_4k_documents",
    "collect_stories_2k_documents",
]
