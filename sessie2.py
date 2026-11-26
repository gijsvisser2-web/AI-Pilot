"""Sessie 2 AI-pilot: bouw je werkwijze.

Alle teksten, prompts en codewoorden staan in inhoud_sessie2.yaml (of inhoud_sessie2_<pilot>.yaml).
Kies een andere pilot met ?pilot=<naam> achter de link, bijvoorbeeld ?pilot=hr.
De app slaat niets op. Invoer blijft alleen in de sessie van de deelnemer.

Staat er in de yaml een blok "tools" met 2 opties, dan kiest de deelnemer in stap 1
waar hij zijn stap doet. Bij de 2e optie (Salesforce) gebruikt de app de teksten met _sf.
Zonder blok "tools" werkt de app alleen met Copilot.
"""
import re
from datetime import date, datetime
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components
import yaml
from fpdf import FPDF

MAP = Path(__file__).parent
TRAINER_STANDAARD = "Gijs"


def kies_bestand():
    """inhoud_sessie2_<pilot>.yaml als ?pilot=<pilot> in de link staat en het bestand bestaat, anders inhoud_sessie2.yaml."""
    try:
        pilot = str(st.query_params.get("pilot", ""))
    except Exception:
        pilot = ""
    pilot = re.sub(r"[^a-z0-9_]", "", pilot.lower())
    bestand = MAP / f"inhoud_sessie2_{pilot}.yaml"
    return bestand if pilot and bestand.exists() else MAP / "inhoud_sessie2.yaml"


def vervang(waarde, naam, tekst):
    """Vult {naam} overal in de inhoud in."""
    if isinstance(waarde, str):
        return waarde.replace("{" + naam + "}", tekst)
    if isinstance(waarde, list):
        return [vervang(w, naam, tekst) for w in waarde]
    if isinstance(waarde, dict):
        return {k: vervang(w, naam, tekst) for k, w in waarde.items()}
    return waarde


C = yaml.safe_load(kies_bestand().read_text(encoding="utf-8"))
TRAINER = (C.get("trainer") or "").strip() or TRAINER_STANDAARD
C = vervang(C, "trainer", TRAINER)
CODES = C.get("codewoorden") or {}  # leeg: geen codewoorden, deelnemers gaan zelf verder
S = C["stappen"]
TOOLS = C.get("tools")

STAPPEN = [
    "Start",
    "1. Terug naar je tests",
    "2. Schrijf je instructie",
    "3. Laat Copilot meekijken",
    "4. Test: gewoon voorbeeld",
    "5. Test: lastig voorbeeld",
    "6. Verbeter 1 ding",
    "7. Bewaar en plan",
]
LAATSTE = len(STAPPEN) - 1
SLOT_VANAF = 4  # vanaf deze stap is codewoord 2 nodig
VELDEN = ["doel", "input", "aanpak", "output"]

st.set_page_config(page_title=C["titel"], page_icon="🛠", layout="centered")
ss = st.session_state
ss.setdefault("stap", 0)
ss.setdefault("code1", False)
ss.setdefault("code2", False)


def script(html):
    """Voert een stukje JavaScript uit. Nieuwe Streamlit: st.iframe. Oude Streamlit: components.html."""
    if hasattr(st, "iframe"):
        st.iframe(html, height=1)
    else:
        components.html(html, height=0)


# ---------- tool en teksten ----------
def is_sf():
    """True als de deelnemer zijn stap in Salesforce (de 2e tool) doet."""
    return bool(TOOLS) and ss.get("tool") == TOOLS["opties"][1]


def tool_naam():
    return ss.get("tool") or "Copilot"


def plak_in():
    """Waar de deelnemer zijn instructie plakt om te testen."""
    return TOOLS["plak"][1] if is_sf() else "Copilot Chat"


def t(s, sleutel):
    """Tekst uit de yaml. Bij Salesforce de _sf-versie als die bestaat."""
    if is_sf() and (sleutel + "_sf") in s:
        return s[sleutel + "_sf"]
    return s.get(sleutel)


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
    waarden.setdefault("functie", ss.get("functie", ""))
    waarden.setdefault("afdeling", ss.get("afdeling", ""))
    for naam, waarde in waarden.items():
        waarde = (waarde or "").strip() or f"[{naam}]"
        # Volgt er in het sjabloon al een punt? Dan geen tweede punt ("workshop..").
        tekst = tekst.replace("{" + naam + "}.", waarde.rstrip(". ") + ".")
        tekst = tekst.replace("{" + naam + "}", waarde)
    return tekst


