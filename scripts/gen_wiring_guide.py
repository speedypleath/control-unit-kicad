#!/usr/bin/env python3
"""Generate docs/wiring-guide.html from scripts/pin_map.json + board_model.json.

The page used to hand-encode the same pin mapping twice -- once in the header
pinout arrays, once per connector card -- which is exactly what drifted out of
sync in earlier revisions. Everything factual on the page now comes from
wiring_model.py, so a pin change lands in one file.

Prose is still written by hand and lives in this script.

Run from the repo root:  python3 scripts/gen_wiring_guide.py
Then:                    python3 scripts/gen_wiring_svg.py   (fills the diagram)
"""
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import wiring_model as M                                       # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "wiring-guide.html"

KIND_LABEL = {"power": "power", "gnd": "ground", "i2c": "I²C / IRQ",
              "signal": "signal"}
SWATCH = {"red": "#c23b2e", "blue": "#2f5fb0", "yellow": "#c99a1e",
          "white": "#e0e0e0", "orange": "#e8912f", "green": "#3f9142"}

TYPE_OF = {"S": "JST-XH-6", "B": "JST-XH-2", "CB": "JST-XH-4", "J": "JST-XH-5",
           "NP": "JST-XH-8"}


# --- small helpers ----------------------------------------------------------
def chip(rp):
    """A clickable grid-ref chip. Clicking one highlights the same hole page-wide."""
    h = M.hole(rp)
    return f'<span class="grid-ref" data-hole="{rp[0]}.{rp[1]}" title="{rp[0]} pin {rp[1]}">{h}</span>'


def part_type(ref):
    pins = sorted((p for p in M.pad_xy if p[0] == ref), key=lambda p: int(p[1]))
    xs = {M.pad_xy[p][0] for p in pins}
    where = (f"col {M.col_letter(next(iter(xs)))}" if len(xs) == 1
             else f"row {round(M.pad_xy[pins[0]][1] / 2.54):02d}")
    if ref.startswith("R"):
        kind = "4.7 kΩ" if ref in ("R12", "R13") else "220 Ω"
    elif ref.startswith("TP"):
        kind = "header pin"
    else:
        kind = TYPE_OF[ref.rstrip("0123456789")]
    return f"{kind} &middot; {where}"


def destination(rp):
    """What the far end of this pad's wire is, as display text + css kind."""
    net = M.PINOUT[rp]
    kind = M.kind_of(net)
    if net in M.BUS:
        return f"{net} rail", kind
    if net.startswith("LED_"):
        other = next(r for r, n in M.PINOUT.items() if n == net and r != rp)
        arrow = "&rarr;" if rp[0].startswith("CB") else "&larr;"
        return f"{arrow} {M.refpin(other)} {chip(other)}", "signal"
    gpio = M.pin_map[net]
    return f"{gpio} &rarr; {chip(M.header_pad[gpio])}", kind


# --- generated blocks -------------------------------------------------------
def header_strip(row, ref, title, note):
    cells = []
    used = {M.pin_map[s]: s for s in M.pin_map}
    for i, name in enumerate(row, 1):
        rp = (ref, str(i))
        kind = M.kind_of(name if name in M.BUS else "x")
        if name in M.BUS:
            use = "rail"
        elif name in used:
            sig = used[name]
            pad = next(r for r, n in M.PINOUT.items() if n == sig)
            use = M.refpin(pad)
            kind = M.kind_of(sig)
        else:
            use = "&mdash;"
            kind = "free"
        cells.append(
            f'<div class="pin-cell {kind}" data-hole="{ref}.{i}"'
            f' data-q="{name} {use} {M.hole(rp)}">'
            f'<span class="pinno">{i}</span>'
            f'<span class="grid">{M.hole(rp)}</span>'
            f'<span class="net">{name}</span>'
            f'<span class="dest">{use}</span></div>')
    return (f'    <div class="header-strip">\n'
            f'      <div class="header-strip-title"><h3>{title}</h3>'
            f'<span class="note">{note}</span></div>\n'
            f'      <div class="pin-row">' + "".join(cells) + '</div>\n    </div>')


def rails_block():
    cards = []
    for net in ("GND", "+3V3", "+5V", "SDA", "SCL"):
        taps = M.bus_taps(net)
        kind = M.kind_of(net)
        body = " ".join(chip(rp) for rp in taps)
        cards.append(
            f'      <div class="rail-card" style="--rail-color:var(--{kind})" data-q="{net}">\n'
            f'        <div class="rail-name">{net} &middot; {len(taps)} taps '
            f'&middot; {M.color_of(net)} wire</div>\n'
            f'        <div class="rail-taps">{body}</div>\n      </div>')
    return "\n".join(cards)


def testpoints_block():
    tps = sorted((rp for rp in M.PINOUT if rp[0].startswith("TP")),
                 key=lambda rp: M.pad_xy[rp][1])
    cards = []
    for rp in tps:
        net = M.PINOUT[rp]
        cards.append(
            f'      <div class="rail-card" style="--rail-color:var(--{M.kind_of(net)})"'
            f' data-q="{rp[0]} {net}">'
            f'<div class="rail-name">{rp[0]} &middot; {net}</div>'
            f'<div class="rail-taps">{chip(rp)}</div></div>')
    return "\n".join(cards)


