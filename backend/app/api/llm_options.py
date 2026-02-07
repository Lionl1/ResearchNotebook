from typing import Optional, Tuple


def resolve_llm_options(
    temperature: Optional[float],
    max_tokens: Optional[int],
    default_temperature: float,
) -> Tuple[float, Optional[int]]:
    resolved_temperature = temperature if temperature is not None else default_temperature
    resolved_max_tokens = max_tokens if max_tokens and max_tokens > 0 else None
    return resolved_temperature, resolved_max_tokens
