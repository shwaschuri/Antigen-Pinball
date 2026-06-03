"""
╔══════════════════════════════════════════════════════════════╗
║   ANTIGEN PINBALL  –  Immune System Arcade Simulator         ║
║   A computational biology + game development project         ║
╚══════════════════════════════════════════════════════════════╝

Controls
  SPACE     hold to charge plunger, release to fire
  Z / ←     left flipper
  X / →     right flipper
  F         toggle fullscreen
  R         restart  (game over)
  ESC       quit
"""

import pygame, sys, math, random, struct, wave, io
pygame.init()
pygame.mixer.init(frequency=44100, size=-16, channels=1, buffer=512)

# ── Screen ─────────────────────────────────────────────────────────────────────
INFO     = pygame.display.Info()
NATIVE_W = INFO.current_w
NATIVE_H = INFO.current_h
LW, LH   = 560, 980          # logical playfield

screen = pygame.display.set_mode((NATIVE_W, NATIVE_H),
                                  pygame.FULLSCREEN | pygame.SCALED)
pygame.display.set_caption("Antigen Pinball – Immune System")
clock = pygame.time.Clock()

# ── Colours ────────────────────────────────────────────────────────────────────
BG       = (6,  10, 24)
WALL_COL = (30, 65, 140)
DIM      = (50, 75, 130)
TEXT     = (200, 220, 255)
HUD_BG   = (10, 15, 35)

C = {
    "virus":      (220,  50,  50),
    "mhc":        ( 79, 195, 247),
    "tcell":      (206, 147, 216),
    "bcell":      (129, 199, 132),
    "antibody":   (255, 204, 128),
    "complement": (239, 154, 154),
    "cytokine":   (128, 222, 234),
    "macrophage": (255, 183,  77),
    "antigen":    (128, 203, 196),
    "pin":        ( 80, 120, 200),
}

# ── Layout ─────────────────────────────────────────────────────────────────────
WL = 55;  WR = LW - 55
FY        = LH - 105            # flippers higher up for easier saves
FL_LEN    = 100; FT = 17
FLX       = WL + 48;  FRX = WR - 48
F_REST    = math.radians(26)
F_ACTIVE  = math.radians(-34)
F_SPEED   = 0.50
BALL_R    = 13
CHUTE_W   = 38
LAUNCH_X  = WR - BALL_R - 4    # inside right wall, just above right flipper
LAUNCH_Y  = FY - 30
GRAVITY   = 0.20               # gentle — ball stays in play longer
MAX_SPD   = 16
TARGET_X  = LW // 2
TARGET_Y  = 90
TARGET_R  = 44

