"""DeepSeek client with persisted call evidence and a conservative CNY budget."""
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import time
import requests
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / 'results/raw/completed'
RAW.mkdir(parents=True, exist_ok=True)


def stamp():
    return datetime.now(timezone(timedelta(hours=8))).isoformat()


def save(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    temporary.replace(path)


class ModelFailure(RuntimeError):
    pass


class DeepSeekModel:
    def __init__(self, config):
        self.config = config
        # Deliberately do not copy the credential into process-wide os.environ.
        self._key = os.environ.get('DEEPSEEK_APIkey') or dotenv_values(ROOT / '.env').get('DEEPSEEK_APIkey')
        if not self._key:
            raise ModelFailure('DEEPSEEK_APIkey is not configured locally')
        self.ledger_path = RAW / 'budget_ledger.json'
        self.ledger = json.loads(self.ledger_path.read_text(encoding='utf-8')) if self.ledger_path.exists() else {'budget_cny': config['budget_cny'], 'cost_upper_bound_cny': 0.0, 'calls': []}
        self.sample_id = 'service_check'
        self.sample_calls = 0

    def redact(self, text):
        return str(text).replace(self._key, '[REDACTED]')

    def verify_service(self):
        response = requests.get(self.config['base_url'].rstrip('/') + '/models', headers={'Authorization': 'Bearer ' + self._key}, timeout=(10, 30))
        result = {'timestamp': stamp(), 'http_status': response.status_code, 'requested_model': self.config['model']}
        if response.status_code == 200:
            result['requested_model_listed'] = self.config['model'] in [r.get('id') for r in response.json().get('data', [])]
        save(RAW / 'service_check.json', result)
        if response.status_code != 200 or not result.get('requested_model_listed'):
            raise ModelFailure('Model service check failed: HTTP ' + str(response.status_code))
        return result

    def begin_sample(self, sample_id):
        self.sample_id, self.sample_calls = sample_id, 0

    def get_response_with_messages(self, model_name, messages):
        if self.sample_calls >= self.config['max_calls_per_sample']:
            raise ModelFailure('Per-sample model call limit reached')
        output_limit = self.config['max_output_tokens']
        # UTF-8 bytes plus message overhead is a deliberately loose input bound.
        input_bound = len(json.dumps(messages, ensure_ascii=False).encode('utf-8')) + 256 * len(messages) + 512
        reserve = (input_bound * self.config['input_cny_per_million_upper'] + output_limit * self.config['output_cny_per_million_upper']) / 1_000_000
        if self.ledger['cost_upper_bound_cny'] + reserve > self.config['budget_cny']:
            raise ModelFailure('10 CNY cumulative budget guard reached')
        call_id = len(self.ledger['calls']) + 1
        entry = {'call_id': call_id, 'sample_id': self.sample_id, 'timestamp': stamp(), 'status': 'reserved', 'cost_upper_bound_cny': reserve}
        self.ledger['calls'].append(entry)
        self.ledger['cost_upper_bound_cny'] += reserve
        save(self.ledger_path, self.ledger)
        self.sample_calls += 1
        start = time.perf_counter()
        record = {'call_id': call_id, 'sample_id': self.sample_id, 'timestamp': entry['timestamp'], 'model_requested': self.config['model'], 'messages': messages, 'parameters': {'temperature': 0.0000001, 'max_tokens': output_limit, 'thinking': {'type': 'disabled'}}}
        try:
            response = requests.post(self.config['base_url'].rstrip('/') + '/chat/completions', headers={'Authorization': 'Bearer ' + self._key, 'Content-Type': 'application/json'}, json={'model': self.config['model'], 'messages': messages, 'temperature': 0.0000001, 'max_tokens': output_limit, 'stream': False, 'thinking': {'type': 'disabled'}}, timeout=(10, 60))
            record['http_status'] = response.status_code
            if response.status_code != 200:
                raise ModelFailure('Chat request returned HTTP ' + str(response.status_code))
            payload = response.json()
            record.update({'model_returned': payload.get('model'), 'response_id': payload.get('id'), 'usage': payload.get('usage'), 'choices': payload.get('choices')})
            choice = payload['choices'][0]
            usage = payload.get('usage') or {}
            if 'prompt_tokens' in usage and 'completion_tokens' in usage:
                measured = (usage['prompt_tokens'] * self.config['input_cny_per_million_upper'] + usage['completion_tokens'] * self.config['output_cny_per_million_upper']) / 1_000_000
                self.ledger['cost_upper_bound_cny'] += measured - reserve
                entry.update({'cost_upper_bound_cny': measured, 'usage': usage})
            if choice.get('finish_reason') != 'stop' or not choice.get('message', {}).get('content'):
                raise ModelFailure('Response incomplete: finish_reason=' + str(choice.get('finish_reason')))
            content = choice['message']['content']
            entry['status'] = 'success'
            return content
        except Exception as exc:
            entry['status'] = 'failed_or_uncertain'
            record['error'] = self.redact(f'{type(exc).__name__}: {exc}')
            raise ModelFailure(record['error']) from None
        finally:
            record['duration_seconds'] = time.perf_counter() - start
            record['cost_upper_bound_cny'] = entry['cost_upper_bound_cny']
            # Sanitize all text, including server responses, before persistence.
            safe = json.loads(self.redact(json.dumps(record, ensure_ascii=False)))
            save(RAW / 'calls' / f'{call_id:04d}.json', safe)
            save(self.ledger_path, self.ledger)
