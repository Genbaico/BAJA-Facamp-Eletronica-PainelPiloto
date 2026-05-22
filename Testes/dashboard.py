"""
BAJA Motorsports Dashboard
Lê dados do Arduino via Serial e exibe em tempo real.

Uso:
  python3 dashboard.py                     # simulação automática (sem Arduino)
  python3 dashboard.py --port /dev/ttyUSB0 # conecta ao Arduino no Linux
  python3 dashboard.py --port COM3         # conecta ao Arduino no Windows
"""

import tkinter as tk
import serial
import threading
import time
import argparse
import random

# ── Configurações gerais ───────────────────────────────────────
BAUD_RATE  = 9600
BLINK_MS   = 350
RPM_MAXIMO = 6000
TEMP_CRIT  = 60       # °C — acima disso acende alerta vermelho

# ── Curva de torque (RPM, % do torque máximo) ─────────────────
# Baseado em Briggs & Stratton 305cc OHV — padrão SAE Baja
# Ajuste os pontos conforme o motor real do veículo
TORQUE_PONTOS = [
    (0,    0.00),
    (800,  0.40),
    (1400, 0.78),
    (1800, 0.94),
    (2200, 1.00),   # pico de torque
    (2600, 0.97),
    (3000, 0.88),
    (3500, 0.73),
    (4000, 0.57),
    (4500, 0.40),
    (5000, 0.22),
    (5500, 0.08),
    (6000, 0.00),
]
ZONA_MIN = 1700    # RPM de entrada na zona ótima  (torque ≥ ~90%)
ZONA_MAX = 3100    # RPM de saída  da zona ótima

# ── Paleta de cores ───────────────────────────────────────────
BG       = "#0d0d0d"
PANEL_BG = "#141414"
BORDER   = "#2a2a2a"
ACCENT   = "#ff6600"
GREEN    = "#00e676"
CYAN     = "#00bcd4"
YELLOW   = "#ffcc00"
RED      = "#f44336"
ORANGE   = "#ff9800"
GRAY     = "#555555"
LGRAY    = "#888888"


# ══════════════════════════════════════════════════════════════
#  Dados compartilhados (thread-safe)
# ══════════════════════════════════════════════════════════════
class DataStore:
    def __init__(self):
        self._lock        = threading.Lock()
        self.rpm          = 0.0
        self.speed        = 0.0
        self.temp         = -127.0
        self.spinning     = False
        self.lean_mixture = False
        self.connected    = False

    def update(self, rpm, speed, temp, spinning, lean=False):
        with self._lock:
            self.rpm          = rpm
            self.speed        = speed
            self.temp         = temp
            self.spinning     = spinning
            self.lean_mixture = lean

    def snapshot(self):
        with self._lock:
            return (self.rpm, self.speed, self.temp,
                    self.spinning, self.lean_mixture, self.connected)


# ══════════════════════════════════════════════════════════════
#  Leitura Serial (Arduino real)
# ══════════════════════════════════════════════════════════════
class SerialReader(threading.Thread):
    def __init__(self, store, port, baud):
        super().__init__(daemon=True)
        self.store = store
        self.port  = port
        self.baud  = baud

    def run(self):
        while True:
            try:
                with serial.Serial(self.port, self.baud, timeout=2) as ser:
                    self.store.connected = True
                    while True:
                        raw = ser.readline().decode("utf-8", errors="ignore").strip()
                        if not raw:
                            continue
                        parts = raw.split(",")
                        if len(parts) >= 4:
                            lean = bool(int(parts[4])) if len(parts) > 4 else False
                            self.store.update(float(parts[0]), float(parts[1]),
                                              float(parts[2]), bool(int(parts[3])), lean)
                        elif len(parts) == 1:
                            try:
                                temp = float(parts[0])
                                if -50 < temp < 200:
                                    with self.store._lock:
                                        self.store.temp = temp
                            except ValueError:
                                pass
            except Exception:
                self.store.connected = False
                time.sleep(2)