def conn_cards(refs):
    cards = []
    for ref in sorted(refs, key=lambda r: M.pad_xy[(r, "1")][0]):
        rows = []
        for pin in sorted((p[1] for p in M.pad_xy if p[0] == ref), key=int):
            rp = (ref, pin)
            net = M.PINOUT[rp]
            text, kind = destination(rp)
            rows.append(f'<tr data-q="{ref}.{pin} {net} {M.hole(rp)}">'
                        f'<td class="pin">{pin}</td>'
                        f'<td class="gridref">{chip(rp)}</td>'
                        f'<td class="net">{net}</td>'
                        f'<td class="dest {kind}">{text}</td></tr>')
        cards.append(
            f'      <div class="conn-card" data-q="{ref}">\n'
            f'        <div class="conn-head"><span class="ref">{ref}</span>'
            f'<span class="type">{part_type(ref)}</span></div>\n'
            f'        <table>' + "".join(rows) + '</table>\n      </div>')
    return "\n".join(cards)


def checklist_block(conns):
    rows = []
    for c in conns:
        key = f'{c["net"]}|{M.refpin(c["a"])}|{M.refpin(c["b"])}'
        rows.append(
            f'<tr data-kind="{c["kind"]}"'
            f' data-q="{c["net"]} {c["signal"]} {M.refpin(c["a"])} {M.refpin(c["b"])}'
            f' {M.hole(c["a"])} {M.hole(c["b"])} {c["color"]}">'
            f'<td class="tick"><input type="checkbox" data-key="{key}" aria-label="soldered"></td>'
            f'<td class="wcolor"><span class="dot" style="background:{SWATCH[c["color"]]}"></span>'
            f'{c["color"]}</td>'
            f'<td class="wnet">{c["net"]}</td>'
            f'<td class="wsig">{c["signal"] if c["signal"] != c["net"] else ""}</td>'
            f'<td class="wend">{chip(c["a"])} <span class="rp">{M.refpin(c["a"])}</span></td>'
            f'<td class="wend">{chip(c["b"])} <span class="rp">{M.refpin(c["b"])}</span></td>'
            f'<td class="wmm">{c["mm"]:.1f}</td></tr>')
    return "".join(rows)


