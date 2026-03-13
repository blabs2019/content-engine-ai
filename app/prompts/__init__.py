from pathlib import Path
from functools import lru_cache

PROMPTS_DIR = Path(__file__).parent


@lru_cache(maxsize=16)
def load_prompt(filename: str) -> str:
    """Load a prompt template from the prompts directory.

    Returns the raw template string with {placeholders} for .format().
    Cached after first load.
    """
    return (PROMPTS_DIR / filename).read_text(encoding="utf-8")
