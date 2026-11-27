"""Invented metadata, IDs and links; no captured provider/user data."""

from copy import deepcopy

ITEMS = [
    {
        "kinopoiskId": 9000001,
        "nameRu": "Синтетический горизонт",
        "nameOriginal": "Synthetic Horizon",
        "year": 2024,
        "ratingKinopoisk": 7.8,
        "ratingImdb": 8.1,
        "type": "FILM",
        "posterUrlPreview": "https://st.kp.yandex.net/images/fixture-unavailable.jpg",
    },
    {
        "kinopoiskId": 9000002,
        "nameRu": "Синтетический горизонт",
        "year": 1998,
        "ratingKinopoisk": None,
        "ratingImdb": 0,
        "type": "TV_SERIES",
    },
    {
        "kinopoiskId": 9000003,
        "nameRu": None,
        "nameOriginal": "Synthetic Original",
        "year": None,
        "ratingKinopoisk": None,
        "ratingImdb": None,
        "type": "UNRECOGNIZED",
    },
]


def response(query, page, ident):
    if ident:
        return deepcopy(
            next((row for row in ITEMS if str(row["kinopoiskId"]) == str(ident)), {})
        )
    return {
        "items": deepcopy(ITEMS if query and "горизонт" in query else []),
        "totalPages": 2 if query and "горизонт" in query else 0,
    }
