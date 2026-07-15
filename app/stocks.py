"""Nasdaq-100 company data used to build the game tiles.

Each tile is a company. The tile's *letter* is the FIRST LETTER OF THE COMPANY
NAME (e.g. Alphabet -> A, Microsoft -> M, Nvidia -> N). The bag is exactly one
tile per company -- no filler tiles. Logos come from each company's domain
(see fetch_logos.py).

Scoring (rule #2): a tile's points = roundup(cap_weight_% x 10), floored at 1.
  - Nvidia ~7.47% -> ceil(74.7) = 75
  - a 0.05% name -> ceil(0.5)  = 1
So megacaps are worth a lot and the long tail is worth ~1, just as intended.

DATA NOTE
---------
The constituent list is the Nasdaq-100 as of mid-2026 (Alphabet appears twice,
Class A/C, like the real index). The `weight` column is the approximate index
cap weight in PERCENT. Top holdings use recent real values; the long tail uses
reasonable estimates. Weights are baked in so the game is self-contained and
deterministic -- edit them here (or wire in a live feed later) and the points
recompute automatically. Domains are best-effort for logo fetching.
"""

import math

# (ticker, company name, logo domain, cap_weight_percent)
COMPANIES = [
    ("ADBE",  "Adobe",                          "adobe.com",                   0.70),
    ("AMD",   "Advanced Micro Devices",         "amd.com",                     3.83),
    ("ABNB",  "Airbnb",                          "airbnb.com",                  0.35),
    ("ALNY",  "Alnylam Pharmaceuticals",         "alnylam.com",                 0.25),
    ("GOOGL", "Alphabet",                        "abc.xyz",                     3.20),
    ("GOOG",  "Alphabet",                        "abc.xyz",                     2.98),
    ("AMZN",  "Amazon",                          "amazon.com",                  4.08),
    ("AEP",   "American Electric Power",         "aep.com",                     0.40),
    ("AMGN",  "Amgen",                           "amgen.com",                   0.75),
    ("ADI",   "Analog Devices",                  "analog.com",                  0.55),
    ("AAPL",  "Apple",                           "apple.com",                   6.80),
    ("AMAT",  "Applied Materials",               "appliedmaterials.com",        2.24),
    ("APP",   "AppLovin",                        "applovin.com",                0.60),
    ("ARM",   "Arm Holdings",                    "arm.com",                     0.45),
    ("ASML",  "ASML Holding",                    "asml.com",                    0.85),
    ("ALAB",  "Astera Labs",                     "asteralabs.com",              0.20),
    ("ADSK",  "Autodesk",                        "autodesk.com",                0.45),
    ("ADP",   "Automatic Data Processing",       "adp.com",                     0.70),
    ("AXON",  "Axon Enterprise",                 "axon.com",                    0.35),
    ("BKR",   "Baker Hughes",                    "bakerhughes.com",             0.40),
    ("BKNG",  "Booking Holdings",                "booking.com",                 1.00),
    ("AVGO",  "Broadcom",                        "broadcom.com",                2.82),
    ("CDNS",  "Cadence Design Systems",          "cadence.com",                 0.65),
    ("CTAS",  "Cintas",                          "cintas.com",                  0.50),
    ("CSCO",  "Cisco",                           "cisco.com",                   2.02),
    ("CCEP",  "Coca-Cola Europacific Partners",  "cocacolaep.com",              0.25),
    ("CMCSA", "Comcast",                         "comcast.com",                 0.90),
    ("CEG",   "Constellation Energy",            "constellationenergy.com",     0.65),
    ("CPRT",  "Copart",                          "copart.com",                  0.45),
    ("CRWV",  "CoreWeave",                       "coreweave.com",               0.30),
    ("COST",  "Costco",                          "costco.com",                  1.90),
    ("CRWD",  "CrowdStrike",                     "crowdstrike.com",             0.70),
    ("CSX",   "CSX",                             "csx.com",                     0.45),
    ("DDOG",  "Datadog",                         "datadoghq.com",               0.35),
    ("DXCM",  "DexCom",                          "dexcom.com",                  0.30),
    ("FANG",  "Diamondback Energy",              "diamondbackenergy.com",       0.35),
    ("DASH",  "DoorDash",                        "doordash.com",                0.55),
    ("EA",    "Electronic Arts",                 "ea.com",                      0.35),
    ("EXC",   "Exelon",                          "exeloncorp.com",              0.35),
    ("FAST",  "Fastenal",                        "fastenal.com",                0.45),
    ("FER",   "Ferrovial",                       "ferrovial.com",               0.25),
    ("FTNT",  "Fortinet",                        "fortinet.com",                0.55),
    ("GEHC",  "GE HealthCare",                   "gehealthcare.com",            0.40),
    ("GILD",  "Gilead Sciences",                 "gilead.com",                  0.65),
    ("HON",   "Honeywell",                       "honeywell.com",               0.85),
    ("IDXX",  "Idexx Laboratories",              "idexx.com",                   0.30),
    ("INTC",  "Intel",                           "intel.com",                   2.90),
    ("INTU",  "Intuit",                          "intuit.com",                  0.90),
    ("ISRG",  "Intuitive Surgical",              "intuitivesurgical.com",       0.85),
    ("KDP",   "Keurig Dr Pepper",                "keurigdrpepper.com",          0.35),
    ("KLAC",  "KLA",                             "kla.com",                     1.46),
    ("KHC",   "Kraft Heinz",                     "kraftheinzcompany.com",       0.25),
    ("LRCX",  "Lam Research",                    "lamresearch.com",             2.13),
    ("LIN",   "Linde",                           "linde.com",                   1.08),
    ("LITE",  "Lumentum",                        "lumentum.com",                0.20),
    ("MAR",   "Marriott International",          "marriott.com",                0.55),
    ("MRVL",  "Marvell Technology",              "marvell.com",                 1.05),
    ("MELI",  "Mercado Libre",                   "mercadolibre.com",            0.55),
    ("META",  "Meta Platforms",                  "meta.com",                    2.66),
    ("MCHP",  "Microchip Technology",            "microchip.com",               0.40),
    ("MU",    "Micron Technology",               "micron.com",                  5.75),
    ("MSFT",  "Microsoft",                       "microsoft.com",               4.52),
    ("MSTR",  "MicroStrategy",                   "microstrategy.com",           0.40),
    ("MDLZ",  "Mondelez International",          "mondelezinternational.com",   0.55),
    ("MPWR",  "Monolithic Power Systems",        "monolithicpower.com",         0.30),
    ("MNST",  "Monster Beverage",                "monsterbevcorp.com",          0.40),
    ("NBIS",  "Nebius Group",                    "nebius.com",                  0.20),
    ("NFLX",  "Netflix",                         "netflix.com",                 1.40),
    ("NVDA",  "Nvidia",                          "nvidia.com",                  7.60),
    ("NXPI",  "NXP Semiconductors",              "nxp.com",                     0.40),
    ("ORLY",  "O'Reilly Automotive",             "oreillyauto.com",             0.55),
    ("ODFL",  "Old Dominion Freight Line",       "odfl.com",                    0.35),
    ("PCAR",  "Paccar",                          "paccar.com",                  0.40),
    ("PLTR",  "Palantir Technologies",           "palantir.com",                1.17),
    ("PANW",  "Palo Alto Networks",              "paloaltonetworks.com",        1.12),
    ("PAYX",  "Paychex",                         "paychex.com",                 0.45),
    ("PYPL",  "PayPal",                          "paypal.com",                  0.50),
    ("PDD",   "PDD Holdings",                    "pddholdings.com",             0.55),
    ("PEP",   "PepsiCo",                         "pepsico.com",                 1.00),
    ("QCOM",  "Qualcomm",                        "qualcomm.com",                0.95),
    ("REGN",  "Regeneron Pharmaceuticals",       "regeneron.com",               0.45),
    ("RKLB",  "Rocket Lab",                      "rocketlabusa.com",            0.25),
    ("ROP",   "Roper Technologies",              "ropertech.com",               0.50),
    ("ROST",  "Ross Stores",                     "rossstores.com",              0.45),
    ("SNDK",  "Sandisk",                         "sandisk.com",                 1.39),
    ("STX",   "Seagate Technology",              "seagate.com",                 0.40),
    ("SHOP",  "Shopify",                         "shopify.com",                 0.85),
    ("SBUX",  "Starbucks",                       "starbucks.com",               0.70),
    ("SNPS",  "Synopsys",                        "synopsys.com",                0.60),
    ("TMUS",  "T-Mobile US",                     "t-mobile.com",                1.10),
    ("TTWO",  "Take-Two Interactive",            "take2games.com",              0.40),
    ("TER",   "Teradyne",                        "teradyne.com",                0.30),
    ("TSLA",  "Tesla",                           "tesla.com",                   3.09),
    ("TXN",   "Texas Instruments",               "ti.com",                      1.17),
    ("TRI",   "Thomson Reuters",                 "thomsonreuters.com",          0.55),
    ("VRTX",  "Vertex Pharmaceuticals",          "vrtx.com",                    0.55),
    ("WMT",   "Walmart",                         "walmart.com",                 2.54),
    ("WBD",   "Warner Bros. Discovery",          "wbd.com",                     0.30),
    ("WDC",   "Western Digital",                 "westerndigital.com",          0.40),
    ("WDAY",  "Workday",                         "workday.com",                 0.45),
    ("XEL",   "Xcel Energy",                     "xcelenergy.com",              0.40),
]