# Guide pins spread across full lower field
GUIDE_PINS = [
    (LW//2,        FY - 32,  11),   # centre post between flippers
    (WL + 24,      FY - 68,  10),   # outlane guard left
    (WR - 24,      FY - 68,  10),   # outlane guard right
    (LW//2,        LH-310,   12),   # mid-lower
    (LW//2 - 90,   LH-350,   10),
    (LW//2 + 90,   LH-350,   10),
    (LW//2 - 45,   LH-265,    9),
    (LW//2 + 45,   LH-265,    9),
]

# ── Fonts — sized for a 980px logical canvas ───────────────────────────────────
def fnt(sz, bold=False): return pygame.font.SysFont("Arial", sz, bold=bold)
F8  = fnt(13)           # sprite inner labels
F10 = fnt(15,True)      # sprite main labels
F10b= fnt(15,True)
F12 = fnt(16)
F13 = fnt(16)
F14 = fnt(18,True)
F16 = fnt(18,True)
F18 = fnt(20,True)
F20 = fnt(22,True)
F22 = fnt(22,True)
F24 = fnt(26,True)
F32 = fnt(34,True)
F36 = fnt(38,True)
F44 = fnt(46,True)

# ══════════════════════════════════════════════════════════════════════════════
#  PROCEDURAL SOUND SYNTHESIS
# ══════════════════════════════════════════════════════════════════════════════

SR = 44100   # sample rate

def _make_sound(samples):
    arr = pygame.sndarray.make_sound(samples.astype("int16"))
    return arr

def _sine(freq, dur, vol=3000, decay=True):
    import array as arr
    n = int(SR * dur)
    data = arr.array("h")
    for i in range(n):
        t = i / SR
        env = math.exp(-4 * t / dur) if decay else 1.0
        v = int(vol * env * math.sin(2 * math.pi * freq * t))
        data.append(max(-32767, min(32767, v)))
    buf = pygame.mixer.Sound(buffer=bytes(data))
    return buf

def _noise_burst(dur=0.06, vol=2000, filt=0.3):
    import array as arr
    n = int(SR * dur)
    data = arr.array("h")
    prev = 0
    for i in range(n):
        t = i / SR
        env = math.exp(-8 * t / dur)
        raw = random.randint(-32767, 32767)
        fv  = int(prev * filt + raw * (1-filt))
        prev = fv
        data.append(max(-32767, min(32767, int(fv * env * vol / 32767))))
    return pygame.mixer.Sound(buffer=bytes(data))

def _chord(freqs, dur=0.18, vol=2500):
    import array as arr
    n = int(SR * dur)
    data = arr.array("h")
    for i in range(n):
        t   = i / SR
        env = math.exp(-5 * t / dur)
        v   = sum(math.sin(2*math.pi*f*t) for f in freqs)
        v   = int(vol * env * v / len(freqs))
        data.append(max(-32767, min(32767, v)))
    return pygame.mixer.Sound(buffer=bytes(data))

def _sweep(f0, f1, dur=0.25, vol=3000):
    import array as arr
    n = int(SR * dur)
    data = arr.array("h")
    for i in range(n):
        t   = i / SR
        f   = f0 + (f1 - f0) * (t / dur)
        env = math.sin(math.pi * t / dur)
        v   = int(vol * env * math.sin(2 * math.pi * f * t))
        data.append(max(-32767, min(32767, v)))
    return pygame.mixer.Sound(buffer=bytes(data))

# build sound table
SFX = {}
try:
    SFX["mhc"]        = _sine(660, 0.14, vol=2800)
    SFX["tcell"]      = _chord([440, 550, 660], dur=0.20, vol=2600)
    SFX["bcell"]      = _sine(520, 0.13, vol=2600)
    SFX["antibody"]   = _sine(880, 0.10, vol=2200)
    SFX["complement"] = _noise_burst(0.08, vol=1800)
    SFX["cytokine"]   = _sine(1100, 0.08, vol=1600)
    SFX["macrophage"] = _chord([110, 165], dur=0.22, vol=3000)
    SFX["flipper"]    = _noise_burst(0.04, vol=1200, filt=0.6)
    SFX["launch"]     = _sweep(200, 800, dur=0.22, vol=2800)
    SFX["lose"]       = _sweep(400, 100, dur=0.5,  vol=2500)
    SFX["win"]        = _chord([523, 659, 784, 1047], dur=0.6, vol=3000)
    SFX["combo"]      = _sweep(400, 1200, dur=0.3, vol=3500)
    SFX["pin"]        = _sine(330, 0.07, vol=1500)
    SOUND_OK = True
except Exception:
    SOUND_OK = False

def play(name):
    if SOUND_OK and name in SFX:
        try: SFX[name].play()
        except: pass

# ══════════════════════════════════════════════════════════════════════════════
#  LAB NOTES  (educational pop-ups)
# ══════════════════════════════════════════════════════════════════════════════

LAB_NOTES = {
    "mhc": {
        "title": "MHC Molecules",
        "body":  ("Major Histocompatibility Complex proteins sit on cell surfaces "
                  "and display peptide fragments to passing T cells. MHC-II shows "
                  "extracellular antigens to helper T cells (CD4+); MHC-I shows "
                  "intracellular peptides to cytotoxic T cells (CD8+). Without "
                  "MHC, the adaptive immune system is blind to infection.")
    },
    "tcell": {
        "title": "T Lymphocytes",
        "body":  ("T cells mature in the thymus. Each carries a unique T-Cell "
                  "Receptor (TCR) that fits only one antigen shape. Helper T cells "
                  "release cytokines that activate B cells and macrophages. "
                  "Cytotoxic T cells inject perforin into infected cells. "
                  "Memory T cells persist for decades — the basis of vaccination.")
    },
    "bcell": {
        "title": "B Lymphocytes",
        "body":  ("B cells recognise antigens via surface immunoglobulins. On "
                  "activation they differentiate into plasma cells that secrete "
                  "up to 2 000 antibodies per second. Affinity maturation in "
                  "germinal centres refines antibody binding over days. Memory "
                  "B cells provide life-long protection against re-infection.")
    },
    "antibody": {
        "title": "Antibodies (Immunoglobulins)",
        "body":  ("IgG antibodies are Y-shaped proteins. The two Fab arms bind "
                  "antigen epitopes with exquisite specificity; the Fc tail recruits "
                  "complement and phagocytes. Neutralisation, opsonisation, and "
                  "ADCC are the three main antibody effector mechanisms. "
                  "A single infection can stimulate 10⁷ distinct B-cell clones.")
    },
    "complement": {
        "title": "Complement System",
        "body":  ("The complement cascade is a set of ~30 plasma proteins. C3b "
                  "covalently binds pathogen surfaces via a reactive thioester bond "
                  "— opsonising them for phagocytosis. The Membrane Attack Complex "
                  "(MAC) punches holes in bacterial membranes. Complement bridges "
                  "innate and adaptive immunity.")
    },
    "cytokine": {
        "title": "Cytokines",
        "body":  ("Cytokines are small signalling proteins that coordinate immune "
                  "responses. IL-2 drives T cell proliferation. TNF-α activates "
                  "macrophages and causes fever. IFN-γ boosts MHC expression. "
                  "IL-6 promotes B cell differentiation. A cytokine storm — "
                  "runaway cytokine production — can be life-threatening.")
    },
    "macrophage": {
        "title": "Macrophages",
        "body":  ("Macrophages ('big eaters') engulf pathogens by extending "
                  "pseudopods and forming a phagosome. They digest up to 100 "
                  "bacteria per cell, present antigens on MHC-II, and release "
                  "cytokines. Tissue-resident macrophages (Kupffer cells, microglia) "
                  "provide constant immune surveillance at barrier sites.")
    },
}

# ══════════════════════════════════════════════════════════════════════════════
#  VIRUS BOSS PHASES  (mutation levels 0-3)
# ══════════════════════════════════════════════════════════════════════════════

VIRUS_PHASES = [
    dict(level=0, name="Wild-type",     spikes=14, spike_col=(190,55,55),  shield=False,
         desc="Wild-type virus — standard surface antigens"),
    dict(level=1, name="Glycan Shield", spikes=14, spike_col=(100,180,100),shield=True,
         desc="Glycan shield added — antibodies partially blocked! +0.5 resist"),
    dict(level=2, name="Escape Mutant", spikes=18, spike_col=(200,150,50), shield=False,
         desc="Antigenic drift mutation — new epitopes, harder to bind!"),
    dict(level=3, name="Hyper-variant", spikes=22, spike_col=(180,80,220), shield=True,
         desc="Hyper-variable surface — maximum immune evasion!"),
]

# ══════════════════════════════════════════════════════════════════════════════
#  IMMUNE CASCADE CHAIN SYSTEM
# ══════════════════════════════════════════════════════════════════════════════

CHAINS = [
    # name, required sequence of kinds (order matters), bonus pts, msg
    ("Antigen Presentation", ["mhc", "tcell"],
     500, "MHC → T cell: Antigen Presentation Cascade! +500"),
    ("Cytotoxic Response",   ["mhc", "tcell", "bcell"],
     800, "Full Adaptive Response! MHC→T→B cascade! +800"),
    ("Cytokine Storm",       ["tcell", "cytokine", "cytokine"],
     600, "CYTOKINE STORM! Runaway immune activation! +600"),
    ("Opsonisation",         ["antibody", "complement"],
     400, "Opsonisation! Ab + C3b = perfect pathogen tag! +400"),
    ("Phagocytosis",         ["complement", "macrophage"],
     450, "Complement-mediated Phagocytosis! +450"),
    ("Full Innate+Adaptive", ["macrophage", "tcell", "bcell"],
     1000,"INNATE → ADAPTIVE bridge! Full immunity! +1000"),
]

# ══════════════════════════════════════════════════════════════════════════════
#  PROGRESSION STAGES
# ══════════════════════════════════════════════════════════════════════════════

STAGES = [
    dict(id=0, name="Innate Immunity",       target_pts=2000,
         desc="Activate macrophages and complement to begin the response"),
    dict(id=1, name="Antigen Presentation",  target_pts=5000,
         desc="MHC molecules present antigen fragments to T cells"),
    dict(id=2, name="Clonal Expansion",      target_pts=10000,
         desc="T and B cells multiply — clonal expansion underway"),
    dict(id=3, name="Antibody Maturation",   target_pts=18000,
         desc="Affinity maturation: antibodies become ever more specific"),
    dict(id=4, name="Memory Response",       target_pts=999999,
         desc="Memory cells formed — immune memory is life-long"),
]

# ══════════════════════════════════════════════════════════════════════════════
#  BUMPER / SLING LAYOUT
# ══════════════════════════════════════════════════════════════════════════════

def make_bumpers():
    cx = LW // 2
    # Bumpers span full field height (y≈155 down to y≈680)
    # so ball MUST pass through them both going up AND coming back down
    return [
        # tier 1 y≈160-200: target guard
        dict(x=cx,     y=160, r=34, kind="tcell",      label="T Cell", pts=200,
             tip="T cells orchestrate the entire adaptive immune response!"),
        dict(x=cx-118, y=198, r=38, kind="mhc",        label="MHC-II", pts=150,
             tip="MHC-II presents peptides to helper T cells (CD4+)"),
        dict(x=cx+118, y=198, r=38, kind="mhc",        label="MHC-I",  pts=150,
             tip="MHC-I activates cytotoxic T cells (CD8+)"),
        # tier 2 y≈295-330: B cells + antibodies
        dict(x=WL+75,  y=310, r=38, kind="bcell",      label="B Cell", pts=200,
             tip="B cells → plasma cells secreting 2000 antibodies per second!"),
        dict(x=WR-75,  y=310, r=38, kind="bcell",      label="B Cell", pts=200,
             tip="Memory B cells persist for decades after infection!"),
        dict(x=cx-65,  y=280, r=27, kind="antibody",   label="Ab",     pts=100,
             tip="IgG antibodies neutralise & opsonise antigens!"),
        dict(x=cx+65,  y=280, r=27, kind="antibody",   label="Ab",     pts=100,
             tip="IgM is the first antibody in a primary response!"),
        # tier 3 y≈420-460: complement + cytokines
        dict(x=cx,     y=418, r=32, kind="complement", label="C3b",    pts=120,
             tip="C3b opsonises pathogens — marks them for destruction!"),
        dict(x=WL+62,  y=440, r=26, kind="cytokine",   label="IL-2",   pts=80,
             tip="IL-2 drives rapid T cell clonal expansion!"),
        dict(x=WR-62,  y=440, r=26, kind="cytokine",   label="TNF",    pts=80,
             tip="TNF-α activates macrophages & induces fever!"),
        # tier 4 y≈545-580: macrophage + flanking cytokines
        dict(x=cx,     y=550, r=38, kind="macrophage", label="Mφ",     pts=130,
             tip="Macrophages engulf up to 100 bacteria per cell!"),
        dict(x=cx-115, y=545, r=24, kind="cytokine",   label="IFN-γ",  pts=80,
             tip="IFN-γ increases MHC-II expression on APCs!"),
        dict(x=cx+115, y=545, r=24, kind="cytokine",   label="IL-6",   pts=80,
             tip="IL-6 drives B cell → plasma cell differentiation!"),
        # tier 5 y≈655-685: near-flipper row — last line of defence
        dict(x=WL+68,  y=660, r=26, kind="cytokine",   label="IL-1",   pts=80,
             tip="IL-1β is a key pro-inflammatory cytokine!"),
        dict(x=WR-68,  y=660, r=26, kind="cytokine",   label="IL-8",   pts=80,
             tip="IL-8 recruits neutrophils to infection sites!"),
        dict(x=cx,     y=668, r=28, kind="complement", label="MAC",    pts=120,
             tip="Membrane Attack Complex punches holes in bacterial membranes!"),
    ]

SLINGS = [
    dict(x=WL, y=742, w=44, h=88, nx= 1.0, ny=-0.55),
    dict(x=WR, y=742, w=44, h=88, nx=-1.0, ny=-0.55),
]

# ══════════════════════════════════════════════════════════════════════════════
#  DRAWING HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def aa_circle(surf, col, cx, cy, r, width=0, alpha=255):
    if r < 1: return
    s = pygame.Surface((r*2+4, r*2+4), pygame.SRCALPHA)
    pygame.draw.circle(s, (*col[:3], alpha), (r+2, r+2), r, width)
    surf.blit(s, (cx-r-2, cy-r-2))

def tc(surf, text, font, col, cx, cy):
    ts = font.render(text, True, col)
    surf.blit(ts, (cx - ts.get_width()//2, cy - ts.get_height()//2))

def draw_panel(surf, x, y, w, h, col=(15,25,55), border=(60,100,200), alpha=210, radius=10):
    s = pygame.Surface((w, h), pygame.SRCALPHA)
    pygame.draw.rect(s, (*col, alpha), (0,0,w,h), border_radius=radius)
    pygame.draw.rect(s, (*border, 200), (0,0,w,h), 2, border_radius=radius)
    surf.blit(s, (x, y))

# ══════════════════════════════════════════════════════════════════════════════
#  BIOLOGICAL SPRITES
# ══════════════════════════════════════════════════════════════════════════════

def draw_virus(surf, cx, cy, r, t=0.0, phase=0, flash=False):
    ph   = VIRUS_PHASES[phase]
    base = C["virus"]
    scol = ph["spike_col"]
    # outer glow — pulses faster at higher phase
    pulse = 1.0 + 0.14 * math.sin(t * (1 + phase * 0.5))
    gr = int((r + 22) * pulse)
    aa_circle(surf, base, cx, cy, gr,    alpha=25)
    aa_circle(surf, base, cx, cy, r+10,  alpha=50)
    # glycan shield ring
    if ph["shield"]:
        aa_circle(surf, (100,200,100), cx, cy, r+4, width=3, alpha=160)
    # body
    aa_circle(surf, (18, 6, 6), cx, cy, r, alpha=245)
    aa_circle(surf, base,       cx, cy, r, width=3, alpha=220)
    # spikes
    n = ph["spikes"]
    for i in range(n):
        a  = t + i * 2*math.pi / n
        bx = cx + math.cos(a) * (r - 3)
        by = cy + math.sin(a) * (r - 3)
        ex = cx + math.cos(a) * (r + r*0.52)
        ey = cy + math.sin(a) * (r + r*0.52)
        sc = (255,120,120) if flash else scol
        pygame.draw.line(surf, sc, (int(bx),int(by)), (int(ex),int(ey)), 3)
        aa_circle(surf, sc, int(ex), int(ey), 5+phase, alpha=230)
    # RNA strands
    s2 = pygame.Surface((r*2, r*2), pygame.SRCALPHA)
    pygame.draw.arc(s2, (160,50,50,170), (6, r//2, r*2-12, r-6), 0.3, 2.8, 2)
    pygame.draw.arc(s2, (160,50,50,130), (6, r//2+8, r*2-12, r-6),
                    math.pi+0.3, math.pi+2.8, 2)
    surf.blit(s2, (cx-r, cy-r))
    # mutation indicator dots
    for i in range(phase):
        mx = cx - 10 + i*10
        aa_circle(surf, scol, mx, cy+r+8, 4, alpha=220)
    lbl_col = (255,120,120) if not flash else (255,255,100)
    tc(surf, "VIRUS",       F12, lbl_col,       cx, cy-7)
    tc(surf, ph["name"],    F8,  (200,100,100),  cx, cy+8)

def draw_tcell(surf, cx, cy, r, flash=False):
    col  = C["tcell"]
    dark = (70, 30, 95)
    aa_circle(surf, col,  cx, cy, r+8,  alpha=40+(30 if flash else 0))
    aa_circle(surf, dark, cx, cy, r,    alpha=235)
    aa_circle(surf, col,  cx, cy, r,    width=3, alpha=205)
    for i in range(8):
        a  = i * math.pi/4
        bx = int(cx + math.cos(a)*r)
        by = int(cy + math.sin(a)*r)
        aa_circle(surf, col, bx, by, 6, alpha=230 if flash else 160)
        pygame.draw.line(surf, col,
            (int(cx+math.cos(a)*(r-3)), int(cy+math.sin(a)*(r-3))),
            (int(cx+math.cos(a)*(r+5)), int(cy+math.sin(a)*(r+5))), 2)
    aa_circle(surf, (110,60,145), cx, cy, r//2+2, alpha=190)
    tc(surf, "T Cell", F10, col if not flash else (255,255,255), cx, cy)

def draw_bcell(surf, cx, cy, r, flash=False):
    col  = C["bcell"]
    dark = (35, 75, 45)
    aa_circle(surf, col,  cx, cy, r+8,  alpha=40+(30 if flash else 0))
    aa_circle(surf, dark, cx, cy, r,    alpha=235)
    aa_circle(surf, col,  cx, cy, r,    width=3, alpha=205)
    for i in range(6):
        a  = i * math.pi/3
        rx = cx + math.cos(a)*r*0.70
        ry = cy + math.sin(a)*r*0.70
        ex = cx + math.cos(a)*(r+11)
        ey = cy + math.sin(a)*(r+11)
        pygame.draw.line(surf, col, (int(rx),int(ry)), (int(ex),int(ey)), 2)
        for da in (-0.45, 0.45):
            ax = int(ex + math.cos(a+da)*7)
            ay = int(ey + math.sin(a+da)*7)
            pygame.draw.line(surf, col, (int(ex),int(ey)), (ax,ay), 2)
    aa_circle(surf, (45,105,65), cx, cy, r//2+2, alpha=185)
    tc(surf, "B Cell", F10, col if not flash else (255,255,255), cx, cy)

def draw_mhc(surf, cx, cy, r, label="MHC", flash=False):
    col  = C["mhc"]
    dark = (18, 65, 105)
    aa_circle(surf, col,  cx, cy, r+7,  alpha=40+(30 if flash else 0))
    aa_circle(surf, dark, cx, cy, r,    alpha=235)
    aa_circle(surf, col,  cx, cy, r,    width=3, alpha=205)
    s2 = pygame.Surface((r*2+4, r*2+4), pygame.SRCALPHA)
    o  = r+2
    pygame.draw.arc(s2, (*col, 190), (o-r+r//4, o-r//2, r//2+r//4*3, r//2),
                    0.1, math.pi-0.1, 3)
    pygame.draw.arc(s2, (*col, 130), (o-r+r//4, o, r//2+r//4*3, r//2),
                    math.pi+0.1, 2*math.pi-0.1, 3)
    surf.blit(s2, (cx-r-2, cy-r-2))
    pygame.draw.line(surf, (255,230,90),
                     (int(cx-r//3), cy), (int(cx+r//3), cy), 3)
    tc(surf, label, F10, col if not flash else (255,255,255), cx, cy+r//3+5)

def draw_antibody(surf, cx, cy, r, flash=False):
    col  = C["antibody"]
    dark = (85, 60, 15)
    aa_circle(surf, col,  cx, cy, r+6,  alpha=40+(30 if flash else 0))
    aa_circle(surf, dark, cx, cy, r,    alpha=235)
    aa_circle(surf, col,  cx, cy, r,    width=3, alpha=205)
    s  = int(r * 0.52);  arm = int(r * 0.48)
    pygame.draw.line(surf, col, (cx, int(cy+s*0.25)), (cx, int(cy+s)), 4)
    pygame.draw.line(surf, col, (cx, int(cy-s*0.1)),
                     (int(cx-arm*0.85), int(cy-arm*0.85)), 4)
    pygame.draw.line(surf, col, (cx, int(cy-s*0.1)),
                     (int(cx+arm*0.85), int(cy-arm*0.85)), 4)
    aa_circle(surf, col, int(cx-arm*0.85), int(cy-arm*0.85), 5, alpha=230)
    aa_circle(surf, col, int(cx+arm*0.85), int(cy-arm*0.85), 5, alpha=230)
    tc(surf, "Ab", F10, col if not flash else (255,255,255), cx, int(cy+s*0.65))

def draw_complement(surf, cx, cy, r, flash=False):
    col  = C["complement"]
    dark = (88, 35, 35)
    aa_circle(surf, col,  cx, cy, r+6,  alpha=40+(30 if flash else 0))
    aa_circle(surf, dark, cx, cy, r,    alpha=235)
    aa_circle(surf, col,  cx, cy, r,    width=3, alpha=205)
    for i in range(5):
        a  = i * 2*math.pi/5 - math.pi/2
        ix = int(cx + math.cos(a)*r*0.55)
        iy = int(cy + math.sin(a)*r*0.55)
        ex = int(cx + math.cos(a)*(r+9))
        ey = int(cy + math.sin(a)*(r+9))
        pygame.draw.line(surf, col, (ix,iy), (ex,ey), 2)
        aa_circle(surf, col, ex, ey, 4, alpha=210)
    pygame.draw.line(surf, (255,180,180),
                     (int(cx-r//4), int(cy+2)), (int(cx+r//4), int(cy+2)), 2)
    tc(surf, "C3b", F10, col if not flash else (255,255,255), cx, cy)

def draw_cytokine(surf, cx, cy, r, label="IL-2", flash=False):
    col  = C["cytokine"]
    dark = (18, 65, 78)
    aa_circle(surf, col,  cx, cy, r+5,  alpha=40+(30 if flash else 0))
    aa_circle(surf, dark, cx, cy, r,    alpha=235)
    aa_circle(surf, col,  cx, cy, r,    width=3, alpha=205)
    for dy_off in (-5, 0, 5):
        pts = [(int(cx-r*0.65+i*r*1.3/8),
                int(cy+dy_off+math.sin(i*1.3)*4)) for i in range(9)]
        if len(pts)>1:
            pygame.draw.lines(surf, col, False, pts, 2)
    tc(surf, label, F8, col if not flash else (255,255,255), cx, cy+r//2+4)

def draw_macrophage(surf, cx, cy, r, t=0.0, flash=False):
    col  = C["macrophage"]
    dark = (75, 50, 8)
    n    = 36
    pts  = []
    for i in range(n):
        a  = i * 2*math.pi / n
        rr = r + 9*math.sin(3*a+t*2.1) + 5*math.cos(5*a+t*1.3)
        pts.append((int(cx+math.cos(a)*rr), int(cy+math.sin(a)*rr)))
    if len(pts) >= 3:
        s2  = pygame.Surface((r*2+40, r*2+40), pygame.SRCALPHA)
        off = r+20
        lp  = [(p[0]-cx+off, p[1]-cy+off) for p in pts]
        pygame.draw.polygon(s2, (*dark, 225), lp)
        pygame.draw.polygon(s2, (*col,  185+(40 if flash else 0)), lp, 3)
        surf.blit(s2, (cx-off, cy-off))
    for i in range(5):
        a  = i*2*math.pi/5 + t*0.8
        aa_circle(surf, col, int(cx+math.cos(a)*(r+16)),
                             int(cy+math.sin(a)*(r+16)), 6, alpha=165)
    aa_circle(surf, (125,85,18), cx, cy, r//2+3, alpha=185)
    tc(surf, "Mφ", F10, col if not flash else (255,255,255), cx, cy)

def draw_antigen(surf, cx, cy, r):
    col  = C["antigen"]
    dark = (28, 78, 78)
    aa_circle(surf, col,  cx, cy, r+5,  alpha=65)
    aa_circle(surf, dark, cx, cy, r,    alpha=245)
    aa_circle(surf, col,  cx, cy, r,    width=2, alpha=210)
    for ao in (0.0, 2.09, 4.19):
        sx = int(cx + math.cos(ao)*r*0.28)
        sy = int(cy + math.sin(ao)*r*0.28)
        ex = int(cx + math.cos(ao)*r*0.82)
        ey = int(cy + math.sin(ao)*r*0.82)
        pygame.draw.line(surf, (200,240,240), (sx,sy), (ex,ey), 2)
        for da in (-0.55, 0.55):
            pygame.draw.line(surf, (200,240,240), (ex,ey),
                             (int(ex+math.cos(ao+da)*5),
                              int(ey+math.sin(ao+da)*5)), 2)
    tc(surf, "Ag", F10, (255,255,255), cx, cy)

# ══════════════════════════════════════════════════════════════════════════════
#  PARTICLE SYSTEM
# ══════════════════════════════════════════════════════════════════════════════

class Particle:
    __slots__ = ("x","y","vx","vy","r","col","life","maxlife","kind","text")
    def __init__(self, x, y, vx, vy, r, col, life, kind="dot", text=""):
        self.x=float(x); self.y=float(y)
        self.vx=vx; self.vy=vy
        self.r=r; self.col=col
        self.life=life; self.maxlife=life
        self.kind=kind; self.text=text

    def update(self):
        self.x  += self.vx;  self.y  += self.vy
        self.vy += 0.07
        self.life -= 1
        return self.life > 0

    def draw(self, surf):
        alpha = int(255 * self.life / self.maxlife)
        if self.kind == "text":
            ts = F14.render(self.text, True, self.col)
            ts.set_alpha(alpha)
            surf.blit(ts, (int(self.x)-ts.get_width()//2,
                           int(self.y)-ts.get_height()//2))
        elif self.kind == "ring":
            aa_circle(surf, self.col, int(self.x), int(self.y),
                      self.r + (self.maxlife-self.life)*2, width=2, alpha=alpha)
        else:
            aa_circle(surf, self.col, int(self.x), int(self.y),
                      self.r, alpha=alpha)

def burst(particles, x, y, col, n=12, r=4):
    for _ in range(n):
        a  = random.uniform(0, 2*math.pi)
        sp = random.uniform(1.5, 5)
        particles.append(Particle(x, y, math.cos(a)*sp, math.sin(a)*sp,
                                  r, col, random.randint(20,40)))

def score_pop(particles, x, y, text, col):
    particles.append(Particle(x, y-5, 0, -2.5, 0, col, 65, kind="text", text=text))

def ring_flash(particles, x, y, col):
    particles.append(Particle(x, y, 0, 0, 5, col, 22, kind="ring"))

# ══════════════════════════════════════════════════════════════════════════════
#  TITLE SCREEN
# ══════════════════════════════════════════════════════════════════════════════

def run_title():
    t    = 0.0
    done = False
    # animated floating viruses
    vps  = [{"x": random.uniform(50, LW-50),
              "y": random.uniform(50, LH-50),
              "vx": random.uniform(-0.6, 0.6),
              "vy": random.uniform(-0.6, 0.6),
              "r":  random.randint(18, 35),
              "ph": random.randint(0,3),
              "t":  random.uniform(0, 6)} for _ in range(8)]
    surf = pygame.display.get_surface()
    while not done:
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                pygame.quit(); sys.exit()
            if ev.type == pygame.KEYDOWN:
                if ev.key == pygame.K_ESCAPE:
                    pygame.quit(); sys.exit()
                done = True
            if ev.type == pygame.MOUSEBUTTONDOWN:
                done = True
        surf.fill(BG)
        # grid
        for gy2 in range(0, LH, 55):
            for gx2 in range(0, LW, 55):
                pygame.draw.circle(surf, (16,28,55), (gx2,gy2), 1)
        # floating viruses
        for vp in vps:
            vp["x"] += vp["vx"];  vp["y"] += vp["vy"];  vp["t"] += 0.03
            if vp["x"] < vp["r"]:  vp["vx"] =  abs(vp["vx"])
            if vp["x"] > LW-vp["r"]: vp["vx"] = -abs(vp["vx"])
            if vp["y"] < vp["r"]:  vp["vy"] =  abs(vp["vy"])
            if vp["y"] > LH-vp["r"]: vp["vy"] = -abs(vp["vy"])
            draw_virus(surf, int(vp["x"]), int(vp["y"]), vp["r"],
                       t=vp["t"], phase=vp["ph"])
        # title panel
        draw_panel(surf, LW//2-220, LH//2-160, 440, 320)
        tc(surf, "ANTIGEN PINBALL", F44, C["antigen"],  LW//2, LH//2-120)
        tc(surf, "Immune System Arcade Simulator",
           F14, TEXT, LW//2, LH//2-80)
        # blinking press key
        if int(t * 2) % 2 == 0:
            tc(surf, "PRESS ANY KEY TO START", F18, (150,220,255), LW//2, LH//2-30)
        # controls summary
        tc(surf, "Z/←  left flipper     X/→  right flipper", F12, DIM, LW//2, LH//2+20)
        tc(surf, "SPACE = charge & fire plunger",             F12, DIM, LW//2, LH//2+42)
        tc(surf, "F = fullscreen    ESC = quit",              F10, DIM, LW//2, LH//2+64)
        # difficulty hint
        tc(surf, "Hit immune cells to build multiplier — reach the VIRUS!", F12, (100,160,200), LW//2, LH//2+100)
        # cell legend
        legend = [("MHC","mhc"),("T Cell","tcell"),("B Cell","bcell"),
                  ("Ab","antibody"),("C3b","complement"),("Cytokine","cytokine"),("Mφ","macrophage")]
        lx0 = LW//2 - len(legend)*36//2
        for li, (nm, kd) in enumerate(legend):
            lx2 = lx0 + li*38
            aa_circle(surf, C[kd], lx2+8, LH//2+138, 8, alpha=220)
            ts = F8.render(nm, True, C[kd])
            surf.blit(ts, (lx2+8-ts.get_width()//2, LH//2+150))
        pygame.display.flip()
        t += 0.016
        clock.tick(60)

# ══════════════════════════════════════════════════════════════════════════════
#  GAME STATE
# ══════════════════════════════════════════════════════════════════════════════

class Game:
    def __init__(self):
        self.reset()

    def reset(self):
        self.score      = 0
        self.lives      = 3
        self.mult       = 1.0
        self.ball       = None
        self.pull       = 0.0
        self.pulling    = False
        self.game_over  = False
        self.bumpers    = make_bumpers()
        self.bflash     = {}        # index → frames
        self.particles  = []
        self.tip        = ""
        self.tip_t      = 0
        self.tpulse     = 0.0
        self.mac_t      = 0.0
        self.fl         = F_REST
        self.fr         = F_REST
        # chain system
        self.chain      = []        # list of kinds hit recently
        self.chain_t    = 0         # frames since last bumper hit
        self.combo_msg  = ""
        self.combo_t    = 0
        # boss phase
        self.virus_phase    = 0
        self.virus_flash_t  = 0
        self.bindings       = 0     # times antigen bound virus
        # progression
        self.stage_idx  = 0
        self.stage_msg  = ""
        self.stage_t    = 0
        # lab note
        self.note       = None      # None or dict
        self.note_t     = 0
        self.last_kind  = None

    def spawn(self):
        # Ball spawns at right side of field, just above right flipper pivot
        return {"x": float(WR - BALL_R - 5),
                "y": float(FY - 32),
                "vx": 0.0, "vy": 0.0}

    def launch(self):
        if not self.ball and not self.game_over:
            self.ball    = self.spawn()
            self.pulling = True
            self.pull    = 0.0

    def _check_chain(self, kind):
        """Add kind to chain, decay timer, check for combos."""
        self.chain.append(kind)
        self.chain_t = 280   # ~4.5 seconds at 60fps
        # keep chain to last 5 hits
        if len(self.chain) > 5:
            self.chain = self.chain[-5:]
        # check all defined combos
        for name, seq, pts, msg in CHAINS:
            n = len(seq)
            if self.chain[-n:] == seq:
                self.chain = []
                total = int(pts * self.mult)
                self.score += total
                self.combo_msg = msg.replace(str(pts), str(total))
                self.combo_t   = 200
                burst(self.particles, LW//2, LH//2, (255,230,80), n=22, r=5)
                play("combo")
                break

    def _check_stage(self):
        if self.stage_idx >= len(STAGES)-1:
            return
        st = STAGES[self.stage_idx]
        if self.score >= st["target_pts"]:
            self.stage_idx  = min(self.stage_idx+1, len(STAGES)-1)
            ns = STAGES[self.stage_idx]
            self.stage_msg  = f"▶ STAGE {self.stage_idx}: {ns['name']}"
            self.stage_t    = 240
            # possibly advance virus phase
            if self.stage_idx in (1, 2, 3):
                self.virus_phase = min(self.stage_idx, 3)
                burst(self.particles, TARGET_X, TARGET_Y,
                      VIRUS_PHASES[self.virus_phase]["spike_col"], n=18, r=6)
                self.tip   = VIRUS_PHASES[self.virus_phase]["desc"]
                self.tip_t = 220

    def update(self, keys):
        if self.game_over:
            return
        self.tpulse += 0.05
        self.mac_t  += 0.03
        if self.virus_flash_t > 0:
            self.virus_flash_t -= 1

        # flippers
        tl = F_ACTIVE if (keys[pygame.K_z]  or keys[pygame.K_LEFT])  else F_REST
        tr = F_ACTIVE if (keys[pygame.K_x]  or keys[pygame.K_RIGHT]) else F_REST
        prev_fl, prev_fr = self.fl, self.fr
        self.fl += (tl - self.fl) * F_SPEED * 2.8
        self.fr += (tr - self.fr) * F_SPEED * 2.8
        if abs(self.fl - prev_fl) > 0.04 or abs(self.fr - prev_fr) > 0.04:
            play("flipper")

        # timers
        for attr in ("tip_t","combo_t","stage_t","note_t"):
            v = getattr(self, attr)
            if v > 0: setattr(self, attr, v-1)
        if self.chain_t > 0:
            self.chain_t -= 1
        else:
            self.chain = []

        # particles
        self.particles = [p for p in self.particles if p.update()]

        if not self.ball:
            return

        b = self.ball

        if self.pulling:
            if keys[pygame.K_SPACE]:
                self.pull = min(self.pull + 0.028, 1.0)
            else:
                # Fire: strong upward + leftward so ball arcs into the field
                spd = 11 + self.pull * 10   # 11-21 range
                b["vx"] = -3.0 - self.pull * 2   # always enters left
                b["vy"] = -spd
                self.pulling = False
                play("launch")
            return

        # physics
        b["vy"] += GRAVITY
        spd = math.hypot(b["vx"], b["vy"])
        if spd > MAX_SPD:
            b["vx"] *= MAX_SPD/spd;  b["vy"] *= MAX_SPD/spd
        b["x"] += b["vx"];  b["y"] += b["vy"]

        # walls
        if b["x"] - BALL_R < WL:
            b["x"] = WL + BALL_R;  b["vx"] = abs(b["vx"])*0.9 + 0.4
        if b["x"] + BALL_R > WR:
            b["x"] = WR - BALL_R;  b["vx"] = -abs(b["vx"])*0.9
        if b["y"] - BALL_R < 4:
            b["y"] = 4 + BALL_R;   b["vy"] = abs(b["vy"])*0.85

        # gutter slopes
        self._slope(b, WL, LH-160, FLX-FL_LEN-8, FY-8, "left")
        self._slope(b, WR, LH-160, FRX+FL_LEN+8, FY-8, "right")
        # slingshots
        for sl in SLINGS:
            self._sling(b, sl)
        # flippers
        self._flipper(b, FLX,  self.fl,  +1)
        self._flipper(b, FRX, -self.fr,  -1)

        # guide pins
        for (gx, gy, gr) in GUIDE_PINS:
            dx = b["x"]-gx;  dy = b["y"]-gy
            d  = math.hypot(dx, dy)
            if d < gr + BALL_R and d > 0:
                nx, ny = dx/d, dy/d
                dot = b["vx"]*nx + b["vy"]*ny
                if dot < 0:
                    b["vx"] -= 2*dot*nx*0.9
                    b["vy"] -= 2*dot*ny*0.9
                b["x"] += nx*(gr+BALL_R-d+1)
                b["y"] += ny*(gr+BALL_R-d+1)
                burst(self.particles, int(gx), int(gy), C["pin"], n=4, r=3)
                play("pin")

        # bumpers
        for i, bm in enumerate(self.bumpers):
            dx = b["x"]-bm["x"];  dy = b["y"]-bm["y"]
            d  = math.hypot(dx, dy)
            if d < bm["r"] + BALL_R and d > 0:
                pts = int(bm["pts"] * self.mult)
                self.score += pts
                k = bm["kind"]
                if k == "mhc":    self.mult = min(self.mult+0.5, 6.0)
                elif k == "tcell":self.mult = min(self.mult+1.0, 6.0)
                self.bflash[i]  = 30
                self.tip        = bm["tip"]
                self.tip_t      = 200
                self.last_kind  = k
                # lab note (only show first time per kind per life)
                if k in LAB_NOTES and self.note is None:
                    self.note   = LAB_NOTES[k]
                    self.note_t = 300
                # chain
                self._check_chain(k)
                self._check_stage()
                # particles
                score_pop(self.particles, bm["x"], bm["y"]-bm["r"]-6,
                          f"+{pts}", C[k])
                burst(self.particles, int(bm["x"]), int(bm["y"]),
                      C[k], n=10, r=4)
                ring_flash(self.particles, int(bm["x"]), int(bm["y"]), C[k])
                play(k)
                # bounce
                nx, ny = dx/d, dy/d
                dot = b["vx"]*nx + b["vy"]*ny
                b["vx"] -= 2*dot*nx;  b["vy"] -= 2*dot*ny
                bst = max(math.hypot(b["vx"],b["vy"]),7)+2.5
                sp2 = math.hypot(b["vx"],b["vy"])
                if sp2>0:
                    b["vx"] = b["vx"]/sp2*min(bst,MAX_SPD)
                    b["vy"] = b["vy"]/sp2*min(bst,MAX_SPD)
                b["x"] += nx*(bm["r"]+BALL_R-d+1)
                b["y"] += ny*(bm["r"]+BALL_R-d+1)

        # virus target — apply shield resistance
        if math.hypot(b["x"]-TARGET_X, b["y"]-TARGET_Y) < TARGET_R + BALL_R:
            ph    = VIRUS_PHASES[self.virus_phase]
            if ph["shield"] and random.random() < 0.35:
                # shield repels
                dx  = b["x"] - TARGET_X;  dy = b["y"] - TARGET_Y
                d   = math.hypot(dx, dy)
                if d > 0:
                    nx, ny = dx/d, dy/d
                    b["vx"] = nx*8;  b["vy"] = ny*8
                self.tip   = "Glycan shield deflected the antigen!"
                self.tip_t = 120
            else:
                self.bindings += 1
                pts = int((2000 + self.bindings*500) * self.mult)
                self.score += pts
                self.virus_flash_t = 40
                score_pop(self.particles, TARGET_X, TARGET_Y-TARGET_R-14,
                          f"BOUND! +{pts}", C["virus"])
                burst(self.particles, TARGET_X, TARGET_Y, C["virus"], n=20, r=6)
                ring_flash(self.particles, TARGET_X, TARGET_Y, (255,200,100))
                self.tip   = f"Antigen-epitope binding! +{pts} pts — immune victory!"
                self.tip_t = 280
                self.mult  = 1.0
                self.ball  = None
                self._check_stage()
                play("win")
                return

        # lost
        if b["y"] > LH + 35:
            self.lives -= 1
            self.mult   = 1.0
            self.chain  = []
            self.ball   = None
            play("lose")
            if self.lives <= 0:
                self.game_over = True
                self.tip   = f"Virus escaped! GAME OVER — Score: {self.score}"
                self.tip_t = 9999
            else:
                self.tip   = f"Antigen lost! {self.lives} {'life' if self.lives==1 else 'lives'} remaining"
                self.tip_t = 160

    # ── physics helpers ────────────────────────────────────────────────────────
    def _slope(self, b, x1, y1, x2, y2, side):
        dx, dy = x2-x1, y2-y1
        L = math.hypot(dx, dy)
        if L==0: return
        nx, ny = -dy/L, dx/L
        nx = abs(nx) if side=="left" else -abs(nx)
        t = max(0., min(1., ((b["x"]-x1)*dx+(b["y"]-y1)*dy)/(L*L)))
        cx2, cy2 = x1+t*dx, y1+t*dy
        d = math.hypot(b["x"]-cx2, b["y"]-cy2)
        if d < BALL_R:
            b["x"] = cx2+nx*BALL_R
            b["y"] = cy2+(abs(ny)*BALL_R*(-1 if ny<0 else 1))
            dot = b["vx"]*nx+b["vy"]*ny
            if dot<0:
                b["vx"] -= 2*dot*nx*0.85;  b["vy"] -= 2*dot*ny*0.85

    def _sling(self, b, sl):
        sx = WL if sl["nx"]>0 else WR-sl["w"]
        sy, sw, sh = sl["y"], sl["w"], sl["h"]
        if sx < b["x"]-BALL_R < sx+sw and sy < b["y"] < sy+sh:
            nx, ny = sl["nx"], sl["ny"]
            m = math.hypot(nx,ny); nx/=m; ny/=m
            dot = b["vx"]*nx+b["vy"]*ny
            if dot<0:
                b["vx"] -= 2*dot*nx*1.15
                b["vy"] -= 2*dot*ny*1.15-1.2
                b["vy"]  = min(b["vy"], -4)

    def _flipper(self, b, px, ang, side):
        tx = px + math.cos(ang)*FL_LEN*side
        ty = FY + math.sin(ang)*FL_LEN
        dx, dy = tx-px, ty-FY
        L = math.hypot(dx,dy)
        if L==0: return
        t   = max(0., min(1., ((b["x"]-px)*dx+(b["y"]-FY)*dy)/(L*L)))
        cx2 = px+t*dx;  cy2 = FY+t*dy
        d   = math.hypot(b["x"]-cx2, b["y"]-cy2)
        if d < BALL_R+FT//2 and b["y"] < FY+20:
            nx = -(dy/L);  ny = (dx/L)
            if ny>0: nx,ny=-nx,-ny
            dot  = b["vx"]*nx+b["vy"]*ny
            spd2 = math.hypot(b["vx"],b["vy"])
            if dot<0:
                b["vx"] -= 2*dot*nx;  b["vy"] -= 2*dot*ny
            if b["vy"]>-6:
                b["vy"] = -max(spd2, 9)
            b["x"] = cx2+nx*(BALL_R+FT//2+1)
            b["y"] = cy2+ny*(BALL_R+FT//2+1)


# ══════════════════════════════════════════════════════════════════════════════
#  DRAW
# ══════════════════════════════════════════════════════════════════════════════

DRAW_FNS = {
    "mhc":        lambda surf, bm, f: draw_mhc(surf, int(bm["x"]), int(bm["y"]), bm["r"], bm["label"], f),
    "tcell":      lambda surf, bm, f: draw_tcell(surf, int(bm["x"]), int(bm["y"]), bm["r"], f),
    "bcell":      lambda surf, bm, f: draw_bcell(surf, int(bm["x"]), int(bm["y"]), bm["r"], f),
    "antibody":   lambda surf, bm, f: draw_antibody(surf, int(bm["x"]), int(bm["y"]), bm["r"], f),
    "complement": lambda surf, bm, f: draw_complement(surf, int(bm["x"]), int(bm["y"]), bm["r"], f),
    "cytokine":   lambda surf, bm, f: draw_cytokine(surf, int(bm["x"]), int(bm["y"]), bm["r"], bm["label"], f),
    "macrophage": lambda surf, bm, f: draw_macrophage(surf, int(bm["x"]), int(bm["y"]), bm["r"], 0, f),
}

def draw(g, surf):
    surf.fill(BG)
    # grid dots
    for gy2 in range(0, LH, 58):
        for gx2 in range(WL, WR, 58):
            pygame.draw.circle(surf, (16,28,55), (gx2,gy2), 1)

    # walls
    pygame.draw.line(surf, WALL_COL, (WL,0),  (WL, LH-160), 4)
    pygame.draw.line(surf, WALL_COL, (WR,0),  (WR, LH-160), 4)
    pygame.draw.line(surf, WALL_COL, (WL,0),  (WR,0),        4)
    pygame.draw.line(surf, WALL_COL, (WL,LH-160), (FLX-FL_LEN-8, FY-8), 4)
    pygame.draw.line(surf, WALL_COL, (WR,LH-160), (FRX+FL_LEN+8, FY-8), 4)

    # plunger charge indicator (shown as a vertical bar on the right wall)
    if g.ball and g.pulling:
        bh  = int(g.pull * 120)
        bar_x = WR + 4
        pygame.draw.rect(surf, (60,20,20), (bar_x, FY-130, 18, 120), border_radius=4)
        if bh > 0:
            col_pct = g.pull
            bar_col = (int(80+175*col_pct), int(200-150*col_pct), 60)
            pygame.draw.rect(surf, bar_col,
                             (bar_x, FY-10-bh, 18, bh), border_radius=4)
        tc(surf, "PWR", F10, (220,100,100), bar_x+9, FY-138)

    # slingshots
    for sl in SLINGS:
        sp = ([(WL, sl["y"]), (WL+sl["w"], sl["y"]), (WL, sl["y"]+sl["h"])]
              if sl["nx"]>0 else
              [(WR, sl["y"]), (WR-sl["w"], sl["y"]), (WR, sl["y"]+sl["h"])])
        s2 = pygame.Surface((LW,LH), pygame.SRCALPHA)
        pygame.draw.polygon(s2, (38,75,165,155), sp)
        pygame.draw.polygon(s2, (*WALL_COL,210), sp, 2)
        surf.blit(s2, (0,0))

    # virus target
    draw_virus(surf, TARGET_X, TARGET_Y, TARGET_R,
               t=g.tpulse, phase=g.virus_phase,
               flash=(g.virus_flash_t>0))

    # bumpers
    for i, bm in enumerate(g.bumpers):
        DRAW_FNS[bm["kind"]](surf, bm, g.bflash.get(i,0)>0)

    # flippers
    for pivot_x, ang, side in [(FLX, g.fl, +1), (FRX, -g.fr, -1)]:
        tx = int(pivot_x + math.cos(ang)*FL_LEN*side)
        ty = int(FY + math.sin(ang)*FL_LEN)
        pygame.draw.line(surf, C["mhc"],        (pivot_x,FY), (tx,ty), FT+5)
        pygame.draw.line(surf, (170,230,255),   (pivot_x,FY), (tx,ty), FT-3)
        pygame.draw.circle(surf, C["mhc"],      (pivot_x,FY), FT//2+4)
        pygame.draw.circle(surf, C["mhc"],      (tx,ty),       FT//2+2)

    # guide pins
    for (gx,gy,gr) in GUIDE_PINS:
        aa_circle(surf, C["pin"], gx, gy, gr,   alpha=210)
        aa_circle(surf, (150,190,255), gx, gy, gr, width=2, alpha=180)

    # antigen ball
    if g.ball:
        draw_antigen(surf, int(g.ball["x"]), int(g.ball["y"]), BALL_R)

    # all particles
    for p in g.particles:
        p.draw(surf)

    # ── HUD bar ──────────────────────────────────────────────────────────────
    pygame.draw.rect(surf, HUD_BG, (0, LH-55, LW+CHUTE_W, 55))
    pygame.draw.line(surf, WALL_COL, (0,LH-55), (LW+CHUTE_W,LH-55), 1)
    tc(surf, f"SCORE  {g.score}", F18, TEXT,        LW//2-145, LH-30)
    tc(surf, "♥"*g.lives,         F18, (230,80,80), LW//2,     LH-30)
    mc = (255,200,80) if g.mult<3 else (255,110,50) if g.mult<5 else (255,60,60)
    tc(surf, f"x{g.mult:.1f}",    F18, mc,           LW//2+145, LH-30)

    # ── stage banner ─────────────────────────────────────────────────────────
    if g.stage_t > 0:
        alpha = min(255, g.stage_t*4)
        st    = STAGES[g.stage_idx]
        draw_panel(surf, LW//2-200, 8, 400, 42, alpha=int(alpha*0.8))
        ts = F14.render(g.stage_msg, True, (255,220,80))
        ts.set_alpha(alpha)
        surf.blit(ts, (LW//2-ts.get_width()//2, 14))
        ts2 = F10.render(st["desc"], True, (180,220,255))
        ts2.set_alpha(alpha)
        surf.blit(ts2, (LW//2-ts2.get_width()//2, 32))

    # ── tip bar ───────────────────────────────────────────────────────────────
    if g.tip_t > 0:
        alpha = min(255, g.tip_t*5)
        words = g.tip.split()
        lines, cur = [], []
        for w in words:
            if F12.size(" ".join(cur+[w]))[0] > LW-35:
                lines.append(" ".join(cur)); cur=[w]
            else: cur.append(w)
        if cur: lines.append(" ".join(cur))
        by2 = LH-58-len(lines)*22
        for li, ln in enumerate(lines):
            ts = F12.render(ln, True, (180,220,255))
            ts.set_alpha(alpha)
            surf.blit(ts, (LW//2-ts.get_width()//2, by2+li*22))

    # ── combo banner ─────────────────────────────────────────────────────────
    if g.combo_t > 0:
        alpha  = min(255, g.combo_t*4)
        scale  = 1.0 + 0.3*(g.combo_t/200)
        draw_panel(surf, LW//2-230, LH//2-38, 460, 76,
                   col=(30,15,5), border=(255,180,50),
                   alpha=int(alpha*0.85))
        tc(surf, "⚡ IMMUNE CASCADE ⚡", F18, (255,200,50), LW//2, LH//2-20)
        ts = F12.render(g.combo_msg, True, (255,240,180))
        ts.set_alpha(alpha)
        surf.blit(ts, (LW//2-ts.get_width()//2, LH//2+4))

    # ── chain indicator ───────────────────────────────────────────────────────
    if g.chain and g.chain_t > 0:
        cx0 = WL + 5
        for ci, ck in enumerate(g.chain[-5:]):
            aa_circle(surf, C[ck], cx0+ci*18, LH-68, 7, alpha=200)
        ts = F8.render("chain", True, DIM)
        surf.blit(ts, (cx0, LH-80))

    # ── lab note panel ────────────────────────────────────────────────────────
    if g.note and g.note_t > 0:
        alpha = min(220, g.note_t*3)
        note  = g.note
        pw, ph2 = 360, 130
        px2 = LW//2 - pw//2
        py2 = LH//2 + 50
        draw_panel(surf, px2, py2, pw, ph2,
                   col=(5,20,45), border=(79,195,247), alpha=alpha)
        ts = F14.render(f"📋 {note['title']}", True, C["mhc"])
        ts.set_alpha(alpha)
        surf.blit(ts, (px2+12, py2+8))
        # wrap body text
        body  = note["body"]
        words = body.split()
        lines2, cur2 = [], []
        for w in words:
            if F10.size(" ".join(cur2+[w]))[0] > pw-24:
                lines2.append(" ".join(cur2)); cur2=[w]
            else: cur2.append(w)
        if cur2: lines2.append(" ".join(cur2))
        for li2, ln2 in enumerate(lines2[:5]):
            ts2 = F10.render(ln2, True, (180,210,240))
            ts2.set_alpha(alpha)
            surf.blit(ts2, (px2+12, py2+28+li2*18))

    # ── idle prompt ───────────────────────────────────────────────────────────
    if not g.ball and not g.game_over:
        draw_panel(surf, 40, LH//2-40, LW-80, 80)
        tc(surf, "Hold SPACE → charge plunger → release to fire",
           F12, (120,200,255), LW//2, LH//2-18)
        tc(surf, "Z/←  left flipper          X/→  right flipper",
           F12, (90,160,220),  LW//2, LH//2+6)
        tc(surf, "F = fullscreen     ESC = quit",
           F10, DIM,            LW//2, LH//2+26)

    # ── game over overlay ─────────────────────────────────────────────────────
    if g.game_over:
        ov = pygame.Surface((LW+CHUTE_W, LH), pygame.SRCALPHA)
        ov.fill((0,0,0,168))
        surf.blit(ov, (0,0))
        tc(surf, "GAME OVER",             F36, C["virus"], LW//2, LH//2-80)
        tc(surf, f"Score: {g.score}",     F24, TEXT,       LW//2, LH//2-22)
        st = STAGES[g.stage_idx]
        tc(surf, f"Stage: {st['name']}",  F18, C["mhc"],   LW//2, LH//2+22)
        tc(surf, f"Virus bindings: {g.bindings}", F14, C["antigen"], LW//2, LH//2+52)
        tc(surf, "Press  R  to restart",  F18, DIM,        LW//2, LH//2+88)

    pygame.display.flip()


# ══════════════════════════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════════════════════════

def main():
    run_title()
    g          = Game()
    fullscreen = True
    while True:
        keys = pygame.key.get_pressed()
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                pygame.quit(); sys.exit()
            if ev.type == pygame.KEYDOWN:
                if ev.key == pygame.K_ESCAPE:
                    pygame.quit(); sys.exit()
                if ev.key == pygame.K_f:
                    fullscreen = not fullscreen
                    pygame.display.set_mode(
                        (NATIVE_W, NATIVE_H) if fullscreen else (int(LW*1.1), LH),
                        (pygame.FULLSCREEN | pygame.SCALED) if fullscreen else pygame.SCALED)
                if ev.key == pygame.K_SPACE and not g.ball and not g.game_over:
                    g.launch()
                if ev.key == pygame.K_r and g.game_over:
                    g = Game()

        g.update(keys)
        draw(g, pygame.display.get_surface())
        clock.tick(60)

if __name__ == "__main__":
    main()