# --- page -------------------------------------------------------------------
CSS = """
  :root {
    --bg: #f3ede2; --surface: #fffdf8; --surface-2: #ece3d3; --ink: #241c15;
    --muted: #6b5f4f; --border: #d8cbb2; --copper: #b1662f;
    --power: #a63b2e; --power-bg: #f6e2dd;
    --gnd: #4a4640; --gnd-bg: #e6e2da;
    --i2c: #8a5a17; --i2c-bg: #f1e2c4;
    --signal: #235e78; --signal-bg: #dfeaef;
    --free: #8d8272; --free-bg: #e9e4da;
    --hl: #ffd977;
    --shadow: 0 1px 2px rgba(36,28,21,0.06), 0 8px 24px rgba(36,28,21,0.05);
  }
  @media (prefers-color-scheme: dark) {
    :root:not([data-theme="light"]) {
      --bg: #17130f; --surface: #211a14; --surface-2: #2a2119; --ink: #f1e7d7;
      --muted: #a6957d; --border: #3c3025; --copper: #e0a868;
      --power: #e2897b; --power-bg: #3a221e;
      --gnd: #cfc7b8; --gnd-bg: #2c2822;
      --i2c: #e8c37e; --i2c-bg: #3a2e15;
      --signal: #8fc4de; --signal-bg: #1c2f37;
      --free: #8b7f6d; --free-bg: #241d17;
      --hl: #6a5116;
      --shadow: 0 1px 2px rgba(0,0,0,0.3), 0 12px 32px rgba(0,0,0,0.35);
    }
  }
  :root[data-theme="dark"] {
    --bg: #17130f; --surface: #211a14; --surface-2: #2a2119; --ink: #f1e7d7;
    --muted: #a6957d; --border: #3c3025; --copper: #e0a868;
    --power: #e2897b; --power-bg: #3a221e;
    --gnd: #cfc7b8; --gnd-bg: #2c2822;
    --i2c: #e8c37e; --i2c-bg: #3a2e15;
    --signal: #8fc4de; --signal-bg: #1c2f37;
    --free: #8b7f6d; --free-bg: #241d17;
    --hl: #6a5116;
    --shadow: 0 1px 2px rgba(0,0,0,0.3), 0 12px 32px rgba(0,0,0,0.35);
  }
  * { box-sizing: border-box; }
  body { margin: 0; background: var(--bg); color: var(--ink); font-family: ui-sans-serif, system-ui, sans-serif; line-height: 1.5; padding: 0 0 6rem; }
  .wrap { max-width: 1040px; margin: 0 auto; padding: 3rem 1.5rem 0; }
  header.page-head { display: flex; flex-direction: column; gap: 0.5rem; margin-bottom: 1.5rem; padding-bottom: 1.75rem; border-bottom: 3px solid var(--copper); }
  .eyebrow { font-family: ui-monospace, monospace; font-size: 0.72rem; letter-spacing: 0.14em; text-transform: uppercase; color: var(--copper); }
  h1 { font-weight: 800; font-size: clamp(2rem, 5vw, 2.7rem); margin: 0; }
  .dek { color: var(--muted); font-size: 1rem; max-width: 68ch; }
  h2 { font-weight: 700; font-size: 1.4rem; margin: 0 0 0.25rem; scroll-margin-top: 5.5rem; }
  h3 { font-weight: 600; font-size: 1.05rem; margin: 0; }
  section { margin-bottom: 3rem; scroll-margin-top: 4.5rem; }
  .wrap.main { padding-top: 2rem; }
  .section-intro { color: var(--muted); font-size: 0.92rem; max-width: 68ch; margin: 0 0 1.25rem; }
  a { color: var(--copper); text-underline-offset: 2px; }
  code { font-family: ui-monospace, monospace; font-size: 0.9em; background: var(--surface-2); padding: 0.05rem 0.3rem; border-radius: 3px; }

  /* --- sticky toolbar --- */
  .toolbar { position: sticky; top: 0; z-index: 20; background: color-mix(in srgb, var(--bg) 92%, transparent); backdrop-filter: blur(8px); border-bottom: 1px solid var(--border); }
  .toolbar-in { max-width: 1040px; margin: 0 auto; padding: 0.6rem 1.5rem; display: flex; gap: 0.75rem; align-items: center; flex-wrap: wrap; }
  .toolbar nav { display: flex; gap: 0.15rem; flex-wrap: wrap; }
  .toolbar nav a { font-size: 0.78rem; color: var(--muted); text-decoration: none; padding: 0.25rem 0.5rem; border-radius: 5px; }
  .toolbar nav a:hover { background: var(--surface-2); color: var(--ink); }
  .grow { flex: 1 1 auto; }
  #q { font-family: ui-monospace, monospace; font-size: 0.8rem; padding: 0.35rem 0.6rem; min-width: 12rem; border: 1px solid var(--border); border-radius: 6px; background: var(--surface); color: var(--ink); }
  .btn { font-size: 0.76rem; padding: 0.3rem 0.6rem; border: 1px solid var(--border); border-radius: 6px; background: var(--surface); color: var(--muted); cursor: pointer; }
  .btn:hover { color: var(--ink); }
  .progress { font-family: ui-monospace, monospace; font-size: 0.76rem; color: var(--muted); display: flex; align-items: center; gap: 0.5rem; }
  .progress .bar { width: 6rem; height: 5px; border-radius: 3px; background: var(--surface-2); overflow: hidden; }
  .progress .bar i { display: block; height: 100%; width: 0; background: var(--copper); transition: width 0.2s; }

  .legend { display: flex; flex-wrap: wrap; gap: 0.5rem 1.25rem; padding: 0.85rem 1.1rem; background: var(--surface); border: 1px solid var(--border); border-radius: 8px; box-shadow: var(--shadow); margin-bottom: 2.5rem; }
  .legend-item { display: flex; align-items: center; gap: 0.5rem; font-family: ui-monospace, monospace; font-size: 0.78rem; color: var(--muted); }
  .swatch { width: 0.65rem; height: 0.65rem; border-radius: 2px; flex: none; }
  .swatch.power { background: var(--power); } .swatch.gnd { background: var(--gnd); }
  .swatch.i2c { background: var(--i2c); } .swatch.signal { background: var(--signal); }

  .grid-ref { font-family: ui-monospace, monospace; font-weight: 700; background: var(--surface-2); border-radius: 4px; padding: 0.05rem 0.4rem; cursor: pointer; }
  .grid-ref.hl, .pin-cell.hl { outline: 2px solid var(--copper); background: var(--hl); }
  .header-strip { background: var(--surface); border: 1px solid var(--border); border-radius: 10px; box-shadow: var(--shadow); padding: 1.25rem; margin-bottom: 1.25rem; overflow-x: auto; }
  .header-strip-title { display: flex; align-items: baseline; justify-content: space-between; margin-bottom: 0.9rem; gap: 1rem; flex-wrap: wrap; }
  .header-strip-title .note { font-family: ui-monospace, monospace; font-size: 0.74rem; color: var(--muted); }
  .pin-row { display: grid; grid-template-columns: repeat(24, minmax(56px, 1fr)); gap: 3px; min-width: 1000px; }
  .pin-cell { display: flex; flex-direction: column; align-items: center; gap: 0.1rem; padding: 0.35rem 0.15rem 0.45rem; border-radius: 6px; text-align: center; }
  .pin-cell.power { background: var(--power-bg); } .pin-cell.gnd { background: var(--gnd-bg); }
  .pin-cell.i2c { background: var(--i2c-bg); } .pin-cell.signal { background: var(--signal-bg); }
  .pin-cell.free { background: var(--free-bg); }
  .pin-cell .pinno { font-family: ui-monospace, monospace; font-size: 0.6rem; color: var(--muted); opacity: 0.7; }
  .pin-cell .grid { font-family: ui-monospace, monospace; font-weight: 700; font-size: 0.78rem; }
  .pin-cell.power .grid { color: var(--power); } .pin-cell.gnd .grid { color: var(--gnd); }
  .pin-cell.i2c .grid { color: var(--i2c); } .pin-cell.signal .grid { color: var(--signal); }
  .pin-cell.free .grid { color: var(--free); }
  .pin-cell .net { font-family: ui-monospace, monospace; font-size: 0.68rem; color: var(--muted); }
  .pin-cell .dest { font-size: 0.62rem; color: var(--muted); font-family: ui-monospace, monospace; }

  .rail-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 0.75rem; }
  .rail-card { background: var(--surface); border: 1px solid var(--border); border-left: 4px solid var(--rail-color, var(--copper)); border-radius: 8px; box-shadow: var(--shadow); padding: 0.85rem 1rem; }
  .rail-card .rail-name { font-family: ui-monospace, monospace; font-weight: 700; font-size: 0.85rem; color: var(--rail-color, var(--copper)); margin-bottom: 0.4rem; }
  .rail-card .rail-taps { font-size: 0.82rem; color: var(--muted); line-height: 1.9; }

  .zone { margin-bottom: 2.25rem; }
  .conn-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 0.9rem; }
  .conn-card { background: var(--surface); border: 1px solid var(--border); border-radius: 8px; box-shadow: var(--shadow); overflow: hidden; }
  .conn-card .conn-head { display: flex; justify-content: space-between; align-items: baseline; padding: 0.6rem 0.85rem; background: var(--surface-2); border-bottom: 1px solid var(--border); }
  .conn-card .conn-head .ref { font-family: ui-monospace, monospace; font-weight: 700; font-size: 0.95rem; }
  .conn-card .conn-head .type { font-size: 0.66rem; color: var(--muted); font-family: ui-monospace, monospace; }
  .conn-card table { width: 100%; border-collapse: collapse; font-size: 0.78rem; }
  .conn-card td { padding: 0.35rem 0.5rem; border-top: 1px solid var(--border); }
  .conn-card td:first-child { padding-left: 0.85rem; }
  .conn-card td:last-child { padding-right: 0.85rem; }
  .conn-card tr:first-child td { border-top: none; }
  .conn-card td.pin { font-family: ui-monospace, monospace; color: var(--muted); width: 1.4rem; }
  .conn-card td.gridref { width: 3.4rem; }
  .conn-card td.net { font-family: ui-monospace, monospace; color: var(--muted); font-size: 0.72rem; }
  .conn-card td.dest { text-align: right; font-family: ui-monospace, monospace; font-weight: 500; white-space: nowrap; }
  .conn-card td.dest.power { color: var(--power); } .conn-card td.dest.gnd { color: var(--gnd); }
  .conn-card td.dest.i2c { color: var(--i2c); } .conn-card td.dest.signal { color: var(--signal); }

  .callout { background: var(--surface); border: 1px solid var(--border); border-left: 4px solid var(--copper); border-radius: 8px; box-shadow: var(--shadow); padding: 0.9rem 1.1rem; margin-bottom: 1.5rem; font-size: 0.88rem; color: var(--muted); }
  .callout strong { color: var(--ink); }
  details.notes { background: var(--surface); border: 1px solid var(--border); border-radius: 8px; box-shadow: var(--shadow); padding: 0.75rem 1.1rem; }
  details.notes > summary { cursor: pointer; font-weight: 600; font-size: 0.9rem; }
  details.notes .callout { box-shadow: none; margin-top: 1rem; }

  .diagram-frame { background: var(--surface); border: 1px solid var(--border); border-radius: 10px; box-shadow: var(--shadow); padding: 1rem; overflow-x: auto; }
  .diagram-frame svg { display: block; max-width: 560px; width: 100%; height: auto; margin: 0 auto; }
  .board-bg { fill: var(--surface-2); }
  .pad-dot { fill: var(--muted); opacity: 0.5; }
  .ref-label { font: 700 9px ui-monospace, monospace; fill: var(--ink); }
  .wire { opacity: 0.92; }
  .wire-power { stroke: var(--power) !important; }
  .wire-gnd { stroke: var(--gnd) !important; }
  .wire-i2c { stroke: var(--i2c) !important; }
  .wire-casing { stroke: var(--muted); opacity: 0.5; }
  .diagram-legend { display: flex; flex-wrap: wrap; gap: 0.5rem 1.25rem; margin-top: 0.9rem; font-family: ui-monospace, monospace; font-size: 0.76rem; color: var(--muted); }
  .diagram-legend span.dot { display: inline-block; width: 0.6rem; height: 0.6rem; border-radius: 50%; margin-right: 0.35rem; vertical-align: -1px; }

  /* --- checklist --- */
  .filters { display: flex; gap: 0.35rem; flex-wrap: wrap; margin-bottom: 0.9rem; }
  .filters button { font-family: ui-monospace, monospace; font-size: 0.74rem; padding: 0.28rem 0.7rem; border: 1px solid var(--border); border-radius: 999px; background: var(--surface); color: var(--muted); cursor: pointer; }
  .filters button[aria-pressed="true"] { background: var(--copper); border-color: var(--copper); color: var(--bg); }
  /* Its own scroll container, so the header row sticks to the top of the panel
     rather than to the page. `top` must be 0 here: a non-zero offset would push
     the header down from its resting position and hide the first wire. */
  .wire-table-frame { background: var(--surface); border: 1px solid var(--border); border-radius: 10px; box-shadow: var(--shadow); overflow: auto; max-height: min(72vh, 44rem); overscroll-behavior: contain; }
  table.wires { width: 100%; border-collapse: separate; border-spacing: 0; font-size: 0.8rem; min-width: 640px; }
  table.wires th { text-align: left; font-size: 0.68rem; letter-spacing: 0.08em; text-transform: uppercase; color: var(--muted); font-weight: 600; padding: 0.6rem 0.6rem; border-bottom: 1px solid var(--border); position: sticky; top: 0; z-index: 2; background: var(--surface); }
  table.wires td { padding: 0.32rem 0.6rem; border-top: 1px solid var(--border); vertical-align: middle; }
  table.wires tr.done td { opacity: 0.42; text-decoration: line-through; }
  table.wires tr.done td.tick { opacity: 1; text-decoration: none; }
  td.tick { width: 1.8rem; padding-left: 0.9rem; }
  td.tick input { width: 1rem; height: 1rem; accent-color: var(--copper); cursor: pointer; }
  td.wcolor { font-family: ui-monospace, monospace; font-size: 0.72rem; color: var(--muted); white-space: nowrap; }
  td.wcolor .dot { display: inline-block; width: 0.6rem; height: 0.6rem; border-radius: 50%; margin-right: 0.4rem; vertical-align: -1px; border: 1px solid var(--border); }
  td.wnet { font-family: ui-monospace, monospace; font-weight: 700; }
  td.wsig { font-family: ui-monospace, monospace; font-size: 0.72rem; color: var(--muted); }
  td.wend .rp { font-family: ui-monospace, monospace; font-size: 0.7rem; color: var(--muted); margin-left: 0.3rem; }
  td.wmm { font-family: ui-monospace, monospace; text-align: right; color: var(--muted); }
  .hidden { display: none !important; }
  .dim { opacity: 0.25; }
  .empty-note { padding: 1rem; color: var(--muted); font-size: 0.85rem; }
  footer { max-width: 1040px; margin: 3rem auto 0; padding: 1.5rem 1.5rem 0; border-top: 1px solid var(--border); color: var(--muted); font-size: 0.82rem; }
  @media print {
    .toolbar, .filters { display: none; }
    body { padding-bottom: 0; }
    .conn-card, .rail-card, .header-strip { break-inside: avoid; }
    .wire-table-frame { max-height: none; overflow: visible; }
  }
"""

