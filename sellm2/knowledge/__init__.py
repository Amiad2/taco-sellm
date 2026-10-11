# ruff: noqa: E501  (long sentences and messages)
"""sellm2's knowledge of the world: the data package read once, per supplier a brief, per case the
facts we may cite. Rewritten for sellm2; it imports nothing from `sellm`."""

from .brief import Brief, PartBrief, build, case_facts, contact_name
from .source import LOCK, Source, source

__all__ = ["Brief", "PartBrief", "build", "case_facts", "contact_name", "LOCK", "Source", "source"]
