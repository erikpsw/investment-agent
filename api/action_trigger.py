"""Server-only dispatch of a fixed set of market workflows."""
import os
import requests
from fastapi import HTTPException

REPO = 'erikpsw/investment-agent'
WORKFLOWS = {'CN': 'cn-market-snapshot.yml', 'US': 'us-universe-snapshot.yml', 'HK': 'market-snapshot.yml'}


def trigger_updates(market, user):
    admins = {value.strip() for value in os.getenv('GITHUB_ACTIONS_ADMIN_SUBS', '').split(',') if value.strip()}
    if user.auth_type != 'auth0' or user.sub not in admins:
        raise HTTPException(403, '仅配置的管理员可触发行情更新')
    token = os.getenv('GITHUB_ACTIONS_TOKEN', '').strip()
    if not token:
        raise HTTPException(503, '服务端尚未配置 GitHub Actions 触发凭据')
    if market not in (*WORKFLOWS, 'all'):
        raise HTTPException(422, '不支持的市场')
    regions = list(WORKFLOWS) if market == 'all' else [market]
    headers = {'Authorization': f'Bearer {token}', 'Accept': 'application/vnd.github+json',
               'X-GitHub-Api-Version': '2022-11-28'}
    results = []
    try:
        for region in regions:
            workflow = WORKFLOWS[region]
            endpoint = f'https://api.github.com/repos/{REPO}/actions/workflows/{workflow}'
            response = requests.get(endpoint + '/runs', headers=headers,
                                    params={'per_page': 10, 'branch': 'main'}, timeout=10)
            response.raise_for_status()
            runs = response.json().get('workflow_runs', [])
            active = next((run for run in runs if run.get('status') != 'completed'), None)
            if active:
                results.append({'market': region, 'status': 'running', 'url': active['html_url']})
                continue
            response = requests.post(endpoint + '/dispatches', headers=headers, json={'ref': 'main'}, timeout=10)
            response.raise_for_status()
            results.append({'market': region, 'status': 'queued',
                            'url': f'https://github.com/{REPO}/actions/workflows/{workflow}'})
    except (requests.RequestException, ValueError, KeyError):
        raise HTTPException(502, 'GitHub 更新服务暂不可用，请稍后重试；已运行的任务可在 GitHub 查看') from None
    return {'status': 'ok', 'result': {'runs': results, 'message': '已提交或复用正在运行的任务，完成并部署后刷新页面即可读取新缓存'}}