JS = """
  // --- highlight one physical hole everywhere it is mentioned ---------------
  document.addEventListener('click', (e) => {
    const el = e.target.closest('[data-hole]');
    const on = document.querySelectorAll('.hl');
    const was = el && el.classList.contains('hl');
    on.forEach(n => n.classList.remove('hl'));
    if (el && !was) {
      document.querySelectorAll('[data-hole="' + el.dataset.hole + '"]')
        .forEach(n => n.classList.add('hl'));
    }
  });

  // --- search: filters the checklist, dims non-matching cards ---------------
  const q = document.getElementById('q');
  const rows = [...document.querySelectorAll('table.wires tbody tr')];
  const cards = [...document.querySelectorAll('[data-q]')].filter(n => !n.closest('table.wires'));
  let kind = 'all';

  function apply() {
    const t = q.value.trim().toLowerCase();
    let shown = 0;
    for (const r of rows) {
      const ok = (kind === 'all' || r.dataset.kind === kind) &&
                 (!t || r.dataset.q.toLowerCase().includes(t));
      r.classList.toggle('hidden', !ok);
      if (ok) shown++;
    }
    document.getElementById('shown').textContent = shown;
    for (const c of cards) {
      c.classList.toggle('dim', !!t && !c.dataset.q.toLowerCase().includes(t));
    }
    document.getElementById('none').classList.toggle('hidden', shown > 0);
  }
  q.addEventListener('input', apply);
  document.querySelectorAll('.filters button').forEach(b => {
    b.addEventListener('click', () => {
      kind = b.dataset.kind;
      document.querySelectorAll('.filters button')
        .forEach(o => o.setAttribute('aria-pressed', String(o === b)));
      apply();
    });
  });
  addEventListener('keydown', e => {
    if (e.key === '/' && document.activeElement !== q) { e.preventDefault(); q.focus(); }
    if (e.key === 'Escape' && document.activeElement === q) { q.value = ''; apply(); q.blur(); }
  });

  // --- solder progress, remembered in this browser -------------------------
  const KEY = 'wiring-guide-done-v1';
  const boxes = [...document.querySelectorAll('td.tick input')];
  let done = new Set();
  try { done = new Set(JSON.parse(localStorage.getItem(KEY) || '[]')); } catch (_) {}

  function paint() {
    for (const b of boxes) {
      b.checked = done.has(b.dataset.key);
      b.closest('tr').classList.toggle('done', b.checked);
    }
    const pct = boxes.length ? (done.size / boxes.length) * 100 : 0;
    document.getElementById('pcount').textContent = done.size;
    document.getElementById('pbar').style.width = pct.toFixed(1) + '%';
  }
  for (const b of boxes) {
    b.addEventListener('change', () => {
      b.checked ? done.add(b.dataset.key) : done.delete(b.dataset.key);
      try { localStorage.setItem(KEY, JSON.stringify([...done])); } catch (_) {}
      paint();
    });
  }
  document.getElementById('reset').addEventListener('click', () => {
    if (!done.size || confirm('Clear all ' + done.size + ' ticks?')) {
      done = new Set();
      try { localStorage.removeItem(KEY); } catch (_) {}
      paint();
    }
  });

  // --- theme override ------------------------------------------------------
  const TKEY = 'wiring-guide-theme';
  const tbtn = document.getElementById('theme');
  function setTheme(v) {
    if (v) { document.documentElement.setAttribute('data-theme', v); }
    else { document.documentElement.removeAttribute('data-theme'); }
    tbtn.textContent = v ? (v === 'dark' ? 'dark' : 'light') : 'auto';
    try { v ? localStorage.setItem(TKEY, v) : localStorage.removeItem(TKEY); } catch (_) {}
  }
  try { setTheme(localStorage.getItem(TKEY)); } catch (_) { setTheme(null); }
  tbtn.addEventListener('click', () => {
    const cur = document.documentElement.getAttribute('data-theme');
    setTheme(cur === 'dark' ? 'light' : cur === 'light' ? null : 'dark');
  });

  paint();
  apply();
"""

