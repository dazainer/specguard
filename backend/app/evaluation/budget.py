"""Conservative persistent spend reservations for the controlled text-only trial.

Reserve the entire model context plus capped output before each HTTP attempt.
Reservations are never refunded, even on transport failure; SDK retries are off.
Prices are standard USD/token rates verified 2026-09-22 from OpenAI's model page.
This bounds this client's requests at those rates, not other account usage/taxes.
"""
from decimal import Decimal, InvalidOperation
import fcntl
import json
import os
from pathlib import Path

MODEL = 'gpt-4o-mini-2024-07-18'
INPUT_RATE = Decimal('0.15') / 1_000_000
OUTPUT_RATE = Decimal('0.60') / 1_000_000
MAX_OUTPUT = 4096
RESERVATION = Decimal(128_000) * INPUT_RATE + Decimal(MAX_OUTPUT) * OUTPUT_RATE


class SpendBudget:
    def __init__(self, path: Path, limit):
        self.path = Path(path).resolve()
        try:
            self.limit = Decimal(str(limit))
        except InvalidOperation as error:
            raise ValueError('Invalid USD budget') from error
        if not self.limit.is_finite() or not 0 < self.limit <= 5:
            raise ValueError('Budget must be greater than zero and at most 5 USD')
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)

    def reserve(self, model):
        if model != MODEL:
            raise ValueError('Budget requires the priced pinned model')
        with self.path.with_suffix('.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            data = json.loads(self.path.read_text()) if self.path.exists() else {
                'model': MODEL, 'limit_usd': str(self.limit), 'reserved_usd': '0',
                'attempts': 0, 'pricing_checked': '2026-09-22',
                'pricing_source': 'https://developers.openai.com/api/docs/models/gpt-4o-mini',
            }
            if data['model'] != MODEL or Decimal(data['limit_usd']) != self.limit:
                raise ValueError('Budget ledger configuration mismatch')
            if (type(data['attempts']) is not int or data['attempts'] < 0
                    or Decimal(data['reserved_usd']) != data['attempts'] * RESERVATION):
                raise ValueError('Invalid budget ledger')
            total = Decimal(data['reserved_usd']) + RESERVATION
            if total > self.limit:
                from app.evaluation.providers import ProviderFailure
                raise ProviderFailure('budget_exhausted', False)
            data.update(reserved_usd=str(total), attempts=data['attempts'] + 1)
            temporary = self.path.with_suffix('.tmp')
            with temporary.open('w') as file:
                json.dump(data, file, indent=2)
                file.flush()
                os.fsync(file.fileno())
            temporary.replace(self.path)
            directory = os.open(self.path.parent, os.O_RDONLY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
