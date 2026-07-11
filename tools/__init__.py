"""GitHub Actions Pipeline deterministic tooling package."""

# Install the fail-closed nested workflow gate before repository-model modules
# bind ``parse_workflow`` from ``tools.ci_workflow_structure``.
from tools.ci_workflow_nested_patch import install_workflow_nested_validation as _install_nested_workflow_validation

_install_nested_workflow_validation()
del _install_nested_workflow_validation