ZONES = [
    ("zone-s", "S1&ndash;S6 &mdash; haptic drivers (I&sup2;C)",
     "Rotated vertical, one per column, centred on the board. GND/+3V3/+5V/SDA/SCL "
     "all fall on the same row across all six &mdash; a horizontal bus wire along "
     "that row reaches every connector. Only pin 6 (IRQ) is unique per connector.",
     [f"S{i}" for i in range(1, 7)]),
    ("zone-pullup", "R12 / R13 &mdash; I&sup2;C pull-ups",
     "Sit just below the S-zone, tapping the SDA/SCL/+3V3 rails directly. "
     "4.7&nbsp;k&Omega; each.",
     ["R12", "R13"]),
    ("zone-b", "B1&ndash;B8 &mdash; diamond buttons (mirrored)",
     "B1&ndash;B4 (left cluster) mirror B5&ndash;B8 (right cluster) on the same row "
     "band, so left to right the refs read B1 B2 B3 B4 B8 B7 B6 B5 &mdash; the cards "
     "below are in that physical order, not numeric order. All eight pin-1 (GND) holes "
     "share one row: a single wire down that row grounds all eight.",
     [f"B{i}" for i in range(1, 9)]),
    ("zone-j", "J1 / J2 &mdash; joysticks (mirrored)",
     "J1 (left stick) mirrors J2 (right stick); pin 5 (GND) on both lands on the "
     "same row.",
     ["J1", "J2"]),
    ("zone-cb", "CB1&ndash;CB5 &mdash; LED buttons (near-symmetric)",
     "CB3 sits on the centre column; CB2/CB4 and CB1/CB5 mirror around it. Pin 3 is "
     "the LED anode and does <em>not</em> go to the Teensy &mdash; it goes to that "
     "connector's series resistor one row below, and the resistor's far end carries "
     "the GPIO. Both GND pins (2 and 4) sit on their own rows across all five.",
     [f"CB{i}" for i in range(1, 6)]),
    ("zone-r", "R1&ndash;R5 &mdash; LED series resistors",
     "Row 48 &mdash; the row immediately below each connector's pin&nbsp;1 &mdash; "
     "with each resistor starting in its matching connector's column and running four "
     "holes right. <strong>Tight fit:</strong> the JST-XH-4 housing overhangs its "
     "pin&nbsp;1 by 2.45&nbsp;mm, putting its edge 0.09&nbsp;mm short of the row-48 "
     "hole, so pin&nbsp;1 of each resistor lands hard against the connector body "
     "&mdash; bend that lead away from the housing before seating the connector.",
     [f"R{i}" for i in range(1, 6)]),
    ("zone-np", "NP1 &mdash; numpad",
     "Pushed to the board's right edge to clear the Teensy header rows it shares "
     "rows with. <strong>Watch the labels here:</strong> the board's 32-column letter "
     "sequence reuses each letter at both ends, so NP1's holes can compute to the same "
     "letter+row as a header hole at the opposite edge. Use the left/right position, "
     "not the label alone. NP1 pin 5 sits on D13, which also drives the Teensy's "
     "onboard LED &mdash; fine for a matrix <em>row</em> (a driven output), but never "
     "put a pulled-up column input there.",
     ["NP1"]),
]

