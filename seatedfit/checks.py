"""The render check. Deterministic image code; no model is called here.

Each check returns a number, pass/warn/fail, the region it looked at and a plain
sentence. Thresholds live in THRESHOLDS and were set from the real runs; see
RESULTS.md for how.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass

import cv2
import numpy as np
from skimage.color import rgb2lab
from skimage.metrics import structural_similarity

from .regions import Regions, mark_support

THRESHOLDS = {
    "change_delta_e": 14.0,  # colour distance that counts as a changed pixel
    "garment_match_delta_e": 20.0,  # how close to the garment's colours a changed pixel must be
    "skin_ab": 14.0,  # colour distance from the face that counts as skin
    "chair_ssim_pass": 0.80,
    "chair_ssim_fail": 0.65,
    "damage_pass": 0.04,  # share of the visible chair changed to a non-garment colour
    "damage_fail": 0.12,
    "edges_kept_fail": 0.55,  # any wheel keeping less of its visible edges than this was lost
    "clearance_pass": 0.05,  # share of the worst wheel under the garment
    "clearance_fail": 0.15,
    "face_ssim_pass": 0.80,
    "face_ssim_fail": 0.60,
    "hand_ssim_pass": 0.65,
    "hand_ssim_fail": 0.55,
    "hand_min_bare": 0.30,  # a hand box mostly under a sleeve is hidden, not altered
    "change_pass": 0.01,  # share of the frame that changed
    "change_fail": 0.003,
    "mark_support": 0.40,  # share of a shopper's mark that must lie on a real edge in the photo
}


@dataclass
class Check:
    id: str
    name: str
    status: str  # pass | warn | fail | not_measured
    value: float | None
    unit: str
    message: str
    detail: dict


@dataclass
class Report:
    verdict: str
    checks: list
    masks: dict  # not serialised: arrays for the overlay

    def to_dict(self):
        return {"verdict": self.verdict, "checks": [asdict(c) for c in self.checks]}


def _grade_high(v, pass_at, fail_at):
    return "pass" if v >= pass_at else "fail" if v < fail_at else "warn"


def _grade_low(v, pass_at, fail_at):
    return "pass" if v <= pass_at else "fail" if v > fail_at else "warn"


def change_mask(src_lab, res_lab) -> np.ndarray:
    de = np.linalg.norm(src_lab - res_lab, axis=2)
    m = (de > THRESHOLDS["change_delta_e"]).astype(np.uint8)
    m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    return m > 0


def garment_colours(res_lab, changed, regions: Regions) -> np.ndarray | None:
    """Learn the garment's colours from changed pixels above the wheels, where a
    change can only be clothing, excluding the face."""
    h = changed.shape[0]
    zone = changed.copy()
    top_of_chair = min((int(w.cy - w.b) for w in regions.wheels), default=int(h * 0.55))
    zone[top_of_chair:] = False
    if regions.face:
        x, y, w, hh = regions.face
        zone[: y + hh] = False
    pts = res_lab[zone]
    if len(pts) < 500:
        return None
    pts = pts[:: max(1, len(pts) // 20000)].astype(np.float32)
    k = 3
    crit = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 20, 0.5)
    cv2.setRNGSeed(7)
    _, labels, centres = cv2.kmeans(pts, k, None, crit, 3, cv2.KMEANS_PP_CENTERS)
    counts = np.bincount(labels.ravel(), minlength=k)
    return centres[counts > 0.1 * len(pts)]


def garment_mask(res_lab, changed, colours) -> np.ndarray:
    if colours is None or not len(colours):
        return np.zeros(changed.shape, bool)
    d = np.min(np.linalg.norm(res_lab[:, :, None, :] - colours[None, None, :, :], axis=3), axis=2)
    m = (changed & (d < THRESHOLDS["garment_match_delta_e"])).astype(np.uint8)
    # a hem is a solid surface: fill spokes showing through the colour match and drop specks
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8))
    return cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8)) > 0


def _ssim_map(src_rgb, res_rgb):
    a = cv2.cvtColor(src_rgb, cv2.COLOR_RGB2GRAY)
    b = cv2.cvtColor(res_rgb, cv2.COLOR_RGB2GRAY)
    _, s = structural_similarity(a, b, full=True, data_range=255, gaussian_weights=True, sigma=1.5,
                                 use_sample_covariance=False)
    return s


def _edges(rgb):
    return cv2.Canny(cv2.GaussianBlur(cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY), (3, 3), 0), 50, 150) > 0


def check_change(changed, regions: Regions) -> Check:
    share = float(changed.mean())
    st = _grade_high(share, THRESHOLDS["change_pass"], THRESHOLDS["change_fail"])
    msg = {"pass": f"The garment changed {share:.0%} of the picture, so this is a real try-on.",
           "warn": f"Only {share:.1%} of the picture changed. The garment may barely have been applied.",
           "fail": f"Only {share:.1%} of the picture changed. The garment was not applied."}[st]
    return Check("change", "Garment applied", st, round(share, 4), "share of picture", msg, {})


def check_chair(src, res, changed, covered, regions: Regions, ssim) -> Check:
    if not regions.wheels:
        return Check("chair", "Wheelchair intact", "not_measured", None, "similarity",
                     "No wheels were marked, so the chair was not compared. Please look at it yourself.", {})
    visible = regions.chair_mask & ~cv2.dilate(covered.astype(np.uint8), np.ones((9, 9), np.uint8)).astype(bool)
    if visible.sum() < 200:
        return Check("chair", "Wheelchair intact", "warn", None, "similarity",
                     "The garment hides so much of the chair that it could not be compared.", {})
    sim = float(ssim[visible].mean())
    damage = float((changed & visible).sum() / visible.sum())
    src_e, res_e = _edges(src), cv2.dilate(_edges(res).astype(np.uint8), np.ones((5, 5), np.uint8)) > 0
    kept = []
    for w in regions.wheels:
        m = w.mask(regions.shape) & visible & src_e
        kept.append(1.0 if m.sum() < 40 else float((m & res_e).sum() / m.sum()))
    worst_edges = min(kept)
    st_sim = _grade_high(sim, THRESHOLDS["chair_ssim_pass"], THRESHOLDS["chair_ssim_fail"])
    st_dmg = _grade_low(damage, THRESHOLDS["damage_pass"], THRESHOLDS["damage_fail"])
    lost = worst_edges < THRESHOLDS["edges_kept_fail"]
    st = "fail" if "fail" in (st_sim, st_dmg) or lost else "warn" if "warn" in (st_sim, st_dmg) else "pass"
    msg = {"pass": "The wheels you marked match your photo." if regions.source == "shopper" else "The wheelchair matches your photo.",
           "warn": "Parts of the wheelchair look slightly different from your photo.",
           "fail": "The wheelchair was changed: parts of it no longer match your photo."}[st]
    if lost:
        msg = "A wheel was lost: its outline is missing from the result."
    return Check("chair", "Wheelchair intact", st, round(sim, 3), "similarity", msg,
                 {"changed_share": round(damage, 4), "worst_wheel_edges_kept": round(worst_edges, 3),
                  "wheels_compared": len(regions.wheels)})


def skin_in_source(src_lab, regions: Regions) -> np.ndarray:
    """Arms and hands already in front of a wheel in the photo. A sleeve over an
    arm hides no more wheel than the arm did, so those pixels don't count."""
    if not regions.face:
        return np.zeros(src_lab.shape[:2], bool)
    x, y, w, h = regions.face
    tone = np.median(src_lab[y + h // 4:y + 3 * h // 4, x + w // 4:x + 3 * w // 4].reshape(-1, 3), axis=0)
    m = (np.linalg.norm((src_lab - tone)[:, :, 1:], axis=2) < THRESHOLDS["skin_ab"]).astype(np.uint8)
    m[(src_lab[:, :, 1] ** 2 + src_lab[:, :, 2] ** 2) < 100] = 0  # greys are metal and tyre, never skin
    return cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8)) > 0


