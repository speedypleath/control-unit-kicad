"""Haptic Console - Control Unit (M6) circuit diagram via SchemDraw (v10, final)."""
from pathlib import Path

import cairosvg
import schemdraw
import schemdraw.elements as elm

DOCS = Path(__file__).resolve().parent.parent / "docs"
OUT = str(DOCS / "control-unit-circuit.svg")

with schemdraw.Drawing(file=OUT, show=False) as d:
    d.config(fontsize=9, lw=1.6, margin=3, bgcolor='white')

    # ---------------- Teensy 4.1 (grouped pins) ----------------
    u1 = elm.Ic(pins=[
        elm.IcPin(name='D0–D3', side='left', slot='1/5', pin='2-5'),
        elm.IcPin(name='D4–D7', side='left', slot='2/5', pin='6-9'),
        elm.IcPin(name='D10–D14', side='left', slot='3/5', pin='10-14'),
        elm.IcPin(name='D20–D27', side='left', slot='4/5', pin='20-27'),
        elm.IcPin(name='D28–D35', side='left', slot='5/5', pin='28-35'),
        elm.IcPin(name='LED PWM', side='right', slot='1/7', pin='8/9/36-38'),
        elm.IcPin(name='IRQ1–IRQ6', side='right', slot='2/7', pin='15-17/39-41'),
        elm.IcPin(name='SCL', side='right', slot='3/7', pin='19'),
        elm.IcPin(name='SDA', side='right', slot='4/7', pin='18'),
        elm.IcPin(name='3V3', side='right', slot='5/7', pin=''),
        elm.IcPin(name='5V', side='right', slot='6/7', pin=''),
        elm.IcPin(name='GND', side='right', slot='7/7', pin=''),
    ], edgepadW=1.8, edgepadH=1.1, leadlen=2.4, pinspacing=0.9)
    u1.label('Teensy 4.1\nU1', loc='bottom', ofst=(0, -0.3), fontsize=11)

    # ============ LEFT: connector blocks (net ranges live on Teensy pins) ============
    blocks = [
        ('D0–D3',   'J1 — joystick 1\nJST-XH 5, U/D/L/R + GND', 4.6),
        ('D4–D7',   'J2 — joystick 2\nJST-XH 5, U/D/L/R + GND', 2.3),
        ('D10–D14', 'CB1–CB5 — command buttons\nJST-XH 4 ×5', 0.0),
        ('D20–D27', 'B1–B8 — action buttons\nJST-XH 2 ×8', -2.3),
        ('D28–D35', 'NP — 4×4 keypad\nJST-XH 8', -4.6),
    ]
    BX = -7.8
    for grp, text, by in blocks:
        blk = elm.Ic(pins=[elm.IcPin(name='IO', side='right', slot='1/1', pin='1')],
                     edgepadW=3.4, edgepadH=0.5).at((BX, by))
        blk.label(text, loc='center', ofst=(-0.55, 0), fontsize=7.5)
        d += blk
        src = u1.absanchors[grp]
        dst = blk.absanchors['IO']
        d += elm.Wire().at(src).to((dst[0], src[1]))
        d += elm.Wire().at((dst[0], src[1])).to(dst).dot()

    # ============ RIGHT: LED chain (representative, single annotation) ============
    base = u1.absanchors['LED PWM']
    d += elm.LED().at(base).right()
    d += elm.Resistor().right()
    d += elm.Line().right().length(0.6)
    gnd = elm.Ground().down()
    d += gnd
    gnd_top = gnd.absanchors['start']
    d += elm.Label().at((gnd_top[0] + 0.35, gnd_top[1] - 0.55)).label('GND', fontsize=6)
    d += elm.Label().at((base[0] + 3.6, base[1] + 0.5)).label('LED_ARM…LED_ALT ×5\nR1–R5 220Ω to GND', fontsize=7)

    # Pullups: SCL + SDA each via 4k7, dropping to the 3V3 pin level.
    # Each resistor runs HORIZONTAL with an explicit .length() (never the unset default,
    # which is long enough to overshoot straight through the rows below) on its own pin's
    # row, then a plain (non-zigzag) vertical Line jogs up to the shared 3V3 rail — using
    # a zigzag Resistor for that short vertical jog instead visibly skews it, since
    # schemdraw can't compress its fixed zigzag pattern into <1 unit without tilting it.
    # The two horizontal runs use different lengths so their jog-up points land at
    # different x and don't coincide.
    scl = u1.absanchors['SCL']
    sda = u1.absanchors['SDA']
    p33 = u1.absanchors['3V3']
    rail_y = p33[1]
    jog_x_scl = scl[0] + 0.4 + 1.8
    jog_x_sda = scl[0] + 0.4 + 1.2
    d += elm.Line().at(scl).right().length(0.4)
    d += elm.Resistor().right().length(1.8)
    d += elm.Line().at((jog_x_scl, scl[1])).toy(rail_y)
    d += elm.Label().at(((scl[0] + 0.4 + jog_x_scl) / 2, scl[1] + 0.3)).label('R13 4k7', fontsize=6.5)
    d += elm.Line().at(sda).right().length(0.4)
    d += elm.Resistor().right().length(1.2)
    d += elm.Line().at((jog_x_sda, sda[1])).toy(rail_y)
    d += elm.Label().at(((sda[0] + 0.4 + jog_x_sda) / 2, sda[1] + 0.3)).label('R12 4k7', fontsize=6.5)
    bus_right = max(jog_x_scl, jog_x_sda) + 1.0
    d += elm.Line().at((min(jog_x_scl, jog_x_sda), rail_y)).tox(bus_right)
    d += elm.Label().at((bus_right + 0.4, rail_y)).label('3V3', fontsize=7)

    # ============ RIGHT: I2C rail S1-S6 ============
    # Offset well clear (in x) of the pullup network above, so the header's pin column
    # doesn't cross R12/R13 or their labels.
    irq = u1.absanchors['IRQ1–IRQ6']
    hdr_x = bus_right + 3.0
    d += elm.Line().at(irq).right().length(hdr_x - irq[0])
    hdr = elm.Header(8, pinspacing=0.42).at((hdr_x, irq[1])).right()
    d += hdr
    d += elm.Label().at((hdr_x, irq[1])).label('S1–S6 — I2C rail slots\nJST-XH 8 ×6 · GND/5V/3V3/SDA/SCL + IRQ',
                                                loc='bottom', ofst=(1.0, -1.9), fontsize=8)

    # Power rails
    d += elm.Label().at(u1.absanchors['3V3']).label('3V3', loc='right', ofst=(1.2, 0.1), fontsize=6.5)
    d += elm.Label().at(u1.absanchors['5V']).label('5V', loc='right', ofst=(1.2, 0.1), fontsize=6.5)
    d += elm.Label().at(u1.absanchors['GND']).label('GND', loc='right', ofst=(1.2, 0.1), fontsize=6.5)

    # Title
    d += elm.Label().at((0, -9)).label('Haptic Console — Control Unit (M6): Teensy 4.1 + JST-XH peripherals + I2C rail',
                                       fontsize=11)

d.save(OUT)
png_out = str(DOCS / "control-unit-circuit.png")
cairosvg.svg2png(url=OUT, write_to=png_out, scale=2, background_color='white')
print('saved', OUT, 'and', png_out)
