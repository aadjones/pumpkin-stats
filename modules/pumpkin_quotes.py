"""
Pumpkin's financial wisdom and grouchy commentary.

A collection of rotating taglines from the perspective of Pumpkin,
the grouchy old dog who inspired this dashboard.

Pumpkin haunts this app with her presence.
"""

import random

PUMPKIN_QUOTES = [
    "Keeping Pumpkin fed since 2025",
    "Where did all my treat money go?",
    "Tracking kibble budgets and belly rubs",
    "I'm too old for financial surprises",
    "Someone's gotta pay for my vet bills",
    "These walks don't fund themselves",
    "Retirement planning for a senior pup",
    "Accounting for squeaky toys and dental chews",
    "Pumpkin's portfolio: mostly naps",
    "Grumpy dog, organized finances",
    "My humans spend HOW MUCH at Petco?",
    "Still cheaper than a boat",
    "Funded by guilt and love",
    "Because someone adopted a senior dog",
    "Fancy feast or financial stability? Both.",
    "I'm not cheap, I'm worth it",
    "Powered by pets and poor decisions",
    "Making sure the kibble fund is healthy",
    "Old dog, new spreadsheet tricks",
    "Fiscally responsible since... never",
    "The only subscription worth keeping",
    "Bark twice for balanced budgets",
    "Woof. That's expensive.",
    "My hip replacements cost WHAT?!",
    "Retirement age: 7 dog years ago",
    "Judging your Amazon purchases since 2025",
    "Investment strategy: Cuddles and chaos",
]


def get_random_quote() -> str:
    """Get a random Pumpkin quote for the dashboard tagline."""
    return random.choice(PUMPKIN_QUOTES)


def get_quote_by_net(net_amount: float) -> str:
    """Get a context-aware quote based on monthly net."""
    if net_amount > 1000:
        positive_quotes = [
            "Look at you, being responsible!",
            "Extra treat money this month?",
            "Pumpkin approves of this budget",
            "My humans are doing great!",
            "Someone's getting extra walks",
        ]
        return random.choice(positive_quotes)
    elif net_amount < -500:
        negative_quotes = [
            "Uh oh. Someone went to Target.",
            "Pumpkin is concerned about your choices",
            "Maybe skip the fancy kibble this month?",
            "I've seen better months...",
            "Time to cut back on my spa days",
        ]
        return random.choice(negative_quotes)
    else:
        return get_random_quote()


# Pumpkin's commentary for various app states
LOADING_MESSAGES = {
    "processing_files": "🐕 Pumpkin is sniffing through your receipts...",
    "creating_backup": "🦴 Burying your data for safekeeping...",
    "restoring": "🐕 Digging up old bones...",
    "exporting": "📦 Pumpkin is packing up your shame...",
}

SUCCESS_MESSAGES = {
    "upload": "✅ Pumpkin has reviewed your spending",
    "backup": "🦴 Data buried. Pumpkin approved.",
    "restore": "🐕 Successfully dug up the past",
    "export": "📦 Pumpkin released the evidence",
    "save": "✓ Changes locked in (Pumpkin witnessed it)",
}

ERROR_MESSAGES = {
    "upload": "❌ Pumpkin rejected this file",
    "backup": "❌ Burial failed. Pumpkin is disappointed.",
    "restore": "❌ Couldn't dig that up. Pumpkin sighs.",
    "export": "❌ Export failed. Pumpkin judges you.",
}

EMPTY_STATES = {
    "no_transactions": "💤 No spending? Pumpkin is suspicious...",
    "no_backups": "🦴 No buried data yet. Pumpkin waits.",
    "no_data": "📁 Upload something. Pumpkin is impatient.",
    "no_trends": "📊 Pumpkin needs more data to judge your patterns. Upload at least 2 months of transactions.",
}