def weight_to_points(weight_pct):
    """Rule #2: points = roundup(cap weight % x 10), with a floor of 1.

        Nvidia 7.60% -> ceil(76.0) = 76
        a 0.05% name -> ceil(0.5)  = 1
    """
    return max(1, math.ceil(weight_pct * 10))


def name_letter(name):
    """The tile letter = first ALPHABETIC character of the company name."""
    for ch in name:
        if ch.isalpha():
            return ch.upper()
    return "?"


# Short, tile-friendly display names for companies whose full name is too long
# to read on a small tile. Keyed by ticker; anything not listed uses its full
# name as-is. The FIRST letter of the display name is still the tile's letter,
# so overrides must start with the same letter as the full name.
SHORT_NAME = {
    "AMD":   "AMD",        # Advanced Micro Devices
    "AEP":   "American EP",
    "AMAT":  "Applied Mat",
    "ADP":   "Auto Data",
    "CDNS":  "Cadence",
    "CCEP":  "Coca-Cola EP",
    "IDXX":  "Idexx",
    "MAR":   "Marriott",
    "MRVL":  "Marvell",
    "MCHP":  "Microchip",
    "MDLZ":  "Mondelez",
    "MPWR":  "Monolithic",
    "MNST":  "Monster",
    "NXPI":  "NXP",
    "ORLY":  "O'Reilly",
    "ODFL":  "Old Dominion",
    "PLTR":  "Palantir",
    "PANW":  "Palo Alto",
    "REGN":  "Regeneron",
    "VRTX":  "Vertex",
    "WBD":   "Warner Bros",
    "WDC":   "Western Dig",
}


