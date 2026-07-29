"""The final Q2 leaderboard — the 64 qualifiers, in finishing order.

These are the real, public competition handles exactly as they appear in the
official Q2 ranking and in the match logs' bot_name fields (including unicode
styling some entrants used). field_profile.py and my_results.py key opponents
against this list to bucket them into strength tiers.
"""

LEADERBOARD = [
    "jew", "CallMeMaybe", "SevenDeuces", "NecessarySkew", "Looper257",
    "Oxvard", "BussBot-v3", "Taleto13", "winning", "CrimsonBot", "FerdaBot",
    "Khan’t Fold", "make_no_mistakes", "Tumble-Weed-Dutch-v2", "Lekemog",
    "ant-bot", "twader", "Hyperion", "durak", "jotaroZAWARUDO", "TheQuantBot",
    "talan", "Overfitted", "Inefficiency", "+ev", "Pantheon", "sam_bot_lfg_2",
    "50CentRaise", "IveyBot", "𝐛𝐚𝐯", "poker? I barely know her", "pavan kumar",
    "I hate arsenal", "Pascal", "RODBOTv2", "BATNEEC", "GrandSlam", "Javis",
    "Freelo", "Super2Trooper", "goku", "72o", "alan", "elprofesoriqo",
    "not_so_simple_bot", "Lyra", "SaviourBot", "TheHouse", "I'mDeffoCappin",
    "VolatileNeuron", "never played poker", "gems_VC2", "PhoonTooMuchForPoker",
    "Thorp", "SummerSun", "SuperExtraDeluxeMegaBot", "NEMESIS", "G-Forge",
    "TheCrystalline", "Bot2", "BeginnersLuck V3", "Foldilocks", "BOTv2",
    "Worm",
]

RANK = {n: i + 1 for i, n in enumerate(LEADERBOARD)}


def rank_of(name, default=999):
    """1-based final rank, or `default` for anyone outside the top 64."""
    return RANK.get(name, default)
