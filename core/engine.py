"""IndieQA core physics engine (Module 1, Person 1).

A deterministic, fixed-timestep 2D side-scroller simulation built on Pygame.
It runs either headless (no window, as fast as the CPU allows) or rendered
in a window throttled to 60 FPS.

Units are pixels and pixels/frame; dt = 1/60 s. Pygame coordinates are used:
origin top-left, +y points DOWN (so "falling forever" means pos_y -> +inf).

The level deliberately contains three hardcoded glitches for the QA agent
to discover:

1. Wall_Clip      -- The right boundary wall is built from two collider
                     segments separated by a 2px seam. The engine's
                     "unstuck" routine fires when the player's hitbox
                     overlaps BOTH segments at once (only possible while
                     airborne next to the seam, i.e. moving diagonally at
                     jump speed, |v| ~ 9-10 px/frame) and ejects the player
                     along its horizontal velocity to the first free space,
                     which lies OUTSIDE the arena. One-frame displacement is
                     ~48px (> the 25px/frame detector threshold), with
                     collision_state = True on that frame.
2. Infinite_Fall  -- A 60px gap in the floor has no collider and no
                     kill-plane. Terminal velocity is only enforced inside
                     the world rectangle, so below the world the player
                     accelerates without bound.
3. Softlock_Pit   -- A 40px-wide pit sunk 150px into the floor. The
                     discrete jump apex is exactly 100px, so the player
                     can never climb out, but keeps receiving inputs.

The engine never resets or teleports the player by itself; episode resets
are the runner's responsibility (main.py) via GameEngine.reset().
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import Enum
from typing import Final, Sequence

import pygame

# --------------------------------------------------------------------------
# Approved constants (see docs/PERSON1_CHECKPOINT.md, section 3.1)
# --------------------------------------------------------------------------
WORLD_WIDTH: Final[int] = 800
WORLD_HEIGHT: Final[int] = 600
FPS: Final[int] = 60
DT: Final[float] = 1.0 / FPS

PLAYER_WIDTH: Final[int] = 32
PLAYER_HEIGHT: Final[int] = 32

GRAVITY: Final[float] = 0.5             # px/frame^2
JUMP_VELOCITY: Final[float] = 10.25     # px/frame -> discrete apex of exactly 100px
MAX_JUMP_HEIGHT: Final[float] = 100.0   # px (j_max, spec)
MAX_RUN_SPEED: Final[float] = 6.0       # px/frame
RUN_ACCEL: Final[float] = 0.8           # px/frame^2
GROUND_FRICTION: Final[float] = 0.85    # vel_x multiplier per grounded frame without input
TERMINAL_VELOCITY: Final[float] = 15.0  # px/frame, enforced only inside the world

# Level layout (approved Phase 2 proposal)
WALL_THICKNESS: Final[int] = 16
FLOOR_Y: Final[int] = 440
FALL_GAP_X: Final[tuple[int, int]] = (240, 300)       # Infinite_Fall, 60px wide
PIT_X: Final[tuple[int, int]] = (440, 480)            # Softlock_Pit, 40px wide
PIT_DEPTH: Final[int] = 150                           # h = 150px
SEAM_Y: Final[tuple[int, int]] = (406, 408)           # Wall_Clip, 2px seam
PLATFORM_RECT: Final[tuple[int, int, int, int]] = (560, 360, 120, 16)
SPAWN_HOVER: Final[int] = 4  # spawn this far above the floor -> no collision on the reset frame

# Implementation tolerances (not physics constants)
CONTACT_EPSILON: Final[float] = 1.0  # px; adjacency that still counts as "touching"
VELOCITY_SNAP: Final[float] = 0.05   # px/frame; friction snaps smaller speeds to 0

_MAX_EJECT_PASSES: Final[int] = 16


class ColliderKind(str, Enum):
    SOLID = "solid"
    SEAM = "seam"  # segment of the bugged Wall_Clip wall


class Glitch(str, Enum):
    WALL_CLIP = "Wall_Clip"
    INFINITE_FALL = "Infinite_Fall"
    SOFTLOCK_PIT = "Softlock_Pit"


class Zone(str, Enum):
    ARENA = "arena"
    FALL_SHAFT = "fall_shaft"      # inside the Infinite_Fall gap, below the floor surface
    SOFTLOCK_PIT = "softlock_pit"  # inside the pit, below the floor surface
    OUT_OF_WORLD = "out_of_world"  # player centre outside the world rectangle


@dataclass(frozen=True)
class InputState:
    """Buttons held during one frame."""

    left: bool = False
    right: bool = False
    jump: bool = False

    @property
    def label(self) -> str:
        """Telemetry string, e.g. 'right+jump' or 'none'."""
        parts: list[str] = [
            name for name, held in (("left", self.left), ("right", self.right), ("jump", self.jump)) if held
        ]
        return "+".join(parts) if parts else "none"

    @classmethod
    def from_label(cls, label: str) -> InputState:
        """Inverse of `label`; used to replay a reproduction_sequence."""
        parts: set[str] = set(label.split("+")) - {"none", ""}
        unknown: set[str] = parts - {"left", "right", "jump"}
        if unknown:
            raise ValueError(f"Unknown input token(s): {sorted(unknown)}")
        return cls(left="left" in parts, right="right" in parts, jump="jump" in parts)


NO_INPUT: Final[InputState] = InputState()


@dataclass(frozen=True)
class FrameState:
    """Everything observable about the player after one simulated frame.

    The first eight fields map 1:1 onto the telemetry CSV contract (plus the
    simulated timestamp, which telemetry derives from frame_id). `zone`,
    `glitch_event` and `episode` are extra context for the agent / runner.
    """

    frame_id: int
    pos_x: float
    pos_y: float
    vel_x: float
    vel_y: float
    is_grounded: bool
    active_input: str
    collision_state: bool
    zone: Zone
    glitch_event: Glitch | None
    episode: int


@dataclass(frozen=True)
class Collider:
    name: str
    rect: pygame.Rect
    kind: ColliderKind = ColliderKind.SOLID


@dataclass(frozen=True)
class Level:
    world: pygame.Rect
    colliders: tuple[Collider, ...]
    spawn_points: tuple[tuple[float, float], ...]
    fall_gap: pygame.Rect
    pit: pygame.Rect
    seam: pygame.Rect


def build_level() -> Level:
    """Construct the 800x600 test arena with the three planted glitches."""
    w: int = WALL_THICKNESS
    floor_h: int = WORLD_HEIGHT - FLOOR_Y
    gap_l, gap_r = FALL_GAP_X
    pit_l, pit_r = PIT_X
    seam_top, seam_bottom = SEAM_Y
    pit_bottom: int = FLOOR_Y + PIT_DEPTH
    right_wall_x: int = WORLD_WIDTH - w

    colliders: tuple[Collider, ...] = (
        Collider("ceiling", pygame.Rect(0, 0, WORLD_WIDTH, w)),
        Collider("left_wall", pygame.Rect(0, 0, w, WORLD_HEIGHT)),
        Collider("floor_a", pygame.Rect(w, FLOOR_Y, gap_l - w, floor_h)),
        # gap_l..gap_r: Infinite_Fall -- intentionally no collider
        Collider("floor_b", pygame.Rect(gap_r, FLOOR_Y, pit_l - gap_r, floor_h)),
        Collider("pit_floor", pygame.Rect(pit_l, pit_bottom, pit_r - pit_l, WORLD_HEIGHT - pit_bottom)),
        Collider("floor_c", pygame.Rect(pit_r, FLOOR_Y, WORLD_WIDTH - pit_r, floor_h)),
        Collider("platform", pygame.Rect(*PLATFORM_RECT)),
        # Wall_Clip: right wall split by a 2px seam at y = seam_top..seam_bottom
        Collider("right_wall_upper", pygame.Rect(right_wall_x, 0, w, seam_top), ColliderKind.SEAM),
        Collider(
            "right_wall_lower",
            pygame.Rect(right_wall_x, seam_bottom, w, FLOOR_Y - seam_bottom),
            ColliderKind.SEAM,
        ),
    )
    spawn_y: float = float(FLOOR_Y - PLAYER_HEIGHT - SPAWN_HOVER)
    return Level(
        world=pygame.Rect(0, 0, WORLD_WIDTH, WORLD_HEIGHT),
        colliders=colliders,
        spawn_points=((40.0, spawn_y), (340.0, spawn_y), (640.0, spawn_y)),
        fall_gap=pygame.Rect(gap_l, FLOOR_Y, gap_r - gap_l, floor_h),
        pit=pygame.Rect(pit_l, FLOOR_Y, pit_r - pit_l, PIT_DEPTH),
        seam=pygame.Rect(right_wall_x, seam_top, w, seam_bottom - seam_top),
    )


def _overlaps(x: float, y: float, rect: pygame.Rect) -> bool:
    """Strict AABB overlap between the player box at (x, y) and `rect` (touching is not overlap)."""
    return x < rect.right and x + PLAYER_WIDTH > rect.left and y < rect.bottom and y + PLAYER_HEIGHT > rect.top


def _touches(x: float, y: float, rect: pygame.Rect, eps: float) -> bool:
    """Overlap test with the player box inflated by `eps` on every side."""
    return (
        x - eps < rect.right
        and x + PLAYER_WIDTH + eps > rect.left
        and y - eps < rect.bottom
        and y + PLAYER_HEIGHT + eps > rect.top
    )


class GameEngine:
    """Fixed-timestep physics simulation with optional 60 FPS rendering."""

    def __init__(self, headless: bool = True, level: Level | None = None, spawn_index: int = 0) -> None:
        self.headless: bool = headless
        self.level: Level = level if level is not None else build_level()

        self.frame_id: int = 0
        self.episode: int = 0
        self.pos_x: float = 0.0
        self.pos_y: float = 0.0
        self.vel_x: float = 0.0
        self.vel_y: float = 0.0
        self.is_grounded: bool = False

        self._screen: pygame.Surface | None = None
        self._clock: pygame.time.Clock | None = None
        self._font: pygame.font.Font | None = None
        if not headless:
            self._init_display()

        self.reset(spawn_index)  # episode 1

    # ------------------------------------------------------------------ setup
    def _init_display(self) -> None:
        pygame.init()
        self._screen = pygame.display.set_mode((self.level.world.width, self.level.world.height))
        pygame.display.set_caption("IndieQA Core Engine")
        self._clock = pygame.time.Clock()
        self._font = pygame.font.Font(None, 20)

    def reset(self, spawn_index: int = 0) -> None:
        """Start a new episode at spawn point `spawn_index` (wraps around).

        frame_id is NOT reset, so telemetry frame ids stay monotonic across episodes.
        """
        spawn_x, spawn_y = self.level.spawn_points[spawn_index % len(self.level.spawn_points)]
        self.pos_x = spawn_x
        self.pos_y = spawn_y
        self.vel_x = 0.0
        self.vel_y = 0.0
        self.is_grounded = False
        self.episode += 1

    # ---------------------------------------------------------------- physics
    def step(self, inputs: InputState) -> FrameState:
        """Advance the simulation by exactly one frame and return the resulting state."""
        was_grounded: bool = self.is_grounded
        collided: bool = False
        glitch: Glitch | None = None

        # 1. Horizontal control
        direction: int = int(inputs.right) - int(inputs.left)
        if direction != 0:
            self.vel_x = max(-MAX_RUN_SPEED, min(MAX_RUN_SPEED, self.vel_x + direction * RUN_ACCEL))
        elif was_grounded:
            self.vel_x *= GROUND_FRICTION
            if abs(self.vel_x) < VELOCITY_SNAP:
                self.vel_x = 0.0

        # 2. Jump (only from the ground)
        if inputs.jump and was_grounded:
            self.vel_y = -JUMP_VELOCITY

        # 3. Gravity + terminal velocity (inside the world only -> Infinite_Fall below it)
        self.vel_y += GRAVITY
        if self._centre_in_world() and self.vel_y > TERMINAL_VELOCITY:
            self.vel_y = TERMINAL_VELOCITY

        # 4. X axis: move, then resolve
        self.pos_x += self.vel_x
        seam_hits: list[Collider] = [
            c for c in self.level.colliders if c.kind is ColliderKind.SEAM and _overlaps(self.pos_x, self.pos_y, c.rect)
        ]
        if len(seam_hits) >= 2 and self.vel_x != 0.0:
            # PLANTED BUG (Wall_Clip): straddling the 2px seam makes the engine think the player is
            # embedded in geometry; it "unsticks" along vel_x to the first free space -- outside the wall.
            self._eject_along_velocity()
            collided = True
            glitch = Glitch.WALL_CLIP
        else:
            for c in self.level.colliders:
                if _overlaps(self.pos_x, self.pos_y, c.rect):
                    collided = True
                    if self.vel_x > 0.0:
                        self.pos_x = float(c.rect.left - PLAYER_WIDTH)
                    elif self.vel_x < 0.0:
                        self.pos_x = float(c.rect.right)
                    self.vel_x = 0.0

        # 5. Y axis: move, then resolve
        self.pos_y += self.vel_y
        self.is_grounded = False
        for c in self.level.colliders:
            if _overlaps(self.pos_x, self.pos_y, c.rect):
                collided = True
                if self.vel_y > 0.0:
                    self.pos_y = float(c.rect.top - PLAYER_HEIGHT)
                    self.is_grounded = True
                elif self.vel_y < 0.0:
                    self.pos_y = float(c.rect.bottom)
                self.vel_y = 0.0

        # 6. Contact (touching counts as colliding for telemetry)
        if not collided:
            collided = any(_touches(self.pos_x, self.pos_y, c.rect, CONTACT_EPSILON) for c in self.level.colliders)

        state = FrameState(
            frame_id=self.frame_id,
            pos_x=self.pos_x,
            pos_y=self.pos_y,
            vel_x=self.vel_x,
            vel_y=self.vel_y,
            is_grounded=self.is_grounded,
            active_input=inputs.label,
            collision_state=collided,
            zone=self._zone(),
            glitch_event=glitch,
            episode=self.episode,
        )
        self.frame_id += 1
        return state

    def _eject_along_velocity(self) -> None:
        """Push the player along sign(vel_x) until it overlaps no collider (the buggy 'unstuck')."""
        moving_right: bool = self.vel_x > 0.0
        for _ in range(_MAX_EJECT_PASSES):
            hits: list[pygame.Rect] = [
                c.rect for c in self.level.colliders if _overlaps(self.pos_x, self.pos_y, c.rect)
            ]
            if not hits:
                return
            if moving_right:
                self.pos_x = float(max(r.right for r in hits))
            else:
                self.pos_x = float(min(r.left for r in hits) - PLAYER_WIDTH)

    def _centre(self) -> tuple[float, float]:
        return self.pos_x + PLAYER_WIDTH / 2.0, self.pos_y + PLAYER_HEIGHT / 2.0

    def _centre_in_world(self) -> bool:
        cx, cy = self._centre()
        world = self.level.world
        return world.left <= cx <= world.right and world.top <= cy <= world.bottom

    def _zone(self) -> Zone:
        if not self._centre_in_world():
            return Zone.OUT_OF_WORLD
        cx, cy = self._centre()
        if self.level.pit.collidepoint(cx, cy):
            return Zone.SOFTLOCK_PIT
        if self.level.fall_gap.collidepoint(cx, cy):
            return Zone.FALL_SHAFT
        return Zone.ARENA

    @property
    def player_rect(self) -> pygame.Rect:
        return pygame.Rect(round(self.pos_x), round(self.pos_y), PLAYER_WIDTH, PLAYER_HEIGHT)

    # -------------------------------------------------------------- rendering
    def render(self, state: FrameState, hud_lines: Sequence[str] = ()) -> bool:
        """Draw one frame and hold 60 FPS. Returns False once the window is closed.

        No-op (returns True) in headless mode.
        """
        if self._screen is None or self._clock is None or self._font is None:
            return True

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False

        screen = self._screen
        screen.fill((24, 26, 32))

        # Glitch zones (drawn under geometry)
        pygame.draw.rect(screen, (90, 30, 30), self.level.fall_gap)
        pygame.draw.rect(screen, (90, 80, 20), self.level.pit)

        for c in self.level.colliders:
            colour = (150, 70, 70) if c.kind is ColliderKind.SEAM else (110, 115, 125)
            pygame.draw.rect(screen, colour, c.rect)
        pygame.draw.rect(screen, (255, 60, 60), self.level.seam.inflate(6, 0), 1)

        labels: tuple[tuple[str, pygame.Rect], ...] = (
            (Glitch.INFINITE_FALL.value, self.level.fall_gap),
            (Glitch.SOFTLOCK_PIT.value, self.level.pit),
        )
        for text, rect in labels:
            surf = self._font.render(text, True, (230, 230, 230))
            screen.blit(surf, (rect.centerx - surf.get_width() // 2, rect.top + 6))
        clip_label = self._font.render(Glitch.WALL_CLIP.value, True, (255, 120, 120))
        screen.blit(clip_label, (self.level.seam.left - clip_label.get_width() - 8, self.level.seam.top - 8))

        player_colour = (255, 70, 70) if state.glitch_event is not None else (80, 200, 255)
        pygame.draw.rect(screen, player_colour, self.player_rect)

        base_hud: list[str] = [
            f"frame {state.frame_id}  episode {state.episode}  zone {state.zone.value}",
            f"pos ({state.pos_x:7.2f}, {state.pos_y:7.2f})  vel ({state.vel_x:6.2f}, {state.vel_y:6.2f})",
            f"input {state.active_input}  grounded {state.is_grounded}  collision {state.collision_state}",
        ]
        for i, line in enumerate([*base_hud, *hud_lines]):
            screen.blit(self._font.render(line, True, (235, 235, 235)), (24, 24 + i * 18))

        pygame.display.flip()
        self._clock.tick(FPS)
        return True

    def close(self) -> None:
        if self._screen is not None:
            pygame.quit()
            self._screen = None


# --------------------------------------------------------------------------
# Self-test:  python -m core.engine
# --------------------------------------------------------------------------
def _settle(engine: GameEngine, max_frames: int = 30) -> FrameState:
    state = engine.step(NO_INPUT)
    for _ in range(max_frames):
        if state.is_grounded:
            return state
        state = engine.step(NO_INPUT)
    raise AssertionError("player did not land after spawning")


def _test_jump_apex() -> float:
    engine = GameEngine(headless=True)
    ground_y: float = _settle(engine).pos_y
    min_y: float = ground_y
    state = engine.step(InputState(jump=True))
    while not state.is_grounded:
        min_y = min(min_y, state.pos_y)
        state = engine.step(NO_INPUT)
    apex: float = ground_y - min_y
    assert abs(apex - MAX_JUMP_HEIGHT) < 1e-9, f"jump apex {apex} != {MAX_JUMP_HEIGHT}"
    return apex


def _test_softlock_pit() -> tuple[int, float]:
    engine = GameEngine(headless=True, spawn_index=1)  # S2, left of the pit
    state = _settle(engine)
    for _ in range(300):
        state = engine.step(InputState(right=True))
        if state.zone is Zone.SOFTLOCK_PIT and state.is_grounded:
            break
    assert state.zone is Zone.SOFTLOCK_PIT, f"player never entered the pit (zone={state.zone})"
    floor_y: float = state.pos_y
    highest: float = floor_y
    spam: tuple[InputState, ...] = (
        InputState(right=True, jump=True),
        InputState(left=True, jump=True),
        InputState(jump=True),
        InputState(left=True),
        InputState(right=True),
    )
    frames: int = 600
    for i in range(frames):
        state = engine.step(spam[(i // 7) % len(spam)])
        highest = min(highest, state.pos_y)
        assert state.zone is Zone.SOFTLOCK_PIT, f"escaped the pit at frame {state.frame_id}"
    rise: float = floor_y - highest
    assert rise <= MAX_JUMP_HEIGHT + 1e-9 and PIT_DEPTH - rise >= 50.0 - 1e-9
    return frames, rise


def _test_infinite_fall() -> tuple[int, float, float]:
    engine = GameEngine(headless=True, spawn_index=0)  # S1, left of the gap
    state = _settle(engine)
    while state.zone is not Zone.FALL_SHAFT:
        state = engine.step(InputState(right=True))
        assert state.frame_id < 500, "player never reached the fall gap"
    airborne: int = 0
    longest: int = 0
    for _ in range(300):
        state = engine.step(NO_INPUT)
        airborne = 0 if state.collision_state else airborne + 1
        longest = max(longest, airborne)
    assert longest > 120, f"only {longest} consecutive frames without collision"
    assert state.vel_y > TERMINAL_VELOCITY and state.pos_y > WORLD_HEIGHT and state.zone is Zone.OUT_OF_WORLD
    return longest, state.vel_y, state.pos_y


def _test_wall_clip() -> tuple[float, FrameState]:
    engine = GameEngine(headless=True, spawn_index=2)  # S3, right side of the arena
    prev = _settle(engine)
    for _ in range(600):
        state = engine.step(InputState(right=True, jump=True))
        if state.glitch_event is Glitch.WALL_CLIP:
            delta: float = ((state.pos_x - prev.pos_x) ** 2 + (state.pos_y - prev.pos_y) ** 2) ** 0.5
            assert delta > 25.0, f"clip displacement {delta} <= 25"
            assert state.collision_state, "collision_state must be True on the clip frame"
            assert state.pos_x >= WORLD_WIDTH, "player did not end up outside the arena"
            return delta, state
        prev = state
    raise AssertionError("Wall_Clip never triggered")


def _test_no_false_clips(frames: int = 20_000, seed: int = 1234) -> int:
    """Random play must never move > 25px in a frame except on Wall_Clip frames."""
    import random

    rng = random.Random(seed)
    engine = GameEngine(headless=True)
    prev = engine.step(NO_INPUT)
    spawn: int = 0
    for _ in range(frames):
        inp = InputState(left=rng.random() < 0.3, right=rng.random() < 0.4, jump=rng.random() < 0.2)
        state = engine.step(inp)
        delta: float = ((state.pos_x - prev.pos_x) ** 2 + (state.pos_y - prev.pos_y) ** 2) ** 0.5
        in_world: bool = prev.zone is not Zone.OUT_OF_WORLD
        if in_world and state.glitch_event is None:
            assert delta <= 25.0, f"normal motion moved {delta:.2f}px at frame {state.frame_id}"
        if state.zone is Zone.OUT_OF_WORLD or state.zone is Zone.SOFTLOCK_PIT:
            spawn += 1
            engine.reset(spawn)
            prev = engine.step(NO_INPUT)
            continue
        prev = state
    return frames


def _self_test() -> None:
    apex = _test_jump_apex()
    print(f"[PASS] jump apex            = {apex:.4f}px (j_max {MAX_JUMP_HEIGHT:.0f}px)")
    frames, rise = _test_softlock_pit()
    print(f"[PASS] Softlock_Pit         : trapped {frames} frames of jump spam, max rise {rise:.2f}px < wall {PIT_DEPTH}px")
    longest, vy, y = _test_infinite_fall()
    print(f"[PASS] Infinite_Fall        : {longest} frames without collision, vel_y {vy:.1f}px/f (uncapped), pos_y {y:.0f}")
    delta, s = _test_wall_clip()
    print(f"[PASS] Wall_Clip            : frame {s.frame_id} jumped {delta:.2f}px to ({s.pos_x:.1f}, {s.pos_y:.1f}), collision={s.collision_state}")
    n = _test_no_false_clips()
    print(f"[PASS] no false >25px moves : {n} random frames")


if __name__ == "__main__":
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    _self_test()