PROSE_KIT = """
  <section id="kit">
    <h2>Using the jumper wire kit</h2>
    <p class="section-intro">You're wiring this with a pre-formed solid-core jumper kit (the boxed assortment of red/yellow/white/orange/green/blue wires, fixed pre-cut lengths, ends bent square) &mdash; the standard kit sold for solderless breadboards. That matters for a few reasons specific to this board:</p>
    <div class="callout">
      <strong>These wires are made for solderless boards &mdash; this perfboard isn't one.</strong> The bent tip is shaped to grip a breadboard's spring clip, not to make a reliable joint on its own. It will friction-fit into a perfboard hole and feel "connected," but it isn't electrically sound until soldered. Treat every insertion as a <em>dry-fit</em>, not a finished connection:
      <ol style="margin:0.5rem 0 0; padding-left:1.25rem;">
        <li>Push the wire's tip through the two holes the guide calls out (component-side/top of the board), and check the fit against the grid ref before committing.</li>
        <li>Flip the board to the copper/solder side and solder both tips to their pads. A perfboard pad is just a ring of copper around the hole &mdash; feed a little solder onto the joint so it wets the ring, not just the wire.</li>
        <li>Clip the excess tip flush once the joint has cooled.</li>
      </ol>
    </div>
    <div class="callout">
      <strong>The kit's lengths are fixed &mdash; the "rail" runs below are not.</strong> A shared bus row (GND/+3V3/+5V/SCL/SDA, see <em>Shared bus rails</em> below) usually spans more holes than any single wire in the kit. Two options, both fine:
      <ul style="margin:0.5rem 0 0; padding-left:1.25rem;">
        <li>Pick the longest wire that reaches and let it bow slightly between holes &mdash; solid core holds its shape, it won't spring back.</li>
        <li>Daisy-chain shorter wires hole-to-hole along the row: at every intermediate hole, both the incoming and outgoing wire tips land in the <em>same</em> hole and both get soldered there together with the pad. Don't skip soldering an intermediate joint just because the wire "looks continuous" &mdash; each hole is a separate solder joint, there's no copper trace linking adjacent holes on bare perfboard.</li>
      </ul>
      The <a href="#checklist">solder checklist</a> already lists each rail hop separately, with its length in millimetres, so you can match a hop to a wire in the box before cutting anything.
    </div>
    <div class="callout">
      <strong>Colour convention</strong> (matches the legend above, the kit's actual colours, and the 3D-modelled wires on the board): <strong style="color:var(--power)">red</strong> for every +5V/+3V3 connection, <strong style="color:var(--gnd)">blue</strong> for every GND connection (the kit has no black &mdash; blue is the closest "stay off the power colours" choice and reads unambiguously once you commit to it), <strong style="color:var(--i2c)">yellow</strong> for the SCL/SDA/IRQ bus, and white/orange/green for the remaining signal wires. Each signal net gets one fixed colour, so the <em>same</em> wire is the same colour everywhere it appears &mdash; on this page, on the diagram, and in the 3D render. The checklist's colour column is the authority.
    </div>
    <div class="callout">
      <strong>Test before you solder the far end.</strong> The small compartment of premade spade/hook-tipped leads in the kit box is handy for exactly this: clip one onto a wire you've already soldered at one end and touch the other lead to the destination pad with a multimeter in continuity mode, confirming against the grid ref, before soldering the second end permanently.
    </div>
  </section>
"""


