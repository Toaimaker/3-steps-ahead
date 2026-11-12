"""La tela sulla scheda video, con l'interfaccia della tela di Tk (Autore, 9 nov 2026: «e se spostassimo sulla scheda video?», poi «Sì, prototipo» e
«Sì, portalo»).

Card view (`tavolo_carte.py`) disegna e legge il mouse con una trentina di funzioni della tela di Tk. TelaGPU le ha tutte, con lo stesso nome e lo stesso
comportamento, ma disegna con OpenGL (pyglet) in una finestra figlia messa dentro la finestra di Tk al posto della tela: cosi' la logica di Card view (pile,
contatore, connessioni, ⇄, salvataggio, ricerca) resta quella provata, e le sue prove girano uguali. Tk ricompone a ogni movimento le immagini trasparenti che la
carta tocca (10-11 ms); qui ogni immagine e' una texture caricata una volta, e spostarla cambia due numeri (il prototipo, `foglio_gpu.py`: 0,2 ms a fotogramma).

Cosa fa: gli elementi (immagini, testi, linee con la freccia, rettangoli) coi loro tag, l'ordine di disegno (tag_raise, tag_lower), move, coords, delete, bbox,
find_withtag («current» compreso), find_overlapping, find_all, gettags, type, itemcget, itemconfigure (state, text); la vista (canvasx, canvasy, xview_moveto,
yview_moveto, xview_scroll, scan_mark, scan_dragto: senza bordi, come Card view); gli eventi coi nomi di Tk (<ButtonPress-1>, <B1-Motion>, <ButtonRelease-1>,
<Double-Button-1>, 2 e 3, <Motion>, <Leave>, <MouseWheel>, <Control-MouseWheel>, <Shift-MouseWheel>, <Configure>) con x, y, x_root, y_root, state, delta.
Le immagini vengono dalle PhotoImage dell'app: chi le fa registra la sorgente PIL (`registra`, e `disegni.Disegno.foto` lo fa da solo). I testi si disegnano con
PIL coi font dell'app (Poppins in `Companion/Grafica`) e diventano texture. Le linee e le punte delle frecce sono forme della scheda, con l'antialias MSAA.
Se pyglet o la scheda non partono, `crea` restituisce la tela di Tk di sempre.

`--prova`: elementi, tag e ordine, move e bbox, hit test, la vista, gli eventi tradotti (doppio clic compreso), testi e immagini come texture, con le negative."""
import os, sys
_casa = os.path.dirname(os.path.abspath(__file__))      # si sale fino a percorsi.py, che mette nel sys.path tutte le cartelle del Companion
while not os.path.isfile(os.path.join(_casa, "percorsi.py")):
    _casa = os.path.dirname(_casa)
if _casa not in sys.path:
    sys.path.insert(0, _casa)
import percorsi  # noqa: E402
import ctypes
import math
import time

SORGENTI = {}           # nome della PhotoImage -> immagine PIL RGBA: da li' la texture
_TEX = {}               # nome della PhotoImage o chiave del testo -> texture (le finestre di pyglet condividono gli oggetti della scheda)
_TELE = []              # le tele aperte: il giro le pompa tutte
_FONT_PIL = {}          # (file, pixel) -> il font di PIL, caricato una volta
_GIRO = {"id": None, "root": None}
GRAFICA = os.path.join(percorsi.ROOT, "Companion", "Grafica")
FONT = {"Poppins Medium": os.path.join(GRAFICA, "Poppins-Medium.ttf"), "Poppins": os.path.join(GRAFICA, "Poppins-Regular.ttf"),
        "Segoe UI": r"C:\Windows\Fonts\segoeui.ttf"}
VSYNC = os.environ.get("TELA_VSYNC", "1") == "1"      # i fotogrammi al ritmo del monitor: niente strappi; TELA_VSYNC=0 per misurare il costo vero
CURSORI = {"fleur": "size", "hand2": "hand", "sb_v_double_arrow": "size_up_down", "": None, None: None}


def errore(dove):
    """Un errore della tela: la finestra gira senza console (pythonw), quindi va su file, col traceback (Log_Arena/tela_gpu_errori.txt)."""
    import traceback
    try:
        with open(os.path.join(percorsi.ROOT, "Log_Arena", "tela_gpu_errori.txt"), "a", encoding="utf-8") as g:
            g.write(time.strftime("%Y-%m-%d %H:%M:%S ") + dove + chr(10) + traceback.format_exc() + chr(10))
    except OSError:
        pass


class Chiave:
    """La chiave di un'immagine registrata solo per la scheda (niente PhotoImage di Tk): create_image(image=Chiave(...), scala=...)."""

    def __init__(self, nome):
        self.nome = nome

    def __str__(self):
        return self.nome


def registra_pil(nome, pil):
    """Un'immagine PIL per la tela sulla scheda, senza PhotoImage. -> la Chiave da passare a create_image."""
    SORGENTI[nome] = pil
    return Chiave(nome)


def registra(foto, pil):
    """La sorgente PIL di una PhotoImage, per la tela sulla scheda. Restituisce la PhotoImage. La sorgente se ne va con la PhotoImage (11 nov 2026, sessione
    Magic 13: ogni immagine di disegni.py, grafici compresi, restava qui per sempre: 60 finestre di un mazzo, +32 MB)."""
    n = str(foto)
    SORGENTI[n] = pil
    try:
        import weakref
        weakref.finalize(foto, SORGENTI.pop, n, None)
    except TypeError:       # un oggetto senza riferimenti deboli: resta finche' non lo si dimentica a mano
        pass
    return foto


def dimentica(foto):
    """La PhotoImage non serve piu': via la sorgente e la texture."""
    n = str(foto)
    SORGENTI.pop(n, None)
    t = _TEX.pop(n, None)
    if t is not None:
        try:
            t.delete()
        except Exception:
            pass


def _pyglet():
    """pyglet, col controllo degli errori di OpenGL spento: e' un'opzione di debug che a ogni chiamata chiede alla scheda se c'e' un errore (il profilo: l'80% del
    fotogramma, 69.000 chiamate in 60 fotogrammi). Va spento prima che pyglet carichi il suo modulo gl."""
    import pyglet
    pyglet.options["debug_gl"] = False
    try:
        import pyglet.window.win32 as pw
        if not isinstance(pw._priority_events, _Tutti):
            pw._priority_events = _Tutti()
    except Exception:
        pass
    return pyglet


class _Tutti:
    """Al posto della lista dei messaggi «prioritari» di pyglet: tutti lo sono. I messaggi della finestra di pyglet li consegna il ciclo di Tk (vedi
    TelaGPU.pompa), e la parte Windows di pyglet deve rispondere subito (WM_PAINT validato, cattura, cursore), se no un WM_PAINT messo in coda torna
    all'infinito e root.update() non finisce piu'. Gli eventi verso il nostro codice (on_mouse_press...) restano in coda: BaseWindow.dispatch_event li
    trattiene finche' _allow_dispatch_event e' spento, e li consegna il giro della tela, fuori dalla procedura della finestra."""

    def __contains__(self, msg):
        return True


def disponibile():
    """La scheda video si usa solo su Windows: la tela di pyglet si incastra nella finestra di Tk con SetParent e le finestre di Windows (_view_hwnd). Su Mac
    il Board resta sulla tela di Tk, con le stesse prove (TAVOLO_TK=1)."""
    if sys.platform != "win32":
        return False
    try:
        _pyglet()
        return True
    except Exception:
        return False


def crea(tk, padre, **kw):
    """La tela sulla scheda video, o quella di Tk se la scheda non parte (TAVOLO_TK=1 nell'ambiente la impone)."""
    if os.environ.get("TAVOLO_TK") != "1" and disponibile():
        try:
            return TelaGPU(tk, padre, bg=kw.get("bg", "#202024"))
        except Exception as e:
            print("tela sulla scheda video non partita, resta Tk:", e)
    return tk.Canvas(padre, **kw)


def _rgba(c, alfa=255):
    if c in (None, ""):
        return None
    c = c.lstrip("#")
    if len(c) == 3:
        c = "".join(x * 2 for x in c)
    return (int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16), alfa)


def _tasto(vk):
    try:
        return bool(ctypes.windll.user32.GetKeyState(vk) & 0x8000)
    except Exception:
        return False


class Evento:
    def __init__(self, **kw):
        self.__dict__.update(kw)


