"""CrewAI multi-agent travel planning.

CrewAI telemetry and tracing are disabled before the library is imported:
the app should never phone home, and it keeps offline tests fast.
"""

import os

os.environ.setdefault("CREWAI_DISABLE_TELEMETRY", "true")
os.environ.setdefault("CREWAI_TRACING_ENABLED", "false")
os.environ.setdefault("OTEL_SDK_DISABLED", "true")