# ══════════════════════════════════════════════════════════════
#  Simulador com dados aleatórios
# ══════════════════════════════════════════════════════════════
class SimulatorReader(threading.Thread):
    def __init__(self, store):
        super().__init__(daemon=True)
        self.store  = store
        self._rpm   = 2000.0
        self._speed = 30.0

    @staticmethod
    def _drift(v, tgt, noise, lo, hi):
        v += (tgt - v) * 0.08 + random.uniform(-noise, noise)
        return max(lo, min(hi, v))

    def run(self):
        self.store.connected = True
        spin_t = lean_t = 0
        next_t = time.time()
        r_tgt = s_tgt = 0.0

        while True:
            now = time.time()
            if now >= next_t:
                r_tgt  = random.uniform(400,  5800)
                s_tgt  = random.uniform(0,    85)
                next_t = now + random.uniform(2.5, 5.0)

            self._rpm   = self._drift(self._rpm,   r_tgt, 90,  0, RPM_MAXIMO)
            self._speed = self._drift(self._speed, s_tgt, 1.5, 0, 110)

            spinning = self._rpm > 4200 or spin_t > 0
            if not spinning and random.random() < 0.005:
                spin_t = random.randint(8, 20)
            if spin_t > 0:
                spin_t -= 1

            lean = lean_t > 0
            if not lean and random.random() < 0.003:
                lean_t = random.randint(12, 35)
            if lean_t > 0:
                lean_t -= 1

            self.store.update(self._rpm, self._speed, -127.0, spinning, lean)
            time.sleep(0.1)


# ══════════════════════════════════════════════════════════════
#  Funções auxiliares
# ══════════════════════════════════════════════════════════════
def make_panel(parent, **kw):
    outer = tk.Frame(parent, bg=BORDER, padx=1, pady=1)
    inner = tk.Frame(outer, bg=PANEL_BG, **kw)
    inner.pack(fill="both", expand=True)
    return outer, inner


def torque_em(rpm):
    """Interpolação linear da curva de torque — retorna valor 0.0–1.0."""
    pts = TORQUE_PONTOS
    if rpm <= pts[0][0]:
        return pts[0][1]
    if rpm >= pts[-1][0]:
        return pts[-1][1]
    for i in range(len(pts) - 1):
        r0, t0 = pts[i]
        r1, t1 = pts[i + 1]
        if r0 <= rpm <= r1:
            return t0 + (rpm - r0) / (r1 - r0) * (t1 - t0)
    return 0.0


def zona_do_rpm(rpm):
    """Retorna (texto, cor) da zona de torque para o RPM atual."""
    if rpm < ZONA_MIN:
        return "ACELERE MAIS ↑", YELLOW
    if rpm <= ZONA_MAX:
        return "ZONA ÓTIMA  ✓", GREEN
    return "REDUZA  ↓", RED


