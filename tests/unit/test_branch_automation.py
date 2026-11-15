from unittest.mock import patch

import pytest

from scripts.auto_promote import candidate, promote, require_protection
from scripts.branch_policy import target_branch, validate_pull_request

REPO = 'example/backend'
SHA = 'a' * 40


def event(branch='feature/fix-login', **changes):
    return {'repository': {'full_name': REPO}, 'workflow_run': {
        'conclusion': 'success', 'event': 'push', 'head_repository': {'full_name': REPO},
        'head_branch': branch, 'head_sha': SHA, **changes,
    }}


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


@pytest.mark.parametrize('changes', [
    {'conclusion': 'failure'}, {'event': 'pull_request_target'},
    {'head_repository': {'full_name': 'fork/backend'}}, {'head_sha': 'invalid'},
])
def test_failed_forked_or_invalid_ci_cannot_promote(changes):
    with patch('scripts.auto_promote.api') as api, pytest.raises(ValueError):
        promote(event(**changes), REPO)
    api.assert_not_called()


def test_missing_server_side_protection_blocks_automation():
    with patch('scripts.auto_promote.api', return_value=[]), pytest.raises(RuntimeError):
        require_protection(REPO, 'develop')


@pytest.mark.parametrize('approvals,contexts', [(0, ['Backend CI', 'Branch policy']),
                                             (1, ['Backend CI'])])
def test_incomplete_reviews_or_checks_block_promotion(approvals, contexts):
    rules = [
        {'type': 'deletion'}, {'type': 'non_fast_forward'},
        {'type': 'pull_request', 'parameters': {'required_approving_review_count': approvals,
            'dismiss_stale_reviews_on_push': True, 'require_last_push_approval': True}},
        {'type': 'required_status_checks', 'parameters': {
            'required_status_checks': [{'context': context} for context in contexts],
            'strict_required_status_checks_policy': True}},
    ]
    with patch('scripts.auto_promote.api', return_value=rules), pytest.raises(RuntimeError):
        require_protection(REPO, 'develop')


def test_stale_ci_does_not_create_or_merge_pr():
    with (
        patch('scripts.auto_promote.require_protection'),
        patch('scripts.auto_promote.api', side_effect=[
            {'allow_auto_merge': True, 'allow_merge_commit': True}, {'object': {'sha': 'b' * 40}},
        ]) as api,
    ):
        promote(event(), REPO)
    assert all(call.kwargs.get('method', 'GET') == 'GET' for call in api.call_args_list)
    assert len(api.call_args_list) == 2


def test_success_requests_auto_merge_without_bypassing_approvals():
    pr = {'number': 7, 'node_id': 'synthetic-pr-node', 'draft': False, 'auto_merge': None,
          'head': {'ref': 'develop', 'sha': SHA, 'repo': {'full_name': REPO}},
          'base': {'ref': 'prod', 'repo': {'full_name': REPO}}}
    with (
        patch('scripts.auto_promote.require_protection'),
        patch('scripts.auto_promote.api', side_effect=[
            {'allow_auto_merge': True, 'allow_merge_commit': True}, {'object': {'sha': SHA}},
            {'ahead_by': 1}, [pr], {},
        ]) as api,
    ):
        promote(event('develop'), REPO)
    path, method, mutation = api.call_args.args
    assert path == '/graphql' and method == 'POST'
    assert 'enablePullRequestAutoMerge' in mutation['query']
    assert 'mergePullRequest(' not in mutation['query']
    assert mutation['variables']['id'] == pr['node_id']


def test_already_promoted_branch_is_idempotent():
    with (
        patch('scripts.auto_promote.require_protection'),
        patch('scripts.auto_promote.api', side_effect=[
            {'allow_auto_merge': True, 'allow_merge_commit': True}, {'object': {'sha': SHA}},
            {'ahead_by': 0},
        ]) as api,
    ):
        promote(event(), REPO)
    assert len(api.call_args_list) == 3


def test_candidate_returns_only_same_repository_success():
    assert candidate(event(), REPO) == ('feature/fix-login', 'develop', SHA)