def is_nummer(tekst):
    """True als de stap alleen een nummer is, zoals '2', 'Stap 2' of 'stap 1, 4 en 7'."""
    return bool(re.fullmatch(r"(stap\s*)?[\d\s,.&+\-]*(en\s*[\d\s,.]*)*", tekst.strip().lower())) and any(c.isdigit() for c in tekst)


def aantal_tests():
    keuze = ss.get("hoe_vaak")
    opties = S["tests"]["hoe_vaak_opties"]
    return min(opties.index(keuze), 3) if keuze in opties else 0


def niet_getest():
    return ss.get("hoe_vaak") == S["tests"]["hoe_vaak_opties"][0]


def basis():
    return dict(
        functie=ss.get("functie", ""),
        stap=ss.get("stap_keuze", ""),
        oplevert=ss.get("oplevert", ""),
        tests=tests_tekst(),
        herstel=herstel_tekst(),
    )


def tests_tekst():
    if niet_getest():
        return "Ik heb nog niet getest. Mijn eerste resultaat in de kickoff: " + (ss.get("kickoff_res", "").strip() or "onbekend")
    delen = []
    for i in range(1, aantal_tests() + 1):
        score = ss.get(f"t{i}_score")
        if not score:
            continue
        deel = f"test {i}: {score.lower()}"
        if ss.get(f"t{i}_opbrengst"):
            deel += f", leverde op: {ss[f't{i}_opbrengst'].lower()}"
        if ss.get(f"t{i}_herstel", "").strip():
            deel += f", zelf nog doen: {ss[f't{i}_herstel'].strip()}"
        delen.append(deel)
    return "; ".join(delen) or "nog niet ingevuld"


def herstel_tekst():
    regels = [ss.get(f"t{i}_herstel", "").strip() for i in range(1, aantal_tests() + 1)]
    regels = [r for r in regels if r]
    return "; ".join(regels) or ss.get("kickoff_res", "").strip()


def instructie(versie=1):
    achter = "" if versie == 1 else "2"
    w = {v: ss.get(v + achter, "").strip() for v in VELDEN}
    return vul_in(t(S["instructie"], "sjabloon"), functie=ss.get("functie", ""), **w)


def tijd(minuten):
    st.caption(f"⏱ {minuten} minuten")


def waarom(s):
    tekst = t(s, "waarom")
    if tekst:
        st.caption(f"💡 **Waarom zo?** {tekst}")


def prompt(tekst, label="Prompt voor Copilot", plak="Copilot Chat"):
    with st.container(border=True):
        st.markdown(f"📋 **{label}**  \n:gray[Ga met je muis over het grijze vak. Klik rechtsboven op het kopieericoon. Plak in {plak}.]")
        st.code(tekst, language=None, wrap_lines=True)


def vet(tekst):
    if tekst:
        st.markdown(f"**{tekst}**")


def navigatie(mag_door=True, reden=""):
    # Terug werkt net als Volgende pas na het tekenen van de velden.
    # Zo blijft invoer bewaard als iemand typt en direct op Terug klikt.
    links, rechts, _ = st.columns([1, 1, 3])
    if ss.stap > 1:
        if links.button("Terug", key=f"terug_{ss.stap}", use_container_width=True):
            ss.stap -= 1
            st.rerun()
    if ss.stap < LAATSTE:
        if rechts.button("Volgende", key=f"volgende_{ss.stap}", type="primary", use_container_width=True):
            if mag_door:
                ss.stap += 1
                st.rerun()
            else:
                st.error(reden or "Je bent nog niet klaar met deze stap.")


def codewoord_ok(invoer, juist):
    return invoer.strip().upper().replace(" ", "") == juist.strip().upper().replace(" ", "")


# ---------- pdf ----------
VERVANG = {
    "’": "'", "‘": "'", "“": '"', "”": '"', "–": "-", "—": "-", "…": "...", "•": "-",
    "→": "->", "≥": ">=", "≤": "<=", "€": "EUR ", "✓": "v", "✔": "v", "✅": "v", "❌": "x",
}


