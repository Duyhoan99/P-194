"""Domain errors for clinical retrieval."""


class ClinicalAuthNotConfigured(Exception):  # noqa: N818
    """Raised when clinical authentication has not been configured."""


class ClinicalAccessDenied(Exception):  # noqa: N818
    """Raised when a user is not authorized for a clinical subject."""


class ClinicalScopeInvalid(Exception):  # noqa: N818
    """Raised when an encounter or stay is outside the requested subject."""


class ClinicalDatabaseUnavailable(Exception):  # noqa: N818
    """Raised when the clinical database cannot be queried."""


class ClinicalAuditUnavailable(Exception):  # noqa: N818
    """Raised when a required scope-only audit event cannot be recorded."""


class ClinicalQueryTimeout(Exception):  # noqa: N818
    """Raised when a clinical query exceeds its timeout."""


class ClinicalAgentUnavailable(Exception):  # noqa: N818
    """Raised when structured clinical summary generation cannot complete safely."""


class ReviewPolicyError(Exception):  # noqa: N818
    """Raised when a clinical summary review policy cannot be satisfied."""


class ClinicalSummaryNotFound(Exception):  # noqa: N818
    """Raised when a requested clinical summary does not exist."""
