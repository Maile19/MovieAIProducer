from dataclasses import dataclass


@dataclass(frozen=True)
class ValueObject:
    """Base class for domain value objects.

    Value objects have no conceptual identity. They describe characteristics
    or things and are defined solely by their attribute values.
    Value objects are immutable; any mutation raises an error.
    Equality and hash are determined by the equality and hash of all attributes.
    """
    pass
