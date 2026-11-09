"""Workshop 3 Mail: gebruik elkaars oplossing (digitale testkaart).

Alle teksten en het codewoord staan in inhoud_mail3.yaml.
De app slaat niets op. Invoer blijft alleen in de sessie van de deelnemer.
"""
from datetime import date
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components
import yaml
from fpdf import FPDF

MAP = Path(__file__).parent
C = yaml.safe_load((MAP / "inhoud_mail3.yaml").read_text(encoding="utf-8"))
S = C["stappen"]

STAPPEN = ["Start", "1. Bereid je test voor", "2. Testronde 1", "3. Testronde 2", "4. Besluit en volgende stap"]
LAATSTE = len(STAPPEN) - 1

st.set_page_config(page_title=C["titel"], page_icon="✉", layout="centered")
ss = st.session_state
ss.setdefault("stap", 0)
ss.setdefault("code1", False)


# ---------- hulpfuncties ----------
def bewaar_tekst(label, k, area=False, **kw):
    ss.setdefault(k, kw.pop("standaard", ""))
    veld = st.text_area if area else st.text_input
    ss[k] = veld(label, value=ss[k], key="w_" + k, **kw)
    return ss[k].strip()


def bewaar_vinkje(label, k):
    ss.setdefault(k, False)
    ss[k] = st.checkbox(label, value=ss[k], key="w_" + k)
    return ss[k]


def bewaar_keuze(label, opties, k, horizontal=False):
    ss.setdefault(k, None)
    index = opties.index(ss[k]) if ss[k] in opties else None
    ss[k] = st.radio(label, opties, index=index, key="w_" + k, horizontal=horizontal)
    return ss[k]


def vul_in(tekst, **waarden):
    for naam, waarde in waarden.items():
        tekst = tekst.replace("{" + naam + "}", waarde or f"[{naam}]")
    return tekst


def tijd(minuten):
    st.caption(f"⏱ {minuten} minuten")


def waarom(s):
    if s.get("waarom"):
        st.caption(f"💡 **Waarom zo?** {s['waarom']}")


def navigatie(mag_door=True, reden=""):
    links, rechts, _ = st.columns([1, 1, 3])
    if ss.stap > 1:
        links.button("Terug", on_click=lambda: ss.update(stap=ss.stap - 1), use_container_width=True)
    if ss.stap < LAATSTE:
        if rechts.button("Volgende", type="primary", use_container_width=True):
            if mag_door:
                ss.stap += 1
                st.rerun()
            else:
                st.error(reden or "Je bent nog niet klaar met deze stap.")


def codewoord_ok(invoer, juist):
    return invoer.strip().upper().replace(" ", "") == juist.strip().upper().replace(" ", "")


def kort(keuze):
    return (keuze or "").split(":")[0]


def testronde(r):
    """Scherm voor testronde r (1 of 2). Geeft True als alles verplicht is ingevuld."""
    s = S["ronde"]
    st.title(s[f"titel_{r}"])
    tijd(s["tijd"])
    st.write(s["intro"])
    with st.container(border=True):
        for regel in s["regels"]:
            st.markdown(f"- {regel}")
    waarom(s)
    maker, tester = st.tabs([s["maker_tab"], s["tester_tab"]])
    with maker:
        uitkomsten = []
        for i, naam in enumerate(S["voorbereiden"]["test_namen"]):
            st.markdown(f"**{naam}**")
            moet = ss.get(f"moet{i}", "")
            magniet = ss.get(f"magniet{i}", "")
            if moet or magniet:
                st.caption(f"Moet erin: {moet or '-'}. Mag er niet in: {magniet or '-'}.")
            uitkomsten.append(bewaar_keuze("Uitkomst", s["uitkomst_opties"], f"r{r}_uit{i}", horizontal=True))
        magniet_fout = bewaar_keuze(s["magniet_vraag"], s["magniet_opties"], f"r{r}_magniet", horizontal=True)
        oorzaak = bewaar_keuze(s["oorzaak_vraag"], s["oorzaken"], f"r{r}_oorzaak")
        bewaar_tekst(s["herstel_label"], f"r{r}_herstel")
        ding = bewaar_tekst(s["ding_label"], f"r{r}_ding")
    with tester:
        bewaar_tekst(s["tester_oplossing_label"], f"r{r}_partner")
        gebruik = bewaar_keuze(s["gebruik_vraag"], s["gebruik_opties"], f"r{r}_gebruik")
        bewaar_tekst(s["tester_leer_label"], f"r{r}_leer", area=True, height=70)
    m = bewaar_vinkje(s["vinkjes"][0], f"r{r}_m")
    t = bewaar_vinkje(s["vinkjes"][1], f"r{r}_t")
    return all(uitkomsten) and bool(magniet_fout) and bool(oorzaak) and bool(ding) and bool(gebruik) and m and t


# ---------- pdf ----------
VERVANG = {"’": "'", "‘": "'", "“": '"', "”": '"', "–": "-", "—": "-", "…": "...", "•": "-", "→": "->", "≥": ">=", "≤": "<="}


