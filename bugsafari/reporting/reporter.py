"""Human-readable report rendering helpers."""

from bugsafari.reporting.models import Finding


def reproduction_steps(finding: Finding) -> list[str]:
    """Format the recorded actions as concise reproduction instructions."""
    return [f"{index}. {action.action} {action.target}" +
            (f" = {action.value}" if action.value is not None else "")
            for index, action in enumerate(finding.reproduction_steps, start=1)]