def build():
    conns = M.connections()
    n_legs = len(json.loads((ROOT / "scripts" / "segments_v3.json").read_text()))
    total_mm = sum(c["mm"] for c in conns)
    longest = max(conns, key=lambda c: c["mm"])

    parts = []
    parts.append(f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Control Unit Wiring Guide</title>
<style>{CSS}</style>
</head>
<body>
<div class="wrap">
  <header class="page-head">
    <span class="eyebrow">Haptic Console &middot; Control Unit &middot; Perfboard Build</span>
    <h1>Wiring Guide</h1>
    <p class="dek">Every connection, given as the actual perfboard hole (column letter + row number, matching the printed grid on your board) &mdash; not an abstract header-pin number. Read a grid ref, find that hole, solder. Click any grid ref to light up every other mention of that same hole.</p>
  </header>
</div>

<div class="toolbar">
  <div class="toolbar-in">
    <nav>
      <a href="#kit">Kit</a><a href="#diagram">Diagram</a><a href="#header">Header</a>
      <a href="#rails">Rails</a><a href="#testpoints">Test points</a>
      <a href="#connectors">Connectors</a><a href="#checklist">Checklist</a>
    </nav>
    <span class="grow"></span>
    <input id="q" type="search" placeholder="filter&hellip;  (press /)" aria-label="Filter wires and connectors">
    <span class="progress"><span class="bar"><i id="pbar"></i></span>
      <span id="pcount">0</span>/{len(conns)}</span>
    <button class="btn" id="reset" type="button">reset</button>
    <button class="btn" id="theme" type="button" title="theme">auto</button>
  </div>
</div>

<div class="wrap main">
  <div class="legend">
    <span class="legend-item"><span class="swatch power"></span>Power (+5V / +3V3) &mdash; red kit wire</span>
    <span class="legend-item"><span class="swatch gnd"></span>Ground &mdash; blue kit wire</span>
    <span class="legend-item"><span class="swatch i2c"></span>I&sup2;C bus (SCL / SDA / IRQ) &mdash; yellow kit wire</span>
    <span class="legend-item"><span class="swatch signal"></span>Signal (per-pin GPIO) &mdash; white / orange / green kit wire</span>
  </div>
{PROSE_KIT}
  <section id="diagram">
    <h2>Back-side wiring diagram</h2>
    <p class="section-intro">The board seen from the solder side (mirrored), with every jumper drawn where it actually runs on the finished board. Wires that cross are drawn in physical over/under order.</p>
    <div class="diagram-frame">
      <svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Back-side wiring diagram placeholder">
  <rect x="0" y="0" width="100" height="100" class="board-bg"/>
  <text x="50" y="52" text-anchor="middle" class="ref-label">run gen_wiring_svg.py</text>
</svg>
      <div class="diagram-legend">
        <span><span class="dot" style="background:var(--power)"></span>power (+5V / +3V3)</span>
        <span><span class="dot" style="background:var(--gnd)"></span>ground</span>
        <span><span class="dot" style="background:var(--i2c)"></span>I&sup2;C bus (SCL / SDA / IRQ)</span>
        <span><span class="dot" style="background:#e0e0e0;border:1px solid var(--border)"></span>signal &mdash; white</span>
        <span><span class="dot" style="background:#e8912f"></span>signal &mdash; orange</span>
        <span><span class="dot" style="background:#3f9142"></span>signal &mdash; green</span>
      </div>
    </div>
    <p class="section-intro" style="margin-top:0.9rem;">The Teensy header sockets aren't outlined (48 near-parallel verticals would crowd the top of the diagram) &mdash; every net still ends at its correct header column. Signal colours are per net, not per connector group, so two adjacent wires can share a colour; cross-check the net name in the tables below.</p>
  </section>

  <section id="header">
    <h2>Teensy header pinout</h2>
    <p class="section-intro">The two 24-pin sockets the Teensy drops into, drawn left to right as they sit on the board. Each cell shows the socket pin number, the perfboard hole under it, the Teensy net, and what this build wires to it. Greyed cells are unused &mdash; free for later expansion.</p>
{header_strip(M.ROW_A, "J_TEENSY_A", "Header A &mdash; board row 23 (upper socket)",
              "pin 1 at the left edge")}
{header_strip(M.ROW_B, "J_TEENSY_B", "Header B &mdash; board row 29 (lower socket)",
              "pin 1 at the left edge")}
  </section>

  <section id="rails">
    <h2>Shared bus rails</h2>
    <p class="section-intro">Five nets touch many holes each. Run each as one continuous chain past every hole listed, in the order listed (that's board order, top to bottom), rather than home-running each connector back to the header separately.</p>
    <div class="rail-grid">
{rails_block()}
    </div>
  </section>

  <section id="testpoints">
    <h2>Test points</h2>
    <p class="section-intro">Five male 2.54mm header pins in the last column past S6 (column A &mdash; the letter sequence wraps back to A at the board's right edge), tapping the same rails S1&ndash;S6 share. Clip a jumper or scope hook straight onto a pin instead of back-probing a live JST connector.</p>
    <div class="rail-grid">
{testpoints_block()}
    </div>
  </section>

  <h2 id="connectors" style="margin-bottom:1.25rem;">Connectors</h2>
""")

    for zid, title, intro, refs in ZONES:
        parts.append(f"""  <section class="zone">
    <h2 id="{zid}">{title}</h2>
    <p class="section-intro">{intro}</p>
    <div class="conn-grid">
{conn_cards(refs)}
    </div>
  </section>
""")

    parts.append(f"""  <section id="checklist">
    <h2>Solder checklist</h2>
    <p class="section-intro">Every wire on the board, once. {len(conns)} connections, {total_mm:.0f}&nbsp;mm of wire in total; the longest single run is {longest["mm"]:.0f}&nbsp;mm ({longest["net"]}, {M.refpin(longest["a"])}&nbsp;&rarr;&nbsp;{M.refpin(longest["b"])}). Lengths are hole-to-hole Manhattan distance &mdash; the routed wire follows the grid, so that <em>is</em> its length, but add a few millimetres for the bend at each tip. Ticks are saved in this browser only.</p>
    <div class="filters">
      <button type="button" data-kind="all" aria-pressed="true">all</button>
      <button type="button" data-kind="power" aria-pressed="false">power</button>
      <button type="button" data-kind="gnd" aria-pressed="false">ground</button>
      <button type="button" data-kind="i2c" aria-pressed="false">I&sup2;C / IRQ</button>
      <button type="button" data-kind="signal" aria-pressed="false">signal</button>
    </div>
    <div class="wire-table-frame">
      <table class="wires">
        <thead><tr><th></th><th>colour</th><th>net</th><th>signal</th><th>from</th><th>to</th><th>mm</th></tr></thead>
        <tbody>{checklist_block(conns)}</tbody>
      </table>
      <div class="empty-note hidden" id="none">Nothing matches that filter.</div>
    </div>
    <p class="section-intro" style="margin-top:0.75rem;"><span id="shown">{len(conns)}</span> of {len(conns)} shown. On the board these {len(conns)} connections become {n_legs} modelled jumper legs, because a run that changes both row and column is drawn as two straight legs meeting at a corner hole, and a run that would lie on top of another wire is detoured around it. Electrically each is still one connection &mdash; one length of wire, bent, will do it.</p>
  </section>

  <section>
    <h2>Revision notes</h2>
    <details class="notes">
      <summary>How this layout got here</summary>
      <div class="callout">
        <strong>GPIO assignment (2026-08-23).</strong> Connector signals are not in sequential blocks. Each one is wired to a Teensy pin chosen for physical proximity, solved as an assignment problem over the free GPIOs, which is why the numbers look scattered. B1&ndash;B8 are additionally pinned to header B and assigned in ascending order along the physical row, so no two button wires cross. <strong>Firmware pin constants must follow this map</strong> (<code>scripts/pin_map.json</code>); the tables on this page, the schematic and the manufactured board are all generated from it.
      </div>
      <div class="callout">
        <strong>Connector standard.</strong> S1&ndash;S6 follow the XH2.54 6-pin Haptic Console Connector Standard v1.1 &mdash; pin 1 GND, pin 2 3.3V, pin 3 5V, pin 4 SDA, pin 5 SCL, pin 6 IRQ &mdash; matching cables crimped to that spec.
      </div>
      <div class="callout">
        <strong>Group layout.</strong> Every JST group shares one anchor row, mirrored left/right to match the physical panel (S1&ndash;S6 centred; B1&ndash;B4 mirrors B5&ndash;B8; J1 mirrors J2; CB1&ndash;CB5 near-symmetric about the centre column). Because each group shares an anchor row, the same pin number lands on the same row across the group, which is what makes the single-wire bus rails possible. Everything fits inside the physical 32&times;50 hole grid.
      </div>
      <div class="callout">
        <strong>Moves since the first revision.</strong> The Teensy sockets moved one column left and two rows up (rows 25&rarr;23 and 31&rarr;29) and R12/R13 shifted two columns; S1&ndash;S6 shifted one column left to clear the TP1&ndash;TP5 header at the right edge; R1&ndash;R5 moved from row 49 to row 48 to match the board as actually built. Every grid ref on this page is re-derived from the current <code>haptic-console-control-unit-perfboard.kicad_pcb</code> placement, so it already reflects all of these.
      </div>
    </details>
  </section>
</div>

<footer>
  Generated by <code>scripts/gen_wiring_guide.py</code> from <code>scripts/pin_map.json</code> and the pad positions in <code>haptic-console-control-unit-perfboard.kicad_pcb</code> &mdash; don't hand-edit this file, regenerate it. Grid refs use the board's own printed columns (F E D C B A Z Y X&hellip;G F E D C B A) and rows (01&ndash;50). GND and +5V are fully available on the main sockets; the Teensy's USB-Host and Ethernet auxiliary pads are not needed.
</footer>

<script>{JS}</script>
</body>
</html>
""")
    OUT.write_text("".join(parts))
    print(f"{OUT.relative_to(ROOT)}: {len(conns)} connections, {total_mm:.0f} mm, "
          f"longest {longest['mm']:.1f} mm ({longest['net']})")


if __name__ == "__main__":
    build()