def unsupported_marks(src_rgb, regions: Regions) -> int:
    """How many of a shopper's marks sit on nothing wheel-like. A mark on a bare
    wall would be clear of any garment, so it must not earn a pass."""
    if regions.source != "shopper":
        return 0
    edges = _edges(src_rgb).astype(np.uint8)
    return sum(mark_support(edges, w) < THRESHOLDS["mark_support"] for w in regions.wheels)


def check_clearance(covered, regions: Regions, skin, stray=0) -> Check:
    if not regions.wheels:
        return Check("clearance", "Wheel clearance", "not_measured", None, "share of wheel",
                     "No wheels were marked, so clearance was not measured. Please look at your wheels yourself.", {})
    shares = []
    for w in regions.wheels:
        m = w.mask(regions.shape) & ~skin
        shares.append((w.kind, float((covered & m).sum() / max(1, m.sum()))))
    worst = max(s for _, s in shares)
    visible = regions.wheel_mask & ~skin
    overall = float((covered & visible).sum() / max(1, visible.sum()))
    st = _grade_low(worst, THRESHOLDS["clearance_pass"], THRESHOLDS["clearance_fail"])
    if stray and st == "pass":
        st = "warn"
    n = round(worst * 100)
    msg = {"pass": "The garment stays clear of the wheels you marked." if regions.source == "shopper" else "The garment stays clear of the wheels.",
           "warn": f"The garment touches a wheel, covering {n}% of it. Check this before you buy.",
           "fail": f"The garment covers {n}% of a wheel. It could catch while you push."}[st]
    if stray and st == "warn" and worst <= THRESHOLDS["clearance_pass"]:
        msg = "A mark isn't on a clear wheel outline in your photo, so we can't call this clear. Check your marks."
    return Check("clearance", "Wheel clearance", st, round(worst, 4), "share of worst wheel", msg,
                 {"per_wheel": [{"kind": k, "share": round(s, 4)} for k, s in shares],
                  "all_wheels_share": round(overall, 4), "marks_off_an_outline": stray})