def latin(t):
    for a, b in VERVANG.items():
        t = t.replace(a, b)
    # Wat dan nog niet in latin-1 past (zoals emoji), valt weg in plaats van een '?' te worden.
    return t.encode("latin-1", "ignore").decode("latin-1")


def als_dan():
    """'Als ..., dan ...' zonder dubbel 'als' of 'dan' als de deelnemer die woorden zelf al typte."""
    def zonder(tekst, woord):
        return re.sub(rf"^\s*{woord}\b[\s,]*", "", tekst or "", flags=re.IGNORECASE).strip().rstrip(".")
    return f"Als {zonder(ss.get('als', ''), 'als')}, dan {zonder(ss.get('dan', ''), 'dan')}."


def pdf_naam():
    """Unieke naam, zodat niemand in de Teams-map de pdf van een ander overschrijft."""
    def slug(x):
        return re.sub(r"[^a-z0-9]+", "-", (x or "").lower()).strip("-")
    delen = ["werkwijze", slug(C["pilot"].replace("AI-pilot", "")), slug(ss.get("functie", ""))[:30], f"{datetime.now():%Y%m%d-%H%M%S}"]
    return "-".join(d for d in delen if d) + ".pdf"


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

    def tekst(t, mono=False):
        pdf.set_font("Courier" if mono else "Helvetica", "", 8 if mono else 11)
        pdf.multi_cell(w, 4.5 if mono else 6, latin(t or "-"), align="L", new_x="LMARGIN", new_y="NEXT")

    pdf.set_font("Helvetica", "B", 18)
    pdf.set_text_color(240, 110, 30)
    pdf.cell(w, 10, latin(f"{C['pilot']}: {C['titel']}"), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(90, 90, 90)
    pdf.cell(w, 6, latin(f"{C['sessie']}, {date.today():%d-%m-%Y}"), new_x="LMARGIN", new_y="NEXT")

    kop("1. Mijn stap en mijn tests")
    tekst("Functie: " + ss.get("functie", "") + ", afdeling: " + ss.get("afdeling", ""))
    tekst("Stap: " + ss.get("stap_keuze", ""))
    tekst("Dit moet het opleveren: " + ss.get("oplevert", ""))
    if TOOLS:
        tekst("Tool: " + tool_naam())
    tekst("Op echt werk gedaan: " + (ss.get("hoe_vaak") or "-"))
    tekst("Tests: " + tests_tekst())
    if niet_getest():
        tekst("Waarom niet getest: " + (ss.get("waarom_niet") or "-"))
    tekst("Hoe verder: " + (ss.get("verder") or "-"))
    if ss.get("idee", "").strip():
        tekst("Idee voor het AI CoE: " + ss.get("idee", ""))
    kop("2 en 3. Mijn werkwijze")
    if ss.get("bestaand") == S["ontwerp"]["bestaand_opties"][1]:
        tekst("Ik had al een instructie of agent")
    else:
        tekst("Hulp bij het schrijven: " + (ss.get("hulp2") or "-"))
    tekst("Wat ik overnam van Copilot als coach: " + ss.get("coach_punt", ""))
    kop("Instructie versie 0.1", 11)
    tekst(instructie(1), mono=True)
    tekst("Mijn controle: " + ss.get("controle", ""))
    tekst("Wanneer ik de uitkomst niet gebruik: " + ss.get("wanneer_niet", ""))
    tekst("Dit blijft mensenwerk: " + ss.get("mensenwerk", ""))
    tekst("Mag het: " + (ss.get("kleur") or "-"))
    kop("4. Test met normale input")
    tekst("Dit moest er zeker in staan: " + ss.get("punten", ""))
    tekst("Score: " + (ss.get("score4") or "-"))
    tekst("Wat ik zelf nog moest doen: " + ss.get("herstel4", ""))
    if ss.get("bijsturing", "").strip():
        tekst("Deze bijsturing maakte het verschil: " + ss.get("bijsturing", ""))
    tekst("Hulp: " + (ss.get("hulp4") or "-"))
    kop("5. Lastige input")
    tekst("Lastig geval: " + ss.get("geval", ""))
    tekst("Wat ging er mis: " + ss.get("mis", ""))
    tekst("Score: " + (ss.get("score5") or "-") + ". Gevallen: " + (ss.get("hulp5") or "-"))
    kop("6. Versie 0.2")
    tekst("Wat ik aanpaste en waarom: " + ss.get("aanpas", ""))
    tekst("Versie 0.2 was: " + (ss.get("beter") or "-"))
    tekst(instructie(2), mono=True)
    kop("7. Mijn plan")
    tekst(als_dan())
    tekst("Hier bewaar ik mijn instructie: " + ss.get("bewaarplek", ""))
    for i in (1, 2, 3):
        tekst(f"Test {i}: " + ss.get(f"plan{i}", ""))
    return bytes(pdf.output())


def samenvatting():
    regels = [
        f"Functie: {ss.get('functie', '')}",
        f"Stap: {ss.get('stap_keuze', '')}",
        f"Dit moet het opleveren: {ss.get('oplevert', '')}",
    ]
    if TOOLS:
        regels.append(f"Tool: {tool_naam()}")
    regels += [
        f"Tests: {tests_tekst()}",
        f"Versie 0.2 was: {ss.get('beter') or '-'}",
        f"Dit blijft mensenwerk: {ss.get('mensenwerk', '')}",
        als_dan(),
        f"Testmomenten: {ss.get('plan1', '')}; {ss.get('plan2', '')}; {ss.get('plan3', '')}",
        f"Instructie versie 0.2: {instructie(2)}",
    ]
    return "\n".join(regels)


# ---------- zijbalk ----------
with st.sidebar:
    st.markdown(f"**{C['pilot']}**  \n{C['sessie']}")
    for i, naam in enumerate(STAPPEN):
        if i < ss.stap:
            st.markdown(f":green[✓ {naam}]")
        elif i == ss.stap:
            st.markdown(f":orange[**● {naam}**]")
        elif (i >= 1 and not ss.code1) or (i >= SLOT_VANAF and not ss.code2):
            st.markdown(f":gray[🔒 {naam}]")
        else:
            st.markdown(f"○ {naam}")
    if TOOLS and ss.get("tool"):
        st.caption(f"Tool: {tool_naam()}")
    st.divider()
    for w in C["zijbalk_waarschuwingen"]:
        st.markdown(f":red[{w}]")

# Bij een nieuwe stap naar boven scrollen
if ss.get("_vorige_stap") != ss.stap:
    ss["_vorige_stap"] = ss.stap
    script(
        "<script>/*" + str(ss.stap) + "*/ const d = window.parent.document;"
        " for (const s of ['[data-testid=\"stMain\"]', 'section.main', '[data-testid=\"stAppViewContainer\"]'])"
        " { const e = d.querySelector(s); if (e) e.scrollTo(0, 0); } window.parent.scrollTo(0, 0);</script>"
    )

# Waarschuwing van de browser bij verversen of sluiten, zodra iemand begonnen is.
# De vlag zorgt dat de waarschuwing maar 1 keer wordt toegevoegd.
if ss.stap > 0:
    # Op streamlit.app draait de app in een frame. Daarom koppelen we de waarschuwing
    # aan het frame van de app en aan de bovenste pagina (die ververst bij F5).
    script(
        "<script>for (const w of [window.parent, window.top]) { try { if (!w.__aiPilotWacht) {"
        " w.__aiPilotWacht = true; w.addEventListener('beforeunload', function (e) {"
        " e.preventDefault(); e.returnValue = ''; }); } } catch (err) {} }</script>"
    )

if ss.stap > 0:
    st.progress(ss.stap / LAATSTE)
    st.caption(f"Stap {ss.stap} van {LAATSTE}")

# ---------- stappen ----------
if ss.stap == 0:
    st.title(C["titel"])
    st.write(C["start"]["tekst"])
    st.info(C["start"]["zo_werk_je"])
    if C["start"].get("tijdelijk_titel"):
        st.markdown(f"**🕶 {C['start']['tijdelijk_titel']}**  \n{C['start']['tijdelijk_tekst']}")
    waarom(C["start"])
    functie = bewaar_tekst(C["start"]["functie_label"], "functie")
    afdeling = bewaar_tekst(C["start"]["afdeling_label"], "afdeling", standaard=C["start"].get("afdeling_standaard", ""))
    st.caption(C["start"]["functie_hulp"])
    code = st.text_input(f"Codewoord van {TRAINER}", key="w_code1") if CODES.get("start") else ""
    if st.button("Start", type="primary"):
        if not functie or not afdeling:
            st.error("Vul eerst je functie en je afdeling in.")
        elif not CODES.get("start") or codewoord_ok(code, CODES["start"]):
            ss.code1 = True
            ss.stap = 1
            st.rerun()
        else:
            st.error(f"Dit codewoord klopt niet. Vraag het aan {TRAINER}.")

elif ss.stap == 1:
    s = S["tests"]
    st.title(s["titel"])
    tijd(s["tijd"])
    st.write(s["intro"])
    waarom(s)
    stap = bewaar_tekst(s["stap_label"], "stap_keuze", area=True, height="content")
    st.caption(s["stap_hulp"])
    st.caption(f"🤖 {s['agent_hulp_sf'] if TOOLS else s['agent_hulp']}")
    stap_nummer = bool(stap) and is_nummer(stap)
    if stap_nummer:
        st.warning(s["stap_fout"])
    oplevert = bewaar_tekst(s["oplevert_label"], "oplevert", area=True, height="content")
    st.caption(s["oplevert_hulp"])
    with st.expander("🔎 " + s["check_titel"]):
        for v in s["check_vragen"]:
            st.markdown(f"- {v}")
        st.markdown(f":red[✗] {s['check_te_breed']}  \n:green[✓] {s['check_concreet']}")
        st.write(s["check_prompt_intro"])
        prompt(vul_in(s["check_prompt"], stap=ss.get("stap_keuze", ""), oplevert=ss.get("oplevert", "")))
    tool_ok = True
    if TOOLS:
        tool = bewaar_keuze(TOOLS["vraag"], TOOLS["opties"], "tool", horizontal=True)
        st.caption(TOOLS["hulp"])
        tool_ok = bool(tool)
    hoe_vaak = bewaar_keuze(s["hoe_vaak"], s["hoe_vaak_opties"], "hoe_vaak", horizontal=True)
    for i in range(1, aantal_tests() + 1):
        with st.container(border=True):
            st.markdown(f"**Test {i}**")
            bewaar_keuze("Hoe ging het?", s["scores"], f"t{i}_score", horizontal=True)
            bewaar_keuze("Wat leverde het op?", s["opbrengst"], f"t{i}_opbrengst", horizontal=True)
            bewaar_tekst("Wat moest je zelf nog doen voordat het bruikbaar was?", f"t{i}_herstel", area=True, height="content")
            bewaar_tekst("Wat leerde je van deze test? Wat houd je zo, of wat wil je anders? (optioneel)", f"t{i}_aanpas", area=True, height="content")
    if niet_getest():
        st.info(s["niet_getest"])
        bewaar_keuze("Waarom niet getest?", s["waarom_niet"], "waarom_niet")
        bewaar_tekst(s["kickoff_label"], "kickoff_res", area=True, height="content")
    verder = bewaar_keuze("Hoe ga je verder?", s["verder_opties"], "verder")
    if verder == s["verder_opties"][1]:
        st.write(s["aanpassen_tekst"])
        prompt(vul_in(s["aanpassen_prompt"], **basis()))
    elif verder == s["verder_opties"][2]:
        st.write(s["andere_tekst"])
        prompt(vul_in(s["andere_prompt"], **basis()))
    door_ok = True
    if verder == s["verder_opties"][3]:
        st.info(s["door_tekst"])
        door_ok = bool(bewaar_tekst(s["door_label"], "idee", area=True, height="content"))
        prompt(vul_in(s["andere_prompt"], **basis()))
    vet(s["vinkjes_intro"])
    klaar = bewaar_vinkje(s["vinkje"], "v1")
    navigatie(
        bool(stap) and not stap_nummer and bool(oplevert) and tool_ok and bool(hoe_vaak) and bool(verder) and door_ok and klaar,
        "Beschrijf je stap in woorden, vul in wat hij oplevert, kies je tool, kies hoe vaak je testte en hoe je verdergaat, en zet het vinkje. Bij doorverwijzen: schrijf je idee op.",
    )

elif ss.stap == 2:
    s = S["ontwerp"]
    si = S["instructie"]
    st.title(s["titel"])
    tijd(s["tijd"])
    st.write(s["intro"])
    waarom(s)
    bestaand = bewaar_keuze(s["bestaand_vraag"], s["bestaand_opties"], "bestaand", horizontal=True)
    is_bestaand = bestaand == s["bestaand_opties"][1]
    if is_bestaand:
        st.info(s["bestaand_tekst"])
        prompt(s["bestaand_prompt"], "Laat Copilot je instructie verdelen")
    else:
        with st.expander("🧭 " + s["vast_titel"]):
            st.write(s["vast_tekst"])
            prompt(vul_in(t(s, "prompt"), **basis()))
            st.warning(s["waarschuwing"])
    ingevuld = [bewaar_tekst(label, k, area=True, height="content") for k, label in t(si, "velden").items()]
    hulp = True
    if not is_bestaand:
        hulp = bewaar_keuze(s["hulp_vraag"], s["hulp_opties"], "hulp2", horizontal=True)
    if all(ingevuld):
        prompt(instructie(1), "Jouw instructie tot nu toe", plak_in())
    navigatie(bool(bestaand) and all(ingevuld) and bool(hulp), "Kies of je al een instructie hebt, vul de 4 velden in en kies wat je hebt gebruikt.")

elif ss.stap == 3:
    s = S["instructie"]
    st.title(s["titel"])
    tijd(s["tijd"])
    st.write(s["intro"])
    st.markdown(f"#### {s['coach_titel']}")
    st.write(s["coach_tekst"])
    prompt(vul_in(t(s, "coach_prompt"), stap=ss.get("stap_keuze", ""), instructie=instructie(1)), "Prompt voor Copilot als coach")
    st.markdown(f"#### {s['aanpas_titel']}")
    coach = bewaar_tekst(s["coach_label"], "coach_punt", area=True, height="content")
    st.write(s["aanpas_tekst"])
    ingevuld = [bewaar_tekst(label, k, area=True, height="content") for k, label in t(s, "velden").items()]
    st.markdown(f"#### {s['jij_titel']}")
    st.write(s["jij_tekst"])
    bewaar_tekst(s["controle_label"], "controle", area=True, height="content")
    bewaar_tekst(s["niet_label"], "wanneer_niet", area=True, height="content")
    mensenwerk = bewaar_tekst(s["mensenwerk_label"], "mensenwerk", area=True, height="content")
    kleuren = t(s, "kleuren")
    kleur = bewaar_keuze(s["kleur_vraag"], kleuren, "kleur")
    rood_ok = True
    if kleur == kleuren[0]:
        st.success(s["groen"])
    elif kleur == kleuren[1]:
        st.warning(s["oranje"])
        prompt(s["uitzoeken_prompt"], "Zoek het uit met Copilot")
        st.caption(s["uitzoeken_noot"])
        prompt(vul_in(s["verzonnen_prompt"], functie=ss.get("functie", "")), "Maak een verzonnen voorbeeld")
    elif kleur == kleuren[2]:
        st.error(t(s, "rood"))
        prompt(vul_in(s["verzonnen_prompt"], functie=ss.get("functie", "")), "Maak een verzonnen voorbeeld")
        rood_ok = bewaar_vinkje(s["rood_vinkje"], "rood_ok")
    prompt(instructie(1), "Jouw instructie, versie 0.1", plak_in())
    waarom(s)
    vet(s["vinkje_intro"])
    klaar = bewaar_vinkje(s["vinkje"], "v3")
    navigatie(
        bool(coach) and all(ingevuld) and bool(mensenwerk) and bool(kleur) and rood_ok and klaar,
        "Schrijf welk punt je overneemt, vul de velden en mensenwerk in, kies een kleur en zet het vinkje. Bij rood: kies een verzonnen voorbeeld.",
    )

elif ss.stap == 4 and not ss.code2:
    s = S["wacht"]
    st.markdown("# ⏸")
    st.title(s["titel"])
    st.write(s["tekst"])
    st.info(t(s, "tip"))
    prompt(instructie(1), "Jouw instructie, versie 0.1", plak_in())
    code = st.text_input("Codewoord", key="w_code2") if CODES.get("verder") else ""
    links, rechts, _ = st.columns([1, 1, 3])
    links.button("Terug", key="terug_wacht", on_click=lambda: ss.update(stap=3), use_container_width=True)
    if rechts.button("Verder", type="primary", use_container_width=True):
        if not CODES.get("verder") or codewoord_ok(code, CODES["verder"]):
            ss.code2 = True
            st.rerun()
        else:
            st.error(f"Dit codewoord klopt niet. Wacht op {TRAINER}.")

elif ss.stap == 4:
    s = S["test"]
    st.title(s["titel"])
    tijd(s["tijd"])
    st.write(s["intro"])
    st.markdown(f"#### {s['stap1_titel']}")
    st.write(t(s, "stap1_tekst"))
    st.markdown(f"#### {s['stap2_titel']}")
    punten = bewaar_tekst(s["punten_label"], "punten", area=True, height="content")
    st.caption(s["punten_waarom"])
    st.markdown(f"#### {t(s, 'stap3_titel')}")
    st.write(t(s, "stap3_tekst"))
    prompt(instructie(1), "Jouw instructie, versie 0.1", plak_in())
    st.caption(f"💡 {t(s, 'waarom')}")
    st.markdown(f"#### {s['stap4_titel']}")
    st.warning(t(s, "waarschuwing"))
    if is_sf():
        st.error(s["klantregel"])
    st.write(s["bijsturen_tekst"])
    with st.expander(s["bijsturen_titel"]):
        for h in s["bijsturen"]:
            prompt(h["prompt"], h["label"], plak_in())
    bewaar_tekst(s["bijsturing_label"], "bijsturing", area=True, height="content")
    hulp = bewaar_keuze("Welke hulp heb je gebruikt?", s["hulp_opties"], "hulp4", horizontal=True)
    st.markdown(f"#### {s['stap5_titel']}")
    vet(s["vinkjes_intro"])
    for i, regel in enumerate(s["controle"]):
        bewaar_vinkje(regel, f"c4_{i}")
    score = bewaar_keuze("Mijn score", s["scores"], "score4", horizontal=True)
    herstel = bewaar_tekst(s["herstel_label"], "herstel4", area=True, height="content")
    navigatie(bool(punten) and bool(hulp) and bool(score) and bool(herstel), "Schrijf op wat er zeker in moet staan, kies welke hulp je gebruikte, kies een score en vul in wat je zelf nog moest doen.")

elif ss.stap == 5:
    s = S["breek"]
    st.title(s["titel"])
    tijd(s["tijd"])
    st.write(s["intro"])
    st.markdown(f"#### {t(s, 'stap1_titel')}")
    st.write(t(s, "stap1_tekst"))
    prompt(vul_in(t(s, "prompt"), instructie=instructie(1), functie=ss.get("functie", "")), "Prompt voor Copilot")
    st.markdown(f"#### {s['stap2_titel']}")
    st.write(t(s, "stap2_tekst"))
    bewaar_tekst(s["geval_label"], "geval", area=True, height="content")
    st.markdown(f"#### {t(s, 'stap3_titel')}")
    st.write(t(s, "stap3_tekst"))
    prompt(instructie(1), "Jouw instructie, versie 0.1", plak_in())
    st.markdown(f"#### {s['stap4_titel']}")
    mis = bewaar_tekst(s["mis_label"], "mis", area=True, height="content")
    st.markdown(f"#### {s['stap5_titel']}")
    score = bewaar_keuze("Mijn score", s["scores"], "score5", horizontal=True)
    hulp = bewaar_keuze("Waar kwam je lastige voorbeeld vandaan?", t(s, "hulp_opties"), "hulp5", horizontal=True)
    st.caption(f"💡 {s['waarom']}")
    navigatie(bool(mis) and bool(hulp) and bool(score), "Vul in wat er misging, kies een score en kies waar je voorbeeld vandaan kwam.")

elif ss.stap == 6:
    s = S["verander"]
    st.title(s["titel"])
    tijd(s["tijd"])
    st.write(s["intro"])
    with st.container(border=True):
        st.markdown(f"**{s['terugblik_titel']}**")
        st.markdown(f"{s['terugblik_mis']} {ss.get('mis', '').strip() or s['terugblik_leeg']}")
        st.markdown(f"{s['terugblik_bijsturing']} {ss.get('bijsturing', '').strip() or s['terugblik_leeg']}")
    st.markdown(f"#### {s['stap1_titel']}")
    st.write(s["stap1_tekst"])
    aanpas = bewaar_tekst(s["aanpas_label"], "aanpas", area=True, height="content")
    with st.expander(s["hulp_titel"]):
        prompt(vul_in(s["hulp_prompt"], instructie=instructie(1), mis=ss.get("mis", "").strip()))
    st.markdown(f"#### {s['stap2_titel']}")
    st.caption(s["velden_noot"])
    # Versie 0.2 begint als kopie van versie 0.1. Paste je in stap 3 iets aan en
    # had je dat veld hier nog niet veranderd, dan neemt versie 0.2 de nieuwe tekst over.
    vorige = ss.get("_v1_kopie", {})
    nu = {k: ss.get(k, "") for k in VELDEN}
    for k in VELDEN:
        if k + "2" not in ss or ss[k + "2"] == vorige.get(k):
            ss[k + "2"] = nu[k]
    ss["_v1_kopie"] = nu
    for k, label in t(S["instructie"], "velden").items():
        bewaar_tekst(label, k + "2", area=True, height="content")
    st.markdown(f"#### {s['stap3_titel']}")
    st.write(t(s, "stap3_tekst"))
    prompt(instructie(2), "Jouw instructie, versie 0.2", plak_in())
    st.markdown(f"#### {s['stap4_titel']}")
    klaar = bewaar_vinkje(s["vinkje"], "v6")
    beter = bewaar_keuze("Was versie 0.2 beter?", s["beter_opties"], "beter", horizontal=True)
    if beter and beter != s["beter_opties"][0]:
        st.info(s["beter_slechter"])
    st.caption(f"💡 {s['waarom']}")
    navigatie(bool(aanpas) and klaar and bool(beter), "Schrijf op wat je aanpast, test versie 0.2 en kies of hij beter was.")

elif ss.stap == 7:
    s = S["bewaar"]
    st.title(s["titel"])
    tijd(s["tijd"])
    st.write(s["intro"])
    waarom(s)
    st.subheader("Veiligheidscheck")
    vet(s["veilig_intro"])
    veilig = [bewaar_vinkje(regel, f"veilig{i}") for i, regel in enumerate(t(s, "veilig"))]
    st.caption(s["twijfel"])
    st.subheader("Jouw als-dan-plan")
    st.write(s["plan_intro"])
    als = bewaar_tekst(s["als_label"], "als")
    dan = bewaar_tekst(s["dan_label"], "dan")
    st.caption(s["tests_hulp"])
    for i, regel in enumerate(s["tests"], 1):
        bewaar_tekst(regel, f"plan{i}")
    st.subheader("Bewaar je instructie")
    st.write(s["bewaar_tekst"])
    prompt(instructie(2), "Jouw instructie, versie 0.2", plak_in())
    plek = bewaar_tekst(s["bewaar_label"], "bewaarplek")
    with st.expander(s["agent_titel"]):
        if is_sf():
            st.info(s["agent_sf"])
        st.write(s["agent_intro"])
        for i, regel in enumerate(s["agent_stappen"], 1):
            st.markdown(f"{i}. {regel}")
        st.caption(s["agent_noot"])
    st.info(s["na_tests"])
    if all(veilig) and als and dan and plek:
        st.markdown("**Deel in Teams**")
        st.caption("Plak deze zin in de draad in het Teams-kanaal. Geen klantgegevens.")
        st.code(
            vul_in(s["teams"], doel=ss.get("doel2", ""), tool=tool_naam(), beter=(ss.get("beter") or "").lower(), mensenwerk=ss.get("mensenwerk", "")),
            language=None,
            wrap_lines=True,
        )
        st.download_button(
            "⬇ Download alles als pdf",
            data=maak_pdf(),
            file_name=pdf_naam(),
            mime="application/pdf",
            type="primary",
        )
        st.markdown("**Snel bewaren voor de showcase**")
        st.caption(s["bewaar_snel"])
        st.code(samenvatting(), language=None, wrap_lines=True)
        st.success(s["afsluiting"])
    else:
        st.caption("Zet de 3 vinkjes van de veiligheidscheck en vul je als-dan-plan en je bewaarplek in. Dan verschijnt de pdf.")
    navigatie()
