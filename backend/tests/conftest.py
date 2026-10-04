"""Shared pytest fixtures and helpers for the backend test suite.

These tests are deliberately dependency-light: they exercise pure logic
(JSON parsing, diffing, sampling) and agent orchestration with a fake LLM,
so they run without a database, network, or real model access.
"""

from typing import Union

import pytest


class FakeLLM:
    """Drop-in replacement for LLMService in tests.

    Records the calls it receives and returns preset responses. A single
    string is returned for every call; a list is consumed one item per call
    (raising if exhausted).
    """

    def __init__(self, responses: Union[str, list]):
        self._responses = responses
        self._index = 0
        self.calls = []

    async def chat(self, messages, temperature: float = 0.7, max_tokens: int = 4000) -> str:
        self.calls.append(
            {"messages": messages, "temperature": temperature, "max_tokens": max_tokens}
        )
        if isinstance(self._responses, str):
            return self._responses
        if self._index >= len(self._responses):
            raise AssertionError("FakeLLM received more chat() calls than responses provided")
        resp = self._responses[self._index]
        self._index += 1
        return resp


def make_agent(agent_cls, responses: Union[str, list]):
    """Instantiate an agent and swap in a FakeLLM.

    BaseAgent.__init__ only stores connection strings (no network), so this is
    safe; we then replace the client with a fake to control responses.
    """
    agent = agent_cls(llm_settings=None)
    agent.llm = FakeLLM(responses)
    return agent


@pytest.fixture
def agent_factory():
    return make_agent
