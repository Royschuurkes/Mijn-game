# wapens.py - Alle wapen en armor definities op één plek
# Pas hier getallen aan om wapens te tweaken
#
# Velden per wapen:
#   naam           Weergavenaam
#   type           "strength" / "dexterity" / "schild"
#   prijs          Gold om te kopen bij de smid
#   schade         Basis schade per normale aanval
#   zwaard_frames  Hoe lang de aanvalsanimatie duurt (lager = sneller)
#   bereik         Hoe ver de aanval reikt in pixels
#   hoek           Hoe breed de zwaai is in graden
#   zwaard_cd      Cooldown tussen aanvallen in frames
#   special        Naam van de special move (None = geen)
#   special_stamina Stamina kosten van de special
#   min_str/dex    Minimale stat vereiste om te dragen
#   omschrijving   Korte tekst in de shop
#   kleur          Kleur van het wapen (R, G, B)

WAPENS = {

    "simpel_zwaard": {
        "naam":            "Simpel Zwaard",
        "type":            "strength",
        "prijs":           0,
        "schade":          25.0,
        "zwaard_frames":   20,
        "bereik":          58,
        "hoek":            100,
        "zwaard_cd":       18,
        "special":         None,
        "special_stamina": 0,
        "min_str": 0, "min_dex": 0, "min_int": 0,
        "omschrijving":    "Een gewoon zwaard. Doet wat het moet doen.",
        "kleur":           (210, 210, 230),
    },

    "schild": {
        "naam":            "Houten Schild",
        "type":            "schild",
        "prijs":           80,
        "schade":          0,
        "zwaard_frames":   0,
        "bereik":          0,
        "hoek":            0,
        "zwaard_cd":       0,
        "special":         "blok",
        "special_stamina": 0,
        "blok_reductie":   0.70,
        "min_str": 0, "min_dex": 0, "min_int": 0,
        "omschrijving":    "Blokkeert 70% schade van voren.\nGeeft geen special attack.",
        "kleur":           (190, 150, 60),
    },

    "grote_bijl": {
        "naam":            "Grote Bijl",
        "type":            "strength",
        "prijs":           150,
        "schade":          40.0,
        "zwaard_frames":   30,
        "bereik":          65,
        "hoek":            110,
        "zwaard_cd":       28,
        "special":         "brede_sweep",
        "special_stamina": 35,
        "sweep_hoek":      200,
        "sweep_schade":    30.0,
        "sweep_frames":    35,
        "sweep_bereik":    72,
        "min_str": 3, "min_dex": 0, "min_int": 0,
        "omschrijving":    "Langzaam maar krachtig.\nSpecial: Brede sweep treft alle vijanden voor je.",
        "kleur":           (200, 120, 60),
    },

    "rapier": {
        "naam":            "Rapier",
        "type":            "dexterity",
        "prijs":           120,
        "schade":          18.0,
        "zwaard_frames":   12,
        "bereik":          70,
        "hoek":            60,
        "zwaard_cd":       12,
        "special":         "stoot",
        "special_stamina": 20,
        "stoot_schade":    35.0,
        "stoot_afstand":   120,
        "stoot_frames":    10,
        "stoot_knockback": 10.0,
        "min_str": 0, "min_dex": 3, "min_int": 0,
        "omschrijving":    "Snel en precies.\nSpecial: Snelle stoot vooruit met knockback.",
        "kleur":           (180, 220, 255),
    },

    "hamer": {
        "naam":            "Oorlogshamer",
        "type":            "strength",
        "prijs":           250,
        "schade":          55.0,
        "zwaard_frames":   38,
        "bereik":          55,
        "hoek":            80,
        "zwaard_cd":       40,
        "special":         "grondstamp",
        "special_stamina": 45,
        "stamp_schade":    45.0,
        "stamp_radius":    110,
        "stamp_frames":    20,
        "stamp_knockback": 14.0,
        "min_str": 5, "min_dex": 0, "min_int": 0,
        "omschrijving":    "Verwoestend maar traag.\nSpecial: Grondstamp raakt ALLE vijanden om je heen.",
        "kleur":           (180, 100, 50),
    },

    "dolk": {
        "naam":            "Scherpe Dolk",
        "type":            "dexterity",
        "prijs":           200,
        "schade":          15.0,
        "zwaard_frames":   10,
        "bereik":          45,
        "hoek":            70,
        "zwaard_cd":       10,
        "special":         "dash_aanval",
        "special_stamina": 30,
        "dash_schade":     50.0,
        "dash_afstand":    160,
        "dash_frames":     8,
        "dash_knockback":  8.0,
        "min_str": 0, "min_dex": 5, "min_int": 0,
        "omschrijving":    "Klein maar dodelijk.\nSpecial: Teleport-dash naar dichtstbijzijnde vijand.",
        "kleur":           (160, 220, 160),
    },
}

SHOP_VOLGORDE = ["schild", "rapier", "grote_bijl", "dolk", "hamer"]


def get_wapen(naam):
    return WAPENS.get(naam, WAPENS["simpel_zwaard"])


def kan_dragen(wapen_data, save_stats):
    return (save_stats.get("strength",     0) >= wapen_data["min_str"] and
            save_stats.get("dexterity",    0) >= wapen_data["min_dex"] and
            save_stats.get("intelligence", 0) >= wapen_data["min_int"])


def vereisten_tekst(wapen_data):
    vereisten = []
    if wapen_data["min_str"] > 0: vereisten.append(f"STR {wapen_data['min_str']}")
    if wapen_data["min_dex"] > 0: vereisten.append(f"DEX {wapen_data['min_dex']}")
    if wapen_data["min_int"] > 0: vereisten.append(f"INT {wapen_data['min_int']}")
    return ", ".join(vereisten) if vereisten else "Geen vereisten"
