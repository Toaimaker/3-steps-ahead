"""Le meccaniche condivise da piu' set (14 nov 2026). Una parola chiave che compare in due o piu' set del perimetro vive qui,
in un modulo suo, e ogni set che la usa ci aderisce dal suo posto (Set/<SET>/meccaniche.py: `from meccaniche_comuni import
station`), cosi' nessun set dipende dal posto di un altro. Una modifica qui tocca tutti i set che aderiscono: si chiude con
`carte_set.py --confronta F` (nessuna carta intera toccata in nessun set).
"""
