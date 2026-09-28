"""Bounded public Bybit DNS, TLS, and API diagnostics. Never changes system settings."""
import argparse
import json
import os
import socket
import ssl
import subprocess
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from tools.market import request, failure_detail


def probe(stage):
    if stage == 'dns':
        answers = socket.getaddrinfo('api.bybit.com', 443, type=socket.SOCK_STREAM)
        return {'addresses_resolved': len(answers)}
    if stage == 'tls':
        with socket.create_connection(('api.bybit.com', 443), timeout=5) as raw:
            with ssl.create_default_context().wrap_socket(raw, server_hostname='api.bybit.com') as conn:
                return {'tls_version': conn.version(), 'certificate_verified': True}
    obj = request('/v5/market/kline', {'category':'spot', 'symbol':'BTCUSDT', 'interval':'60', 'limit':1})
    if obj['response']['result'].get('symbol') != 'BTCUSDT':
        raise ValueError('Wrong symbol in response')
    return {'valid_spot_json': True, 'exchange_time_ms': obj['response']['time']}


def diagnose():
    output = {'checked_at': datetime.now(timezone.utc).isoformat(), 'host':'api.bybit.com',
              'proxy_types_present': sorted(urllib.request.getproxies()),
              'custom_ca_config_present': any(os.environ.get(k) for k in ('SSL_CERT_FILE','SSL_CERT_DIR')),
              'route':'direct HTTPS; no automatic proxy/fallback', 'checks':[]}
    for stage in ('dns','tls','api'):
        try:
            run = subprocess.run([sys.executable, '-m', 'tools.diagnose', '--probe', stage],
                                 capture_output=True, text=True, timeout=12)
            check = json.loads(run.stdout)
        except subprocess.TimeoutExpired:
            check = {'stage':stage, 'ok':False, 'failure':stage+'_timeout', 'message':f'{stage} did not finish within 12 seconds.'}
        output['checks'].append(check)
        if not check['ok']:
            break
    output['ok'] = len(output['checks']) == 3 and all(c['ok'] for c in output['checks'])
    return output


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path)
    parser.add_argument('--probe', choices=['dns','tls','api'], help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.probe:
        try:
            result = {'stage':args.probe, 'ok':True, **probe(args.probe)}
        except Exception as exc:
            kind, message = failure_detail(exc)
            result = {'stage':args.probe, 'ok':False, 'failure':kind, 'message':message}
        print(json.dumps(result))
    else:
        if args.out and args.out.exists():
            parser.exit(2, 'Output exists; choose a new filename.\n')
        result = diagnose()
        if args.out:
            with args.out.open('x') as f:
                json.dump(result, f, indent=2)
        print(json.dumps(result, indent=2))
        sys.exit(0 if result['ok'] else 2)
