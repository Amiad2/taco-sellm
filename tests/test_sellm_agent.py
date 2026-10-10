"""`--agent sellm` is registered and plays every arena-sim case to the end."""

import secrets
from pathlib import Path

import pytest

from arena_kit import ArenaClient, RemoteTable, play
from arena_kit.cli import AGENTS, agent_factory, main

DATA = Path(__file__).resolve().parents[1] / "data" / "package"
RESULT = {"ended", "deal", "supplier_id", "offer_id", "terms", "c_open", "c_deal", "c_best", "score"}


def team(url):
    key = ArenaClient(url).register(f"test-{secrets.token_hex(3)}", "sim")["api_key"]
    return ArenaClient(url, key, rate=1000)


def test_the_cli_offers_our_agent():
    assert "sellm" in AGENTS
    with pytest.raises(SystemExit):
        main(["play", "case:S01", "--agent", "nope"])


@pytest.mark.parametrize("data", [None, DATA], ids=["no-data", "data"])
def test_sellm_plays_every_sim_case(sim, data):
    if data and not data.is_dir():
        pytest.skip("data package not downloaded (uv run arena data)")
    client = team(sim[0])
    new_agent = agent_factory("sellm", data and str(data))
    for case in client.cases("practice"):
        result = play(RemoteTable(client), case["case_id"], new_agent())
        assert RESULT <= set(result) and result["ended"]
        assert result["score"] is None or 0 <= result["score"] <= 1
