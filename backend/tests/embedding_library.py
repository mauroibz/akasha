"""The small book library the embedding fixtures were written for (Sprint 136).

`scripts/record_embedding_fixtures.py` embeds exactly these texts, in this order, and
`test_embeddings.py` seeds exactly these items, so a recorded reply and the test
agree on what each vector is of. Rayuela is the seed (read, a 9); the rest wait.
"""

from __future__ import annotations

from typing import Any

LIBRARY: list[dict[str, Any]] = [
    {
        "title": "Rayuela",
        "year": 1963,
        "status": "read",
        "score": 9,
        "metadata": {
            "creators": ["Julio Cortázar"],
            "subjects": ["Argentine fiction", "Experimental fiction", "Paris"],
        },
    },
    {
        "title": "62: Modelo para armar",
        "year": 1968,
        "status": "to_read",
        "metadata": {
            "creators": ["Julio Cortázar"],
            "subjects": ["Argentine fiction", "Experimental fiction", "Paris"],
        },
    },
    {
        "title": "A Brief History of Time",
        "year": 1988,
        "status": "to_read",
        "metadata": {
            "creators": ["Stephen Hawking"],
            "subjects": ["Cosmology", "Popular science"],
        },
    },
    {
        "title": "Ficciones",
        "year": 1944,
        "status": "to_read",
        "metadata": {
            "creators": ["Jorge Luis Borges"],
            "subjects": ["Argentine fiction", "Short stories"],
        },
    },
    {
        "title": "The Hobbit",
        "year": 1937,
        "status": "to_read",
        "metadata": {
            "creators": ["J. R. R. Tolkien"],
            "subjects": ["Fantasy fiction", "Dragons"],
        },
    },
    {
        "title": "Pedro Páramo",
        "year": 1955,
        "status": "to_read",
        "metadata": {
            "creators": ["Juan Rulfo"],
            "subjects": ["Mexican fiction", "Experimental fiction"],
        },
    },
]

#: The order the nearest waiting books stand in, from the seed: what the fixtures say.
NEAREST_TO_RAYUELA = [
    "62: Modelo para armar",
    "Ficciones",
    "Pedro Páramo",
    "The Hobbit",
    "A Brief History of Time",
]
