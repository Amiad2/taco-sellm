"""`python -m sellm.evalrun --set practice --agent sellm.variants:bank --cases P01 ...`: the runner, but
a session that cannot open because other runs of the team hold the key's 10 open sessions waits
for a free slot instead of failing."""

import sys
import time

from arena_kit.client import ArenaClient, ArenaError

_open = ArenaClient.open_session


def open_session(self, case_id):
    for _ in range(90):  # up to 7 minutes
        try:
            return _open(self, case_id)
        except ArenaError as e:
            text = str(getattr(e, "detail", e)).lower()
            if e.status == 429 and "practice" not in text and "limit:" not in text:
                time.sleep(5)
                continue
            raise
    return _open(self, case_id)


ArenaClient.open_session = open_session

if __name__ == "__main__":
    from sellm.runner import main

    sys.exit(main(sys.argv[1:]))
