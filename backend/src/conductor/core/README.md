# Core

Owns process bootstrap and genuinely application-wide infrastructure. M1 uses it for request context and structured logging; feature-specific policy must remain in its owning module.
