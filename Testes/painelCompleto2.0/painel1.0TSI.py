"""
BAJA Motorsports Dashboard
Lê dados do Arduino via Serial e exibe em tempo real.

Uso:
  python dashboard.py                     # simulação automática (sem Arduino)
  python dashboard.py --port /dev/ttyUSB0 # conecta ao Arduino no Linux
  python dashboard.py --port COM3         # conecta ao Arduino no Windows
"""

import tkinter as tk
import serial
import threading
import time
import math
import argparse
import random

# ── Configurações ─────────────────────────────────────────────
BAUD_RATE  = 115200
BLINK_MS   = 350
RPM_MAXIMO = 6000
TEMP_WARN  = 90
TEMP_CRIT  = 110

# ── Paleta ────────────────────────────────────────────────────
BG         = "#0d0d0d"
PANEL_BG   = "#141414"
BORDER     = "#2a2a2a"
ACCENT     = "#ff6600"
GREEN      = "#00e676"
CYAN       = "#00bcd4"
YELLOW     = "#ffcc00"
RED        = "#f44336"
ORANGE     = "#ff9800"
GRAY       = "#555555"
LGRAY      = "#888888"


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
        self.lean_mixture = False   # mistura pobre
        self.connected    = False

    def update(self, rpm, speed, temp, spinning, lean_mixture=False):
        with self._lock:
            self.rpm          = rpm
            self.speed        = speed
            self.temp         = temp
            self.spinning     = spinning
            self.lean_mixture = lean_mixture

    def snapshot(self):
        with self._lock:
            return (self.rpm, self.speed, self.temp,
                    self.spinning, self.lean_mixture, self.connected)


# ══════════════════════════════════════════════════════════════
#  Leitura Serial (Arduino real)
# ══════════════════════════════════════════════════════════════
class SerialReader(threading.Thread):
    def __init__(self, store: DataStore, port: str, baud: int):
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
                            rpm   = float(parts[0])
                            speed = float(parts[1])
                            temp  = float(parts[2])
                            spin  = bool(int(parts[3]))
                            # campo 5 opcional (mistura pobre — futuro)
                            lean  = bool(int(parts[4])) if len(parts) > 4 else False
                            self.store.update(rpm, speed, temp, spin, lean)
            except Exception:
                self.store.connected = False
                time.sleep(2)


# ══════════════════════════════════════════════════════════════
#  Simulador com dados aleatórios
# ══════════════════════════════════════════════════════════════
class SimulatorReader(threading.Thread):
    def __init__(self, store: DataStore):
        super().__init__(daemon=True)
        self.store  = store
        self._rpm   = 1500.0
        self._speed = 25.0
        self._temp  = 78.0

    @staticmethod
    def _drift(val, target, noise, lo, hi):
        """Move o valor suavemente em direção ao alvo com ruído aleatório."""
        val += (target - val) * 0.08 + random.uniform(-noise, noise)
        return max(lo, min(hi, val))

    def run(self):
        self.store.connected = True

        spin_timer  = 0
        lean_timer  = 0
        next_change = time.time()
        rpm_target   = 2000.0
        speed_target = 30.0
        temp_target  = 80.0

        while True:
            now = time.time()

            # Sorteia novos alvos a cada 2–5 segundos
            if now >= next_change:
                rpm_target   = random.uniform(400,  5800)
                speed_target = random.uniform(0,    85)
                temp_target  = random.uniform(60,   125)
                next_change  = now + random.uniform(2.5, 5.0)

            self._rpm   = self._drift(self._rpm,   rpm_target,   90,  0, RPM_MAXIMO)
            self._speed = self._drift(self._speed, speed_target, 1.5, 0, 110)
            self._temp  = self._drift(self._temp,  temp_target,  0.5, 40, 135)

            # ── Patinagem ──
            spinning = self._rpm > 4200 or spin_timer > 0
            if not spinning and random.random() < 0.005:
                spin_timer = random.randint(8, 20)   # 0.8–2 s
            if spin_timer > 0:
                spin_timer -= 1

            # ── Mistura pobre (menos frequente) ──
            lean = lean_timer > 0
            if not lean and random.random() < 0.003:
                lean_timer = random.randint(12, 35)  # 1.2–3.5 s
            if lean_timer > 0:
                lean_timer -= 1

            self.store.update(self._rpm, self._speed, self._temp, spinning, lean)
            time.sleep(0.1)


