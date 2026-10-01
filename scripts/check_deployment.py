"""Read-only deployment smoke check: python scripts/check_deployment.py BASE_URL."""
import argparse
import json
from urllib.error import HTTPError
from urllib.parse import quote, urlparse
from urllib.request import urlopen


def check(base_url):
    def get(path, expected=200, as_json=True):
        try:
            with urlopen(base_url.rstrip('/') + path, timeout=90) as response:
                status, body = response.status, response.read().decode('utf-8')
        except HTTPError as error:
            status, body = error.code, error.read().decode('utf-8')
        if status != expected:
            raise RuntimeError(f'{path}: expected {expected}, got {status}')
        print(f'PASS {path} ({status})')
        return json.loads(body) if as_json else body

    assert get('/health')['status'] == 'ok'
    assert 'subscriber-body' in get('/', as_json=False)
    for asset in ('app.js', 'style.css'):
        assert get('/static/' + asset, as_json=False).strip()
    subscribers = get('/api/subscribers')
    assert isinstance(subscribers, list) and subscribers, 'No subscribers'
    devices_checked = 0
    for subscriber in subscribers:
        user_id = quote(subscriber['userId'], safe='')
        devices = get(f'/api/subscribers/{user_id}/devices')
        assert isinstance(devices, list)
        assert len(devices) == subscriber['deviceCount']
        for device in devices:
            device_id = quote(device['deviceId'], safe='')
            usage = get(f'/api/devices/{device_id}/usage')
            assert usage['deviceId'] == device['deviceId']
            assert len(usage['weeklyUsageTrend']) == 7
            devices_checked += 1
    assert devices_checked > 0, 'No device usage checked'
    get('/api/subscribers/__missing__/devices', expected=404)
    get('/api/devices/__missing__/usage', expected=404)
    print(f'PASS: {len(subscribers)} subscribers, {devices_checked} devices. Browser UI checks remain required.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('base_url')
    args = parser.parse_args()
    if urlparse(args.base_url).scheme not in ('http', 'https'):
        parser.error('base_url must start with http:// or https://')
    check(args.base_url)
