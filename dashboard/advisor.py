"""Local and API-backed fix advisors for the failure-point chatbot."""
from __future__ import annotations

from dataclasses import dataclass
import json
import os
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class AdvisorBackend(Protocol):
    """Contract an HTTP or hosted model backend can implement later."""

    def answer(self, question: str, bug: dict[str, Any]) -> str:
        ...


FIXES = {
    'Wall Clip': (
        'Inspect the right-wall seam and the diagonal jump collision-resolution path. '
        'Keep the reproduction inputs, then assert that the player cannot cross x=784 '
        'while the seam is occupied. Add a regression test around the trigger frame.'
    ),
    'Infinite Fall': (
        'Inspect the floor gap and the missing recovery boundary. Add a kill plane or '
        'safe respawn below the world, then test that falling past y=600 produces a '
        'bounded recovery event instead of unbounded velocity.'
    ),
    'Softlock': (
        'Compare the pit depth with the player jump apex. Add an exit, raise the jump '
        'height, or provide a recovery action. Keep the input sequence as a regression '
        'case so continuous input cannot leave the player trapped.'
    ),
    'Out of Bounds': (
        'Trace the last in-arena position and the frame-to-frame velocity. Verify world '
        'bounds and recovery handling, then decide whether this event is a root bug or '
        'a consequence of another collision failure.'
    ),
}


@dataclass(frozen=True)
class LocalFixAdvisor:
    """Deterministic fallback advisor used until a remote API is connected."""

    name: str = 'Local rules advisor'

    def answer(self, question: str, bug: dict[str, Any]) -> str:
        bug_type = str(bug.get('type', 'Unknown'))
        priority = str(bug.get('priority', 'Review'))
        severity = str(bug.get('severity', 'UNKNOWN'))
        frame = bug.get('frame_id', '?')
        coords = bug.get('coordinates_xyz', [0, 0, 0])
        base = FIXES.get(bug_type, 'Inspect the trigger frame and add a focused regression test.')
        question_lower = question.lower().strip()
        if any(word in question_lower for word in ('reproduce', 'repro', 'input', 'button')):
            sequence = bug.get('reproduction_sequence', [])
            return (f"Reproduce {bug_type} at frame {frame} with the last {len(sequence)} "
                    f"recorded inputs: {', '.join(map(str, sequence[-10:])) or 'no inputs recorded'}. "
                    'Start from the same spawn and seed for a deterministic replay.')
        if any(word in question_lower for word in ('priority', 'urgent', 'severity')):
            return f"This is {priority} ({severity}) at ({coords[0]:.1f}, {coords[1]:.1f}). {base}"
        return f"{bug_type} is {priority} ({severity}) at frame {frame}. {base}"


class AdvisorAPIError(RuntimeError):
    """Raised when the configured remote advisor cannot answer."""


@dataclass(frozen=True)
class OpenAIResponsesAdvisor:
    """Small dependency-free client for an OpenAI-compatible Responses API."""

    api_key: str
    model: str = 'gpt-4.1-mini'
    endpoint: str = 'https://api.openai.com/v1/responses'
    timeout: float = 20.0
    name: str = 'OpenAI fix advisor'

    @classmethod
    def from_environment(cls) -> 'OpenAIResponsesAdvisor | None':
        """Build a client from environment variables, or return None offline."""
        groq_key = _setting('GROQ_API_KEY')
        if groq_key:
            return cls(
                api_key=groq_key.strip(),
                model=_setting('GROQ_MODEL', 'openai/gpt-oss-20b').strip(),
                endpoint=_setting(
                    'GROQ_RESPONSES_URL',
                    'https://api.groq.com/openai/v1/responses',
                ).strip(),
                name='Groq Fix Advisor',
            )
        api_key = _setting('OPENAI_API_KEY') or _setting('ADVISOR_API_KEY')
        if not api_key:
            return None
        endpoint = _setting('OPENAI_RESPONSES_URL') or _setting(
            'ADVISOR_API_URL', 'https://api.openai.com/v1/responses'
        )
        model = _setting('OPENAI_MODEL') or _setting('ADVISOR_MODEL', 'gpt-4.1-mini')
        try:
            timeout = float(_setting('ADVISOR_TIMEOUT_SECONDS', '20'))
        except ValueError:
            timeout = 20.0
        return cls(api_key=api_key.strip(), model=model.strip(), endpoint=endpoint.strip(), timeout=timeout)

    def answer(self, question: str, bug: dict[str, Any]) -> str:
        context = {
            'type': bug.get('type'),
            'priority': bug.get('priority'),
            'severity': bug.get('severity'),
            'frame_id': bug.get('frame_id'),
            'coordinates_xyz': bug.get('coordinates_xyz'),
            'reproduction_sequence': bug.get('reproduction_sequence', [])[-30:],
            'recommended_action': bug.get('recommended_action'),
        }
        prompt = (
            'Question from a game QA engineer:\n'
            f'{question.strip()}\n\n'
            'Failure-point telemetry (treat this as the source of truth):\n'
            f'{json.dumps(context, ensure_ascii=False)}'
        )
        payload = {
            'model': self.model,
            'instructions': (
                'You are IndieQA Fix Advisor. Give concise, practical debugging guidance '
                'for a small 2D game. Use only the supplied telemetry. Mention a concrete '
                'reproduction check and regression test when useful. Do not invent files, '
                'coordinates, or test results.'
            ),
            'input': [{'role': 'user', 'content': [{'type': 'input_text', 'text': prompt}]}],
            'max_output_tokens': 450,
        }
        request = Request(
            self.endpoint,
            data=json.dumps(payload).encode('utf-8'),
            headers={
                'Authorization': f'Bearer {self.api_key}',
                'Content-Type': 'application/json',
            },
            method='POST',
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:
                body = json.loads(response.read().decode('utf-8'))
        except HTTPError as exc:
            detail = exc.read().decode('utf-8', errors='replace')[:240]
            raise AdvisorAPIError(f'Advisor API returned HTTP {exc.code}: {detail}') from exc
        except (URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
            raise AdvisorAPIError(f'Advisor API request failed: {exc}') from exc
        text = _response_text(body)
        if not text:
            raise AdvisorAPIError('Advisor API returned no text output.')
        return text


def _response_text(body: dict[str, Any]) -> str:
    """Read text from Responses API JSON, with a compatible fallback shape."""
    output_text = body.get('output_text')
    if isinstance(output_text, str) and output_text.strip():
        return output_text.strip()
    chunks: list[str] = []
    for item in body.get('output', []):
        if not isinstance(item, dict):
            continue
        for content in item.get('content', []):
            if isinstance(content, dict) and isinstance(content.get('text'), str):
                chunks.append(content['text'])
    return '\n'.join(chunks).strip()


def _setting(name: str, default: str | None = None) -> str | None:
    """Read env configuration first, then optional Streamlit secrets."""
    value = os.getenv(name)
    if value:
        return value
    try:
        import streamlit as st
        value = st.secrets.get(name)
    except Exception:
        value = None
    return str(value) if value else default


def configured_advisor() -> AdvisorBackend:
    """Return the remote advisor when configured, otherwise the local fallback."""
    return OpenAIResponsesAdvisor.from_environment() or LocalFixAdvisor()

