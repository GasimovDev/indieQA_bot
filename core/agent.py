"""IndieQA autonomous QA agent (Module 1, Person 1).

A seeded, deterministic state machine that replaces the human player:

* Boundary_Seeker -- probes the level geometry with horizontal raycasts
  (walls) and downward ground probes (ledges / gaps), walks to the nearest
  boundary in its heading, hugs ledges for a moment and then either drops
  off, jumps across or turns back. Touching a wall in its heading hands
  control to the spammer.
* Input_Spammer   -- activated on wall/corner collision frames. Fires rapid,
  non-linear combos biased toward the wall (diagonal + jump, direction
  toggles) to force clipping state transitions, then returns control.

The agent only uses what a black-box tester could know: the player's
kinematic state and the static collider list. It never reads `zone` or
`glitch_event` (those exist for the runner and the self-tests).
Same seed + same engine => identical input sequence (reproducible bugs).
"""

from __future__ import annotations

import random
from enum import Enum
from typing import Final, Sequence

import pygame

from core.engine import PLAYER_HEIGHT, PLAYER_WIDTH, FrameState, InputState, Level

# Behaviour tuning (agent policy, not physics)
RAY_MAX: Final[float] = 800.0          # px, horizontal raycast range
WALL_CONTACT: Final[float] = 1.5       # px, distance that counts as "pressed into a wall"
LEDGE_PROBE_MAX: Final[int] = 120      # px, how far ahead to probe for missing ground
LEDGE_PROBE_STEP: Final[int] = 4       # px
GROUND_TOLERANCE: Final[float] = 4.0   # px below the feet still counted as ground
EDGE_HUG_FRAMES: Final[tuple[int, int]] = (6, 20)
SPAM_FRAMES: Final[tuple[int, int]] = (45, 120)
SPAM_HOLD_FRAMES: Final[tuple[int, int]] = (2, 6)   # frames each combo is held
EXPLORE_JUMP_CHANCE: Final[float] = 0.02            # random hop while walking (finds the platform)
EDGE_CHOICES: Final[tuple[tuple[str, float], ...]] = (("drop", 0.5), ("jump", 0.3), ("reverse", 0.2))


class AgentMode(str, Enum):
    BOUNDARY_SEEKER = "Boundary_Seeker"
    INPUT_SPAMMER = "Input_Spammer"


def _combo(heading: int, toward: bool, jump: bool) -> InputState:
    """Direction relative to `heading` (+1 right / -1 left)."""
    go_right: bool = (heading > 0) == toward
    return InputState(left=not go_right, right=go_right, jump=jump)


