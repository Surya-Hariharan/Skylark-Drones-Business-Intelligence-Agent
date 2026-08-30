"""Single Vercel serverless entrypoint. All routes are rewritten here
(see vercel.json) so the whole app runs as one function and can share
the FastAPI instance, rather than being split across api/*.py files into
separate isolated functions that can't share state."""
from app.main import app

__all__ = ["app"]