# ══════════════════════════════════════════════════════════════
#  Dashboard principal
# ══════════════════════════════════════════════════════════════
class Dashboard:
    def __init__(self, root, store):
        self.root  = root
        self.store = store

        self.spin_visible = True
        self.lean_visible = True
        self.temp_visible = True
        self._last_rpm    = 0.0

        root.title("BAJA Dashboard")
        root.configure(bg=BG)
        root.resizable(True, True)

        self._build_ui()
        self._schedule_update()
        self._schedule_blink()

    # ── Construção da UI ──────────────────────────────────────
    def _build_ui(self):
        root = self.root

        # ── Cabeçalho ──
        hdr = tk.Frame(root, bg=BG)
        hdr.pack(fill="x", padx=16, pady=(14, 4))
        tk.Label(hdr, text="BAJA MOTORSPORTS", bg=BG, fg=ACCENT,
                 font=("Courier New", 18, "bold")).pack(side="left")
        self.lbl_status = tk.Label(hdr, text="● SIMULAÇÃO", bg=BG, fg=ORANGE,
                                   font=("Courier New", 11, "bold"))
        self.lbl_status.pack(side="right")

        # ── Gráfico de torque ──
        tq_outer, tq_inner = make_panel(root)
        tq_outer.pack(fill="x", padx=16, pady=4)

        tq_hdr = tk.Frame(tq_inner, bg=PANEL_BG)
        tq_hdr.pack(fill="x", padx=12, pady=(8, 2))
        tk.Label(tq_hdr, text="FAIXA DE TORQUE DO MOTOR",
                 bg=PANEL_BG, fg=LGRAY,
                 font=("Courier New", 9, "bold")).pack(side="left")
        tk.Label(tq_hdr,
                 text=f"ZONA ÓTIMA  {ZONA_MIN/1000:.1f}k – {ZONA_MAX/1000:.1f}k RPM",
                 bg=PANEL_BG, fg=GREEN,
                 font=("Courier New", 9, "bold")).pack(side="right")

        self.canvas_torque = tk.Canvas(tq_inner, bg=PANEL_BG, height=140,
                                       highlightthickness=0)
        self.canvas_torque.pack(fill="x", padx=8, pady=(0, 2))
        self.canvas_torque.bind("<Configure>",
                                lambda e: self._draw_torque(self._last_rpm))

        # Indicador de zona (texto embaixo do gráfico)
        self.lbl_zona = tk.Label(tq_inner, text="RPM: 0  |  --",
                                  bg=PANEL_BG, fg=LGRAY,
                                  font=("Courier New", 14, "bold"))
        self.lbl_zona.pack(pady=(2, 8))

        # ── Linha central: velocidade + RPM ──
        mid = tk.Frame(root, bg=BG)
        mid.pack(fill="x", padx=16, pady=4)
        mid.columnconfigure(0, weight=3)
        mid.columnconfigure(1, weight=2)

        spd_o, spd_i = make_panel(mid)
        spd_o.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        tk.Label(spd_i, text="VELOCIDADE", bg=PANEL_BG, fg=LGRAY,
                 font=("Courier New", 11, "bold")).pack(pady=(12, 0))
        self.lbl_speed = tk.Label(spd_i, text="0.0", bg=PANEL_BG, fg=GREEN,
                                  font=("Courier New", 58, "bold"))
        self.lbl_speed.pack()
        tk.Label(spd_i, text="km/h", bg=PANEL_BG, fg=GRAY,
                 font=("Courier New", 13)).pack(pady=(0, 12))

        rpm_o, rpm_i = make_panel(mid)
        rpm_o.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
        tk.Label(rpm_i, text="RPM", bg=PANEL_BG, fg=LGRAY,
                 font=("Courier New", 11, "bold")).pack(pady=(12, 0))
        self.lbl_rpm = tk.Label(rpm_i, text="0", bg=PANEL_BG, fg=CYAN,
                                font=("Courier New", 44, "bold"))
        self.lbl_rpm.pack(expand=True)
        tk.Label(rpm_i, text="rpm", bg=PANEL_BG, fg=GRAY,
                 font=("Courier New", 13)).pack(pady=(0, 12))

        # ── Linha inferior: Temp | Patinagem | Mistura pobre ──
        bot = tk.Frame(root, bg=BG)
        bot.pack(fill="x", padx=16, pady=4)
        for col in range(3):
            bot.columnconfigure(col, weight=1)

        # Temperatura (LED vermelho)
        tmp_o, tmp_i = make_panel(bot)
        tmp_o.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        tk.Label(tmp_i, text="TEMPERATURA ÓLEO", bg=PANEL_BG, fg=LGRAY,
                 font=("Courier New", 9, "bold")).pack(pady=(12, 0))
        self.canvas_temp = tk.Canvas(tmp_i, bg=PANEL_BG,
                                     width=74, height=74, highlightthickness=0)
        self.canvas_temp.pack(pady=(8, 0))
        self._draw_led(self.canvas_temp, active=False, bright=True, cor=RED,
                       halo="#2a0000", escuro="#1a0000")
        tk.Label(tmp_i, text="ALTA TEMPERATURA", bg=PANEL_BG, fg=LGRAY,
                 font=("Courier New", 9, "bold")).pack(pady=(6, 12))

        # Controle de tração
        spn_o, spn_i = make_panel(bot)
        spn_o.grid(row=0, column=1, sticky="nsew", padx=5)
        tk.Label(spn_i, text="CONTROLE DE TRAÇÃO", bg=PANEL_BG, fg=LGRAY,
                 font=("Courier New", 9, "bold")).pack(pady=(12, 0))
        self.lbl_spin_icon = tk.Label(spn_i, text="⬟", bg=PANEL_BG, fg="#1a1a1a",
                                      font=("Courier New", 44, "bold"))
        self.lbl_spin_icon.pack(pady=(4, 0))
        self.lbl_spin_text = tk.Label(spn_i, text="NORMAL", bg=PANEL_BG, fg=GRAY,
                                      font=("Courier New", 12, "bold"))
        self.lbl_spin_text.pack(pady=(2, 12))

        # Mistura pobre (LED laranja)
        lean_o, lean_i = make_panel(bot)
        lean_o.grid(row=0, column=2, sticky="nsew", padx=(5, 0))
        tk.Label(lean_i, text="SENSOR DE MISTURA", bg=PANEL_BG, fg=LGRAY,
                 font=("Courier New", 9, "bold")).pack(pady=(12, 0))
        self.canvas_lean = tk.Canvas(lean_i, bg=PANEL_BG,
                                     width=74, height=74, highlightthickness=0)
        self.canvas_lean.pack(pady=(8, 0))
        self._draw_led(self.canvas_lean, active=False, bright=True, cor=ORANGE,
                       halo="#2a1400", escuro="#1a1200")
        tk.Label(lean_i, text="MISTURA POBRE", bg=PANEL_BG, fg=LGRAY,
                 font=("Courier New", 10, "bold")).pack(pady=(6, 12))

        # Rodapé
        ftr = tk.Frame(root, bg=BG)
        ftr.pack(fill="x", padx=16, pady=(0, 10))
        self.lbl_time = tk.Label(ftr, text="", bg=BG, fg=GRAY,
                                  font=("Courier New", 9))
        self.lbl_time.pack(side="right")

    # ── Gráfico de curva de torque ─────────────────────────────
    def _draw_torque(self, rpm_val=0):
        c = self.canvas_torque
        w = c.winfo_width()
        h = c.winfo_height()
        if w < 30:
            return

        c.delete("all")

        PL, PR, PT, PB = 34, 10, 10, 20
        pw = w - PL - PR
        ph = h - PT - PB

        def rx(rpm):
            return PL + (rpm / RPM_MAXIMO) * pw

        def ty(pct):
            return PT + (1.0 - pct) * ph

        base_y = h - PB

        # Grade horizontal
        for pct, lbl in [(1.0, "100%"), (0.75, "75%"), (0.5, "50%"), (0.25, "25%")]:
            y = ty(pct)
            c.create_line(PL, y, w - PR, y, fill=BORDER, width=1)
            c.create_text(PL - 3, y, text=lbl, fill=GRAY,
                          font=("Courier New", 6), anchor="e")

        # Fundo da zona ótima
        x0z, x1z = rx(ZONA_MIN), rx(ZONA_MAX)
        c.create_rectangle(x0z, PT, x1z, base_y, fill="#001a08", outline="")

        # Pontos da curva
        N = 300
        curva = [(rx(i * RPM_MAXIMO / N), ty(torque_em(i * RPM_MAXIMO / N)))
                 for i in range(N + 1)]

        # Área sob a curva (fundo escuro)
        poly = [(PL, base_y)] + curva + [(w - PR, base_y)]
        c.create_polygon(poly, fill="#0d0d0d", outline="")

        # Área da zona ótima (verde escuro)
        opt = [(rx(r), ty(torque_em(r))) for r in range(ZONA_MIN, ZONA_MAX + 1, 8)]
        if opt:
            c.create_polygon([(x0z, base_y)] + opt + [(x1z, base_y)],
                             fill="#002d12", outline="")

        # Bordas tracejadas da zona
        for xz in (x0z, x1z):
            c.create_line(xz, PT, xz, base_y, fill="#00aa44", width=1, dash=(5, 3))

        # Rótulo da zona
        c.create_text((x0z + x1z) / 2, PT + 5, text="ZONA ÓTIMA",
                      fill="#00cc55", font=("Courier New", 8, "bold"), anchor="n")

        # Curva de torque
        flat = [v for pt in curva for v in pt]
        c.create_line(flat, fill=GREEN, width=2, smooth=True)

        # Eixos
        c.create_line(PL, base_y, w - PR, base_y, fill=LGRAY, width=1)
        c.create_line(PL, PT, PL, base_y, fill=LGRAY, width=1)

        # Ticks do eixo X
        for mrpm in range(0, RPM_MAXIMO + 1, 1000):
            x = rx(mrpm)
            c.create_line(x, base_y, x, base_y + 3, fill=LGRAY, width=1)
            c.create_text(x, base_y + 4, text=f"{mrpm // 1000}k",
                          fill=GRAY, font=("Courier New", 6), anchor="n")

        # Linha e ponto do RPM atual
        if rpm_val > 0:
            xc = rx(rpm_val)
            yc = ty(torque_em(rpm_val))
            c.create_line(xc, PT, xc, base_y, fill="white", width=2)
            c.create_oval(xc - 5, yc - 5, xc + 5, yc + 5,
                          fill="white", outline=PANEL_BG, width=2)

    # ── LED genérico (temperatura e mistura pobre) ─────────────
    def _draw_led(self, canvas, active, bright, cor, halo, escuro):
        canvas.delete("all")
        cx = cy = 37
        r  = 30

        if active and bright:
            canvas.create_oval(cx-r-8, cy-r-8, cx+r+8, cy+r+8,
                               fill=halo, outline="")
            body, border, glare = cor, "#aaaaaa", "#ffffff"
        elif active:
            body   = escuro
            border = "#444444"
            glare  = ""
        else:
            body   = escuro
            border = "#333333"
            glare  = ""

        canvas.create_oval(cx-r, cy-r, cx+r, cy+r,
                           fill=body, outline=border, width=3)
        if glare:
            canvas.create_oval(cx-r+8, cy-r+6, cx-r+22, cy-r+16,
                               fill="#dddddd", outline="")

    # ── Atualização da UI (100 ms) ─────────────────────────────
    def _schedule_update(self):
        self._update()
        self.root.after(100, self._schedule_update)

    def _update(self):
        rpm, speed, temp, spinning, lean, connected = self.store.snapshot()
        self._last_rpm = rpm

        # Conexão
        if connected:
            self.lbl_status.config(text="● CONECTADO", fg=GREEN)
        else:
            self.lbl_status.config(text="● SIMULAÇÃO", fg=ORANGE)

        # Velocidade e RPM
        self.lbl_speed.config(text=f"{speed:.1f}")
        self.lbl_rpm.config(text=f"{int(rpm):,}")

        # Gráfico de torque + indicador de zona
        self._draw_torque(rpm)
        z_txt, z_clr = zona_do_rpm(rpm)
        self.lbl_zona.config(text=f"RPM: {int(rpm):,}  |  {z_txt}", fg=z_clr)

        self.lbl_time.config(text=time.strftime("%H:%M:%S"))

    # ── Pisca-pisca (350 ms) ───────────────────────────────────
    def _schedule_blink(self):
        self._blink()
        self.root.after(BLINK_MS, self._schedule_blink)

    def _blink(self):
        _, _, temp, spinning, lean, _ = self.store.snapshot()
        temp_alta = temp >= TEMP_CRIT

        # Patinagem
        if spinning:
            clr = RED if self.spin_visible else "#4a0000"
            self.lbl_spin_icon.config(fg=clr)
            self.lbl_spin_text.config(text="!! PATINANDO !!", fg=clr)
            self.spin_visible = not self.spin_visible
        else:
            self.lbl_spin_icon.config(fg="#1a3a1a")
            self.lbl_spin_text.config(text="NORMAL", fg=GRAY)
            self.spin_visible = True

        # Temperatura alta
        self._draw_led(self.canvas_temp,
                       active=temp_alta, bright=self.temp_visible,
                       cor=RED, halo="#2a0000", escuro="#1a0000")
        self.temp_visible = (not self.temp_visible) if temp_alta else True

        # Mistura pobre
        self._draw_led(self.canvas_lean,
                       active=lean, bright=self.lean_visible,
                       cor=ORANGE, halo="#2a1400", escuro="#1a1200")
        self.lean_visible = (not self.lean_visible) if lean else True


# ══════════════════════════════════════════════════════════════
#  Ponto de entrada
# ══════════════════════════════════════════════════════════════
def main():
    parser = argparse.ArgumentParser(description="BAJA Dashboard")
    parser.add_argument("--port", default=None,
                        help="Porta serial (ex: COM3 ou /dev/ttyUSB0). "
                             "Sem este argumento roda em simulação.")
    args = parser.parse_args()

    store = DataStore()

    if args.port is None:
        print("[SIMULAÇÃO] Sem --port especificado → dados aleatórios.")
        reader = SimulatorReader(store)
    else:
        print(f"[SERIAL] Conectando em {args.port} @ {BAUD_RATE} baud...")
        reader = SerialReader(store, args.port, BAUD_RATE)

    reader.start()

    root = tk.Tk()
    root.geometry("820x640")
    root.minsize(660, 540)

    Dashboard(root, store)
    root.mainloop()


if __name__ == "__main__":
    main()
