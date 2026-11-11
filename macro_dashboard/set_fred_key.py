# ============================================================================
# File: macro_dashboard/set_fred_key.py
# ============================================================================

# Tallennuspaikka: C:\Users\markk\Talous\macro_dashboard\set_fred_key.py
"""Tallenna FRED API -avain pysyvästi käyttäjän ympäristömuuttujaksi FRED_API_KEY.

Aja kansiosta macro_dashboard:  python set_fred_key.py

* Avain kysytään piilotettuna (getpass), joten se ei jää komentohistoriaan
  eikä tähän tiedostoon.
* Windowsissa tallennus tehdään komennolla ``setx`` (käyttäjän ympäristömuuttujat).
  Muuttuja näkyy vasta UUSISSA terminaali-ikkunoissa.
* Lopuksi avain voidaan testata hakemalla USA:n työttömyysaste FRED:stä.
"""

from __future__ import annotations

import getpass
import os
import re
import subprocess
import sys

VAR = "FRED_API_KEY"
KEY_PATTERN = re.compile(r"[0-9a-f]{32}")  # FRED-avain: 32 pientä heksamerkkiä


def persist(key: str, *, runner=subprocess.run, is_windows: bool | None = None) -> bool:
    """Tallenna avain pysyvästi. Palauttaa True, jos tallennus tehtiin."""
    if is_windows is None:
        is_windows = os.name == "nt"
    if not is_windows:
        print("Tämä ei ole Windows. Lisää tiedostoon ~/.bashrc (tai ~/.zshrc) rivi:")
        print(f'  export {VAR}="<avain>"')
        return False
    result = runner(["setx", VAR, key], capture_output=True, text=True)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip().replace(key, "***")
        raise SystemExit(f"setx epäonnistui: {detail}")
    return True


def test_key(key: str) -> bool:
    """Hae USA:n työttömyysaste FRED:stä annetulla avaimella."""
    from data_fetchers import FetcherError, Frequency, SeriesSpec, fetch_series

    spec = SeriesSpec("US.unrate.m", "UNRATE", Frequency.MONTHLY)
    try:
        df = fetch_series("fred", [spec], start="2025-01-01", api_key=key)
    except FetcherError as exc:
        print(f"Testi epäonnistui: {exc}")
        return False
    print(df.tail(3))
    return True


def main(*, getpass_fn=getpass.getpass, input_fn=input, runner=subprocess.run,
         is_windows: bool | None = None) -> int:
    key = getpass_fn("Liitä FRED API -avain (ei näy ruudulla): ").strip()
    if not key:
        print("Avainta ei annettu.")
        return 1
    if not KEY_PATTERN.fullmatch(key):
        print("Varoitus: avain ei ole 32 merkin heksajono, tarkista että kopioit sen kokonaan.")
        if input_fn("Jatketaanko silti? [k/E] ").strip().lower() != "k":
            return 1

    if persist(key, runner=runner, is_windows=is_windows):
        print(f"{VAR} tallennettu pysyvästi. Avaa uusi terminaali, niin se on käytössä.")

    if input_fn("Testataanko avain nyt? [K/e] ").strip().lower() != "e":
        return 0 if test_key(key) else 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