def latin(t):
    for a, b in VERVANG.items():
        t = t.replace(a, b)
    return t.encode("latin-1", "replace").decode("latin-1")


def maak_pdf():
    pdf = FPDF(format="A4")
    pdf.set_auto_page_break(True, margin=15)
    pdf.add_page()
    w = pdf.w - pdf.l_margin - pdf.r_margin

    def kop(t, grootte=13):
        pdf.ln(3)
        pdf.set_font("Helvetica", "B", grootte)
        pdf.set_text_color(31, 42, 107)
        pdf.multi_cell(w, 7, latin(t), new_x="LMARGIN", new_y="NEXT")
        pdf.set_text_color(27, 31, 59)

    def tekst(t):
        pdf.set_font("Helvetica", "", 11)
        pdf.multi_cell(w, 6, latin(t or "-"), align="L", new_x="LMARGIN", new_y="NEXT")

    pdf.set_font("Helvetica", "B", 18)
    pdf.set_text_color(240, 110, 30)
    pdf.cell(w, 10, latin(f"{C['pilot']}: {C['titel']}"), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(90, 90, 90)
    pdf.cell(w, 6, latin(f"{C['sessie']}, {date.today():%d-%m-%Y}"), new_x="LMARGIN", new_y="NEXT")

    g = ss.get
    v = S["voorbereiden"]
    kop("1. Mijn oplossing en mijn test")
    tekst("Functie: " + g("functie", "") + ", afdeling: " + g("afdeling", ""))
    tekst("Tests sinds workshop 2: " + (g("tests") or "-"))
    tekst("Wat het moet opleveren: " + g("opleveren", ""))
    tekst("Soort oplossing: " + (g("soort") or "-"))
    for i, naam in enumerate(v["test_namen"]):
        tekst(f"{naam}. Moet erin: {g(f'moet{i}', '') or '-'}. Mag er niet in: {g(f'magniet{i}', '') or '-'}.")
    for r in (1, 2):
        kop(f"{1 + r}. Testronde {r}")
        uit = ", ".join(f"test {i + 1}: {(g(f'r{r}_uit{i}') or '-').lower()}" for i in range(3))
        tekst("Als maker: " + uit + ". Iets dat er niet in mocht: " + (g(f"r{r}_magniet") or "-") + ".")
        tekst("Oorzaak: " + (g(f"r{r}_oorzaak") or "-"))
        tekst("Wat de tester zelf nog moest doen: " + g(f"r{r}_herstel", ""))
        tekst("1 ding dat ik aanpas: " + g(f"r{r}_ding", ""))
        tekst("Als tester: " + g(f"r{r}_partner", "") + ". Zelf gebruiken: " + (g(f"r{r}_gebruik") or "-") + ".")
        if g(f"r{r}_leer", "").strip():
            tekst("Wat ik meenam: " + g(f"r{r}_leer", ""))
    kop("4. Besluit en volgende stap")
    tekst((g("besluit") or "-") + ". Waarom: " + g("besluit_waarom", ""))
    if g("delen_waar", "").strip():
        tekst("Delen met en waar: " + g("delen_waar", ""))
    if g("door_wat", "").strip():
        tekst("Nodige koppeling: " + g("door_wat", ""))
    tekst(f"Trigger: als {g('als', '')}, dan {g('dan', '')}.")
    tekst("Oplossing van een collega die ik ga gebruiken: " + (g("overnemen") or "-") + ". Eerste keer: " + g("overnemen_wanneer", ""))
    tekst("Laten zien aan: " + g("buiten", "") + ", " + g("buiten_wanneer", ""))
    return bytes(pdf.output())


# ---------- zijbalk ----------
with st.sidebar:
    st.markdown(f"**{C['pilot']}**  \n{C['sessie']}")
    for i, naam in enumerate(STAPPEN):
        if i < ss.stap:
            st.markdown(f":green[✓ {naam}]")
        elif i == ss.stap:
            st.markdown(f":orange[**● {naam}**]")
        elif i >= 1 and not ss.code1:
            st.markdown(f":gray[🔒 {naam}]")
        else:
            st.markdown(f"○ {naam}")
    st.divider()
    for w in C["zijbalk_waarschuwingen"]:
        st.markdown(f":red[{w}]")

if ss.get("_vorige_stap") != ss.stap:
    ss["_vorige_stap"] = ss.stap
    components.html(
        "<script>/*" + str(ss.stap) + "*/ const d = window.parent.document;"
        " for (const s of ['[data-testid=\"stMain\"]', 'section.main', '[data-testid=\"stAppViewContainer\"]'])"
        " { const e = d.querySelector(s); if (e) e.scrollTo(0, 0); } window.parent.scrollTo(0, 0);</script>",
        height=0,
    )

if ss.stap > 0:
    st.progress(ss.stap / LAATSTE)
    st.caption(f"Stap {ss.stap} van {LAATSTE}")

# ---------- stappen ----------
if ss.stap == 0:
    st.title(C["titel"])
    st.write(C["start"]["tekst"])
    waarom(C["start"])
    functie = bewaar_tekst(C["start"]["functie_label"], "functie")
    afdeling = bewaar_tekst(C["start"]["afdeling_label"], "afdeling", standaard=C["start"].get("afdeling_standaard", ""))
    code = st.text_input("Codewoord van Gijs", key="w_code1")
    if st.button("Start", type="primary"):
        if not functie or not afdeling:
            st.error("Vul eerst je functie en je afdeling in.")
        elif codewoord_ok(code, C["codewoord"]):
            ss.code1 = True
            ss.stap = 1
            st.rerun()
        else:
            st.error("Dit codewoord klopt niet. Vraag het aan Gijs.")

elif ss.stap == 1:
    s = S["voorbereiden"]
    st.title(s["titel"])
    tijd(s["tijd"])
    st.write(s["intro"])
    tests = bewaar_keuze(s["tests_vraag"], s["tests_opties"], "tests", horizontal=True)
    opleveren = bewaar_tekst(s["opleveren_label"], "opleveren")
    bewaar_tekst(s["input_label"], "input")
    soort = bewaar_keuze(s["soort_vraag"], s["soorten"], "soort", horizontal=True)
    if soort:
        with st.container(border=True):
            st.markdown(f"**Voorbeelden bij {soort.lower()}**")
            for regel in s["voorbeelden"][soort]:
                st.markdown(f"- {regel}")
    gevuld = []
    for i, naam in enumerate(s["test_namen"]):
        st.markdown(f"**{naam}**")
        a, b = st.columns(2)
        with a:
            gevuld.append(bewaar_tekst(s["moet_label"], f"moet{i}", area=True, height=70))
        with b:
            bewaar_tekst(s["magniet_label"], f"magniet{i}", area=True, height=70)
    waarom(s)
    klaar = bewaar_vinkje(s["vinkje"], "v1")
    navigatie(
        bool(tests) and bool(opleveren) and bool(soort) and all(gevuld) and klaar,
        "Kies hoe je tests gingen, vul in wat je oplossing oplevert en wat er bij elke test in moet staan. Zet daarna het vinkje.",
    )

elif ss.stap in (2, 3):
    r = ss.stap - 1
    ok = testronde(r)
    navigatie(ok, "Vul op het tabblad Ik was maker de 3 uitkomsten, de oorzaak en je 1 ding in. Kies op het tabblad Ik was tester of je de oplossing zelf zou gebruiken. Zet daarna beide vinkjes.")

elif ss.stap == 4:
    s = S["besluit"]
    st.title(s["titel"])
    tijd(s["tijd"])
    st.write(s["intro"])
    besluit = bewaar_keuze("Mijn besluit", s["opties"], "besluit")
    reden = bewaar_tekst(s["waarom_label"], "besluit_waarom", area=True, height=70)
    extra_ok = True
    if kort(besluit) == "Delen":
        with st.container(border=True):
            st.markdown("**Veiligheidscheck**")
            veilig = [bewaar_vinkje(t, f"veilig{i}") for i, t in enumerate(s["veilig"])]
            waar = bewaar_tekst(s["delen_label"], "delen_waar")
            st.caption(s["twijfel"])
        extra_ok = all(veilig) and bool(waar)
    elif kort(besluit) == "Doorverwijzen":
        extra_ok = bool(bewaar_tekst(s["door_label"], "door_wat"))
    st.markdown(f"**{s['trigger_intro']}**")
    als = bewaar_tekst(s["als_label"], "als")
    dan = bewaar_tekst(s["dan_label"], "dan")
    overnemen = bewaar_keuze(s["overnemen_vraag"], s["overnemen_opties"], "overnemen", horizontal=True)
    if overnemen and overnemen != s["overnemen_opties"][2]:
        bewaar_tekst(s["overnemen_label"], "overnemen_wanneer")
    st.markdown(f"**{s['buiten_intro']}**")
    buiten = bewaar_tekst(s["buiten_label"], "buiten")
    bewaar_tekst(s["buiten_wanneer"], "buiten_wanneer")
    waarom(s)
    klaar = bool(besluit) and bool(reden) and extra_ok and bool(overnemen) and bool(buiten)
    if kort(besluit) != "Stoppen":
        klaar = klaar and bool(als) and bool(dan)
    if klaar:
        st.markdown("**Deel in Teams**")
        st.caption("Plak deze zin in de draad in het Teams-kanaal. Geen klantgegevens.")
        st.code(vul_in(s["teams"], oplossing=ss.get("opleveren", ""), besluit=kort(besluit), overnemen=(overnemen or "").lower()), language=None, wrap_lines=True)
        st.download_button(
            "⬇ Download alles als pdf",
            data=maak_pdf(),
            file_name=f"workshop3-{date.today():%Y%m%d}.pdf",
            mime="application/pdf",
            type="primary",
        )
        st.success(s["afsluiting"])
    else:
        st.caption("Kies je besluit, schrijf op waarom, vul je trigger in (niet nodig bij stoppen), kies welke oplossing je overneemt en aan wie je hem laat zien. Bij delen: de veiligheidscheck. Dan verschijnt de pdf.")
    navigatie()