def check_person(ssim, regions: Regions, covered) -> Check:
    face = None
    if regions.face:
        x, y, w, h = regions.face
        face = float(ssim[y:y + h, x:x + w].mean())
    # a sleeve over a wrist is the garment doing its job, so only bare pixels are compared
    hand_scores = []
    for x0, y0, x1, y1 in regions.hands:
        bare = ~covered[y0:y1, x0:x1]
        if bare.mean() >= THRESHOLDS["hand_min_bare"]:
            hand_scores.append(float(ssim[y0:y1, x0:x1][bare].mean()))
    hand = min(hand_scores) if hand_scores else None
    if face is None:
        return Check("person", "Face and hands", "not_measured", None, "similarity",
                     "We could not find a face to compare.", {})
    st = _grade_high(face, THRESHOLDS["face_ssim_pass"], THRESHOLDS["face_ssim_fail"])
    if hand is not None:
        hs = _grade_high(hand, THRESHOLDS["hand_ssim_pass"], THRESHOLDS["hand_ssim_fail"])
        st = "fail" if "fail" in (st, hs) else "warn" if "warn" in (st, hs) else "pass"
    msg = {"pass": "The face and hands match your photo.",
           "warn": "The face or hands look slightly different from your photo.",
           "fail": "The face or hands were altered, so this is not a fair picture of you."}[st]
    if not regions.hands:  # uploads: hands aren't located, so don't claim them
        msg = {"pass": "The face matches your photo. Hands were not compared.",
               "warn": "The face looks slightly different from your photo. Hands were not compared.",
               "fail": "The face was altered, so this is not a fair picture of you."}[st]
    return Check("person", "Face and hands", st, round(face, 3), "similarity", msg,
                 {"face": round(face, 3), "worst_hand": None if hand is None else round(hand, 3)})


def run_checks(src_rgb: np.ndarray, res_rgb: np.ndarray, regions: Regions) -> Report:
    """src and res are the same size; regions were located on src only."""
    if res_rgb.shape != src_rgb.shape:
        res_rgb = cv2.resize(res_rgb, (src_rgb.shape[1], src_rgb.shape[0]), interpolation=cv2.INTER_AREA)
    src_lab = rgb2lab(cv2.GaussianBlur(src_rgb, (0, 0), 1.2))
    res_lab = rgb2lab(cv2.GaussianBlur(res_rgb, (0, 0), 1.2))
    changed = change_mask(src_lab, res_lab)
    colours = garment_colours(res_lab, changed, regions)
    covered = garment_mask(res_lab, changed, colours)
    ssim = _ssim_map(src_rgb, res_rgb)
    skin = skin_in_source(src_lab, regions)
    checks = [check_clearance(covered, regions, skin, unsupported_marks(src_rgb, regions)), check_chair(src_rgb, res_rgb, changed, covered, regions, ssim),
              check_person(ssim, regions, covered), check_change(changed, regions)]
    states = [c.status for c in checks]
    verdict = "fail" if "fail" in states else "warn" if "warn" in states or "not_measured" in states else "pass"
    return Report(verdict, checks, {"changed": changed, "covered": covered & ~skin})
