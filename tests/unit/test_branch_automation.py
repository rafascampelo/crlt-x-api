import pytest

from scripts.branch_policy import target_branch, validate_pull_request

REPO = 'example/backend'


@pytest.mark.parametrize('branch,base', [('feature/fix-login', 'develop'), ('develop', 'prod')])
def test_only_allowed_promotion_directions(branch, base):
    assert target_branch(branch) == base
    validate_pull_request({'head': {'ref': branch, 'repo': {'full_name': REPO}},
                           'base': {'ref': base, 'repo': {'full_name': REPO}}}, REPO)


@pytest.mark.parametrize('branch', ['prod', 'main', 'feature/Bad_Name', 'feature/a/other'])
def test_disallowed_branches_cannot_promote(branch):
    with pytest.raises(ValueError):
        target_branch(branch)


def test_feature_cannot_target_prod():
    with pytest.raises(ValueError):
        validate_pull_request({'head': {'ref': 'feature/fix', 'repo': {'full_name': REPO}},
                               'base': {'ref': 'prod', 'repo': {'full_name': REPO}}}, REPO)