class QAAgent:
    """Boundary_Seeker / Input_Spammer state machine. Call `decide()` once per frame."""

    def __init__(self, level: Level, seed: int = 0) -> None:
        self.level: Level = level
        self.seed: int = seed
        self.rng: random.Random = random.Random(seed)
        self.mode: AgentMode = AgentMode.BOUNDARY_SEEKER
        self.heading: int = 1
        self.mode_switches: int = 0

        self._episode: int = -1
        self._edge_hug_left: int = 0
        self._edge_action: str = ""
        self._edge_jump_committed: bool = False
        self._spam_left: int = 0
        self._spam_hold_left: int = 0
        self._spam_current: InputState = InputState()
        self._solids: tuple[pygame.Rect, ...] = tuple(c.rect for c in level.colliders)

    # ------------------------------------------------------------- interface
    def decide(self, state: FrameState) -> InputState:
        """Choose the buttons for the next frame from the latest observed state."""
        if state.episode != self._episode:
            self._on_new_episode(state.episode)

        wall_dist: float = self.wall_distance(state, self.heading)
        pressing_wall: bool = state.collision_state and wall_dist <= WALL_CONTACT

        if self.mode is AgentMode.BOUNDARY_SEEKER and pressing_wall:
            self._enter_spammer()

        if self.mode is AgentMode.INPUT_SPAMMER:
            return self._spam(state, pressing_wall)
        return self._seek(state, wall_dist)

    # --------------------------------------------------------------- probing
    def wall_distance(self, state: FrameState, heading: int) -> float:
        """Raycast from the player's leading face at head, mid and feet height; nearest solid face."""
        front_x: float = state.pos_x + PLAYER_WIDTH if heading > 0 else state.pos_x
        sample_ys: Sequence[float] = (state.pos_y + 1.0, state.pos_y + PLAYER_HEIGHT / 2.0, state.pos_y + PLAYER_HEIGHT - 1.0)
        best: float = RAY_MAX
        for rect in self._solids:
            if not any(rect.top <= y < rect.bottom for y in sample_ys):
                continue
            if heading > 0 and rect.left >= front_x - 0.5:
                best = min(best, rect.left - front_x)
            elif heading < 0 and rect.right <= front_x + 0.5:
                best = min(best, front_x - rect.right)
        return max(best, 0.0)

    def ledge_distance(self, state: FrameState, heading: int) -> float | None:
        """Distance ahead (along `heading`) to the first point with no ground under the feet, if any."""
        feet_y: float = state.pos_y + PLAYER_HEIGHT
        front_x: float = state.pos_x + PLAYER_WIDTH if heading > 0 else state.pos_x
        for d in range(0, LEDGE_PROBE_MAX + 1, LEDGE_PROBE_STEP):
            px: float = front_x + heading * d
            if not self._ground_at(px, feet_y):
                return float(d)
        return None

    def _ground_at(self, x: float, feet_y: float) -> bool:
        return any(
            r.left <= x < r.right and feet_y - 0.5 <= r.top <= feet_y + GROUND_TOLERANCE for r in self._solids
        )

    # ------------------------------------------------------- Boundary_Seeker
    def _seek(self, state: FrameState, wall_dist: float) -> InputState:
        if not state.is_grounded:
            # Airborne: keep drifting toward the boundary (diagonal approach into walls/corners).
            self._edge_hug_left = 0
            return _combo(self.heading, toward=True, jump=False)

        if self._edge_hug_left > 0:
            return self._continue_edge_hug()

        ledge: float | None = self.ledge_distance(state, self.heading)
        if ledge is not None and ledge <= LEDGE_PROBE_STEP and ledge < wall_dist:
            # Arrived at a platform edge: stick to it, then commit to a choice.
            self._edge_hug_left = self.rng.randint(*EDGE_HUG_FRAMES)
            self._edge_action = self._weighted_choice(EDGE_CHOICES)
            self._edge_jump_committed = False
            return InputState()

        jump: bool = self.rng.random() < EXPLORE_JUMP_CHANCE
        return _combo(self.heading, toward=True, jump=jump)

    def _continue_edge_hug(self) -> InputState:
        self._edge_hug_left -= 1
        if self._edge_hug_left > 0:
            return InputState()  # hold position on the edge
        if self._edge_action == "reverse":
            self.heading = -self.heading
            return _combo(self.heading, toward=True, jump=False)
        if self._edge_action == "jump":
            return _combo(self.heading, toward=True, jump=True)
        return _combo(self.heading, toward=True, jump=False)  # "drop": walk off the edge

    # --------------------------------------------------------- Input_Spammer
    def _enter_spammer(self) -> None:
        self.mode = AgentMode.INPUT_SPAMMER
        self.mode_switches += 1
        self._spam_left = self.rng.randint(*SPAM_FRAMES)
        self._spam_hold_left = 0
        self._edge_hug_left = 0

    def _spam(self, state: FrameState, pressing_wall: bool) -> InputState:
        self._spam_left -= 1
        if self._spam_left <= 0:
            if pressing_wall:
                # Still pinned (e.g. trapped): keep stress-testing instead of idling.
                self._spam_left = self.rng.randint(*SPAM_FRAMES)
            else:
                self.mode = AgentMode.BOUNDARY_SEEKER
                self.mode_switches += 1
                if self.rng.random() < 0.5:
                    self.heading = -self.heading
                return _combo(self.heading, toward=True, jump=False)

        if self._spam_hold_left <= 0:
            self._spam_current = self._random_combo()
            self._spam_hold_left = self.rng.randint(*SPAM_HOLD_FRAMES)
        self._spam_hold_left -= 1
        return self._spam_current

    def _random_combo(self) -> InputState:
        """Non-linear combos biased toward the wall; never 'none' so pressure is continuous."""
        roll: float = self.rng.random()
        if roll < 0.45:
            return _combo(self.heading, toward=True, jump=True)    # diagonal into the wall
        if roll < 0.65:
            return _combo(self.heading, toward=True, jump=False)   # push
        if roll < 0.80:
            return InputState(jump=True)                            # vertical hop
        if roll < 0.92:
            return _combo(self.heading, toward=False, jump=False)  # back off (builds run-up)
        return _combo(self.heading, toward=False, jump=True)       # reverse diagonal

    # ----------------------------------------------------------------- utils
    def _on_new_episode(self, episode: int) -> None:
        self._episode = episode
        self.mode = AgentMode.BOUNDARY_SEEKER
        self.heading = 1 if self.rng.random() < 0.5 else -1
        self._edge_hug_left = 0
        self._spam_left = 0
        self._spam_hold_left = 0

    def _weighted_choice(self, choices: Sequence[tuple[str, float]]) -> str:
        roll: float = self.rng.random() * sum(w for _, w in choices)
        for name, weight in choices:
            roll -= weight
            if roll <= 0.0:
                return name
        return choices[-1][0]


