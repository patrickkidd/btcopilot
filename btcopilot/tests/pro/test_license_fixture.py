"""The licence a test's user holds is chosen, not assumed.

Exempt from the citation rule: this asserts the test harness's own machinery.
"""

import pytest

import btcopilot


@pytest.mark.parametrize(
    "licenseProduct",
    [btcopilot.LICENSE_PROFESSIONAL, btcopilot.LICENSE_BETA],
    indirect=True,
)
def test_the_licence_can_be_parametrized(licenseProduct, test_policy):
    assert test_policy.product == licenseProduct


def test_the_default_licence_is_professional(test_policy):
    assert test_policy.product == btcopilot.LICENSE_PROFESSIONAL

    assert test_policy.code == btcopilot.LICENSE_PROFESSIONAL_MONTHLY


@pytest.mark.beta
def test_a_beta_test_holds_a_beta_licence(test_policy):
    """The marker sets the build and the licence together; a beta build that
    honours only beta licences would otherwise launch with none."""
    assert test_policy.product == btcopilot.LICENSE_BETA