_BATCH = []


def batch_che_tiene(tetto=300):
    """Un Batch di pyglet che non butta i domini vuoti (11 nov 2026). Il Board si ridisegna tutto: cancella ogni elemento e lo rifa' subito, con gli stessi
    gruppi d'ordine. pyglet a ogni fotogramma toglieva i domini rimasti vuoti e al disegno dopo li ricreava, coi loro buffer sulla scheda (90 per ridisegno,
    ~25 ms). Qui un dominio vuoto resta pronto (si «disegna» senza vertici: costa una chiamata); oltre tetto domini vuoti si fa la pulizia di pyglet, cosi' la memoria non cresce."""
    if not _BATCH:
        import pyglet

        class BatchCheTiene(pyglet.graphics.Batch):
            def _update_draw_list(self):
                try:
                    return self._tieni()
                except Exception:       # un pyglet diverso da quello provato (2.1.19): la pulizia sua, come prima
                    return super()._update_draw_list()

            def _tieni(self):
                vuoti = sum(1 for dm in self.group_map.values() for d in dm.values() if d.is_empty)
                if vuoti > self.tetto:
                    return super()._update_draw_list()

                def visit(group):
                    draw_list = []
                    domain_map = self.group_map[group]
                    for (_ix, _inst, mode, _f), domain in domain_map.items():      # anche i vuoti: pyglet non segna da ridisegnare quando un dominio
                        draw_list.append((lambda d, m: lambda: d.draw(m))(domain, mode))      # che c'e' gia' riceve vertici (lo fa solo per i domini nuovi)
                    children = self.group_children.get(group)
                    if children:
                        children.sort()
                        for child in list(children):
                            if child.visible:
                                draw_list.extend(visit(child))
                    return [group.set_state, *draw_list, group.unset_state] if draw_list else []
                self.top_groups.sort()
                self._draw_list = []
                for group in list(self.top_groups):
                    if group.visible:
                        self._draw_list.extend(visit(group))
                self._draw_list_dirty = False
        _BATCH.append(BatchCheTiene)
    b = _BATCH[0]()
    b.tetto = tetto
    return b


