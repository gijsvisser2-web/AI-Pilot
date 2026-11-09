"""Workshop 3 Mail: gebruik elkaars oplossing (digitale testkaart).

Alle teksten staan in inhoud_mail3.yaml.
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

STAPPEN = [
    "Start",
    "1. Zet je test klaar",
    "2. Deel je testopdracht",
    "3. Testronde 1",
    "4. Testronde 2",
    "5. Pas 1 ding aan",
    "6. Besluit en showcase",
]
LAATSTE = len(STAPPEN) - 1

st.set_page_config(page_title=C["titel"], page_icon="✉", layout="centered")
ss = st.session_state
ss.setdefault("stap", 0)
ss.setdefault("gestart", False)


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


def kort(keuze):
    return (keuze or "").split(":")[0]


def rol_in(r):
    """Rol in ronde r. Ronde 2 is automatisch de andere rol."""
    eerste = ss.get("rol1")
    if r == 1 or not eerste:
        return eerste
    rollen = S["ronde"]["rollen"]
    return rollen[1] if eerste == rollen[0] else rollen[0]


def g(k):
    v = ss.get(k)
    return v.strip() if isinstance(v, str) else ""


def testopdracht():
    k, d = S["klaarzetten"], S["delen"]
    regels = [f"{d['kop']} van: {g('functie')}, {g('afdeling')}", ""]
    regels.append("Wat het moet opleveren (de lat): " + (g("opleveren") or "-"))
    if ss.get("vorm") == k["vormen"][0]:
        regels.append(vul_in(d["zo_agent"], agent=g("agent")))
    else:
        regels.append(vul_in(d["zo_prompt"], waar=g("waar")))
        regels += ["", "Prompt:", g("prompt") or "-"]
    regels.append("")
    for i, naam in enumerate(k["test_namen"]):
        regels.append(naam)
        regels.append("  Voer in: " + (g(f"invoer{i}") or "-"))
    regels += [d["test4"], "", d["tester_instructie"]]
    return "\n".join(regels)


def uitkomst_kort():
    uit = [ss.get(f"m_uit{i}") for i in range(4)]
    gedaan = [u for u in uit if u]
    if not gedaan:
        return ""
    werkte = sum(1 for u in gedaan if u == "Werkte")
    return f"{werkte} van {len(gedaan)} tests werkten"


def maker_frame():
    s = S["ronde"]
    k = S["klaarzetten"]
    st.info(s["maker_intro"])
    namen = k["test_namen"] + [s["test4_naam"]]
    uitkomsten = []
    for i, naam in enumerate(namen):
        st.markdown(f"**{naam}**")
        if i < 3 and g(f"invoer{i}"):
            st.caption("Invoer: " + g(f"invoer{i}"))
        uitkomsten.append(bewaar_keuze(s["uitkomst_label"], s["uitkomst_opties"], f"m_uit{i}", horizontal=True))
        bewaar_tekst(s["mis_label"], f"m_mis{i}")
    magniet_fout = bewaar_keuze(s["magniet_vraag"], s["magniet_opties"], "m_magniet", horizontal=True)
    oorzaak = bewaar_keuze(s["oorzaak_vraag"], s["oorzaken"], "m_oorzaak")
    if oorzaak:
        st.caption(s["wat_nu"][kort(oorzaak)])
    bewaar_tekst(s["herstel_label"], "m_herstel")
    ding = bewaar_tekst(s["ding_label"], "m_ding")
    return all(uitkomsten) and bool(magniet_fout) and bool(oorzaak) and bool(ding)


def tester_frame():
    s = S["ronde"]
    st.info(s["tester_intro"])
    wat = bewaar_tekst(s["tester_oplossing_label"], "t_partner")
    bewaar_tekst(s["tester_test4_label"], "t_test4", area=True, height=70)
    gebruik = bewaar_keuze(s["gebruik_vraag"], s["gebruik_opties"], "t_gebruik")
    bewaar_tekst(s["tester_leer_label"], "t_leer", area=True, height=70)
    return bool(wat) and bool(gebruik)


def testronde(r):
    s = S["ronde"]
    st.title(s[f"titel_{r}"])
    tijd(s["tijd"])
    if r == 1:
        rol = bewaar_keuze(s["rol_vraag"], s["rollen"], "rol1", horizontal=True)
    else:
        rol = rol_in(2)
        st.markdown(f"**{vul_in(s['rol_2'], rol=(rol or '').lower())}**")
    with st.container(border=True):
        for regel in s["regels"]:
            st.markdown(f"- {regel}")
    if not rol:
        return False
    ok = maker_frame() if rol == s["rollen"][0] else tester_frame()
    waarom(s)
    return ok


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

    kop("1. Mijn testopdracht")
    tekst("Tests sinds workshop 2: " + (g("tests") or "-"))
    tekst(testopdracht())

    kop("2. Als maker")
    namen = S["klaarzetten"]["test_namen"] + [S["ronde"]["test4_naam"]]
    for i, naam in enumerate(namen):
        regel = f"{naam}: {(ss.get(f'm_uit{i}') or '-').lower()}."
        if g(f"m_mis{i}"):
            regel += " Mis: " + g(f"m_mis{i}")
        tekst(regel)
    tekst("Iets dat er niet in mocht: " + (ss.get("m_magniet") or "-"))
    tekst("Oorzaak: " + (ss.get("m_oorzaak") or "-"))
    tekst("Wat de tester zelf nog moest doen: " + g("m_herstel"))
    tekst("1 ding dat ik aanpas: " + g("m_ding"))

    kop("3. Als tester")
    tekst("De oplossing van mijn partner: " + g("t_partner"))
    tekst("Test 4: " + g("t_test4"))
    tekst("Zelf gebruiken: " + (ss.get("t_gebruik") or "-"))
    tekst("Wat ik meeneem: " + g("t_leer"))

    kop("4. Aangepast")
    tekst("Wat ik aanpaste: " + g("aangepast"))
    tekst("Werkt het nu: " + (ss.get("werkt") or "-"))

    kop("5. Besluit")
    tekst((ss.get("besluit") or "-") + ". Waarom: " + g("besluit_waarom"))
    if g("delen_waar"):
        tekst("Delen met en waar: " + g("delen_waar"))
    if g("door_wat"):
        tekst("Nodige koppeling: " + g("door_wat"))
    if g("als") or g("dan"):
        tekst(f"Als {g('als')}, dan {g('dan')}.")
    return bytes(pdf.output())


# ---------- zijbalk ----------
with st.sidebar:
    st.markdown(f"**{C['pilot']}**  \n{C['sessie']}")
    for i, naam in enumerate(STAPPEN):
        if i < ss.stap:
            st.markdown(f":green[✓ {naam}]")
        elif i == ss.stap:
            st.markdown(f":orange[**● {naam}**]")
        elif i >= 1 and not ss.gestart:
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
    if st.button("Start", type="primary"):
        if not functie or not afdeling:
            st.error("Vul eerst je functie en je afdeling in.")
        else:
            ss.gestart = True
            ss.stap = 1
            st.rerun()

elif ss.stap == 1:
    s = S["klaarzetten"]
    st.title(s["titel"])
    tijd(s["tijd"])
    st.write(s["intro"])
    tests = bewaar_keuze(s["tests_vraag"], s["tests_opties"], "tests", horizontal=True)
    opleveren = bewaar_tekst(s["opleveren_label"], "opleveren")
    vorm = bewaar_keuze(s["vorm_vraag"], s["vormen"], "vorm", horizontal=True)
    vorm_ok = False
    if vorm == s["vormen"][0]:
        vorm_ok = bool(bewaar_tekst(s["agent_label"], "agent"))
        st.caption(s["agent_hulp"])
    elif vorm == s["vormen"][1]:
        p = bewaar_tekst(s["prompt_label"], "prompt", area=True, height=120)
        w = bewaar_tekst(s["waar_label"], "waar", standaard=s["waar_standaard"])
        vorm_ok = bool(p) and bool(w)
    if vorm:
        st.caption(s["nieuwe_chat"])
    with st.expander(s["voorbeelden_titel"]):
        for regel in s["voorbeelden"]:
            st.markdown(f"- {regel}")
    gevuld = []
    for i, naam in enumerate(s["test_namen"]):
        st.markdown(f"**{naam}**")
        gevuld.append(bewaar_tekst(s["invoer_label"], f"invoer{i}"))
    st.caption(s["test4"])
    waarom(s)
    klaar = bewaar_vinkje(s["vinkje_klaar"], "klaar1")
    navigatie(
        bool(tests) and bool(opleveren) and vorm_ok and all(gevuld) and klaar,
        "Vul in wat je oplossing oplevert. Kies agent of prompt en vul de naam of je prompt in. Vul per test in wat de tester invoert. Zet daarna het vinkje.",
    )

elif ss.stap == 2:
    s = S["delen"]
    st.title(s["titel"])
    tijd(s["tijd"])
    st.write(s["intro"])
    st.code(testopdracht(), language=None, wrap_lines=True)
    klaar = bewaar_vinkje(s["vinkje"], "gedeeld")
    navigatie(klaar, "Zet je testopdracht open op je laptop en zet dan het vinkje.")

elif ss.stap in (3, 4):
    r = ss.stap - 2
    ok = testronde(r)
    navigatie(ok, "Kies je rol en vul je scherm in. Als maker: de 4 uitkomsten, de oorzaak en je 1 ding. Als tester: wat de oplossing doet en of je hem zelf zou gebruiken.")

elif ss.stap == 5:
    s = S["aanpassen"]
    st.title(s["titel"])
    tijd(s["tijd"])
    st.write(s["intro"])
    with st.container(border=True):
        st.markdown(f"**{s['ding_kop']}:** {g('m_ding') or '-'}")
        if ss.get("m_oorzaak"):
            st.caption(S["ronde"]["wat_nu"][kort(ss.m_oorzaak)])
    bewaar_tekst(s["gedaan_label"], "aangepast")
    bewaar_keuze(s["werkt_vraag"], s["werkt_opties"], "werkt", horizontal=True)
    waarom(s)
    navigatie()

elif ss.stap == 6:
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
    trigger_ok = True
    if besluit and kort(besluit) != "Stoppen":
        st.markdown(f"**{s['trigger_intro']}**")
        als = bewaar_tekst(s["als_label"], "als")
        dan = bewaar_tekst(s["dan_label"], "dan")
        trigger_ok = bool(als) and bool(dan)
    waarom(s)
    if bool(besluit) and bool(reden) and extra_ok and trigger_ok:
        with st.container(border=True):
            st.markdown(f"**{s['showcase_kop']}**")
            for regel in s["showcase"]:
                st.markdown(f"- {regel}")
        st.markdown("**Deel in Teams**")
        st.caption("Plak deze zin in de draad in het Teams-kanaal. Geen klantgegevens.")
        st.code(vul_in(s["teams"], oplossing=g("opleveren"), uitkomst=uitkomst_kort(), besluit=kort(besluit)), language=None, wrap_lines=True)
        st.download_button(
            "⬇ Download alles als pdf",
            data=maak_pdf(),
            file_name=f"workshop3-{date.today():%Y%m%d}.pdf",
            mime="application/pdf",
            type="primary",
        )
        st.success(s["afsluiting"])
    else:
        st.caption("Kies je besluit, schrijf op waarom en vul je trigger in (niet nodig bij stoppen). Bij delen: de veiligheidscheck. Dan zie je wat we in de showcase verwachten en verschijnt de pdf.")
    navigatie()