# --------------------------------------------------------------------------
# Self-test:  python -m core.agent
# --------------------------------------------------------------------------
def _run(seed: int, frames: int) -> tuple[list[str], dict[str, int], dict[AgentMode, int], int]:
    """Agent-driven run with a minimal episode policy (the real one lives in main.py)."""
    from core.engine import GameEngine, Glitch, Zone

    engine = GameEngine(headless=True, spawn_index=0)
    agent = QAAgent(engine.level, seed=seed)
    spawn_rng = random.Random(seed)
    inputs: list[str] = []
    found: dict[str, int] = {g.value: 0 for g in Glitch}
    mode_frames: dict[AgentMode, int] = {m: 0 for m in AgentMode}
    state = engine.step(InputState())
    zone_frames: int = 0
    episode_frames: int = 0
    last_zone: Zone = state.zone
    for _ in range(frames):
        inp = agent.decide(state)
        mode_frames[agent.mode] += 1
        inputs.append(inp.label)
        state = engine.step(inp)
        episode_frames += 1
        if state.glitch_event is Glitch.WALL_CLIP:
            found[Glitch.WALL_CLIP.value] += 1
        zone_frames = zone_frames + 1 if state.zone is last_zone else 0
        last_zone = state.zone
        if state.zone is Zone.FALL_SHAFT and zone_frames == 0:
            found[Glitch.INFINITE_FALL.value] += 1
        if state.zone is Zone.SOFTLOCK_PIT and zone_frames == 0:
            found[Glitch.SOFTLOCK_PIT.value] += 1
        stuck_pit: bool = state.zone is Zone.SOFTLOCK_PIT and zone_frames > 600
        lost: bool = state.zone is Zone.OUT_OF_WORLD and zone_frames > 300
        if stuck_pit or lost or episode_frames > 3000:
            engine.reset(spawn_rng.randrange(len(engine.level.spawn_points)))
            episode_frames = 0
            state = engine.step(InputState())
    return inputs, found, mode_frames, agent.mode_switches


def _self_test() -> None:
    frames: int = 30_000
    inputs_a, found, mode_frames, switches = _run(seed=42, frames=frames)
    inputs_b, _, _, _ = _run(seed=42, frames=frames)
    inputs_c, _, _, _ = _run(seed=7, frames=frames)

    assert inputs_a == inputs_b, "same seed produced different input sequences"
    print(f"[PASS] deterministic             : seed 42 twice -> identical {frames} inputs")
    assert inputs_a != inputs_c
    print("[PASS] seed-sensitive            : seed 7 -> different run")
    assert all(n > 0 for n in mode_frames.values()) and switches > 0
    share = {m.value: f"{n / frames:.0%}" for m, n in mode_frames.items()}
    print(f"[PASS] both modes active         : {share}, {switches} mode switches")
    combos = {lbl for lbl in inputs_a if "+" in lbl}
    assert combos
    print(f"[PASS] combo inputs              : {sorted(combos)}")
    for name, count in found.items():
        assert count > 0, f"agent never reached {name}"
    print(f"[PASS] glitches reached          : {found}")


if __name__ == "__main__":
    import os

    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    _self_test()
