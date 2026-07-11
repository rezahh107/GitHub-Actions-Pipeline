"""GitHub Actions Pipeline deterministic tooling package."""

# Install the fail-closed nested workflow gate before repository-model modules
# bind ``parse_workflow`` from ``tools.ci_workflow_structure``.
from tools.ci_workflow_nested_patch import install_workflow_nested_validation as _install_nested_workflow_validation

_install_nested_workflow_validation()
del _install_nested_workflow_validation

# Refine trigger validation after the nested gate is installed so event-specific
# rejection happens before the existing root/job/step and command-evidence path.
from tools.ci_workflow_trigger_patch import install_workflow_trigger_validation as _install_workflow_trigger_validation

_install_workflow_trigger_validation()
del _install_workflow_trigger_validation

# Validate represented schedule semantics after the event/property registry is
# installed and before repository-model modules bind ``parse_workflow``.
from tools.ci_workflow_schedule_patch import install_workflow_schedule_validation as _install_workflow_schedule_validation

_install_workflow_schedule_validation()
del _install_workflow_schedule_validation

# Pin timezone identity and enforce cumulative schedule work budgets last so the
# resource gate wraps all earlier structural and semantic boundaries.
from tools.ci_schedule_resource_patch import install_schedule_resource_hardening as _install_schedule_resource_hardening

_install_schedule_resource_hardening()
del _install_schedule_resource_hardening
