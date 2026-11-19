"""Changeling, meccanica condivisa (ECL e FDN aderiscono dai loro posti; nata in Set/ECL il 14 nov 2026, spostata qui il 15 nov
2026 quando e' comparsa anche in FDN: Taurean Mauler, Three Tree Mascot).

702.73a: «Changeling» e' un'abilita' che definisce le caratteristiche: «This object is every creature type.» Funziona ovunque,
anche fuori dalla partita (604.3). Si scrive come `car["tutti_i_tipi_creatura"]`; il nucleo la legge in `effetti.ha_sottotipo`.
"""


def paragrafo(c, low, orig, car, ctx, info):
    if low == "changeling":                                                                    # 702.73a
        car["tutti_i_tipi_creatura"] = True
        return True
    return None