# ══════════════════════════════════════════════════════════════
#  Helpers de layout
# ══════════════════════════════════════════════════════════════
def make_panel(parent, **kw):
    outer = tk.Frame(parent, bg=BORDER, padx=1, pady=1)
    inner = tk.Frame(outer, bg=PANEL_BG, **kw)
    inner.pack(fill="both", expand=True)
    return outer, inner


# ══════════════════════════════════════════════════════════════
#  Dashboard principal
# ══════════════════════════════════════════════════════════════
class Dashboard:
    def __init__(self, root: tk.Tk, store: DataStore):
        self.root  = root
        self.store = store
        self.spin_visible = True
        self.lean_visible = True

        root.title("BAJA Dashboard")
        root.configure(bg=BG)
        root.resizable(True, True)

        self._build_ui()
        self._schedule_update()
        self._schedule_blink()

    # ── Construção da UI ──────────────────────────────────────
    def _build_ui(self):
        root = self.root

        # ── Cabeçalho ──────────────────────────────────────────
        hdr = tk.Frame(root, bg=BG)
        hdr.pack(fill="x", padx=16, pady=(14, 4))
        tk.Label(hdr, text="BAJA MOTORSPORTS", bg=BG, fg=ACCENT,
                 font=("Courier New", 18, "bold")).pack(side="left")
        self.lbl_status = tk.Label(hdr, text="● DESCONECTADO", bg=BG, fg=RED,
                                   font=("Courier New", 11, "bold"))
        self.lbl_status.pack(side="right")

        # ── Barra de RPM (LED strip) ────────────────────────────
        bar_outer, bar_inner = make_panel(root)
        bar_outer.pack(fill="x", padx=16, pady=4)

        # Rótulos de zona acima da barra
        zone_row = tk.Frame(bar_inner, bg=PANEL_BG)
        zone_row.pack(fill="x", padx=14, pady=(6, 0))
        tk.Label(zone_row, text="ROTAÇÃO (RPM)", bg=PANEL_BG, fg=LGRAY,
                 font=("Courier New", 9, "bold")).pack(side="left")
        tk.Label(zone_row, text="▶ ZONA VERMELHA  4000+",
                 bg=PANEL_BG, fg=RED, font=("Courier New", 9, "bold")).pack(side="right")

        # Canvas dos segmentos LED
        self.canvas_rpm = tk.Canvas(bar_inner, bg=PANEL_BG, height=54,
                                    highlightthickness=0)
        self.canvas_rpm.pack(fill="x", padx=12, pady=(2, 0))
        self.canvas_rpm.bind("<Configure>", lambda e: self._draw_rpm_bar())

        # Marcações textuais abaixo da barra
        ticks_row = tk.Frame(bar_inner, bg=PANEL_BG)
        ticks_row.pack(fill="x", padx=14, pady=(0, 4))
        for label, anchor in [("0", "w"), ("1k", "center"), ("2k", "center"),
                                ("3k", "center"), ("4k", "center"),
                                ("5k", "center"), ("6k", "e")]:
            tk.Label(ticks_row, text=label, bg=PANEL_BG, fg=GRAY,
                     font=("Courier New", 7)).pack(side="left", expand=True)

        # Valor numérico do RPM
        self.lbl_rpm_val = tk.Label(bar_inner, text="0 rpm",
                                     bg=PANEL_BG, fg=CYAN,
                                     font=("Courier New", 20, "bold"))
        self.lbl_rpm_val.pack(pady=(0, 8))

        # ── Linha central: velocidade + RPM numérico ────────────
        mid = tk.Frame(root, bg=BG)
        mid.pack(fill="x", padx=16, pady=4)
        mid.columnconfigure(0, weight=3)
        mid.columnconfigure(1, weight=2)

        spd_outer, spd_inner = make_panel(mid)
        spd_outer.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        tk.Label(spd_inner, text="VELOCIDADE", bg=PANEL_BG, fg=LGRAY,
                 font=("Courier New", 11, "bold")).pack(pady=(12, 0))
        self.lbl_speed = tk.Label(spd_inner, text="0.0", bg=PANEL_BG, fg=GREEN,
                                  font=("Courier New", 58, "bold"))
        self.lbl_speed.pack()
        tk.Label(spd_inner, text="km/h", bg=PANEL_BG, fg=GRAY,
                 font=("Courier New", 13)).pack(pady=(0, 12))

        rpm_num_outer, rpm_num_inner = make_panel(mid)
        rpm_num_outer.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
        tk.Label(rpm_num_inner, text="RPM", bg=PANEL_BG, fg=LGRAY,
                 font=("Courier New", 11, "bold")).pack(pady=(12, 0))
        self.lbl_rpm_big = tk.Label(rpm_num_inner, text="0", bg=PANEL_BG, fg=CYAN,
                                    font=("Courier New", 44, "bold"))
        self.lbl_rpm_big.pack(expand=True)
        tk.Label(rpm_num_inner, text="rpm", bg=PANEL_BG, fg=GRAY,
                 font=("Courier New", 13)).pack(pady=(0, 12))

        # ── Linha inferior: Temp | Patinagem | Mistura pobre ────
        bot = tk.Frame(root, bg=BG)
        bot.pack(fill="x", padx=16, pady=4)
        bot.columnconfigure(0, weight=1)
        bot.columnconfigure(1, weight=1)
        bot.columnconfigure(2, weight=1)

        # Temperatura
        tmp_outer, tmp_inner = make_panel(bot)
        tmp_outer.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        tk.Label(tmp_inner, text="TEMPERATURA MOTOR", bg=PANEL_BG, fg=LGRAY,
                 font=("Courier New", 9, "bold")).pack(pady=(12, 0))
        self.lbl_temp = tk.Label(tmp_inner, text="--", bg=PANEL_BG, fg=YELLOW,
                                 font=("Courier New", 44, "bold"))
        self.lbl_temp.pack()
        self.canvas_temp_bar = tk.Canvas(tmp_inner, bg=PANEL_BG, height=8,
                                         highlightthickness=0)
        self.canvas_temp_bar.pack(fill="x", padx=16, pady=(4, 0))
        tk.Label(tmp_inner, text="°C", bg=PANEL_BG, fg=GRAY,
                 font=("Courier New", 12)).pack(pady=(2, 12))

        # Controle de tração (patinagem)
        spn_outer, spn_inner = make_panel(bot)
        spn_outer.grid(row=0, column=1, sticky="nsew", padx=5)
        tk.Label(spn_inner, text="CONTROLE DE TRAÇÃO", bg=PANEL_BG, fg=LGRAY,
                 font=("Courier New", 9, "bold")).pack(pady=(12, 0))
        self.lbl_spin_icon = tk.Label(spn_inner, text="⬟", bg=PANEL_BG,
                                      fg="#1a1a1a",
                                      font=("Courier New", 44, "bold"))
        self.lbl_spin_icon.pack(pady=(4, 0))
        self.lbl_spin_text = tk.Label(spn_inner, text="NORMAL", bg=PANEL_BG,
                                      fg=GRAY, font=("Courier New", 12, "bold"))
        self.lbl_spin_text.pack(pady=(2, 12))

        # Mistura pobre
        lean_outer, lean_inner = make_panel(bot)
        lean_outer.grid(row=0, column=2, sticky="nsew", padx=(5, 0))
        tk.Label(lean_inner, text="SENSOR DE MISTURA", bg=PANEL_BG, fg=LGRAY,
                 font=("Courier New", 9, "bold")).pack(pady=(12, 0))

        # LED circular via Canvas
        self.canvas_lean = tk.Canvas(lean_inner, bg=PANEL_BG,
                                     width=74, height=74, highlightthickness=0)
        self.canvas_lean.pack(pady=(8, 0))
        self._draw_lean_led(active=False, bright=True)

        tk.Label(lean_inner, text="MISTURA POBRE", bg=PANEL_BG, fg=LGRAY,
                 font=("Courier New", 10, "bold")).pack(pady=(6, 12))

        # ── Rodapé ─────────────────────────────────────────────
        ftr = tk.Frame(root, bg=BG)
        ftr.pack(fill="x", padx=16, pady=(0, 10))
        self.lbl_time = tk.Label(ftr, text="", bg=BG, fg=GRAY,
                                  font=("Courier New", 9))
        self.lbl_time.pack(side="right")

    # ── Barra de RPM — segmentos LED ─────────────────────────
    def _draw_rpm_bar(self, rpm_val=0):
        c = self.canvas_rpm
        w = c.winfo_width()
        h = c.winfo_height()
        if w < 20:
            return

        c.delete("all")

        N     = 52          # número de segmentos
        PAD_X = 8
        PAD_Y = 5
        gap   = 3
        bar_w = w - 2 * PAD_X
        seg_w = max(2, (bar_w - (N - 1) * gap) / N)

        pct = min(rpm_val / RPM_MAXIMO, 1.0)
        lit = int(pct * N)

        for i in range(N):
            x1 = PAD_X + i * (seg_w + gap)
            x2 = x1 + seg_w
            frac = (i + 0.5) / N       # posição relativa do segmento

            # Zonas de cor: verde → amarelo → vermelho
            if frac < 0.55:
                on_clr  = GREEN
                off_clr = "#011a0a"
            elif frac < 0.80:
                on_clr  = YELLOW
                off_clr = "#1c1600"
            else:
                on_clr  = RED
                off_clr = "#1c0000"

            fill = on_clr if i < lit else off_clr
            c.create_rectangle(x1, PAD_Y, x2, h - PAD_Y,
                               fill=fill, outline="")

        # Linha vertical marcando 4000 RPM
        mark_x = PAD_X + (4000 / RPM_MAXIMO) * bar_w
        c.create_line(mark_x, 0, mark_x, h, fill=RED, width=1, dash=(3, 3))

    # ── LED da mistura pobre ──────────────────────────────────
    def _draw_lean_led(self, active: bool, bright: bool = True):
        c  = self.canvas_lean
        c.delete("all")
        cx, cy, r = 37, 37, 30

        if active and bright:
            # Halo externo
            c.create_oval(cx - r - 8, cy - r - 8, cx + r + 8, cy + r + 8,
                          fill="#2a1400", outline="")
            body   = ORANGE
            border = "#ffcc00"
            glare  = "#ffe0a0"
        elif active:                        # piscando (fase escura)
            body   = "#3a1800"
            border = "#4a2200"
            glare  = ""
        else:                               # apagado
            body   = "#1a1200"
            border = "#333333"
            glare  = ""

        c.create_oval(cx - r, cy - r, cx + r, cy + r,
                      fill=body, outline=border, width=3)
        if glare:
            c.create_oval(cx - r + 8, cy - r + 6,
                          cx - r + 22, cy - r + 16,
                          fill=glare, outline="")

    # ── Atualização da UI (100 ms) ────────────────────────────
    def _schedule_update(self):
        self._update()
        self.root.after(100, self._schedule_update)

    def _update(self):
        rpm, speed, temp, spinning, lean, connected = self.store.snapshot()

        # Status
        if connected:
            self.lbl_status.config(text="● CONECTADO", fg=GREEN)
        else:
            self.lbl_status.config(text="● SIMULAÇÃO", fg=ORANGE)

        # Velocidade
        self.lbl_speed.config(text=f"{speed:.1f}")

        # RPM — barra + número
        self._draw_rpm_bar(rpm)
        self.lbl_rpm_val.config(text=f"{int(rpm):,} rpm")
        self.lbl_rpm_big.config(text=f"{int(rpm):,}")

        # Temperatura
        if temp > -50:
            tclr = RED if temp >= TEMP_CRIT else YELLOW if temp >= TEMP_WARN else GREEN
            self.lbl_temp.config(text=f"{temp:.0f}", fg=tclr)
            self._draw_temp_bar(temp, tclr)
        else:
            self.lbl_temp.config(text="--", fg=GRAY)

        # Horário
        self.lbl_time.config(text=time.strftime("%H:%M:%S"))

    # ── Barra de temperatura ──────────────────────────────────
    def _draw_temp_bar(self, temp, color):
        bar = self.canvas_temp_bar
        w   = bar.winfo_width()
        if w < 10:
            return
        bar.delete("all")
        bar.create_rectangle(0, 0, w, 8, fill=BORDER, outline="")
        pct = min(temp / 150.0, 1.0)
        bar.create_rectangle(0, 0, int(w * pct), 8, fill=color, outline="")

    # ── Pisca-pisca (350 ms) ──────────────────────────────────
    def _schedule_blink(self):
        self._blink()
        self.root.after(BLINK_MS, self._schedule_blink)

    def _blink(self):
        _, _, _, spinning, lean, _ = self.store.snapshot()

        # Patinagem
        if spinning:
            clr = RED if self.spin_visible else "#4a0000"
            txt = "!! PATINANDO !!"
            self.lbl_spin_icon.config(fg=clr)
            self.lbl_spin_text.config(text=txt, fg=clr)
            self.spin_visible = not self.spin_visible
        else:
            self.lbl_spin_icon.config(fg="#1a3a1a")
            self.lbl_spin_text.config(text="NORMAL", fg=GRAY)
            self.spin_visible = True

        # Mistura pobre
        if lean:
            self._draw_lean_led(active=True, bright=self.lean_visible)
            self.lean_visible = not self.lean_visible
        else:
            self._draw_lean_led(active=False)
            self.lean_visible = True


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
    root.geometry("820x600")
    root.minsize(660, 500)

    Dashboard(root, store)
    root.mainloop()


if __name__ == "__main__":
    main()