class TelaGPU:
    """La tela. Il frame di Tk sta nel layout al posto della tela; la finestra di pyglet ci sta dentro come figlia (SetParent) e ne segue la misura.
    Coordinate: quelle della tela di Tk, con la y in giu' (la proiezione della scheda e' capovolta apposta) e la vista (vx, vy) come canvasx(0), canvasy(0)."""

    def __init__(self, tk, padre, bg="#202024"):
        pyglet = _pyglet()
        from pyglet import gl
        self.pyglet, self.gl, self.tk = pyglet, gl, tk
        self.frame = tk.Frame(padre, bg=bg, highlightthickness=0, bd=0)
        self.bg = _rgba(bg)
        try:
            cfg = gl.Config(sample_buffers=1, samples=8, double_buffer=True)
            self.w = pyglet.window.Window(64, 64, style=pyglet.window.Window.WINDOW_STYLE_BORDERLESS, visible=False, vsync=VSYNC, config=cfg)
        except Exception:
            self.w = pyglet.window.Window(64, 64, style=pyglet.window.Window.WINDOW_STYLE_BORDERLESS, visible=False, vsync=VSYNC)
        self.batch = batch_che_tiene()
        self.batch_fisso = pyglet.graphics.Batch()      # lo strato fisso: coordinate della finestra, sopra tutto, non segue pan e zoom (l'HUD del Board)
        # lo strato senza zoom (12 nov 2026, Autore: «sistema lo zoom sideboard»): finche' dura lo zoom immediato della rotella gli elementi coi tag di
        # senza_zoom (la fascia della sideboard del Board) passano qui e si disegnano con la vista senza lo zoom, sopra il foglio; poi tornano al loro posto
        self.batch_banda = pyglet.graphics.Batch()
        self.tag_senza_zoom = set()
        self._banda = False
        self.el = {}                # id -> elemento
        self.per_tag = {}           # tag -> gli id che lo hanno: _ids non scorre tutti gli elementi (10 nov 2026: move costava 0,7 ms a chiamata con 500 elementi)
        self.ord = []               # gli id in ordine di disegno
        self.prossimo = 1
        self.legami = {}            # "<ButtonPress-1>" -> [funzioni]
        self.vx = self.vy = 0.0
        self.zk, self.ztx, self.zty = 1.0, 0.0, 0.0      # lo zoom immediato: schermo = zk * (tela - vista) + zt, finche' Card view non ridisegna
        self.sr = (0, 0, 1, 1)
        self.mark = None
        self.sporco = True
        self.attaccata = False
        self.puntatore = (-1e9, -1e9)
        self.ultimo_clic = (0.0, 0, 0)
        self._gruppi = {}
        # la riserva degli sprite (11 nov 2026): un elemento cancellato lascia il suo sprite nascosto, e un elemento nuovo con la stessa immagine allo stesso
        # posto nell'ordine di disegno lo riprende. Il Board si ridisegna tutto (cancella e rifa'), e pyglet rifaceva ogni volta i suoi blocchi di vertici
        # (90 domini per ridisegno, il 60% del tempo). Quel che avanza si cancella prima del fotogramma (_svuota_riserva)
        self._riuso = {}
        self._cursore = None
        try:
            self.scala_font = float(padre.tk.call("tk", "scaling"))      # pixel per punto, come Tk misura i font
        except Exception:
            self.scala_font = 1.333
        w = self.w
        w.on_mouse_press = self._premi
        w.on_mouse_release = self._rilascia
        w.on_mouse_drag = self._trascina
        w.on_mouse_motion = self._muovi
        w.on_mouse_leave = lambda x, y: self._manda("<Leave>", self._ev(x, y))
        w.on_mouse_scroll = self._rotella
        w.on_key_press = self._tasto
        w.on_draw = self._disegna
        w.on_resize = lambda a, b: None         # la vista la fa _disegna
        self.frame.bind("<Configure>", self._misura, add="+")
        self.frame.bind("<Map>", lambda e: self._attacca(), add="+")
        self.frame.bind("<Destroy>", self._distruggi, add="+")
        if not _TELE:       # il timer di Windows a 1 ms: con quello normale (15,6 ms) il giro «ogni 4 ms» girava ogni 20 ms, 49 volte al secondo
            try:
                ctypes.windll.winmm.timeBeginPeriod(1)
            except Exception:
                pass
        _TELE.append(self)
        self._avvia_giro(padre)

    # ------------------------------------------------ la finestra figlia e il giro
    def _attacca(self):
        if self.attaccata or not self.frame.winfo_exists():
            return
        u = ctypes.windll.user32
        hwnd = self.w._hwnd
        u.SetParent(hwnd, self.frame.winfo_id())
        GWL_STYLE, WS_CHILD, WS_VISIBLE, WS_CLIPSIBLINGS = -16, 0x40000000, 0x10000000, 0x04000000
        u.SetWindowLongW(hwnd, GWL_STYLE, WS_CHILD | WS_VISIBLE | WS_CLIPSIBLINGS)
        self.attaccata = True
        self._misura()
        self.w.set_visible(True)

    def _misura(self, e=None):
        if not self.attaccata:
            if self.frame.winfo_ismapped():
                self._attacca()
            return
        L, H = max(1, self.frame.winfo_width()), max(1, self.frame.winfo_height())
        ctypes.windll.user32.MoveWindow(self.w._hwnd, 0, 0, L, H, True)
        self.sporco = True
        self._manda("<Configure>", Evento(width=L, height=H, widget=self))

    def _distruggi(self, e=None):
        if e is not None and e.widget is not self.frame:
            return
        if self in _TELE:
            _TELE.remove(self)
            if not _TELE:
                try:
                    ctypes.windll.winmm.timeEndPeriod(1)
                except Exception:
                    pass
        for k in list(self.el):
            self._via(k)
        try:
            self.w.close()
        except Exception:
            pass

    def _avvia_giro(self, padre):
        """Il giro sta sulla radice dell'app, mai sulla finestra della tela: fino al 10 nov 2026 stava sul Toplevel della prima tela aperta, e chiusa quella finestra
        Tk ne cancellava i comandi, compreso l'after del giro; _GIRO["id"] restava pieno, la tela nuova non lo faceva ripartire e il Card view riaperto restava
        nero. Ora riparte anche se non batte da mezzo secondo."""
        vivo = _GIRO["id"] is not None and time.time() - _GIRO.get("battito", 0.0) < 0.5
        if not vivo:
            vecchio = _GIRO.get("root")
            if _GIRO["id"] is not None and vecchio is not None:
                try:
                    vecchio.after_cancel(_GIRO["id"])
                except Exception:
                    pass
            _GIRO["root"] = padre._root()
            _GIRO["id"] = None
            _giro()

    def pompa(self):
        """Un giro: gli eventi della finestra e, se qualcosa e' cambiato, un fotogramma.
        I messaggi di Windows li distribuisce Tk (il suo ciclo prende quelli di tutto il thread, anche della finestra di pyglet, che li mette in coda):
        qui si consegnano solo gli eventi gia' in coda. MAI w.dispatch_events(): fa PeekMessage su tutto il thread e, siccome Tk fa girare i suoi
        after anche dentro il ciclo modale con cui Windows sposta una finestra, si mangiava i movimenti del mouse e il rilascio di quel ciclo:
        Card view non si spostava trascinando la barra del titolo e restava agganciata al mouse (9 nov 2026)."""
        w = self.w
        try:
            w.switch_to()
            w._allow_dispatch_event = True
            try:
                w.dispatch_pending_events()
            finally:
                w._allow_dispatch_event = False
            if self.sporco and self.attaccata:
                self.sporco = False
                self._disegna()
                w.flip()
        except Exception:
            errore("giro della tela")

    def _svuota_riserva(self):
        """Gli sprite della riserva che nessuno ha ripreso se ne vanno davvero."""
        if self._riuso:
            for lista in self._riuso.values():
                for o in lista:
                    try:
                        o.delete()
                    except Exception:
                        pass
            self._riuso = {}

    def _disegna(self):
        from pyglet.math import Mat4, Vec3
        self._svuota_riserva()
        gl, w = self.gl, self.w
        L, H = w.get_framebuffer_size()
        gl.glViewport(0, 0, L, H)
        r, g, b, _a = self.bg
        gl.glClearColor(r / 255, g / 255, b / 255, 1)
        w.clear()
        w.projection = Mat4.orthogonal_projection(0, w.width, w.height, 0, -8192, 8192)      # la y in giu', come Tk
        w.view = (Mat4.from_translation(Vec3(self.ztx, self.zty, 0)) @ Mat4.from_scale(Vec3(self.zk, self.zk, 1))
                  @ Mat4.from_translation(Vec3(-self.vx, -self.vy, 0)))
        self.batch.draw()
        if self._banda:         # lo strato senza zoom: la vista com'e', senza lo zoom immediato
            w.view = Mat4.from_translation(Vec3(-self.vx, -self.vy, 0))
            self.batch_banda.draw()
        w.view = Mat4()         # lo strato fisso: in coordinate della finestra
        self.batch_fisso.draw()

    # ------------------------------------------------ gli eventi, coi nomi di Tk
    def bind(self, seq, f=None, add=None):
        if f is None:
            return self.legami.get(seq)
        if add:
            self.legami.setdefault(seq, []).append(f)
        else:
            self.legami[seq] = [f]

    def tag_bind(self, *a, **k):        # Card view non lo usa piu': il clic unico decide dalla geometria
        pass

    def _ev(self, x, y, **kw):
        ty = self.w.height - y
        st = (0x1 if _tasto(0x10) else 0) | (0x4 if _tasto(0x11) else 0)
        return Evento(x=x, y=ty, x_root=self.frame.winfo_rootx() + x, y_root=self.frame.winfo_rooty() + ty, state=st, widget=self, **kw)

    def _manda(self, seq, e):
        for f in self.legami.get(seq, []):
            try:
                if f(e) == "break":
                    break
            except Exception:
                errore(f"evento {seq}")
        self.sporco = True

    def _bottone(self, b):
        m = self.pyglet.window.mouse
        return 1 if b == m.LEFT else 2 if b == m.MIDDLE else 3 if b == m.RIGHT else 0

    def _premi(self, x, y, b, mod):
        n = self._bottone(b)
        e = self._ev(x, y)
        self.puntatore = (self.canvasx(e.x), self.canvasy(e.y))
        # niente SetCapture qui: la cattura del mouse la fa gia' pyglet sulla sua finestra interna (_view_hwnd). Il 9 nov 2026 la tela la prendeva sulla finestra
        # esterna: da li' Windows mandava ogni clic e movimento dell'app a una finestra che non li gestisce, il rilascio non arrivava mai e tutto era bloccato
        try:
            self.frame.focus_set()      # il fuoco torna a Tk: i tasti li riceve la finestra del Board
        except Exception:
            pass
        if n == 1:
            t, px, py = self.ultimo_clic
            doppio = time.time() - t < 0.35 and abs(px - x) < 5 and abs(py - y) < 5 and "<Double-Button-1>" in self.legami
            self.ultimo_clic = (0.0 if doppio else time.time(), x, y)
            if doppio:
                return self._manda("<Double-Button-1>", e)
        self._manda(f"<ButtonPress-{n}>", e)

    def _rilascia(self, x, y, b, mod):
        self._manda(f"<ButtonRelease-{self._bottone(b)}>", self._ev(x, y))

    def _trascina(self, x, y, dx, dy, bottoni, mod):
        m = self.pyglet.window.mouse
        e = self._ev(x, y)
        self.puntatore = (self.canvasx(e.x), self.canvasy(e.y))
        for n, b in ((1, m.LEFT), (2, m.MIDDLE), (3, m.RIGHT)):
            if bottoni & b:
                self._manda(f"<B{n}-Motion>", e)

    def _muovi(self, x, y, dx, dy):
        e = self._ev(x, y)
        self.puntatore = (self.canvasx(e.x), self.canvasy(e.y))
        if "<Motion>" in self.legami:
            self._manda("<Motion>", e)

    def _rotella(self, x, y, sx, sy):
        e = self._ev(x, y, delta=int(120 * (sy or sx)))
        if e.state & 0x4 and "<Control-MouseWheel>" in self.legami:
            return self._manda("<Control-MouseWheel>", e)
        if e.state & 0x1 and "<Shift-MouseWheel>" in self.legami:
            return self._manda("<Shift-MouseWheel>", e)
        self._manda("<MouseWheel>", e)

    def _tasto(self, simbolo, mod):
        """I tasti che arrivano alla finestra della scheda: Esc e le lettere (A e F del Board, 10 nov 2026) vanno a chi li ha legati sulla tela, direttamente.
        Generarli sulla finestra di Tk non basta: quando il fuoco di Windows e' sulla finestra della scheda, Tk non ha il fuoco e scarta i tasti generati."""
        k = self.pyglet.window.key
        try:
            if simbolo == k.ESCAPE:
                if "<Escape>" in self.legami:
                    self._manda("<Escape>", Evento(keysym="Escape", widget=self))
                else:
                    self.frame.winfo_toplevel().event_generate("<Escape>")
            elif k.A <= simbolo <= k.Z:     # con Ctrl e Maiuscolo nello stato, come Tk (Ctrl+Z e Ctrl+Y del Board, 12 nov 2026)
                st = (0x1 if mod & k.MOD_SHIFT else 0) | (0x4 if mod & k.MOD_CTRL else 0)
                self._manda("<Key>", Evento(keysym=chr(ord("a") + simbolo - k.A), state=st, widget=self))
        except Exception:
            errore("tasto")
        return True

    # ------------------------------------------------ i metodi di Tk che non disegnano
    def pack(self, **kw):
        self.frame.pack(**kw)

    def after(self, ms, f=None, *a):
        return self.frame.after(ms, f, *a) if f else self.frame.after(ms)

    def after_cancel(self, i):
        self.frame.after_cancel(i)

    def after_idle(self, f, *a):
        return self.frame.after_idle(f, *a)

    def winfo_width(self):
        return self.frame.winfo_width()

    def winfo_height(self):
        return self.frame.winfo_height()

    def winfo_rootx(self):
        return self.frame.winfo_rootx()

    def winfo_rooty(self):
        return self.frame.winfo_rooty()

    def winfo_exists(self):
        return self.frame.winfo_exists()

    def update_idletasks(self):
        self.frame.update_idletasks()

    def focus_set(self):
        pass

    def configure(self, **kw):
        if "scrollregion" in kw:
            self.sr = tuple(float(v) for v in kw["scrollregion"])
        if "cursor" in kw and kw["cursor"] != self._cursore:
            self._cursore = kw["cursor"]
            nome = CURSORI.get(kw["cursor"])
            try:
                w = self.w
                w.set_mouse_cursor(w.get_system_mouse_cursor(nome) if nome else None)
            except Exception:
                pass
        if "bg" in kw:
            self.bg = _rgba(kw["bg"])
            self.frame.configure(bg=kw["bg"])
        self.sporco = True

    config = configure

    def cget(self, k):
        if k == "scrollregion":
            return " ".join(str(v) for v in self.sr)
        return self.frame.cget(k)

    # ------------------------------------------------ la vista: senza bordi
    def canvasx(self, x):
        return (x - self.ztx) / self.zk + self.vx

    def canvasy(self, y):
        return (y - self.zty) / self.zk + self.vy

    def senza_zoom(self, tags):
        """I tag degli elementi che lo zoom immediato non ingrandisce (la fascia della sideboard e le sue carte): restano dove sono, alla loro misura."""
        tags = set(tags)
        if tags == self.tag_senza_zoom:
            return
        vecchi, self.tag_senza_zoom = self.tag_senza_zoom, tags
        if self._banda:
            for e in self.el.values():
                if bool(set(e["tags"]) & vecchi) != bool(set(e["tags"]) & tags):
                    self._costruisci(e)

    def _in_banda(self, e):
        return self._banda and not e.get("fisso") and bool(self.tag_senza_zoom.intersection(e["tags"]))

    def _strato_banda(self, acceso):
        """Accende o spegne lo strato senza zoom: gli elementi coi tag di senza_zoom passano di strato (si rifanno, nell'ordine di sempre)."""
        if self._banda == acceso:
            return
        self._banda = acceso
        if self.tag_senza_zoom:
            for e in self.el.values():
                if not e.get("fisso") and self.tag_senza_zoom.intersection(e["tags"]):
                    self._costruisci(e)

    def zoom_immediato(self, r, px, py):
        """Lo zoom subito, sulla scheda: tutto si ingrandisce di r intorno al punto (px, py) della finestra, senza ridisegnare niente, tranne lo strato senza zoom
        (senza_zoom). Si somma agli scatti di prima; azzera_zoom lo toglie quando Card view ha ridisegnato alla misura nuova."""
        self._strato_banda(True)
        self.zk *= r
        self.ztx = px + (self.ztx - px) * r
        self.zty = py + (self.zty - py) * r
        self.sporco = True

    def azzera_zoom(self):
        self.zk, self.ztx, self.zty = 1.0, 0.0, 0.0
        self._strato_banda(False)
        self.sporco = True

    def xview_moveto(self, f):
        self.vx = self.sr[0] + f * (self.sr[2] - self.sr[0]); self.sporco = True

    def yview_moveto(self, f):
        self.vy = self.sr[1] + f * (self.sr[3] - self.sr[1]); self.sporco = True

    def xview_scroll(self, n, cosa="units"):
        self.vx += n * 30; self.sporco = True

    def yview_scroll(self, n, cosa="units"):
        self.vy += n * 30; self.sporco = True

    def scan_mark(self, x, y):
        self.mark = (x, y, self.vx, self.vy)

    def scan_dragto(self, x, y, gain=10):
        mx, my, vx, vy = self.mark
        self.vx, self.vy = vx - (x - mx) * gain, vy - (y - my) * gain
        self.sporco = True

    # ------------------------------------------------ gli elementi
    def _nuovo(self, tipo, coords, tags, **opz):
        i = self.prossimo
        self.prossimo += 1
        if isinstance(tags, str):
            tags = (tags,)
        fisso = bool(opz.pop("fisso", False))
        e = dict(id=i, tipo=tipo, c=list(coords), tags=tuple(tags or ()), opz=opz, stato=opz.pop("state", "normal"), obj=[], ord=float(len(self.ord) and self.el[self.ord[-1]]["ord"] + 1),
                 fisso=fisso)
        self.el[i] = e
        for tg in e["tags"]:
            self.per_tag.setdefault(tg, set()).add(i)
        self.ord.append(i)
        self._costruisci(e)
        self.sporco = True
        return i

    def _gruppo(self, o):
        g = self._gruppi.get(o)
        if g is None:
            g = self._gruppi[o] = self.pyglet.graphics.Group(order=o)
        return g

    def _texture(self, chiave, pil, mip=False):
        t = _TEX.get(chiave)
        if t is None:
            import pyglet
            from pyglet import gl
            dati = pyglet.image.ImageData(pil.width, pil.height, "RGBA", pil.tobytes(), pitch=pil.width * 4)     # le righe dall'alto: con la y in giu' esce dritta
            t = dati.get_texture()
            gl.glBindTexture(t.target, t.id)
            if mip:         # una texture che la scheda rimpicciolisce (le carte a 2x): le mipmap, se no i dettagli sfarfallano
                gl.glGenerateMipmap(t.target)
                gl.glTexParameteri(t.target, gl.GL_TEXTURE_MIN_FILTER, gl.GL_LINEAR_MIPMAP_LINEAR)
            else:
                gl.glTexParameteri(t.target, gl.GL_TEXTURE_MIN_FILTER, gl.GL_LINEAR)
            gl.glTexParameteri(t.target, gl.GL_TEXTURE_MAG_FILTER, gl.GL_LINEAR)
            _TEX[chiave] = t
        return t

    def _testo_pil(self, e):
        """Il testo come immagine PIL: font dell'app, misura in punti come Tk, a capo sulla larghezza."""
        from PIL import Image, ImageDraw, ImageFont
        o = e["opz"]
        font = o.get("font") or ("Segoe UI", 9)
        fam, size = font[0], font[1]
        grassetto = len(font) > 2 and "bold" in str(font[2:])
        px = -size if size < 0 else round(size * self.scala_font)
        file_ = FONT.get(fam) or FONT["Segoe UI"]
        if grassetto and fam == "Poppins":
            file_ = FONT["Poppins Medium"]
        f = _FONT_PIL.get((file_, max(6, px)))
        if f is None:
            try:
                f = ImageFont.truetype(file_, max(6, px))
            except OSError:
                f = ImageFont.load_default()
            _FONT_PIL[(file_, max(6, px))] = f
        testo = str(o.get("text", ""))
        larg = o.get("width")
        righe = []
        for par in testo.split("\n"):
            if larg:
                riga = ""
                for parola in par.split(" "):
                    prova = (riga + " " + parola).strip()
                    if riga and f.getlength(prova) > larg:
                        righe.append(riga); riga = parola
                    else:
                        riga = prova
                righe.append(riga)
            else:
                righe.append(par)
        asc, desc = f.getmetrics()
        alto = asc + desc
        L = max(1, int(math.ceil(max(f.getlength(r) for r in righe)))) + 2
        im = Image.new("RGBA", (L, alto * len(righe) + 2), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        col = _rgba(o.get("fill") or "#000000")
        for k, r in enumerate(righe):
            x = (L - f.getlength(r)) / 2 if o.get("justify") == "center" else 0
            d.text((x + 1, 1 + k * alto), r, font=f, fill=col)
        return im

    def _ancora(self, x, y, l, h, anchor):
        """Dove va l'angolo in alto a sinistra per l'ancora di Tk (nw, n, ne, w, center, e, sw, s, se). «center» non va letto lettera per lettera."""
        a = anchor or "center"
        if a == "center":
            return x - l / 2, y - h / 2
        dx = 0 if "w" in a else -l if "e" in a else -l / 2
        dy = 0 if "n" in a else -h if "s" in a else -h / 2
        return x + dx, y + dy

    def _sprite(self, tex, x, y, b, g, e, k=1.0):
        """Uno sprite: dalla riserva se ce n'e' uno con la stessa immagine allo stesso posto nell'ordine (stesso gruppo), se no nuovo."""
        lista = self._riuso.get((e["ord"], id(tex), id(b)))
        if lista:
            s = lista.pop()
            s.position = (x, y, s.z)
            if s.scale != k:
                s.scale = k
            s.visible = True
            return s
        s = self.pyglet.sprite.Sprite(tex, x=x, y=y, batch=b, group=g)
        if k != 1.0:
            s.scale = k
        return s

    def _costruisci(self, e):
        """Gli oggetti di pyglet dell'elemento, nell'ordine di disegno."""
        from pyglet import shapes
        for o in e["obj"]:
            o.delete()
        e["obj"] = []
        g = self._gruppo(e["ord"])
        b = self.batch_fisso if e.get("fisso") else self.batch_banda if self._in_banda(e) else self.batch
        o, c = e["opz"], e["c"]
        if e["tipo"] == "image":
            foto = o.get("image")
            pil = SORGENTI.get(str(foto))
            if pil is None:
                e["box"] = (c[0], c[1], c[0], c[1])
                return
            k = o.get("scala") or 1.0
            tex = self._texture(str(foto), pil, mip=k != 1.0)
            L, H = pil.width * k, pil.height * k
            x, y = self._ancora(c[0], c[1], L, H, o.get("anchor"))
            s = self._sprite(tex, x, y, b, g, e, k)
            e["obj"] = [s]
            e["box"] = (x, y, x + L, y + H)
        elif e["tipo"] == "text":
            chiave = ("testo", str(o.get("text")), str(o.get("font")), o.get("fill"), o.get("width"), o.get("justify"))
            tex = _TEX.get(chiave)
            if tex is None:         # il testo si disegna con PIL una volta sola: poi la sua immagine e' gia' sulla scheda (10 nov 2026: era un terzo del disegno)
                tex = self._texture(chiave, self._testo_pil(e))
            x, y = self._ancora(c[0], c[1], tex.width, tex.height, o.get("anchor"))
            e["obj"] = [self._sprite(tex, x, y, b, g, e)]
            e["box"] = (x, y, x + tex.width, y + tex.height)
        elif e["tipo"] == "line":
            col = _rgba(o.get("fill") or "#000000")
            lw = float(o.get("width") or 1)
            pts = list(zip(c[0::2], c[1::2]))
            if o.get("arrow") == "last" and len(pts) >= 2:
                d1, d2, d3 = o.get("arrowshape") or (8, 10, 3)
                (ax, ay), (bx, by) = pts[-2], pts[-1]
                lung = math.hypot(bx - ax, by - ay) or 1
                ux, uy = (bx - ax) / lung, (by - ay) / lung
                base = (bx - ux * d1, by - uy * d1)
                pts = pts[:-1] + [base]
                dietro = (bx - ux * d2, by - uy * d2)
                px, py = -uy * d3, ux * d3
                e["obj"].append(shapes.Triangle(bx, by, dietro[0] + px, dietro[1] + py, dietro[0] - px, dietro[1] - py, color=col[:3], batch=b, group=g))
            dash = o.get("dash")
            for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
                if dash:
                    pieno, vuoto = dash[0], dash[1] if len(dash) > 1 else dash[0]
                    lung = math.hypot(x1 - x0, y1 - y0) or 1
                    t = 0.0
                    while t < lung:
                        t1 = min(lung, t + pieno)
                        e["obj"].append(shapes.Line(x0 + (x1 - x0) * t / lung, y0 + (y1 - y0) * t / lung, x0 + (x1 - x0) * t1 / lung, y0 + (y1 - y0) * t1 / lung,
                                                    thickness=lw, color=col[:3], batch=b, group=g))
                        t = t1 + vuoto
                else:
                    e["obj"].append(shapes.Line(x0, y0, x1, y1, thickness=lw, color=col[:3], batch=b, group=g))
            xs, ys = c[0::2], c[1::2]
            m = lw / 2 + (o.get("arrowshape") or (0, 0, 0))[2] if o.get("arrow") else lw / 2
            e["box"] = (min(xs) - m, min(ys) - m, max(xs) + m, max(ys) + m)
        elif e["tipo"] == "rectangle":
            x0, y0, x1, y1 = min(c[0], c[2]), min(c[1], c[3]), max(c[0], c[2]), max(c[1], c[3])
            if o.get("fill"):
                e["obj"].append(shapes.Rectangle(x0, y0, x1 - x0, y1 - y0, color=_rgba(o["fill"])[:3], batch=b, group=g))
            lw = float(o.get("width", 1) or 0)
            if o.get("outline") and lw > 0:
                col = _rgba(o["outline"])[:3]
                if o.get("dash"):
                    for (a0, b0), (a1, b1) in (((x0, y0), (x1, y0)), ((x1, y0), (x1, y1)), ((x1, y1), (x0, y1)), ((x0, y1), (x0, y0))):
                        pieno, vuoto = o["dash"][0], o["dash"][1] if len(o["dash"]) > 1 else o["dash"][0]
                        lung = math.hypot(a1 - a0, b1 - b0) or 1
                        t = 0.0
                        while t < lung:
                            t1 = min(lung, t + pieno)
                            e["obj"].append(shapes.Line(a0 + (a1 - a0) * t / lung, b0 + (b1 - b0) * t / lung, a0 + (a1 - a0) * t1 / lung, b0 + (b1 - b0) * t1 / lung,
                                                        thickness=lw, color=col, batch=b, group=g))
                            t = t1 + vuoto
                else:
                    e["obj"].append(shapes.Box(x0, y0, x1 - x0, y1 - y0, thickness=lw, color=col, batch=b, group=g))
            e["box"] = (x0, y0, x1, y1)
        if e["stato"] == "hidden":
            for ob in e["obj"]:
                ob.visible = False

    def create_image(self, x, y, image=None, anchor="center", tags=(), scala=None, **k):
        """scala: l'immagine disegnata a quella scala dalla scheda (le carte: texture a 2x, scala zoom/2), senza rifarla a ogni zoom."""
        return self._nuovo("image", (x, y), tags, image=image, anchor=anchor, scala=scala, **k)

    def create_text(self, x, y, tags=(), **k):
        return self._nuovo("text", (x, y), tags, **k)

    def create_line(self, *c, tags=(), **k):
        c = c[0] if len(c) == 1 else c
        return self._nuovo("line", c, tags, **k)

    def create_rectangle(self, x0, y0, x1, y1, tags=(), **k):
        return self._nuovo("rectangle", (x0, y0, x1, y1), tags, **k)

    def _ids(self, t):
        """Gli id di un tag o di un id, in ordine di disegno."""
        if t == "all":
            return list(self.ord)
        if isinstance(t, int):
            return [t] if t in self.el else []
        if t == "current":
            x, y = self.puntatore
            for i in reversed(self.ord):
                e = self.el[i]
                b = e.get("box")
                if e["stato"] != "hidden" and b and b[0] <= x <= b[2] and b[1] <= y <= b[3]:
                    return [i]
            return []
        ids = self.per_tag.get(t)
        if not ids:
            return []
        el = self.el
        return sorted(ids, key=lambda i: el[i]["ord"])       # in ordine di disegno: l'ordine dei numeri e' quello di self.ord

    def find_withtag(self, t):
        return tuple(self._ids(t))

    def find_all(self):
        return tuple(self.ord)

    def find_overlapping(self, x0, y0, x1, y1):
        out = []
        for i in self.ord:
            e = self.el[i]
            b = e.get("box")
            if e.get("fisso"):      # lo strato fisso e' in coordinate della finestra: non e' sul foglio
                continue
            if e["stato"] != "hidden" and b and b[0] <= x1 and x0 <= b[2] and b[1] <= y1 and y0 <= b[3]:
                out.append(i)
        return tuple(out)

    def gettags(self, i):
        ids = self._ids(i)
        return self.el[ids[0]]["tags"] if ids else ()

    def type(self, i):
        ids = self._ids(i)
        return self.el[ids[0]]["tipo"] if ids else None

    def bbox(self, t):
        bs = [self.el[i]["box"] for i in self._ids(t) if self.el[i].get("box") and self.el[i]["stato"] != "hidden"]
        if not bs:
            return None
        return (int(math.floor(min(b[0] for b in bs))), int(math.floor(min(b[1] for b in bs))), int(math.ceil(max(b[2] for b in bs))), int(math.ceil(max(b[3] for b in bs))))

    def coords(self, i, *c):
        ids = self._ids(i)
        if not ids:
            return []
        e = self.el[ids[0]]
        if not c:
            return list(e["c"])
        e["c"] = list(c[0] if len(c) == 1 else c)
        self._costruisci(e)
        self.sporco = True

    def move(self, t, dx, dy):
        for i in self._ids(t):
            e = self.el[i]
            e["c"] = [v + (dx if k % 2 == 0 else dy) for k, v in enumerate(e["c"])]
            b = e.get("box")
            if b:
                e["box"] = (b[0] + dx, b[1] + dy, b[2] + dx, b[3] + dy)
            for o in e["obj"]:
                if hasattr(o, "x2"):            # una linea: le due estremita'
                    o.x, o.y, o.x2, o.y2 = o.x + dx, o.y + dy, o.x2 + dx, o.y2 + dy
                elif hasattr(o, "x3"):          # una punta
                    o.x, o.y, o.x2, o.y2, o.x3, o.y3 = o.x + dx, o.y + dy, o.x2 + dx, o.y2 + dy, o.x3 + dx, o.y3 + dy
                elif hasattr(o, "position") and hasattr(o, "image"):       # uno sprite: posizione in un passo solo, i vertici si rifanno una volta
                    p_ = o.position
                    o.position = (p_[0] + dx, p_[1] + dy) + tuple(p_[2:])
                else:
                    o.x, o.y = o.x + dx, o.y + dy
        self.sporco = True

    def _via(self, i):
        e = self.el.pop(i, None)
        if e is None:
            return
        for tg in e["tags"]:
            ids = self.per_tag.get(tg)
            if ids is not None:
                ids.discard(i)
                if not ids:
                    del self.per_tag[tg]
        for o in e["obj"]:
            try:
                if hasattr(o, "image") and hasattr(o, "position") and len(self._riuso) < 3000:      # uno sprite: nella riserva, nascosto
                    o.visible = False
                    self._riuso.setdefault((e["ord"], id(o.image), id(o.batch)), []).append(o)
                else:
                    o.delete()
            except Exception:
                pass
        if i in self.ord:
            self.ord.remove(i)

    def delete(self, t):
        for i in self._ids(t):
            self._via(i)
        self.sporco = True

    def itemcget(self, i, k):
        ids = self._ids(i)
        if not ids:
            return ""
        e = self.el[ids[0]]
        return e["stato"] if k == "state" else e["opz"].get(k, "")

    def itemconfigure(self, t, **k):
        """Lo stato vale per TUTTI gli elementi del tag: fino al 9 nov 2026 si toglieva da k al primo, e dal secondo in poi restava com'era (trascinando una
        carta le sue frecce vecchie restavano a vista fino al rilascio)."""
        k = dict(k)
        stato = k.pop("state") if "state" in k else None
        for i in self._ids(t):
            e = self.el[i]
            if stato is not None:
                e["stato"] = stato or "normal"
                for o in e["obj"]:
                    o.visible = e["stato"] != "hidden"
            if k:
                e["opz"].update(k)
                self._costruisci(e)
        self.sporco = True

    itemconfig = itemconfigure

    def _riordina(self, ids, sopra):
        """Gli elementi ids in cima (sopra=True) o in fondo, nell'ordine che avevano fra loro."""
        if not ids:
            return
        resto = [i for i in self.ord if i not in set(ids)]
        self.ord = resto + ids if sopra else ids + resto
        base = (self.el[resto[-1]]["ord"] + 1) if sopra and resto else ((self.el[resto[0]]["ord"] - len(ids) - 1) if resto else 0)
        for k, i in enumerate(ids):
            e = self.el[i]
            e["ord"] = base + k
            g = self._gruppo(e["ord"])
            for o in e["obj"]:
                o.group = g
        self.sporco = True

    def _metti(self, ids, resto, pos):
        """Gli elementi ids nell'ordine di disegno alla posizione pos di resto, con un numero d'ordine fra i due vicini: gli altri elementi non cambiano gruppo.
        Fino al 10 nov 2026 si rinumeravano tutti, e ogni elemento rinumerato migrava in un altro gruppo di pyglet: il disegno intero del Board costava 135 ms."""
        n = len(ids)
        prima = self.el[resto[pos - 1]]["ord"] if pos > 0 else None
        dopo = self.el[resto[pos]]["ord"] if pos < len(resto) else None
        if prima is None and dopo is None:
            lo, hi = 0.0, float(n + 1)
        elif prima is None:
            lo, hi = dopo - n - 1, dopo
        elif dopo is None:
            lo, hi = prima, prima + n + 1
        else:
            lo, hi = prima, dopo
        passo = (hi - lo) / (n + 1)
        self.ord = resto[:pos] + ids + resto[pos:]
        if passo < 1e-7:        # i numeri fra due vicini sono finiti (tante inserzioni nello stesso punto): si rinumera tutto, una volta
            for k, i in enumerate(self.ord):
                self._ordine(i, float(k))
        else:
            for k, i in enumerate(ids):
                self._ordine(i, lo + passo * (k + 1))
        self.sporco = True

    def _ordine(self, i, o):
        e = self.el[i]
        if e["ord"] != o:
            e["ord"] = o
            g = self._gruppo(o)
            for ob in e["obj"]:
                ob.group = g

    def tag_raise(self, t, sopra_a=None):
        ids = self._ids(t)
        if sopra_a is None:
            return self._riordina(ids, True)
        ref = self._ids(sopra_a)
        if not ref or not ids:
            return
        resto = [i for i in self.ord if i not in set(ids)]        # subito sopra l'ultimo di sopra_a
        if ref[-1] not in resto:
            return
        self._metti(ids, resto, resto.index(ref[-1]) + 1)

    def tag_lower(self, t, sotto_a=None):
        """In fondo, o subito sotto il piu' basso di sotto_a, come in Tk (le frecce sotto le carte e sopra le label: 9 nov 2026)."""
        ids = self._ids(t)
        if sotto_a is None:
            return self._riordina(ids, False)
        ref = set(self._ids(sotto_a))
        if not ref or not ids:
            return
        resto = [i for i in self.ord if i not in set(ids)]
        pos = next((k for k, i in enumerate(resto) if i in ref), None)
        if pos is None:
            return
        self._metti(ids, resto, pos)

def _giro():
    """Il giro di tutte le tele, chiamato dal ciclo di Tk ogni 2 ms (col timer a 1 ms): eventi e fotogrammi; col vsync il flip aspetta il monitor."""
    root = _GIRO["root"]
    _GIRO["battito"] = time.time()
    for t in list(_TELE):
        t.pompa()
    if _TELE and root is not None:
        try:
            _GIRO["id"] = root.after(2, _giro)
            return
        except Exception:
            pass
    _GIRO["id"] = None


def _pompa_vecchia(self):
    """Per la prova negativa: il giro com'era fino al 9 nov 2026 sera, con w.dispatch_events() (PeekMessage su tutto il thread)."""
    w = self.w
    try:
        w.switch_to()
        w.dispatch_events()
        if self.sporco and self.attaccata:
            self.sporco = False
            self._disegna()
            w.flip()
    except Exception:
        errore("giro della tela (vecchio)")


def _sposta_finestra(root, t, tasti=10):
    """Sposta la finestra di root con lo spostamento vero di Windows: WM_SYSCOMMAND SC_MOVE (il ciclo modale che parte anche trascinando la barra
    del titolo) e le frecce, poi Invio, tutti messaggi messi nella coda del thread. Se il ciclo resta appeso (i messaggi rubati) dopo 1,5 s un
    WM_CANCELMODE lo chiude, cosi' la prova non si blocca. Rimette il puntatore dov'era (lo spostamento da tastiera lo muove).
    Restituisce i pixel di cui si e' mossa la finestra e se la finestra di pyglet (esterna e interna) sta ancora sul frame."""
    from ctypes import wintypes
    u = ctypes.windll.user32
    pt = wintypes.POINT()
    u.GetCursorPos(ctypes.byref(pt))
    fr = int(root.wm_frame(), 16)

    def rett(h):
        r = wintypes.RECT()
        u.GetWindowRect(ctypes.c_void_p(h), ctypes.byref(r))
        return r.left, r.top
    x0 = root.winfo_rootx()
    salva = root.after(1500, lambda: u.SendMessageW(fr, 0x001F, 0, 0))       # WM_CANCELMODE
    u.PostMessageW(fr, 0x0112, 0xF010, 0)                                     # WM_SYSCOMMAND, SC_MOVE
    for _ in range(tasti):
        u.PostMessageW(fr, 0x0100, 0x27, 0)                                   # WM_KEYDOWN, freccia destra
    u.PostMessageW(fr, 0x0100, 0x0D, 0)                                       # Invio: fine dello spostamento
    t0 = time.time()
    while time.time() - t0 < 1.8:
        root.update()
        time.sleep(0.005)
    try:
        root.after_cancel(salva)
    except Exception:
        pass
    u.SetCursorPos(pt.x, pt.y)
    dx = root.winfo_rootx() - x0
    f = (t.frame.winfo_rootx(), t.frame.winfo_rooty())
    return dx, rett(t.w._hwnd) == f and rett(t.w._view_hwnd) == f


def _avvia_vecchio(self, padre):
    """Per la prova negativa: l'avvio del giro com'era fino al 10 nov 2026 (sul Toplevel della prima tela)."""
    if _GIRO["id"] is None:
        _GIRO["root"] = padre.winfo_toplevel()
        _giro()


def chiudi_e_riapri(tk, root, avvio=None):
    """Una tela in una finestra, la finestra chiusa, una tela nuova in un'altra finestra: la nuova deve disegnare. -> True se ha disegnato."""
    giusto = TelaGPU._avvia_giro
    if avvio is not None:
        TelaGPU._avvia_giro = avvio
    try:
        def gira(sec):
            fine = time.time() + sec
            while time.time() < fine:
                root.update(); time.sleep(0.005)
        a = tk.Toplevel(root); a.geometry("300x200+5000+700")
        ta = TelaGPU(tk, a); ta.pack(fill="both", expand=True)
        gira(0.3)
        a.destroy()
        gira(0.3)
        b = tk.Toplevel(root); b.geometry("300x200+5000+700")
        tb = TelaGPU(tk, b); tb.pack(fill="both", expand=True)
        gira(0.3)
        tb.sporco = True
        gira(0.3)
        disegnata = not tb.sporco
        b.destroy()
        gira(0.2)
        return disegnata
    finally:
        TelaGPU._avvia_giro = giusto


def prova_riserva(t, root, foto):
    """La riserva degli sprite e i domini che restano (11 nov 2026): lo sprite cancellato e rifatto e' lo stesso, il dominio di una forma pure, e quel che
    torna in un dominio rimasto vuoto si disegna davvero (il pixel letto dalla scheda). Negativa: col Batch di pyglet il dominio si rifa'."""
    from pyglet import gl
    casi = []

    def giro():
        t.sporco = True; t.pompa()

    def pixel(x, y):
        t.w.switch_to(); t._disegna()
        buf = (gl.GLubyte * 4)()
        gl.glReadPixels(int(x), int(t.w.get_framebuffer_size()[1] - y - 1), 1, 1, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE, buf)
        return tuple(buf[:3])

    def domini(b):
        return {id(d) for dm in b.group_map.values() for d in dm.values()}
    s0 = t.create_image(400, 50, image=foto, anchor="nw", tags="ris"); o0 = t.el[s0]["obj"][0]
    t.delete("ris")
    s1 = t.create_image(420, 60, image=foto, anchor="nw", tags="ris"); o1 = t.el[s1]["obj"][0]
    casi.append(("riserva: lo sprite cancellato e rifatto e' lo stesso, al posto nuovo e visibile", o1 is o0 and o1.visible and t.bbox(s1) == (420, 60, 460, 90)
                 and tuple(round(v) for v in o1.position[:2]) == (420, 60)))
    t.delete("ris"); giro()
    casi.append(("riserva: quel che nessuno riprende se ne va al fotogramma", not t._riuso))
    r0 = t.create_rectangle(400, 200, 440, 240, fill="#00ff00", width=0, tags="dom"); giro()
    prima = domini(t.batch)
    t.delete("dom"); giro()
    casi.append(("il dominio rimasto vuoto resta nel Batch", domini(t.batch) == prima))
    r1 = t.create_rectangle(400, 200, 440, 240, fill="#00ff00", width=0, tags="dom")
    casi.append(("la forma rifatta riprende il dominio, nessuno nuovo", domini(t.batch) == prima))
    px = pixel(420, 220)
    casi.append(("e si disegna davvero (il pixel letto dalla scheda e' verde)", px[1] > 200 and px[0] < 60))
    t.delete("dom"); giro()
    import pyglet
    b_ = pyglet.graphics.Batch(); g_ = pyglet.graphics.Group(order=0)
    from pyglet import shapes
    q = shapes.Rectangle(0, 0, 10, 10, color=(1, 2, 3), batch=b_, group=g_); d0 = domini(b_)
    q.delete(); b_._update_draw_list()
    q = shapes.Rectangle(0, 0, 10, 10, color=(1, 2, 3), batch=b_, group=g_)
    casi.append(("negativa: col Batch di pyglet il dominio vuoto se ne va e si rifa'", domini(b_) != d0))
    del r0, r1
    return casi


def prova():
    import tkinter as tk
    from PIL import Image, ImageTk
    casi = []
    root0 = tk.Tk(); root0.withdraw()
    casi.append(("chiusa una finestra con la tela, la tela riaperta in un'altra si disegna (il giro riparte)", chiudi_e_riapri(tk, root0)))
    _GIRO.update(id=None, root=None)
    casi.append(("negativa: col giro sulla finestra della prima tela, la tela riaperta resta nera", not chiudi_e_riapri(tk, root0, _avvia_vecchio)))
    root0.destroy()
    _GIRO.update(id=None, root=None)
    root = tk.Tk(); root.geometry("800x600+5000+20")
    t = TelaGPU(tk, root, bg="#202024")
    t.pack(fill="both", expand=True)
    root.update()
    for _ in range(20):
        root.update(); time.sleep(0.01)
    pil = Image.new("RGBA", (40, 30), (200, 50, 50, 255))
    foto = registra(ImageTk.PhotoImage(pil), pil)
    a = t.create_image(10, 20, image=foto, anchor="nw", tags=("carta", "c1"))
    b = t.create_rectangle(100, 100, 150, 140, fill="#ffffff", outline="#000000", width=2, tags="r")
    tx = t.create_text(50, 200, text="Prova 4x", fill="#ffffff", font=("Poppins Medium", 9), anchor="nw", tags=("carta", "c1"))
    ln = t.create_line(0, 0, 100, 0, fill="#d6ac2e", width=2, arrow="last", arrowshape=(11, 13, 4), tags="rete_viva")
    casi.append(("le immagini con la loro misura e l'ancora", t.bbox(a) == (10, 20, 50, 50)))
    cen = t.create_image(100, 100, image=foto, tags="cen")
    casi.append(("l'ancora «center» (quella di Tk se non la scrivi) mette il centro sul punto", t.bbox(cen) == (80, 85, 120, 115)))
    t.delete("cen")
    casi.append(("i tag: find_withtag e gettags", t.find_withtag("c1") == (a, tx) and "carta" in t.gettags(a)))
    t.move("c1", 5, 7)
    casi.append(("move sposta tutto il tag", t.bbox(a) == (15, 27, 55, 57) and t.coords(a) == [15, 27]))
    casi.append(("il testo diventa un'immagine con la sua misura", t.bbox(tx)[2] - t.bbox(tx)[0] > 30 and t.type(tx) == "text"))
    casi.append(("find_overlapping nel suo ordine", t.find_overlapping(120, 120, 121, 121) == (b,) and t.find_overlapping(0, 0, 1, 1) == (ln,)))
    t.tag_raise("c1")
    casi.append(("tag_raise porta in cima", t.find_all()[-2:] == (a, tx)))
    t.tag_lower("r")
    casi.append(("tag_lower porta in fondo", t.find_all()[0] == b))
    t.tag_lower(ln, "c1")
    tutti_ = t.find_all()
    casi.append(("tag_lower sotto un tag: subito sotto il suo piu' basso, come in Tk", tutti_.index(ln) == tutti_.index(a) - 1 and tutti_[0] == b))
    t.itemconfigure("rete_viva", state="hidden")
    casi.append(("lo stato nascosto non conta per l'hit test", t.find_overlapping(0, 0, 1, 1) == () and t.itemcget(ln, "state") == "hidden"))
    l2 = t.create_line(0, 300, 100, 300, fill="#d6ac2e", width=2, tags="rete_viva")
    t.itemconfigure("rete_viva", state="hidden")
    casi.append(("lo stato vale per TUTTI gli elementi del tag, non solo il primo", all(t.itemcget(i, "state") == "hidden" for i in (ln, l2))
                 and not any(o.visible for i in (ln, l2) for o in t.el[i]["obj"])))
    t.delete(l2)
    t.itemconfigure(ln, state="normal")       # un elemento nascosto non ha bbox, come in Tk
    t.coords(ln, 0, 50, 200, 50)
    casi.append(("coords rifa' la linea", t.bbox(ln)[1] < 50 < t.bbox(ln)[3]))
    t.configure(scrollregion=(0, 0, 2000, 1000))
    t.xview_moveto(0.5)
    casi.append(("la vista: xview_moveto e canvasx", t.canvasx(0) == 1000))
    t.scan_mark(0, 0); t.scan_dragto(-300, -200, gain=1)
    casi.append(("scan_dragto senza bordi", t.canvasx(0) == 1300 and t.canvasy(0) == 200))
    t.scan_mark(0, 0); t.scan_dragto(5000, 5000, gain=1)
    casi.append(("anche in negativo", t.canvasx(0) < 0 and t.canvasy(0) < 0))
    t.xview_moveto(0); t.yview_moveto(0)
    visti = []
    t.bind("<ButtonPress-1>", lambda e: visti.append(("p", e.x, e.y)))
    t.bind("<Double-Button-1>", lambda e: visti.append(("d", e.x, e.y)))
    t.bind("<MouseWheel>", lambda e: visti.append(("w", e.delta)))
    H = t.w.height
    t._premi(30, H - 40, t.pyglet.window.mouse.LEFT, 0); t._rilascia(30, H - 40, t.pyglet.window.mouse.LEFT, 0)
    t._premi(31, H - 41, t.pyglet.window.mouse.LEFT, 0); t._rilascia(31, H - 41, t.pyglet.window.mouse.LEFT, 0)
    casi.append(("il clic arriva con la y di Tk, il secondo vicino e' un doppio clic", visti[:2] == [("p", 30, 40), ("d", 31, 41)]))
    time.sleep(0.4)
    t._premi(31, H - 41, t.pyglet.window.mouse.LEFT, 0)
    casi.append(("negativa: dopo una pausa e' un clic semplice", visti[-1] == ("p", 31, 41)))
    t._rotella(10, 10, 0, 1)
    casi.append(("la rotella col delta di Tk", visti[-1] == ("w", 120)))
    t.puntatore = (20, 30)
    casi.append(("«current» e' l'elemento sotto il puntatore", t.find_withtag("current") == (a,)))
    t.delete("c1")
    casi.append(("delete toglie il tag", not t.find_withtag("c1") and len(t.find_all()) == 2))
    for _ in range(5):
        root.update(); time.sleep(0.01)
    casi += prova_riserva(t, root, foto)
    big = Image.new("RGBA", (80, 60), (50, 200, 50, 255))
    ch = registra_pil("prova:2x", big)
    sc = t.create_image(300, 300, image=ch, anchor="nw", scala=0.5, tags="sc")
    casi.append(("un'immagine con la scala: misura e bbox scalate", t.bbox(sc) == (300, 300, 340, 330)))
    t.delete("sc")
    vx0 = t.canvasx(100)
    t.zoom_immediato(2.0, 100, 100)
    casi.append(("lo zoom immediato tiene fermo il punto sotto il puntatore", abs(t.canvasx(100) - vx0) < 1e-9 and abs(t.canvasx(300) - (vx0 + 100)) < 1e-9))
    t.azzera_zoom()
    casi.append(("azzerato, la vista torna quella di prima", t.canvasx(300) == vx0 + 200))
    fa_ = t.create_rectangle(10, 10, 60, 40, fill="#ff00ff", tags=("fascia_p",))
    fo_ = t.create_rectangle(10, 10, 60, 40, fill="#00ffff", tags=("foglio_p",))
    t.senza_zoom({"fascia_p"})
    prima_ = t.el[fa_]["obj"][0].batch is t.batch
    t.zoom_immediato(2.0, 100, 100)
    casi.append(("lo strato senza zoom: durante lo zoom immediato la fascia passa nel suo strato, il foglio resta (12 nov 2026)",
                 prima_ and t.el[fa_]["obj"][0].batch is t.batch_banda and t.el[fo_]["obj"][0].batch is t.batch))
    t._disegna()
    t.azzera_zoom()
    casi.append(("azzerato lo zoom, la fascia torna nello strato del foglio; negativa: senza i tag resta sempre li'",
                 t.el[fa_]["obj"][0].batch is t.batch and (t.senza_zoom(set()), t.zoom_immediato(2.0, 100, 100), t.el[fa_]["obj"][0].batch is t.batch)[2]))
    t.azzera_zoom(); t.delete("fascia_p"); t.delete("foglio_p")
    casi.append(("la finestra figlia sta dentro il frame", t.attaccata))
    t.xview_moveto(0); t.yview_moveto(0)
    fx = t.create_rectangle(10, 10, 60, 40, fill="#ff0000", tags="hud", fisso=True)
    nf = t.create_rectangle(10, 10, 60, 40, fill="#00ff00", tags="foglio")
    t.scan_mark(0, 0); t.scan_dragto(-300, -200, gain=1)
    casi.append(("lo strato fisso: nello strato sopra, fuori dalla ricerca sul foglio, la vista non lo sposta", t.el[fx]["obj"][0].batch is t.batch_fisso
                 and fx not in t.find_overlapping(0, 0, 100, 100) and nf in t.find_overlapping(0, 0, 100, 100) and t.bbox(fx) == (10, 10, 60, 40)))
    t.delete("hud"); t.delete("foglio"); t.xview_moveto(0); t.yview_moveto(0)
    lettere = []
    t.bind("<Key>", lambda e: lettere.append(e.keysym))
    t._tasto(t.pyglet.window.key.F, 0); t._tasto(t.pyglet.window.key.A, 0)
    for _ in range(5):
        root.update(); time.sleep(0.01)
    casi.append(("le lettere premute sulla finestra della scheda arrivano a chi le ha legate sulla tela (A e F del Board)", lettere[-2:] == ["f", "a"]))
    # i messaggi veri di Windows alla finestra interna di pyglet: il clic arriva, e il mouse si cattura sulla finestra giusta e si libera al rilascio
    u = ctypes.windll.user32
    u.GetCapture.restype = ctypes.c_void_p
    vista = t.w._view_hwnd
    lp = lambda x, y: (y << 16) | (x & 0xFFFF)
    visti.clear()
    t.bind("<ButtonRelease-1>", lambda e: visti.append(("r", e.x, e.y)))
    t.ultimo_clic = (0.0, 0, 0)
    u.PostMessageW(vista, 0x0201, 1, lp(60, 70))
    for _ in range(10):
        root.update(); time.sleep(0.01)
    presa = u.GetCapture()
    u.PostMessageW(vista, 0x0202, 0, lp(60, 70))
    for _ in range(10):
        root.update(); time.sleep(0.01)
    casi.append(("un clic vero di Windows arriva coi nomi di Tk", ("p", 60, 70) in visti and ("r", 60, 70) in visti))
    casi.append(("premuto, il mouse e' della finestra interna (mai di quella esterna)", presa in (vista, None, 0) and presa != t.w._hwnd))
    casi.append(("lasciato, il mouse e' libero", not u.GetCapture()))
    # la finestra si sposta con lo spostamento vero di Windows (il ciclo modale di SC_MOVE, da tastiera) e il foglio la segue
    dx, dentro = _sposta_finestra(root, t)
    casi.append(("spostata da Windows, la finestra si muove", dx > 0))
    casi.append(("e il foglio sulla scheda si muove con lei", dentro))
    giusta = TelaGPU.pompa
    TelaGPU.pompa = _pompa_vecchia                   # il giro di prima del 9 nov sera, che svuotava i messaggi di tutto il thread
    try:
        dx_neg, _d = _sposta_finestra(root, t)
    finally:
        TelaGPU.pompa = giusta
    casi.append(("negativa: col giro che svuota i messaggi del thread la finestra non si sposta", dx_neg == 0))
    root.destroy()
    casi.append(("chiuso il frame, la tela esce dal giro", t not in _TELE))
    ok = sum(1 for _n, v in casi if v)
    for n, v in casi:
        print(("ok    " if v else "ROSSO ") + n)
    print(f"{ok}/{len(casi)}")
    return ok == len(casi)


if __name__ == "__main__":
    if "--prova" in sys.argv:
        sys.exit(0 if prova() else 1)
