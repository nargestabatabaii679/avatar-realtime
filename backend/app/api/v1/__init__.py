"""
app/api/v1/__init__.py
-----------------------
Exports the v1 API router so that ``app.main`` can import it as::

    from app.api.v1 import router
"""

from app.api.v1.router import router  # noqa: F401