def display_name(ticker, name):
    """A short, tile-friendly company name (falls back to the full name)."""
    return SHORT_NAME.get(ticker, name)


class Stock:
    """A Nasdaq-100 company and its single game tile.

    `points` are derived from the cap `weight` via rule #2, unless an explicit
    points value is passed (used for neutral/blank tiles).
    """

    __slots__ = ("ticker", "name", "domain", "weight", "letter", "points",
                 "display")

    def __init__(self, ticker, name, domain, weight=0.0, points=None):
        self.ticker = ticker
        self.name = name
        self.domain = domain
        self.weight = weight
        self.letter = name_letter(name)
        self.points = points if points is not None else weight_to_points(weight)
        self.display = display_name(ticker, name)

    def __repr__(self):
        return (f"<Stock {self.ticker} '{self.letter}' "
                f"{self.weight:.2f}% -> {self.points}pt ({self.name})>")


class LetterTile:
    """One playable tile: a company, contributing its name's first letter.

    Kept as a distinct class (rather than reusing Stock) because the rest of
    the game treats a "tile" as the placeable unit. One tile == one company.
    """

    __slots__ = ("letter", "ticker", "name", "domain", "points", "neutral",
                 "display")

    def __init__(self, stock):
        self.letter = stock.letter
        self.ticker = stock.ticker
        self.name = stock.name
        self.domain = stock.domain
        self.points = stock.points
        self.neutral = False
        self.display = getattr(stock, "display", stock.name)

    def __repr__(self):
        return f"<LetterTile '{self.letter}' {self.points}pt {self.ticker}>"


# --- Blank (wildcard) tiles --------------------------------------------------
# Rule #6: 2 blank tiles in the NDX bag. A blank scores 0 points and can stand
# in for any letter; the player picks the letter when placing it. Its `letter`
# is "" until assigned.
NEUTRAL_TICKER = "--"      # sentinel ticker for non-company (blank) tiles
BLANK_COUNT = 2            # number of blanks in the bag (NDX)


def neutral_tile(letter):
    """Build a neutral (non-company) tile carrying a fixed letter, 0 points."""
    s = Stock(NEUTRAL_TICKER, letter or "?", "", weight=0.0, points=0)
    s.letter = (letter or "").upper()
    t = LetterTile(s)
    t.name = "Neutral"
    t.neutral = True
    return t


def blank_tile():
    """Build an unassigned blank wildcard tile (letter chosen at placement)."""
    t = neutral_tile("")
    t.name = "Blank"
    return t


def all_stocks():
    """Return one Stock per Nasdaq-100 company."""
    return [Stock(t, n, d, w) for (t, n, d, w) in COMPANIES]


def all_letter_tiles():
    """Return the full bag: one tile per company plus BLANK_COUNT blanks."""
    bag = [LetterTile(s) for s in all_stocks()]
    bag.extend(blank_tile() for _ in range(BLANK_COUNT))
    return bag


_BY_TICKER = {t: (t, n, d, w) for (t, n, d, w) in COMPANIES}


def stock_for_ticker(ticker):
    """Return the Stock for a ticker, or None if unknown."""
    row = _BY_TICKER.get(ticker)
    return Stock(*row) if row else None


if __name__ == "__main__":
    from collections import Counter
    stocks = all_stocks()
    print(f"{len(stocks)} tiles (one per Nasdaq-100 company)\n")

    print("Top 10 by points (market-cap weighted):")
    for s in sorted(stocks, key=lambda x: -x.points)[:10]:
        print(f"  {s.ticker:6} '{s.letter}'  {s.weight:5.2f}%  -> {s.points:3d} pts  {s.name}")

    print("\nPoint-value distribution:")
    vals = Counter(s.points for s in stocks)
    for v in sorted(vals):
        print(f"  {v:3d} pt : {vals[v]:2d} tiles")
    print(f"  range {min(vals)}..{max(vals)}, "
          f"avg {sum(s.points for s in stocks)/len(stocks):.1f}")

    # Verify the rule against the user's example.
    print(f"\nRule check: NVDA 7.60% -> {weight_to_points(7.60)} (example said ~75)")
    print(f"            0.05%     -> {weight_to_points(0.05)} (should be 1)")
