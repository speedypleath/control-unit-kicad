"""Haptic Console - Control Unit (M6) circuit diagram via SchemDraw (v10, final)."""
from pathlib import Path

import cairosvg
import schemdraw
import schemdraw.elements as elm

DOCS = Path(__file__).resolve().parent.parent / "docs"
OUT = str(DOCS / "control-unit-circuit.svg")

with schemdraw.Drawing(file=OUT, show=False) as d:
    d.config(fontsize=9, lw=1.6, margin=3)

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
    ], edgepadW=1.8, edgepadH=1.1, leadlen=2.4)
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
                     edgepadW=1.6, edgepadH=0.5).at((BX, by))
        blk.label(text, loc='center', fontsize=7.5)
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
    d += elm.Ground().down().label('GND', loc='right', ofst=(0.25, 0), fontsize=6)
    d += elm.Label().at((base[0] + 5.0, base[1] + 0.8)).label('LED_ARM…LED_ALT ×5\nR1–R5 220Ω → GND', fontsize=7)

    # ============ RIGHT: I2C rail S1-S6 ============
    d += elm.Header(8, pinspacing=0.42).at(u1.absanchors['IRQ1–IRQ6']).right()
    d += elm.Label().at(u1.absanchors['IRQ1–IRQ6']).label('S1–S6 — I2C rail slots\nJST-XH 8 ×6 · GND/5V/3V3/SDA/SCL + IRQ',
                                                          loc='bottom', ofst=(1.0, -1.6), fontsize=8)

    # Pullups: SCL + SDA each via 4k7, dropping to the 3V3 pin level
    scl = u1.absanchors['SCL']
    sda = u1.absanchors['SDA']
    p33 = u1.absanchors['3V3']
    xr = scl[0] + 1.2
    rail_y = p33[1]
    d += elm.Line().at(scl).right().length(1.2)
    d += elm.Resistor().down().at((xr, scl[1]))
    d += elm.Label().at((xr - 1.1, (scl[1] + rail_y) / 2)).label('R13 4k7', fontsize=6.5)
    d += elm.Line().down().toy(rail_y)
    d += elm.Line().at(sda).right().length(1.2)
    d += elm.Resistor().down().at((xr, sda[1]))
    d += elm.Label().at((xr + 1.1, (sda[1] + rail_y) / 2)).label('R12 4k7', fontsize=6.5)
    d += elm.Line().down().toy(rail_y)
    d += elm.Line().at((xr, rail_y)).right().length(1.0)
    d += elm.Label().at((xr + 1.4, rail_y)).label('3V3', fontsize=7)

    # Power rails
    d += elm.Label().at(u1.absanchors['3V3']).label('3V3', loc='right', ofst=(1.2, 0.1), fontsize=6.5)
    d += elm.Label().at(u1.absanchors['5V']).label('5V', loc='right', ofst=(1.2, 0.1), fontsize=6.5)
    d += elm.Label().at(u1.absanchors['GND']).label('GND', loc='right', ofst=(1.2, 0.1), fontsize=6.5)

    # Title
    d += elm.Label().at((0, -9)).label('Haptic Console — Control Unit (M6): Teensy 4.1 + JST-XH peripherals + I2C rail',
                                       fontsize=11)

d.save(OUT)
png_out = str(DOCS / "control-unit-circuit.png")
cairosvg.svg2png(url=OUT, write_to=png_out, scale=2)
print('saved', OUT, 'and', png_out)
